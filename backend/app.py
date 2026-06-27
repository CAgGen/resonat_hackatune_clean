"""HTTP 层 · 冻死的数据契约 + 路由（你负责）。

只做两件事：定义请求/响应 schema（前后端的接缝），把请求转给 orchestrator。
业务编排全在 orchestrator.py，这里保持薄。

run: uv run uvicorn app:app --reload
"""
from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import cyanite
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


# ─────────── Cyanite 透传（调试用，直接在 /docs 试）───────────
# ponytail: 给每条结果拼上 title/artist，Swagger 里看得懂；底层就是 cyanite.py
def _enrich(rows: list[dict]) -> list[dict]:
    return [{**r, **{k: cyanite.display(r["cyanite_id"]).get(k) for k in ("track_id", "title", "artist")}}
            for r in rows]


def _cy(fn, *args):
    """把 Cyanite 的上游 HTTP 错误翻成干净的状态码，而不是 500 + 堆栈。"""
    try:
        return fn(*args)
    except requests.HTTPError as e:
        resp = e.response
        code = resp.status_code if resp is not None else 502
        raise HTTPException(code, f"Cyanite {code}（检查 id/参数，别带引号空格）")


@app.get("/cyanite/search", tags=["cyanite-debug"],
         summary="#2 文本搜索 · 自然语言 → 候选曲")
def cyanite_search(query: str, limit: int = 10):
    """官方端点 #2「Find Library Tracks based on a text prompt」。

    把一句自然语言（中英都行）打进音频空间，返回最匹配的曲目，按相关度降序。

    - **query**：自然语言描述，如 `lonely midnight train ride, restrained`
    - **limit**：返回条数（软上限，Cyanite 可能多给几条）

    返回每条带 `cyanite_id` / `score`（相关度）/ `title` / `artist`。
    若曲目不在数据包内，`title`/`artist` 会为空。
    """
    return _enrich(_cy(cyanite.search_by_prompt, query, limit))


@app.get("/cyanite/similar-single/{cyanite_id}", tags=["cyanite-debug"],
         summary="#3 单种子相似 · 一首曲 → 声学相似曲")
def cyanite_similar_single(cyanite_id: str, limit: int = 10):
    """官方端点 #3「Find Similar Library Tracks」（单种子）。

    给一首曲（`cyanite_id`，形如 `libtr_xxx`），返回声学上最相似的曲目，按相似度降序。
    这是 like 后做候选扩展用的调用。

    - **cyanite_id**：种子曲的 Cyanite id（别带引号/空格，会自动清理）
    - **limit**：返回条数

    返回每条带 `cyanite_id` / `score`（相似度）/ `title` / `artist`。
    """
    return _enrich(_cy(cyanite.find_similar, cyanite_id.strip().strip('"'), limit))


@app.get("/cyanite/tags/{cyanite_id}", tags=["cyanite-debug"],
         summary="#1 取标签 · 一首曲 → AI 模型标签")
def cyanite_tags(cyanite_id: str, models: str = "MainGenreV2,MoodSimpleV2,InstrumentsV2,BpmV2"):
    """官方端点 #1「Get inferred AI Models for a Library Track」（tagging）。

    返回某曲的 Cyanite 模型推断结果（流派 / 情绪 / 乐器 / BPM 等），
    用来支撑前端的「Why this track?」解释。

    - **cyanite_id**：曲目的 Cyanite id（别带引号/空格，会自动清理）
    - **models**：要取哪些模型，逗号分隔。默认 `MainGenreV2,MoodSimpleV2,InstrumentsV2,BpmV2`

    返回 Cyanite 原始 `{items:[...]}`，每项含该模型的 tags / scores。
    """
    ms = [m.strip() for m in models.split(",") if m.strip()]
    return _cy(cyanite.model_tags, cyanite_id.strip().strip('"'), ms)


@app.get("/cyanite/resolve-id/{track_id}", tags=["cyanite-debug"],
         summary="工具 · 数据包 track_id → cyanite_id + 展示信息")
def cyanite_resolve_id(track_id: str):
    """把数据包里的 Jamendo `track_id`（`data/tracks.csv` 里那列）换成 Cyanite id，
    顺带返回 `title` / `artist`。不碰网络，纯本地映射。

    - **track_id**：数据包的 Jamendo 曲目 id

    不在数据包内的 id 返回 404。
    """
    try:
        return cyanite.display(cyanite.to_cyanite(track_id.strip()))
    except KeyError:
        raise HTTPException(404, f"track_id {track_id!r} 不在数据包里")
