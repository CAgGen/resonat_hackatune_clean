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
import explanation_builder
import intent_agent
import memory
import rerank
import user_profiles

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
    profile = memory.feeling_injection(s["user_id"])   # 只注入「感觉」，不带历史曲风/搜索词
    s["query_card"] = intent_agent.compile_query_card(s["whiteboard_posts"], profile)


def _card(cyanite_id: str, score: float, source: str, track_id: str = "") -> dict:
    """统一的推荐卡。source ∈ {'free_text','similar','profile_semantic'}；score 是主信号分。
    track_id 来自 Cyanite 响应（{jamendoId}.mp3），直接透传给 display，不本地反查。"""
    d = cyanite.display(cyanite_id, track_id)
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


def _visible_card(s: dict, cyanite_id: str) -> dict:
    for card in s["visible_cards"]:
        if card["cyanite_id"] == cyanite_id or card["track_id"] == cyanite_id:
            return card
    raise SessionNotFound(cyanite_id)


def _remove_visible(s: dict, cyanite_id: str) -> None:
    s["visible_cards"] = [
        c for c in s["visible_cards"]
        if c["cyanite_id"] != cyanite_id and c["track_id"] != cyanite_id
    ]


def _replace_visible(s: dict, cyanite_id: str, fill: dict | None) -> None:
    """把被划走的卡原地换成回填卡：位置不变，可见顺序才稳定（点一首喜欢，
    旁边的歌不会跟着重排消失）。没回填则只删掉该卡。"""
    idx = next(
        (i for i, c in enumerate(s["visible_cards"])
         if c["cyanite_id"] == cyanite_id or c["track_id"] == cyanite_id),
        None,
    )
    if idx is None:
        return
    if fill is None:
        s["visible_cards"].pop(idx)
    else:
        s["visible_cards"][idx] = fill


def _record_like(s: dict, cyanite_id: str) -> None:
    # 只记 liked 种子；记忆（证据 + 画像）在一轮结束时统一落，见 finish_round。
    if cyanite_id not in s["liked_tracks"]:
        s["liked_tracks"].append(cyanite_id)


def _card_from_candidate(candidate: dict, source: str) -> dict | None:
    card = _card(candidate["cyanite_id"], candidate["final_score"], source, candidate.get("track_id", ""))
    card.update({
        "source_liked_track": candidate.get("source_liked_track"),
        "similar_score": candidate.get("similar_score"),
        "final_score": candidate.get("final_score"),
        "ranking_basis": candidate.get("ranking_basis"),
    })
    enriched = cyanite.enrich_meta([card])
    return enriched[0] if enriched else None


def _set_single_seed_pool(s: dict, cyanite_id: str) -> None:
    rows = cyanite.find_similar(cyanite_id, limit=config.SIMILAR_LIMIT)
    s["candidate_pool"] = [{
        "cyanite_id": r["cyanite_id"],
        "track_id": r.get("track_id", ""),
        "source_liked_track": cyanite_id,
        "similar_score": r["score"],
        "prompt_match_score": None,
        "status": "candidate",
    } for r in rows]
    s["pool_sig"] = tuple(s["liked_tracks"])


def _best_similar_refill(s: dict) -> dict | None:
    best = rerank.rank_refill_candidates(
        s["candidate_pool"],
        visible_ids=_visible_ids(s),
        disliked_ids=set(s["disliked_tracks"]) | set(s["liked_tracks"]),
    )
    if not best:
        return None
    s["candidate_pool"] = [p for p in s["candidate_pool"] if p["cyanite_id"] != best["cyanite_id"]]
    return _card_from_candidate(best, "similar")


def _profile_refill(s: dict) -> dict | None:
    profile_text = memory.feeling_injection(s["user_id"])   # 只用「感觉」做语义回填，不被旧曲风带跑
    query = (
        profile_text
        or s["query_card"].get("free_text_query")
        or s["query_card"].get("interpretation_plain")
        or _final_prompt(s)
    )
    rows = cyanite.search_by_prompt(query, limit=config.PROFILE_REFILL_LIMIT)
    excluded = _visible_ids(s) | set(s["disliked_tracks"]) | set(s["liked_tracks"])
    for row in rows:
        cid = row["cyanite_id"]
        if cid in excluded:
            continue
        card = _card(cid, row["score"], "profile_semantic", row.get("track_id", ""))
        card.update({
            "prompt_match_score": row["score"],
            "final_score": row["score"],
            "ranking_basis": "profile_semantic_search",
            "profile_query": query,
        })
        enriched = cyanite.enrich_meta([card])
        if enriched:
            return enriched[0]
    return None


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
        "cyanite_id": r["cyanite_id"], "track_id": r.get("track_id", ""),
        "source_liked_track": ",".join(s["liked_tracks"]),
        "similar_score": r["score"], "prompt_match_score": None, "status": "candidate"
    } for r in rows]
    s["pool_sig"] = sig


