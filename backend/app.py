"""HTTP 层 · 冻死的数据契约 + 路由（你负责）。

只做两件事：定义请求/响应 schema（前后端的接缝），把请求转给 orchestrator。
业务编排全在 orchestrator.py，这里保持薄。

run: uv run uvicorn app:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import orchestrator

app = FastAPI(title="Cochlea")

# ponytail: dev 全放行；上线再收敛到具体来源
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ─────────── 请求契约 ───────────
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


# ─────────── 响应裁剪（只把前端要的字段吐出去）───────────
def _intent_view(s: dict) -> dict:
    return {"session_id": s["id"], "whiteboard_posts": s["whiteboard_posts"],
            "query_card": s["query_card"]}


def _board_view(s: dict) -> dict:
    return {"whiteboard_posts": s["whiteboard_posts"], "query_card": s["query_card"]}


def _cards_view(s: dict) -> dict:
    return {"cards": s["visible_cards"], "candidate_pool_size": len(s["candidate_pool"])}


def _guard(fn, *args):
    try:
        return fn(*args)
    except orchestrator.SessionNotFound:
        raise HTTPException(404, "unknown session_id")


# ─────────── 路由 ───────────
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
    return _cards_view(_guard(orchestrator.confirm, body.session_id))


@app.post("/feedback")
def feedback(body: FeedbackIn):
    return _cards_view(_guard(orchestrator.feedback, body.session_id, body.track_id, body.verdict))


@app.get("/your-sound")
def your_sound(user_id: str = "demo"):
    return {"memory_md": orchestrator.your_sound(user_id)}
