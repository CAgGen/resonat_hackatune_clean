"""Cochlea backend — 4 端点骨架（PRD 第 3 节）。会话状态=内存 dict，记忆=markdown。

run: uv run uvicorn app:app --reload
"""
from __future__ import annotations
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import memory

app = FastAPI(title="Cochlea")

# ponytail: dev 全放行；上线再收敛到具体来源
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# 会话状态：内存 dict，会话结束就扔，不落盘
SESSIONS: dict[str, dict] = {}


class IntentIn(BaseModel):
    text: str
    user_id: str = "demo"


class SoftTarget(BaseModel):
    dim: str
    value: str
    weight: float = 0.5


class QueryCard(BaseModel):
    interpretation_plain: str
    free_text_query: str
    soft_targets: list[SoftTarget] = []
    negatives: list[dict] = []


class FeedbackIn(BaseModel):
    session_id: str
    track_id: str
    verdict: str  # "like" | "dislike"


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intent")
def intent(body: IntentIn):
    """LLM 编译意图 → Query Card 草稿，带 memory.md 里的画像做 prompt。"""
    _profile = memory.read_memory(body.user_id)  # TODO(B1): 注入系统 prompt
    # ponytail: 先回写死草稿，B1 接 LLM
    return QueryCard(
        interpretation_plain=f"（占位）我把『{body.text}』理解成…",
        free_text_query=body.text,
    )


@app.post("/intent/confirm")
def confirm(card: QueryCard):
    """过确认门 → freeText 出种子 → 簇扩展 → 首批候选。"""
    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = {"card": card.model_dump(), "queue": [], "pruned": {}}
    # TODO(B2): freeTextSearch 5 种子 + similarById 簇扩展，填 queue
    return {"session_id": sid, "cards": []}


@app.post("/feedback")
def feedback(body: FeedbackIn):
    """剪枝 / 回填 / 薄重排 → 下一批。like 还要落记忆。"""
    s = SESSIONS.get(body.session_id)
    if s is None:
        raise HTTPException(404, "unknown session_id")
    # TODO(B3): dislike→邻域剪枝；like→similarById 回填 + 薄重排
    if body.verdict == "like":
        prompt = s["card"]["free_text_query"]
        memory.append_evidence("demo", prompt, [body.track_id])
        memory.rewrite_memory("demo")
    return {"cards": []}


@app.get("/your-sound")
def your_sound(user_id: str = "demo"):
    """记忆摘要，演『越用越准』。"""
    return {"memory_md": memory.read_memory(user_id)}