def _backfill(s: dict) -> dict | None:
    """dislike 留下的空位回填一首：先用 liked 种子搜出相似候选（只在此刻、只搜没搜过的种子），
    再挑 score 最高、未被踩、未在列表的那首；没有 liked 种子则用 freeText backlog 补位。"""
    if s["liked_tracks"]:
        _expand_pool(s)
        fill = _best_similar_refill(s)
        if fill:
            return fill
    if s["free_text_backlog"]:
        return s["free_text_backlog"].pop(0)  # backlog 已在 confirm 里 enrich 过
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
        "round_finished": False,  # 「完成本轮」是否已落记忆（幂等防重复写）
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
    """③ 过确认门 → 此刻才跑 search 阶段（tool calling）拿检索参数 → freeTextSearch
       → 填首批推荐 + backlog。不做 similar 粗扩展。"""
    s = _get(session_id)
    args = intent_agent.search_args(s["whiteboard_posts"], memory.feeling_injection(s["user_id"]))
    s["query_card"]["free_text_query"] = args["query"]
    s["query_card"]["metadata_filter"] = args["metadata_filter"]
    results = cyanite.search_by_prompt(args["query"], limit=config.SEARCH_LIMIT,
                                       metadata_filter=args["metadata_filter"])
    cards = cyanite.enrich_meta([_card(r["cyanite_id"], r["score"], "free_text", r.get("track_id", "")) for r in results])
    s["visible_cards"] = cards[:config.VISIBLE_N]
    s["free_text_backlog"] = cards[config.VISIBLE_N:]
    _inject_surprise(s)  # 惊喜位只在本轮第一批出现；后续 feedback 回填不再加
    return s


def _inject_surprise(s: dict) -> None:
    """惊喜位：忠于本轮需求、刻意偏离画像的一张卡，source='surprise'。只在 confirm 调用。
    没画像/无 key/检索失败一律静默跳过，绝不拖垮主推荐。被 like 后它进 liked 种子，
    之后的解释自然走 similar（两曲为何相似）路径——不再是惊喜文案。"""
    profile = memory.read_memory(s["user_id"])
    try:
        args = intent_agent.surprise_args(s["whiteboard_posts"], profile)
        if not args:
            return
        seen = {c["cyanite_id"] for c in s["visible_cards"]} | {c["cyanite_id"] for c in s["free_text_backlog"]}
        results = cyanite.search_by_prompt(args["query"], limit=config.SEARCH_LIMIT,
                                           metadata_filter=args["metadata_filter"])
        pick = next((r for r in results if r["cyanite_id"] not in seen), None)
        if not pick:
            return
    except Exception:
        return
    card = cyanite.enrich_meta([_card(pick["cyanite_id"], pick["score"], "surprise", pick.get("track_id", ""))])[0]
    s["visible_cards"].insert(min(3, len(s["visible_cards"])), card)  # 沿用「第4张」惊喜位
    if len(s["visible_cards"]) > config.VISIBLE_N:                    # 挤出的普通卡退回 backlog
        s["free_text_backlog"].insert(0, s["visible_cards"].pop())


def feedback(session_id: str, track_id: str, verdict: str, mode: str = "normal") -> dict:
    """⑤ normal like → 记 liked + 划走 + 用该曲相似回填；
       anti_addiction like → 只记 liked，不动列表；
       dislike → 移除该曲，普通模式按 liked 相似回填，防沉迷按用户画像语义回填。
       记忆不在此落——一轮结束（finish_round）才统一写。"""
    s = _get(session_id)
    card = _visible_card(s, track_id)
    cid = card["cyanite_id"]
    if verdict == "like":
        _record_like(s, cid)
        if mode != "anti_addiction":
            _set_single_seed_pool(s, cid)               # 单种子：只用刚点的这首搜相似
            fill = _best_similar_refill(s)
            if fill is None and s["free_text_backlog"]:  # 相似搜不到 → 兜底 backlog，位别空
                fill = s["free_text_backlog"].pop(0)
            _replace_visible(s, cid, fill)               # 原地换：顺序稳定，旁卡不动
    elif verdict == "dislike":
        s["disliked_tracks"][cid] = True
        fill = _profile_refill(s) if mode == "anti_addiction" else _backfill(s)
        _replace_visible(s, cid, fill)
    return s


