# Cochlea Backend Core Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend state machine for Cochlea's confirm-gated, like-expands / dislike-backfills music discovery loop on top of the Cyanite API, with two-file markdown memory.

**Architecture:** A FastAPI app holds per-session state in an in-memory dict (whiteboard posts, query card, visible cards, freeText backlog, like-seeded candidate pool, dislikes). Cyanite REST calls are isolated behind a thin `cyanite.py` client so the session logic is testable by monkeypatching that module. Cross-session memory is two markdown files per user (`evidence` append-only, `memory` LLM-rewritten), no database.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, `requests` (already the notebook's client) or `httpx`, pytest. Managed by `uv`.

**Scope note:** This plan covers the backend only — the PRD's "永不砍" core (PRD §1 ④⑤, §3). The frontend whiteboard UI (left whiteboard + right Query Card + recommendation list + "Why this") is a **separate plan** to be written after this one lands. The LLM-based intent compiler and the LLM memory summarizer are stubbed here with deterministic baselines that run offline; swap points are marked.

## Global Constraints

- **No hard filters.** Query Card only carries interpretation + freeText query + soft targets/weights; negatives only subtract score, never remove. (PRD §0)
- **Confirm gate is mandatory.** `/intent` and `/intent/follow-up` never trigger search; only `/intent/confirm` does. (PRD §1 ②③)
- **No premature expansion.** `similarById` runs only after a `like`, never before. (PRD §0, §1 ⑤)
- **Session state is in-memory only**, discarded on process exit — never persisted. (PRD §3)
- **Cross-session memory = two markdown files per user**, no DB: `backend/memory/<user_id>.evidence.md` (append-only) and `backend/memory/<user_id>.memory.md` (rewritten). (PRD §3)
- **Cyanite REST:** base `https://rest-api.cyanite.ai/v1`, auth header `x-api-key: <CYANITE_API_KEY>`. Track ids: data-pack `track_id` (Jamendo) ↔ `cyanite_id` via `data/tracks.csv`.
- **Rerank guardrail:** `w_primary > w_soft + w_neg` must hold. (PRD §3)
- All backend commands run from `backend/` via `uv run …`.

---

### Task 1: Cyanite client wrapper

**Files:**
- Create: `backend/cyanite.py`
- Test: `backend/test_cyanite.py`

**Interfaces:**
- Consumes: env `CYANITE_API_KEY`; `data/tracks.csv` columns `track_id,cyanite_id,name,artist_name`.
- Produces:
  - `to_cyanite(track_id: str) -> str` and `to_jamendo(cyanite_id: str) -> str`
  - `display(cyanite_id: str) -> dict` → `{"track_id","cyanite_id","title","artist"}`
  - `normalize(resp: dict) -> list[dict]` → each `{"cyanite_id","score"}` from a Cyanite `{items:[{track,score}]}` envelope
  - `search_by_prompt(query: str, limit: int = 20) -> list[dict]` (freeText) → normalized
  - `find_similar(cyanite_id: str, limit: int = 20) -> list[dict]` → normalized
  - `model_tags(cyanite_id: str, models: list[str]) -> dict` (for "Why this")

- [ ] **Step 1: Write the failing test** (`backend/test_cyanite.py`)

```python
import cyanite


def test_normalize_extracts_id_and_score():
    resp = {"items": [
        {"track": {"id": "libtr_a"}, "score": 0.9},
        {"track": {"id": "libtr_b"}, "score": 0.5},
    ], "pageInfo": {"nextCursor": None}}
    out = cyanite.normalize(resp)
    assert out == [
        {"cyanite_id": "libtr_a", "score": 0.9},
        {"cyanite_id": "libtr_b", "score": 0.5},
    ]


def test_normalize_handles_empty():
    assert cyanite.normalize({"items": []}) == []


def test_id_roundtrip():
    # any id present in data/tracks.csv survives jamendo->cyanite->jamendo
    jam = next(iter(cyanite._JAM_TO_CYAN))
    assert cyanite.to_jamendo(cyanite.to_cyanite(jam)) == jam
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_cyanite.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cyanite'`

- [ ] **Step 3: Write minimal implementation** (`backend/cyanite.py`)

```python
"""Thin Cyanite REST wrapper. The only place that talks to the network.
Session logic monkeypatches this module in tests."""
from __future__ import annotations
import csv
import os
import pathlib

import requests

BASE_URL = "https://rest-api.cyanite.ai/v1"
_DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "tracks.csv"

_JAM_TO_CYAN: dict[str, str] = {}
_DISPLAY: dict[str, dict] = {}
with _DATA.open() as f:
    for row in csv.DictReader(f):
        _JAM_TO_CYAN[row["track_id"]] = row["cyanite_id"]
        _DISPLAY[row["cyanite_id"]] = {
            "track_id": row["track_id"],
            "cyanite_id": row["cyanite_id"],
            "title": row.get("name", ""),
            "artist": row.get("artist_name", ""),
        }
_CYAN_TO_JAM = {c: j for j, c in _JAM_TO_CYAN.items()}

_session = requests.Session()
_session.headers.update({"x-api-key": os.environ.get("CYANITE_API_KEY", "")})


def to_cyanite(track_id: str) -> str:
    return _JAM_TO_CYAN[str(track_id)]


def to_jamendo(cyanite_id: str) -> str:
    return _CYAN_TO_JAM[cyanite_id]


def display(cyanite_id: str) -> dict:
    return _DISPLAY.get(cyanite_id, {"cyanite_id": cyanite_id, "title": "", "artist": ""})


def normalize(resp: dict) -> list[dict]:
    out = []
    for it in resp.get("items", []):
        track = it.get("track", it)
        out.append({"cyanite_id": track.get("id"), "score": it.get("score")})
    return out


def search_by_prompt(query: str, limit: int = 20) -> list[dict]:
    r = _session.post(f"{BASE_URL}/private-alpha/library-tracks/search",
                      params={"limit": limit}, json={"query": query}, timeout=60)
    r.raise_for_status()
    return normalize(r.json())


def find_similar(cyanite_id: str, limit: int = 20) -> list[dict]:
    r = _session.post(f"{BASE_URL}/private-alpha/library-tracks/{cyanite_id}/similar",
                      params={"limit": limit}, json={}, timeout=60)
    r.raise_for_status()
    return normalize(r.json())


def model_tags(cyanite_id: str, models: list[str]) -> dict:
    params = [("model", m) for m in models]
    r = _session.get(f"{BASE_URL}/library-tracks/{cyanite_id}/models", params=params, timeout=60)
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_cyanite.py -v`
Expected: PASS (3 passed). `requests` must be installed: `uv add requests pytest` first if missing.

- [ ] **Step 5: Commit**

```bash
git add backend/cyanite.py backend/test_cyanite.py backend/pyproject.toml backend/uv.lock
git commit -m "feat: thin Cyanite REST client wrapper"
```

---

### Task 2: Query Card compiler (deterministic baseline)

**Files:**
- Create: `backend/compile.py`
- Test: `backend/test_compile.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `compile_query_card(posts: list[dict], profile_md: str = "") -> dict`
  where each post is `{"role","text",...}` and the return is a Query Card dict
  `{"interpretation_plain","free_text_query","soft_targets":[],"negatives":[]}`.

**Note:** This is the offline baseline — it concatenates whiteboard text into the
freeText query and a plain-language interpretation. `# ponytail: baseline, no LLM.
Swap body for an LLM call later; signature stays.` `profile_md` is the user's
`memory.md` to bias compilation (PRD §1 ⑧); the baseline prepends it as context.

- [ ] **Step 1: Write the failing test** (`backend/test_compile.py`)

```python
import compile as c


def test_initial_prompt_becomes_query():
    card = c.compile_query_card([{"role": "initial_prompt", "text": "lonely midnight train"}])
    assert card["free_text_query"].strip() == "lonely midnight train"
    assert "lonely midnight train" in card["interpretation_plain"]
    assert card["soft_targets"] == [] and card["negatives"] == []


def test_followups_are_appended_in_order():
    card = c.compile_query_card([
        {"role": "initial_prompt", "text": "dark betrayal"},
        {"role": "follow_up", "text": "less epic, more restrained"},
    ])
    q = card["free_text_query"]
    assert q.index("dark betrayal") < q.index("less epic, more restrained")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_compile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compile'`... wait, `compile` is a Python builtin name but a local `compile.py` shadows it on import within `backend/`. If the import resolves to the builtin, rename file to `intent_compile.py` and update imports. Run again; expected FAIL with attribute/`compile_query_card` missing.

- [ ] **Step 3: Write minimal implementation** (`backend/compile.py`)

```python
"""Whiteboard posts -> Query Card. Offline baseline.
# ponytail: deterministic v1, no LLM. Swap body for an LLM call; signature stays."""
from __future__ import annotations


def compile_query_card(posts: list[dict], profile_md: str = "") -> dict:
    texts = [p["text"].strip() for p in posts if p.get("text", "").strip()]
    query = " ".join(texts)
    return {
        "interpretation_plain": f"我把你的需求理解成：{query}",
        "free_text_query": query,
        "soft_targets": [],
        "negatives": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_compile.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/compile.py backend/test_compile.py
git commit -m "feat: deterministic Query Card compiler baseline"
```

---

### Task 3: Session store + `/intent` + `/intent/follow-up` (confirm gate, no search)

**Files:**
- Modify: `backend/app.py` (replace `IntentIn`, `/intent`; add `/intent/follow-up`)
- Test: `backend/test_intent.py`

**Interfaces:**
- Consumes: `compile.compile_query_card` (Task 2), `memory.read_memory` (exists).
- Produces:
  - `SESSIONS: dict[str, dict]` where a session is
    `{"id","user_id","whiteboard_posts":[],"query_card":dict,"visible_cards":[],"free_text_backlog":[],"candidate_pool":[],"disliked_tracks":{}}`
  - `POST /intent {text,user_id}` → `{"session_id","whiteboard_posts","query_card"}`
  - `POST /intent/follow-up {session_id,text}` → `{"whiteboard_posts","query_card"}`
  - Helper `_new_post(role,text) -> dict` = `{"id","role","text","created_at"}`
  - Neither endpoint calls `cyanite` — gate is enforced by absence of search.

- [ ] **Step 1: Write the failing test** (`backend/test_intent.py`)

```python
from fastapi.testclient import TestClient
import app

client = TestClient(app.app)


def test_intent_creates_session_and_card_without_search(monkeypatch):
    called = {"search": False}
    monkeypatch.setattr(app.cyanite, "search_by_prompt",
                        lambda *a, **k: called.__setitem__("search", True) or [])
    r = client.post("/intent", json={"text": "lonely midnight train", "user_id": "u1"})
    body = r.json()
    assert r.status_code == 200
    assert body["session_id"] in app.SESSIONS
    assert body["query_card"]["free_text_query"] == "lonely midnight train"
    assert len(body["whiteboard_posts"]) == 1
    assert called["search"] is False  # confirm gate: no search yet


def test_followup_appends_post_and_recompiles(monkeypatch):
    sid = client.post("/intent", json={"text": "dark betrayal", "user_id": "u1"}).json()["session_id"]
    r = client.post("/intent/follow-up", json={"session_id": sid, "text": "more restrained"})
    body = r.json()
    assert len(body["whiteboard_posts"]) == 2
    assert "more restrained" in body["query_card"]["free_text_query"]


def test_followup_unknown_session_404():
    r = client.post("/intent/follow-up", json={"session_id": "nope", "text": "x"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_intent.py -v`
Expected: FAIL — `/intent/follow-up` returns 404 for the happy path / `whiteboard_posts` missing from response. (`uv add pytest httpx` if TestClient import fails.)

- [ ] **Step 3: Write minimal implementation** — replace the `/intent` section of `backend/app.py`

```python
import uuid
import datetime as _dt

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import cyanite
import compile as _compile
import memory

app = FastAPI(title="Cochlea")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

SESSIONS: dict[str, dict] = {}


class IntentIn(BaseModel):
    text: str
    user_id: str = "demo"


class FollowUpIn(BaseModel):
    session_id: str
    text: str


def _new_post(role: str, text: str) -> dict:
    return {"id": uuid.uuid4().hex[:8], "role": role, "text": text,
            "created_at": _dt.datetime.now().isoformat(timespec="seconds")}


def _get(session_id: str) -> dict:
    s = SESSIONS.get(session_id)
    if s is None:
        raise HTTPException(404, "unknown session_id")
    return s


def _recompile(s: dict) -> None:
    profile = memory.read_memory(s["user_id"])
    s["query_card"] = _compile.compile_query_card(s["whiteboard_posts"], profile)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intent")
def intent(body: IntentIn):
    sid = uuid.uuid4().hex[:12]
    s = {"id": sid, "user_id": body.user_id,
         "whiteboard_posts": [_new_post("initial_prompt", body.text)],
         "query_card": {}, "visible_cards": [], "free_text_backlog": [],
         "candidate_pool": [], "disliked_tracks": {}}
    _recompile(s)
    SESSIONS[sid] = s
    return {"session_id": sid, "whiteboard_posts": s["whiteboard_posts"],
            "query_card": s["query_card"]}


@app.post("/intent/follow-up")
def follow_up(body: FollowUpIn):
    s = _get(body.session_id)
    s["whiteboard_posts"].append(_new_post("follow_up", body.text))
    _recompile(s)
    return {"whiteboard_posts": s["whiteboard_posts"], "query_card": s["query_card"]}
```

(Leave the old `/intent/confirm`, `/feedback`, `/your-sound` defined below this — they are rewritten in Tasks 4–6.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_intent.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/test_intent.py
git commit -m "feat: session store + intent/follow-up behind confirm gate"
```

---

### Task 4: `/intent/confirm` → freeText search → first recommendations

**Files:**
- Modify: `backend/app.py` (rewrite `/intent/confirm`; add `_card_from` helper)
- Test: `backend/test_confirm.py`

**Interfaces:**
- Consumes: `SESSIONS`, `_get` (Task 3); `cyanite.search_by_prompt`, `cyanite.display` (Task 1).
- Produces:
  - `POST /intent/confirm {session_id}` → `{"cards":[RecCard], "candidate_pool_size":0}`
  - `_card_from(cyanite_id, score, source) -> dict` RecCard =
    `{"track_id","cyanite_id","title","artist","source","search_score","why"}`
  - Side effect: fills `s["visible_cards"]` (top N) and `s["free_text_backlog"]` (the rest).
  - `VISIBLE_N = 5`.

- [ ] **Step 1: Write the failing test** (`backend/test_confirm.py`)

```python
from fastapi.testclient import TestClient
import app

client = TestClient(app.app)

FAKE = [{"cyanite_id": f"libtr_{i}", "score": 1.0 - i / 10} for i in range(8)]


def _session(monkeypatch):
    monkeypatch.setattr(app.cyanite, "search_by_prompt", lambda q, limit=20: FAKE)
    monkeypatch.setattr(app.cyanite, "display",
                        lambda cid: {"track_id": cid.replace("libtr_", ""),
                                     "cyanite_id": cid, "title": "T", "artist": "A"})
    return client.post("/intent", json={"text": "x", "user_id": "u1"}).json()["session_id"]


def test_confirm_returns_visible_and_backlogs_rest(monkeypatch):
    sid = _session(monkeypatch)
    r = client.post("/intent/confirm", json={"session_id": sid})
    body = r.json()
    assert len(body["cards"]) == app.VISIBLE_N
    assert body["cards"][0]["source"] == "free_text"
    assert body["cards"][0]["search_score"] == 1.0
    assert len(app.SESSIONS[sid]["free_text_backlog"]) == len(FAKE) - app.VISIBLE_N


def test_confirm_unknown_session_404():
    assert client.post("/intent/confirm", json={"session_id": "nope"}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_confirm.py -v`
Expected: FAIL — current `/intent/confirm` returns `{"session_id","cards":[]}` so `cards` is empty and `VISIBLE_N` is undefined (`AttributeError`).

- [ ] **Step 3: Write minimal implementation** — replace `/intent/confirm` in `backend/app.py`

```python
VISIBLE_N = 5


class ConfirmIn(BaseModel):
    session_id: str


def _card_from(cyanite_id: str, score: float, source: str) -> dict:
    d = cyanite.display(cyanite_id)
    return {"track_id": d.get("track_id", ""), "cyanite_id": cyanite_id,
            "title": d.get("title", ""), "artist": d.get("artist", ""),
            "source": source, "search_score": score,
            "why": f"匹配你确认过的需求（score {score:.2f}）。"}


@app.post("/intent/confirm")
def confirm(body: ConfirmIn):
    s = _get(body.session_id)
    results = cyanite.search_by_prompt(s["query_card"]["free_text_query"], limit=20)
    cards = [_card_from(r["cyanite_id"], r["score"], "free_text") for r in results]
    s["visible_cards"] = cards[:VISIBLE_N]
    s["free_text_backlog"] = cards[VISIBLE_N:]
    return {"cards": s["visible_cards"], "candidate_pool_size": len(s["candidate_pool"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_confirm.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/test_confirm.py
git commit -m "feat: confirm gate runs freeText search, fills visible + backlog"
```

---

### Task 5: `/feedback` — like builds candidate pool, dislike removes + backfills

**Files:**
- Modify: `backend/app.py` (rewrite `/feedback`; add `_backfill` helper)
- Test: `backend/test_feedback.py`

**Interfaces:**
- Consumes: `SESSIONS`, `_get`, `_card_from`, `VISIBLE_N`; `cyanite.find_similar`.
- Produces:
  - `POST /feedback {session_id,track_id,verdict}` → `{"cards":[...], "candidate_pool_size":int}`
  - Candidate pool item = `{"cyanite_id","source_liked_track","similar_score","prompt_match_score":None,"status":"candidate"}`
  - `_backfill(s) -> dict|None` — picks the highest-`similar_score` pool item not
    disliked / not already visible, removes it from the pool, returns a RecCard;
    falls back to `free_text_backlog`; returns `None` if both empty.
  - **`like` does NOT touch `visible_cards`** (pool is supply, not a swap). **`dislike` removes T from `visible_cards` then backfills one slot.** (PRD §1 ⑤)
  - **Backfill ordering = `similar_score` descending** — the PRD's "ideal" `prompt_match_score` path is left as `# ponytail:` TODO because Cyanite has no single-track↔prompt score endpoint (confirmed from the starter notebook). `prompt_match_score` stays `None`.

- [ ] **Step 1: Write the failing test** (`backend/test_feedback.py`)

```python
from fastapi.testclient import TestClient
import app

client = TestClient(app.app)

SEARCH = [{"cyanite_id": f"libtr_{i}", "score": 1.0 - i / 10} for i in range(6)]
SIMILAR = [{"cyanite_id": f"sim_{i}", "score": 0.9 - i / 10} for i in range(3)]


def _ready(monkeypatch):
    monkeypatch.setattr(app.cyanite, "search_by_prompt", lambda q, limit=20: SEARCH)
    monkeypatch.setattr(app.cyanite, "find_similar", lambda cid, limit=20: SIMILAR)
    monkeypatch.setattr(app.cyanite, "display",
                        lambda cid: {"track_id": cid, "cyanite_id": cid, "title": "T", "artist": "A"})
    monkeypatch.setattr(app.cyanite, "to_cyanite", lambda tid: tid)
    sid = client.post("/intent", json={"text": "x", "user_id": "u1"}).json()["session_id"]
    client.post("/intent/confirm", json={"session_id": sid})
    return sid


def test_like_fills_pool_without_changing_visible(monkeypatch):
    sid = _ready(monkeypatch)
    before = [c["track_id"] for c in app.SESSIONS[sid]["visible_cards"]]
    r = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    body = r.json()
    assert body["candidate_pool_size"] == len(SIMILAR)
    assert [c["track_id"] for c in body["cards"]] == before  # visible unchanged


def test_dislike_removes_and_backfills_highest_similar(monkeypatch):
    sid = _ready(monkeypatch)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    r = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"})
    ids = [c["track_id"] for c in r.json()["cards"]]
    assert "libtr_1" not in ids                 # removed
    assert "sim_0" in ids                        # highest similar_score backfilled
    assert len(ids) == app.VISIBLE_N             # slot count preserved


def test_dislike_with_empty_pool_uses_backlog(monkeypatch):
    sid = _ready(monkeypatch)  # backlog has libtr_5 (6 results - 5 visible)
    r = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "dislike"})
    ids = [c["track_id"] for c in r.json()["cards"]]
    assert "libtr_0" not in ids and "libtr_5" in ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_feedback.py -v`
Expected: FAIL — current `/feedback` returns `{"cards":[]}` and ignores pool/backfill.

- [ ] **Step 3: Write minimal implementation** — replace `/feedback` in `backend/app.py`

```python
class FeedbackIn(BaseModel):
    session_id: str
    track_id: str
    verdict: str  # "like" | "dislike"


def _visible_ids(s: dict) -> set[str]:
    return {c["cyanite_id"] for c in s["visible_cards"]}


def _backfill(s: dict) -> dict | None:
    # highest similar_score candidate not disliked / not already visible
    pool = [p for p in s["candidate_pool"]
            if p["cyanite_id"] not in s["disliked_tracks"]
            and p["cyanite_id"] not in _visible_ids(s)]
    if pool:
        best = max(pool, key=lambda p: p["similar_score"] or 0)
        s["candidate_pool"].remove(best)
        # ponytail: order by similar_score. Cyanite has no track<->prompt score endpoint;
        # if one appears, set prompt_match_score and sort by it instead.
        return _card_from(best["cyanite_id"], best["similar_score"], "similar")
    if s["free_text_backlog"]:
        return s["free_text_backlog"].pop(0)
    return None


@app.post("/feedback")
def feedback(body: FeedbackIn):
    s = _get(body.session_id)
    cid = body.track_id  # recommendation cards expose the cyanite_id as track_id
    if body.verdict == "like":
        for sim in cyanite.find_similar(cid, limit=20):
            s["candidate_pool"].append({
                "cyanite_id": sim["cyanite_id"], "source_liked_track": cid,
                "similar_score": sim["score"], "prompt_match_score": None,
                "status": "candidate"})
    elif body.verdict == "dislike":
        s["disliked_tracks"][cid] = True
        s["visible_cards"] = [c for c in s["visible_cards"] if c["cyanite_id"] != cid]
        fill = _backfill(s)
        if fill:
            s["visible_cards"].append(fill)
    return {"cards": s["visible_cards"], "candidate_pool_size": len(s["candidate_pool"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_feedback.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/test_feedback.py
git commit -m "feat: like builds candidate pool, dislike removes and backfills"
```

---

### Task 6: Memory wiring — like persists evidence + rewrites memory; `/your-sound`; `/intent` injection

**Files:**
- Modify: `backend/memory.py` (rename param to `whiteboard_context`)
- Modify: `backend/app.py` (call memory on `like`; rewrite `/your-sound`)
- Test: `backend/test_memory_loop.py`

**Interfaces:**
- Consumes: `memory.append_evidence`, `memory.rewrite_memory`, `memory.read_memory`.
- Produces:
  - `memory.append_evidence(user_id, whiteboard_context, liked_track_ids)` — append-only row in `<user_id>.evidence.md`.
  - On `like`: append evidence with the session's current whiteboard text joined, then `rewrite_memory(user_id)`.
  - `GET /your-sound?user_id=` → `{"memory_md": <str>}` (already present; verify).
  - `_whiteboard_text(s) -> str` = the joined whiteboard post texts (the "current context" the PRD §3 evidence row records).

- [ ] **Step 1: Write the failing test** (`backend/test_memory_loop.py`)

```python
import pathlib
from fastapi.testclient import TestClient
import app, memory

client = TestClient(app.app)
SIMILAR = [{"cyanite_id": "sim_0", "score": 0.9}]


def test_like_appends_evidence_and_rewrites_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, "MEM_DIR", tmp_path)
    monkeypatch.setattr(app.cyanite, "search_by_prompt",
                        lambda q, limit=20: [{"cyanite_id": "libtr_0", "score": 1.0}])
    monkeypatch.setattr(app.cyanite, "find_similar", lambda cid, limit=20: SIMILAR)
    monkeypatch.setattr(app.cyanite, "display",
                        lambda cid: {"track_id": cid, "cyanite_id": cid, "title": "T", "artist": "A"})
    sid = client.post("/intent", json={"text": "dark betrayal", "user_id": "u9"}).json()["session_id"]
    client.post("/intent/confirm", json={"session_id": sid})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})

    ev = (tmp_path / "u9.evidence.md").read_text(encoding="utf-8")
    assert "dark betrayal" in ev and "libtr_0" in ev
    assert client.get("/your-sound", params={"user_id": "u9"}).json()["memory_md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_memory_loop.py -v`
Expected: FAIL — `/feedback` like path does not call `memory.append_evidence`, so the evidence file is absent.

- [ ] **Step 3: Write minimal implementation**

In `backend/memory.py`, rename the second parameter for clarity (behavior unchanged):

```python
def append_evidence(user_id: str, whiteboard_context: str, liked_track_ids: list[str]) -> None:
    p = _ev_path(user_id)
    if not p.exists():
        p.write_text(f"# evidence · {user_id}\n\n## 反馈记录\n", encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    liked = ", ".join(liked_track_ids) or "-"
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- 「{whiteboard_context}」→ liked {liked}   ({ts})\n")
```

In `backend/app.py`, add the helper and extend the `like` branch of `feedback`:

```python
def _whiteboard_text(s: dict) -> str:
    return " / ".join(p["text"] for p in s["whiteboard_posts"])
```

Inside `feedback`, in the `if body.verdict == "like":` branch, after the pool is filled:

```python
        memory.append_evidence(s["user_id"], _whiteboard_text(s), [cid])
        memory.rewrite_memory(s["user_id"])
```

Verify `/your-sound` reads memory (keep as-is):

```python
@app.get("/your-sound")
def your_sound(user_id: str = "demo"):
    return {"memory_md": memory.read_memory(user_id)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest test_memory_loop.py -v && uv run python memory.py`
Expected: test PASS (1 passed); `memory.py` self-check prints `memory self-check OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/memory.py backend/app.py backend/test_memory_loop.py
git commit -m "feat: like persists evidence and rewrites memory; your-sound reads it"
```

---

### Task 7: Full-loop smoke + thin rerank guardrail

**Files:**
- Create: `backend/rerank.py`
- Modify: `backend/app.py` (apply `rerank.thin_rerank` to `visible_cards` before returning from `/feedback`)
- Test: `backend/test_rerank.py`

**Interfaces:**
- Consumes: card dicts with `search_score`/`similar_score`.
- Produces: `thin_rerank(cards: list[dict], w_primary=1.0, w_soft=0.3, w_neg=0.3) -> list[dict]`
  sorted by `primary_match` (the card's `search_score` or `similar_score`), with an
  assert enforcing the `w_primary > w_soft + w_neg` guardrail.

- [ ] **Step 1: Write the failing test** (`backend/test_rerank.py`)

```python
import pytest
import rerank


def test_orders_by_primary_score_desc():
    cards = [{"search_score": 0.2}, {"search_score": 0.9}, {"search_score": 0.5}]
    out = rerank.thin_rerank(cards)
    assert [c["search_score"] for c in out] == [0.9, 0.5, 0.2]


def test_guardrail_rejects_bad_weights():
    with pytest.raises(AssertionError):
        rerank.thin_rerank([], w_primary=0.3, w_soft=0.3, w_neg=0.3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest test_rerank.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rerank'`.

- [ ] **Step 3: Write minimal implementation** (`backend/rerank.py`)

```python
"""Thin rerank — audio/semantic similarity stays the dominant signal (PRD §3).
# ponytail: soft/neg tag terms are 0 until tag fetch lands; guardrail is the real check."""
from __future__ import annotations


def thin_rerank(cards: list[dict], w_primary: float = 1.0,
                w_soft: float = 0.3, w_neg: float = 0.3) -> list[dict]:
    assert w_primary > w_soft + w_neg, "guardrail: primary must dominate"

    def primary(c: dict) -> float:
        v = c.get("search_score")
        if v is None:
            v = c.get("similar_score")
        return v or 0.0

    return sorted(cards, key=primary, reverse=True)
```

Then in `backend/app.py`, `import rerank` and at the end of `feedback`, before returning, sort visible cards:

```python
    s["visible_cards"] = rerank.thin_rerank(s["visible_cards"])
    return {"cards": s["visible_cards"], "candidate_pool_size": len(s["candidate_pool"])}
```

- [ ] **Step 4: Run the whole suite + thin rerank test**

Run: `cd backend && uv run pytest -v`
Expected: PASS — all tests across `test_cyanite/compile/intent/confirm/feedback/memory_loop/rerank` green.

- [ ] **Step 5: Commit**

```bash
git add backend/rerank.py backend/app.py backend/test_rerank.py
git commit -m "feat: thin rerank with primary-dominates guardrail; full loop green"
```

---

## Self-Review

**1. Spec coverage (PRD §1/§3 → task):**
- ① whiteboard + compile → Task 2, Task 3
- ② confirm gate (no search on /intent, follow-up recompiles) → Task 3
- ③ confirm runs freeText only, no premature similar → Task 4
- ④ recommendation cards + "why" → Task 4 (`_card_from.why`); full tag-grounded "Why this" is frontend + `cyanite.model_tags` (Task 1 provides the call) — **flagged below**
- ⑤ like→candidate pool; dislike→remove+backfill → Task 5
- ⑥ thin rerank, primary dominates → Task 7
- ⑦ evidence append + memory rewrite → Task 6
- ⑧ memory injected at compile → Task 3 (`_recompile` passes `profile`) + Task 2 (`profile_md` param)
- §3 endpoints: `/intent`, `/intent/follow-up`, `/intent/confirm`, `/feedback`, `/your-sound` → Tasks 3–6 ✓

**2. Placeholder scan:** No "TODO/handle errors" left as instructions; the one deliberate shortcut (no `prompt_match_score` endpoint) is documented with the reason and an upgrade path, not a gap. The `compile`/`rerank`/`memory` LLM swap points are explicit baselines with working code, not placeholders.

**3. Type consistency:** RecCard shape (`track_id,cyanite_id,title,artist,source,search_score,why`) is defined in Task 4 `_card_from` and reused unchanged in Tasks 5–7. Candidate item shape defined in Task 5 and read by `_backfill` consistently. `normalize` output `{cyanite_id,score}` (Task 1) is consumed by Tasks 4–5.

**Known gaps deferred to the frontend plan (not this scope):**
- Tag-grounded "Why this track?" rendering via `cyanite.model_tags` (call exists; UI + richer `why` string is frontend).
- Audio playback URLs (Jamendo mp3 link helper exists in the notebook; fold into `cyanite.display` when the frontend needs it).
- Soft-target / negative tag scoring in `thin_rerank` (currently 0; needs batch tag fetch — add when a card-tag cache exists).

**Real-Cyanite caveat:** all tests monkeypatch `cyanite`. Before the demo, run one live smoke with a real `CYANITE_API_KEY` against `/intent → confirm → feedback` to confirm the REST shapes match `normalize`.
