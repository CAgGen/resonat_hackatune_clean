"""HTTP layer · frozen data contracts + routes.

Only does two things: define request/response schemas (the frontend/backend seam)
and pass requests to orchestrator. Business orchestration stays in orchestrator.py;
keep this layer thin.

run: uv run uvicorn app:app --reload
"""
from __future__ import annotations

from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

import config
import cyanite
import orchestrator

app = FastAPI(title="Sounds Like You")

# ponytail: allow all origins in dev; tighten to specific origins for production.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ─────────── Request contracts ───────────
class IntentIn(BaseModel):
    text: str
    user_id: str = "demo"


class FollowUpIn(BaseModel):
    session_id: str
    text: str


class ConfirmIn(BaseModel):
    session_id: str


class FeedbackIn(BaseModel):
    session_id: str
    track_id: str
    verdict: str  # "like" | "dislike"
    mode: str = "normal"  # "normal" | "anti_addiction"


class ExplainIn(BaseModel):
    session_id: str
    track_id: str


class ExplainSoundsLikeYouIn(BaseModel):
    user_id: str = "demo"
    cyanite_id: str


# ─────────── Response trimming (only return fields the frontend needs) ───────────
def _intent_view(s: dict) -> dict:
    return {"session_id": s["id"], "whiteboard_posts": s["whiteboard_posts"],
            "query_card": s["query_card"]}


def _board_view(s: dict) -> dict:
    return {"whiteboard_posts": s["whiteboard_posts"], "query_card": s["query_card"]}


def _cards_view(s: dict) -> dict:
    fields = ("track_id", "cyanite_id", "title", "artist", "source", "score", "why")
    cards = [{k: c[k] for k in fields if k in c} for c in s["visible_cards"]]
    return {"cards": cards, "candidate_pool_size": len(s["candidate_pool"])}


def _guard(fn, *args):
    try:
        return fn(*args)
    except orchestrator.SessionNotFound:
        raise HTTPException(404, "unknown session_id")
    except requests.HTTPError as e:
        resp = e.response
        code = resp.status_code if resp is not None else 502
        hint = " (check that CYANITE_API_KEY is set and valid)" if code == 401 else ""
        raise HTTPException(code, f"Cyanite {code}{hint}")


def _require_cyanite_key() -> None:
    if not config.CYANITE_API_KEY:
        raise HTTPException(
            503,
            "CYANITE_API_KEY is missing. Create repo-root .env and set CYANITE_API_KEY.",
        )


# ─────────── Routes ───────────
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intent")
def intent(body: IntentIn):
    return _intent_view(orchestrator.start_session(body.user_id, body.text))


@app.post("/intent/follow-up")
def follow_up(body: FollowUpIn):
    return _board_view(_guard(orchestrator.add_follow_up, body.session_id, body.text))


@app.post("/intent/confirm")
def confirm(body: ConfirmIn):
    _require_cyanite_key()
    return _cards_view(_guard(orchestrator.confirm, body.session_id))


@app.post("/feedback")
def feedback(body: FeedbackIn):
    _require_cyanite_key()
    return _cards_view(_guard(orchestrator.feedback, body.session_id, body.track_id, body.verdict, body.mode))


@app.post("/round/finish")
def round_finish(body: ConfirmIn):
    """User clicked "finish this round": persist selected songs as feeling memory and return the updated profile."""
    return _guard(orchestrator.finish_round, body.session_id)


@app.post("/explain")
def explain(body: ExplainIn):
    _require_cyanite_key()
    return _guard(orchestrator.explain, body.session_id, body.track_id)


@app.get("/your-sound")
def your_sound(user_id: str = "demo"):
    return {"memory_md": orchestrator.your_sound(user_id)}


@app.post("/explain-sounds-like-you")
def explain_sounds_like_you(body: ExplainSoundsLikeYouIn):
    """Why the sounds-like-you track IS this user — based on their taste profile."""
    _require_cyanite_key()
    return _guard(orchestrator.explain_sounds_like_you, body.user_id, body.cyanite_id)


@app.get("/sounds-like-you")
def sounds_like_you(user_id: str = "demo"):
    """Find tracks that represent this user through the AI's view of their long-term profile."""
    _require_cyanite_key()
    return _guard(orchestrator.sounds_like_you, user_id)


# ─────────── High-quality download proxy ───────────
# Use the official /tracks API to get audiodownload + audiodownload_allowed
# (artists can disable downloads), then fetch the file server-side with Referer.
# Browsers cannot download directly: Jamendo hotlink protection returns 403 and no CORS headers.
# Retry all the way through: Jamendo sometimes resets connections, and one failure should not give users a 500.
_DL_HEADERS = {"Referer": "https://www.jamendo.com/", "User-Agent": "Mozilla/5.0"}


