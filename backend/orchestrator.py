"""编排核心 · 会话状态机（你负责）。

把意图编译 / Cyanite 检索 / 记忆 三个接缝串成 PRD 的主循环：
  确认门 → freeText 首批 → like 建候选池 → dislike 移除+回填 → 薄重排。

会话状态全在内存 dict，进程退出即丢，绝不落盘（PRD §3）。
本模块不直接碰网络/LLM/文件——只调接缝模块，所以测试 monkeypatch 接缝即可离线跑。
"""
from __future__ import annotations
import datetime as _dt
import uuid

import config
import cyanite
import intent_compiler
import memory
import rerank

# 会话存储：内存 dict
SESSIONS: dict[str, dict] = {}


class SessionNotFound(KeyError):
    """未知 session_id。app.py 把它翻成 404。"""


# ─────────────────────────── 内部辅助 ───────────────────────────
def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _new_post(role: str, text: str) -> dict:
    return {"id": uuid.uuid4().hex[:8], "role": role, "text": text, "created_at": _now()}


def _get(session_id: str) -> dict:
    s = SESSIONS.get(session_id)
    if s is None:
        raise SessionNotFound(session_id)
    return s


def _recompile(s: dict) -> None:
    """白板有变就重编 Query Card，带上该用户的记忆画像。"""
    profile = memory.read_memory(s["user_id"])
    s["query_card"] = intent_compiler.compile_query_card(s["whiteboard_posts"], profile)


def _card(cyanite_id: str, score: float, source: str) -> dict:
    """统一的推荐卡。source ∈ {'free_text','similar'}；score 是主信号分。"""
    d = cyanite.display(cyanite_id)
    return {
        "track_id": d.get("track_id", ""),
        "cyanite_id": cyanite_id,
        "title": d.get("title", ""),
        "artist": d.get("artist", ""),
        "source": source,
        "score": score,
        "why": f"匹配你确认过的需求（score {score:.2f}）。",  # 占位，队友接标签后做真 Why this
    }


def _final_prompt(s: dict) -> str:
    """记忆的根基：用户最后确认的那版白板上下文（initial + 全部 follow-up）。
    确认门之后才会 like，所以此刻白板即最终意图。"""
    return " / ".join(p["text"] for p in s["whiteboard_posts"])


def _visible_ids(s: dict) -> set[str]:
    return {c["cyanite_id"] for c in s["visible_cards"]}


def _expand_pool(s: dict) -> None:
    """按当前 liked 集合搜相似候选，重建 candidate_pool。
    - liked 集合没变 → 直接复用，不重复打 API。
    - liked ≥ 2 → 多种子 `find_similar_multi`（求公共声音区）；正好 1 个 → 单种子 `find_similar`。"""
    sig = tuple(s["liked_tracks"])
    if not sig or sig == s["pool_sig"]:
        return
    if len(s["liked_tracks"]) >= 2:
        rows = cyanite.find_similar_multi(s["liked_tracks"], limit=config.SIMILAR_LIMIT)
    else:
        rows = cyanite.find_similar(s["liked_tracks"][0], limit=config.SIMILAR_LIMIT)
    s["candidate_pool"] = [{
        "cyanite_id": r["cyanite_id"], "source_liked_track": ",".join(s["liked_tracks"]),
        "similar_score": r["score"], "prompt_match_score": None, "status": "candidate"
    } for r in rows]
    s["pool_sig"] = sig


def _backfill(s: dict) -> dict | None:
    """dislike 留下的空位回填一首：先用 liked 种子搜出相似候选（只在此刻、只搜没搜过的种子），
    再挑 score 最高、未被踩、未在列表的那首；没有 liked 种子则用 freeText backlog 补位。"""
    if s["liked_tracks"]:
        _expand_pool(s)
        best = rerank.rank_refill_candidates(
            s["candidate_pool"],
            visible_ids=_visible_ids(s),
            disliked_ids=set(s["disliked_tracks"]),
        )
        if best:
            s["candidate_pool"] = [p for p in s["candidate_pool"] if p["cyanite_id"] != best["cyanite_id"]]
            return _card(best["cyanite_id"], best["final_score"], "similar")
    if s["free_text_backlog"]:
        return s["free_text_backlog"].pop(0)
    return None


# ─────────────────────────── 编排动作 ───────────────────────────
def start_session(user_id: str, text: str) -> dict:
    """① 首条 prompt 上白板 → 编译 Query Card。停在确认门，不检索。"""
    sid = uuid.uuid4().hex[:12]
    s = {
        "id": sid, "user_id": user_id,
        "whiteboard_posts": [_new_post("initial_prompt", text)],
        "query_card": {},
        "visible_cards": [],      # 当前右下推荐列表
        "free_text_backlog": [],  # freeText 召回里尚未展示的（liked 为空时的回填来源）
        "liked_tracks": [],       # 用户 like 的曲 = dislike 时 similarById 的种子
        "pool_sig": None,         # 上次建池用的 liked 集合签名（变了才重搜）
        "candidate_pool": [],     # dislike 时对 liked 种子搜出的相似候选
        "disliked_tracks": {},    # 明确踩过的
    }
    _recompile(s)
    SESSIONS[sid] = s
    return s


def add_follow_up(session_id: str, text: str) -> dict:
    """② 不可行时往白板追加 follow-up，重编 Query Card。仍停在确认门。"""
    s = _get(session_id)
    s["whiteboard_posts"].append(_new_post("follow_up", text))
    _recompile(s)
    return s


def confirm(session_id: str) -> dict:
    """③ 过确认门 → 只跑 freeTextSearch → 填首批推荐 + backlog。不做 similar 粗扩展。"""
    s = _get(session_id)
    results = cyanite.search_by_prompt(s["query_card"]["free_text_query"], limit=config.SEARCH_LIMIT)
    cards = [_card(r["cyanite_id"], r["score"], "free_text") for r in results]
    s["visible_cards"] = cards[:config.VISIBLE_N]
    s["free_text_backlog"] = cards[config.VISIBLE_N:]
    return s


def feedback(session_id: str, track_id: str, verdict: str) -> dict:
    """⑤ like → 只记为 liked 种子 + 落记忆，不搜索、不动列表；
       dislike → 移除该曲 → 用 liked 种子搜相似回填一格。最后薄重排。"""
    s = _get(session_id)
    cid = track_id  # 推荐卡里 track_id 暴露的就是 cyanite_id 来源；见 _card
    if verdict == "like":
        if cid not in s["liked_tracks"]:
            s["liked_tracks"].append(cid)
        # ⑦ 落记忆：证据追加（以最后确认的 prompt 为根基）+ 画像重写（接缝在 memory 模块）
        memory.append_evidence(s["user_id"], _final_prompt(s), [cid])
        memory.rewrite_memory(s["user_id"])
        # 不跑任何检索，visible_cards 不动
    elif verdict == "dislike":
        s["disliked_tracks"][cid] = True
        s["visible_cards"] = [c for c in s["visible_cards"] if c["cyanite_id"] != cid]
        fill = _backfill(s)  # similarById 只在这里、由 dislike 触发
        if fill:
            s["visible_cards"].append(fill)
    s["visible_cards"] = rerank.thin_rerank(s["visible_cards"])  # ⑥
    return s


def your_sound(user_id: str) -> str:
    """⑧ 记忆摘要，演'越用越准'。"""
    return memory.read_memory(user_id)
