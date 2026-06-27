"""FastAPI routes for the user-profile / taste-memory module.

Exposes a `router` the team's main app can mount, plus a standalone `app` so this
module runs on its own (handy for the /feedback + /your-sound demo).

Endpoints
  POST /feedback            record one like/dislike/skip/note -> updated summary
  POST /feedback/batch      record a list of feedback events
  GET  /your-sound/{uid}    memory summary (headline + structured prefs)
  GET  /profile/{uid}/seeds       liked-track seed pool (for similarById)   [?prompt=&limit=]
  GET  /profile/{uid}/injection   system-prompt taste block (for /intent)
  GET  /profile/{uid}/markdown    the raw markdown memory file (nice for demo)
"""
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import mdmemory

router = APIRouter()


# ---- request models ---------------------------------------------------------
class Feedback(BaseModel):
    user_id: str
    track_id: str
    verdict: str                      # like | dislike | skip | play | note
    prompt: Optional[str] = None
    note: Optional[str] = None
    track_tags: Optional[dict] = None  # optional; fetched from Cyanite if absent


class FeedbackBatch(BaseModel):
    user_id: str
    events: List[Feedback]


_VERDICTS = {"like", "dislike", "skip", "play", "note"}


# ---- routes -----------------------------------------------------------------
@router.post("/feedback")
def post_feedback(fb: Feedback):
    if fb.verdict not in _VERDICTS:
        raise HTTPException(400, f"verdict must be one of {sorted(_VERDICTS)}")
    return mdmemory.record_feedback(
        fb.user_id, fb.track_id, fb.verdict,
        prompt=fb.prompt, note=fb.note, track_tags=fb.track_tags)


@router.post("/feedback/batch")
def post_feedback_batch(batch: FeedbackBatch):
    summary = None
    for e in batch.events:
        if e.verdict not in _VERDICTS:
            raise HTTPException(400, f"bad verdict: {e.verdict}")
        summary = mdmemory.record_feedback(
            batch.user_id, e.track_id, e.verdict,
            prompt=e.prompt, note=e.note, track_tags=e.track_tags)
    return summary or {"detail": "no events"}


@router.get("/your-sound/{user_id}")
def your_sound(user_id: str):
    return mdmemory.summary(user_id)


@router.get("/profile/{user_id}/seeds")
def seeds(user_id: str, prompt: Optional[str] = None, limit: Optional[int] = None):
    return {"user_id": user_id, "seeds": mdmemory.seed_pool(user_id, prompt=prompt, limit=limit)}


@router.get("/profile/{user_id}/injection")
def injection(user_id: str):
    return {"user_id": user_id, "injection": mdmemory.prompt_injection(user_id)}


@router.get("/profile/{user_id}/memory")
def memory_md(user_id: str):
    """The natural-language profile (memory.md) — what /intent injects."""
    import os
    p = mdmemory._memory_path(user_id)
    if not os.path.exists(p):
        raise HTTPException(404, "no memory for this user yet")
    return {"user_id": user_id, "markdown": open(p).read()}


@router.get("/profile/{user_id}/evidence")
def evidence_md(user_id: str):
    """The append-only raw evidence log (evidence.md)."""
    import os
    p = mdmemory._evidence_path(user_id)
    if not os.path.exists(p):
        raise HTTPException(404, "no evidence for this user yet")
    return {"user_id": user_id, "markdown": open(p).read()}


@router.get("/profile/{user_id}/card.png")
def taste_card(user_id: str):
    """A rendered 'Taste Card' PNG visualizing the user's memory (for the demo)."""
    from . import visualize
    try:
        path = visualize.render_card(user_id)
    except SystemExit:
        raise HTTPException(404, "no memory for this user yet")
    return FileResponse(path, media_type="image/png")


@router.get("/profile/{user_id}/timeline.png")
def taste_timeline(user_id: str):
    """Taste-evolution timeline PNG (how the profile drifted over feedback)."""
    from . import visualize
    try:
        path = visualize.render_timeline(user_id)
    except SystemExit:
        raise HTTPException(404, "not enough history for this user yet")
    return FileResponse(path, media_type="image/png")


@router.get("/profile/{user_id}/year.png")
def year_report(user_id: str, year: int = 2025):
    """A 'Year in Sound' yearbook PNG (mood-based, Spotify-Wrapped style)."""
    from . import yearreport
    try:
        path, _ = yearreport.render_report(user_id, year)
    except SystemExit:
        raise HTTPException(404, "no listening data for this user yet")
    return FileResponse(path, media_type="image/png")


class Rerank(BaseModel):
    user_id: str
    track_ids: List[str]
    limit: Optional[int] = None


@router.post("/rerank")
def post_rerank(req: Rerank):
    """Re-rank candidate track ids by the user's taste memory, with a grounded
    'why this track' per result."""
    from . import recommend
    return {"user_id": req.user_id,
            "results": recommend.rerank(req.user_id, req.track_ids, limit=req.limit)}


@router.get("/profile/{user_id}/discover")
def discover_endpoint(user_id: str, limit: int = 10):
    """Profile -> inferred text prompt -> Cyanite prompt search -> NEW tracks,
    memory-reranked with a 'why' each. Returns {prompt, results}."""
    from . import discover
    return discover.discover(user_id, limit=limit)


# ---- standalone app ---------------------------------------------------------
app = FastAPI(title="Cochlea — user profile / taste memory")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    from . import config
    return {"ok": True, "mock": config.MOCK}