def _get_with_retry(url: str, *, params=None, tries: int = 3, **kw) -> requests.Response:
    last = None
    for _ in range(tries):
        try:
            r = requests.get(url, params=params, headers=_DL_HEADERS, timeout=30, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
    raise HTTPException(502, f"Jamendo unreachable: {last}")


@app.get("/download/{track_id}")
def download(track_id: str):
    if not track_id.isdigit():  # Only allow numeric Jamendo ids to block SSRF.
        raise HTTPException(400, "track_id must be numeric")
    if not config.JAMENDO_CLIENT_ID:
        raise HTTPException(503, "download disabled: JAMENDO_CLIENT_ID not set")

    meta = _get_with_retry(f"{config.JAMENDO_BASE_URL}/tracks",
                           params={"client_id": config.JAMENDO_CLIENT_ID, "id": track_id,
                                   "format": "json", "audioformat": "mp32"}).json()
    results = meta.get("results") or []
    if not results:
        raise HTTPException(404, "track not found on Jamendo")
    t = results[0]
    if not t.get("audiodownload_allowed") or not t.get("audiodownload"):
        raise HTTPException(403, "The artist has disabled download for this track.")

    # Stream through: the browser starts downloading immediately and can show progress
    # instead of waiting for the server to buffer the whole file.
    # Error status codes are covered by the /tracks metadata precheck above; only
    # midstream upstream disconnects can fail halfway here (rare, acceptable).
    r = _get_with_retry(t["audiodownload"], stream=True)
    name = quote(f'{t.get("name", "track")} - {t.get("artist_name", "Jamendo")}.mp3')
    headers = {"content-disposition": f"attachment; filename*=UTF-8''{name}"}
    if cl := r.headers.get("content-length"):  # Pass length through so the browser shows progress.
        headers["content-length"] = cl
    return StreamingResponse(r.iter_content(64 * 1024), media_type="audio/mpeg", headers=headers)


# ─────────── Cyanite passthrough (debug; try directly in /docs) ───────────
# ponytail: attach title/artist to each result for readable Swagger output; the underlying layer is cyanite.py.
def _enrich(rows: list[dict]) -> list[dict]:
    return [{**r, **{k: cyanite.display(r["cyanite_id"], r.get("track_id", "")).get(k)
                     for k in ("track_id", "title", "artist")}}
            for r in rows]


def _cy(fn, *args):
    """Translate upstream Cyanite HTTP errors into clean status codes instead of 500 + stack trace."""
    try:
        return fn(*args)
    except requests.HTTPError as e:
        resp = e.response
        code = resp.status_code if resp is not None else 502
        raise HTTPException(code, f"Cyanite {code} (check id/params; do not include quotes or spaces)")


@app.get("/cyanite/search", tags=["cyanite-debug"],
         summary="#2 Text search · natural language -> candidate tracks (raw response)")
def cyanite_search(query: str, limit: int = 10):
    """Official endpoint #2, "Find Library Tracks based on a text prompt".

    Passes Cyanite raw JSON through directly, without CSV / normalize. Data comes from the real database.

    - **query**: natural-language description, e.g. `lonely midnight train ride, restrained`
    - **limit**: number of results
    """
    return _cy(cyanite.search_raw, query, limit)


@app.get("/cyanite/similar-single/{cyanite_id}", tags=["cyanite-debug"],
         summary="#3 Single-seed similarity · one track -> acoustically similar tracks")
def cyanite_similar_single(cyanite_id: str, limit: int = 10):
    """Official endpoint #3, "Find Similar Library Tracks" (single seed).

    Given one track (`cyanite_id`, shaped like `libtr_xxx`), return the most acoustically similar tracks,
    sorted by similarity descending. Used to expand candidates after a like.

    - **cyanite_id**: seed track Cyanite id (quotes/spaces are stripped automatically)
    - **limit**: number of results

    Returns each row with `cyanite_id` / `score` (similarity) / `title` / `artist`.
    """
    return _enrich(_cy(cyanite.find_similar, cyanite_id.strip().strip('"'), limit))


@app.get("/cyanite/tags/{cyanite_id}", tags=["cyanite-debug"],
         summary="#1 Get tags · one track -> AI model tags")
def cyanite_tags(cyanite_id: str, models: str = "MainGenreV2,MoodSimpleV2,InstrumentsV2,BpmV2"):
    """Official endpoint #1, "Get inferred AI Models for a Library Track" (tagging).

    Returns Cyanite model inference for a track (genre / mood / instruments / BPM, etc.),
    used to support the frontend "Why this track?" explanation.

    - **cyanite_id**: track Cyanite id (quotes/spaces are stripped automatically)
    - **models**: comma-separated model list. Default `MainGenreV2,MoodSimpleV2,InstrumentsV2,BpmV2`

    Returns Cyanite raw `{items:[...]}`; each item contains that model's tags / scores.
    """
    ms = [m.strip() for m in models.split(",") if m.strip()]
    return _cy(cyanite.model_tags, cyanite_id.strip().strip('"'), ms)


@app.get("/cyanite/resolve-id/{track_id}", tags=["cyanite-debug"],
         summary="Tool · data-pack track_id -> cyanite_id + display info")
def cyanite_resolve_id(track_id: str):
    """Convert a Jamendo `track_id` from the data pack (`data/tracks.csv`) to a Cyanite id,
    and return `title` / `artist` alongside it. No network; pure local mapping.

    - **track_id**: Jamendo track id from the data pack

    Ids outside the data pack return 404.
    """
    try:
        return cyanite.display(cyanite.to_cyanite(track_id.strip()))
    except KeyError:
        raise HTTPException(404, f"track_id {track_id!r} is not in the data pack")