def finish_round(session_id: str) -> dict:
    """⑦ 用户点「完成本轮」→ 把这一轮（当前 prompt + 选的歌）落记忆：
    证据追加（每首歌带它的「感觉」标签）+ 画像重写。没 like 则只读不写。
    幂等：重复点击不会重复写入。"""
    s = _get(session_id)
    if s["liked_tracks"] and not s["round_finished"]:
        memory.append_evidence(s["user_id"], _final_prompt(s), s["liked_tracks"])
        memory.rewrite_memory(s["user_id"])
        s["round_finished"] = True
    return {"memory_md": memory.read_memory(s["user_id"]), "liked": s["liked_tracks"]}


def your_sound(user_id: str) -> str:
    """⑧ 记忆摘要，演'越用越准'。"""
    return memory.read_memory(user_id)


def sounds_like_you(user_id: str) -> dict:
    """⑧b 「听起来像你」：把长期画像忠实翻成检索词，搜出「AI 眼中的你本人」的一小串候选。
    前端逐张播放，不喜欢就翻下一张，翻完即止。
    没画像/无 key/检索失败一律静默返回 cards=[]，画像照常展示。"""
    profile = memory.read_memory(user_id)
    cards = []
    try:
        args = intent_agent.sounds_like_you_args(profile)
        if args:
            results = cyanite.search_by_prompt(args["query"], limit=config.SEARCH_LIMIT)
            top = results[: config.SOUNDS_LIKE_YOU_LIMIT]
            if top:
                cards = cyanite.enrich_meta(
                    [_card(r["cyanite_id"], r["score"], "sounds_like_you", r.get("track_id", "")) for r in top]
                )
    except Exception:
        pass
    return {"cards": cards, "memory_md": profile}


def explain_sounds_like_you(user_id: str, cyanite_id: str) -> dict:
    """Why this track IS the user — based purely on long-term taste profile."""
    profile_md = memory.read_memory(user_id)
    track_tags = cyanite.model_tags(cyanite_id, config.EXPLAIN_TAG_MODELS)
    display = cyanite.display(cyanite_id, "")
    return explanation_builder.build_sounds_like_you_explanation(profile_md, display, track_tags)


def explain(session_id: str, track_id: str) -> dict:
    """生成 Why this track：当前意图 + 用户画像 + Cyanite tags + 可选历史相似例子。"""
    s = _get(session_id)
    card = _visible_card(s, track_id)
    cyanite_id = card["cyanite_id"]
    profile_md = memory.read_memory(s["user_id"])
    evidence_md = memory.read_evidence(s["user_id"])
    provided_likes = user_profiles.liked_cyanite_ids(s["user_id"])
    recommended_tags = cyanite.model_tags(cyanite_id, config.EXPLAIN_TAG_MODELS)
    similar_rows = cyanite.find_similar(cyanite_id, limit=config.EXPLAIN_SIMILAR_LIMIT)
    display_by_id = {row["cyanite_id"]: cyanite.display(row["cyanite_id"], row.get("track_id", ""))
                     for row in similar_rows}
    historical_candidates = explanation_builder.build_historical_candidates_from_similar_rows(
        evidence_md,
        similar_rows,
        display_by_id=display_by_id,
        liked_track_ids=provided_likes,
    )
    recommendation_meta = {
        "source": card.get("source"),
        "score": card.get("score"),
        "ranking_basis": card.get("ranking_basis") or "visible_card_score",
    }
    for field in ("source_liked_track", "similar_score", "final_score", "prompt_match_score", "profile_query"):
        if card.get(field) is not None:
            recommendation_meta[field] = card[field]
    explanation_example = explanation_builder.select_explanation_example(
        s["liked_tracks"],
        recommendation_meta,
        historical_candidates=historical_candidates,
    )
    if explanation_example:
        display = cyanite.display(explanation_example["track_id"])
        # 种子曲（前面那首 liked）不在数据包时 title/artist 为空，会让解释退化成 "(seed song)"。
        # 拿 track_id 走和其它曲一样的 Jamendo 补全，取回真实歌名/作者再填进解释。
        if not display.get("title") and display.get("track_id"):
            enriched = cyanite.enrich_meta([display])
            if enriched:
                display = enriched[0]
        for field in ("title", "artist"):
            if display.get(field):
                explanation_example[field] = display[field]
    liked_tags = {}
    if explanation_example:
        liked_tags = cyanite.model_tags(explanation_example["track_id"], config.EXPLAIN_TAG_MODELS)
    result = explanation_builder.build_explanation(
        profile_md,
        s["query_card"],
        liked_tags,
        recommended_tags,
        recommendation_meta,
        explanation_example,
        cyanite.display(cyanite_id, card.get("track_id", "")),
    )
    # 角标：主导情绪随时间的时间轴，时间戳直接来自 Cyanite segments（已在 recommended_tags 里，零额外请求）。
    result["segments"] = explanation_builder.mood_timeline(recommended_tags)
    return result
