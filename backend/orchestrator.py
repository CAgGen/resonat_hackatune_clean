"""Orchestration core · session state machine.

Connects intent compilation / Cyanite retrieval / memory seams into the PRD main loop:
  confirmation gate -> first freeText batch -> like builds candidate pool -> dislike removes + refills -> light rerank.

Session state is entirely in an in-memory dict and disappears when the process exits; never persisted (PRD §3).
This module does not directly touch network/LLM/files. It only calls seam modules, so tests can monkeypatch
those seams and run offline.
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

# Session storage: in-memory dict.
SESSIONS: dict[str, dict] = {}


class SessionNotFound(KeyError):
    """Unknown session_id. app.py translates this into 404."""


# ─────────────────────────── Internal helpers ───────────────────────────
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
    """Recompile the Query Card whenever the whiteboard changes, including this user's memory profile."""
    profile = memory.feeling_injection(s["user_id"])   # Inject only feelings, without historical genres/search terms.
    s["query_card"] = intent_agent.compile_query_card(s["whiteboard_posts"], profile)


def _card(cyanite_id: str, score: float, source: str, track_id: str = "") -> dict:
    """Unified recommendation card. source is in {'free_text','similar','profile_semantic'}; score is the main signal.
    track_id comes from the Cyanite response ({jamendoId}.mp3) and is passed directly to display, with no local reverse lookup."""
    d = cyanite.display(cyanite_id, track_id)
    return {
        "track_id": d.get("track_id", ""),
        "cyanite_id": cyanite_id,
        "title": d.get("title", ""),
        "artist": d.get("artist", ""),
        "source": source,
        "score": score,
        "why": f"Matches your confirmed request (score {score:.2f}).",  # Placeholder until tag-backed Why this is attached.
    }


def _final_prompt(s: dict) -> str:
    """Memory's foundation: the final confirmed whiteboard context (initial + all follow-ups).
    Likes only happen after the confirmation gate, so the whiteboard is the final intent at this moment."""
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
    """Replace the swiped-away card in place with a refill card.
    Position stays fixed so visible order is stable (liking one song does not make neighboring songs reorder away).
    If there is no refill, only remove that card."""
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
    # Only record liked seeds; memory (evidence + profile) is persisted together at round end, see finish_round.
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
    profile_text = memory.feeling_injection(s["user_id"])   # Use only feelings for semantic refill, not stale genres.
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
    """Search similar candidates from the current liked set and rebuild candidate_pool.
    - liked set unchanged -> reuse directly; do not hit the API again.
    - liked >= 2 -> multi-seed `find_similar_multi` (shared sound area); exactly 1 -> single-seed `find_similar`."""
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
    """Refill the empty slot left by a dislike.
    First search similar candidates from liked seeds (only now, only for seeds not already searched), then choose
    the highest-score track that is not disliked and not visible. Without liked seeds, refill from freeText backlog."""
    if s["liked_tracks"]:
        _expand_pool(s)
        fill = _best_similar_refill(s)
        if fill:
            return fill
    if s["free_text_backlog"]:
        return s["free_text_backlog"].pop(0)  # backlog was already enriched in confirm.
    return None


# ─────────────────────────── Orchestration actions ───────────────────────────
def start_session(user_id: str, text: str) -> dict:
    """1. Put the first prompt on the whiteboard -> compile Query Card. Stop at the confirmation gate; no retrieval."""
    sid = uuid.uuid4().hex[:12]
    s = {
        "id": sid, "user_id": user_id,
        "whiteboard_posts": [_new_post("initial_prompt", text)],
        "query_card": {},
        "visible_cards": [],      # Current recommendation list.
        "free_text_backlog": [],  # Unshown freeText recalls (refill source when liked is empty).
        "liked_tracks": [],       # User-liked tracks = similarById seeds on dislike.
        "pool_sig": None,         # liked-set signature used for the previous pool build (re-search only when changed).
        "candidate_pool": [],     # Similar candidates searched from liked seeds on dislike.
        "disliked_tracks": {},    # Explicitly disliked tracks.
        "round_finished": False,  # Whether "finish round" has persisted memory (idempotency guard).
    }
    _recompile(s)
    SESSIONS[sid] = s
    return s


def add_follow_up(session_id: str, text: str) -> dict:
    """2. Append follow-up to the whiteboard when the interpretation is not viable, then recompile Query Card. Still at the gate."""
    s = _get(session_id)
    s["whiteboard_posts"].append(_new_post("follow_up", text))
    _recompile(s)
    return s


def confirm(session_id: str) -> dict:
    """3. Pass the confirmation gate -> only now run search stage (tool calling) for retrieval args -> freeTextSearch
       -> fill first recommendation batch + backlog. No broad similar expansion."""
    s = _get(session_id)
    args = intent_agent.search_args(s["whiteboard_posts"], memory.feeling_injection(s["user_id"]))
    s["query_card"]["free_text_query"] = args["query"]
    s["query_card"]["metadata_filter"] = args["metadata_filter"]
    results = cyanite.search_by_prompt(args["query"], limit=config.SEARCH_LIMIT,
                                       metadata_filter=args["metadata_filter"])
    cards = cyanite.enrich_meta([_card(r["cyanite_id"], r["score"], "free_text", r.get("track_id", "")) for r in results])
    s["visible_cards"] = cards[:config.VISIBLE_N]
    s["free_text_backlog"] = cards[config.VISIBLE_N:]
    _inject_surprise(s)  # Surprise slot only appears in the first batch of this round; later feedback refills do not add it.
    return s


def _inject_surprise(s: dict) -> None:
    """Surprise slot: one source='surprise' card that fits this round while deliberately offsetting the profile.
    Called only from confirm. Without profile/key, or on retrieval failure, silently skip so primary recommendations survive.
    If liked, it becomes a liked seed; later explanations naturally use the similar path, not surprise copy."""
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
    s["visible_cards"].insert(min(3, len(s["visible_cards"])), card)  # Keep the "4th card" surprise slot.
    if len(s["visible_cards"]) > config.VISIBLE_N:                    # Return the displaced normal card to backlog.
        s["free_text_backlog"].insert(0, s["visible_cards"].pop())


def feedback(session_id: str, track_id: str, verdict: str, mode: str = "normal") -> dict:
    """5. normal like -> record liked + swipe away + refill with similarity from that track;
       anti_addiction like -> only record liked, list stays unchanged;
       dislike -> remove that track; normal mode refills by liked similarity, anti-addiction mode refills by profile semantics.
       Memory is not persisted here; finish_round writes it all at round end."""
    s = _get(session_id)
    card = _visible_card(s, track_id)
    cid = card["cyanite_id"]
    if verdict == "like":
        _record_like(s, cid)
        if mode != "anti_addiction":
            _set_single_seed_pool(s, cid)               # Single seed: search similarity only from the just-clicked track.
            fill = _best_similar_refill(s)
            if fill is None and s["free_text_backlog"]:  # No similar result -> fallback backlog so the slot is not empty.
                fill = s["free_text_backlog"].pop(0)
            _replace_visible(s, cid, fill)               # Replace in place: stable order, neighboring cards do not move.
    elif verdict == "dislike":
        s["disliked_tracks"][cid] = True
        fill = _profile_refill(s) if mode == "anti_addiction" else _backfill(s)
        _replace_visible(s, cid, fill)
    return s


def finish_round(session_id: str) -> dict:
    """7. User clicks "finish this round" -> persist this round (current prompt + selected songs) to memory:
    append evidence (each song with its feel tags) + rewrite profile. With no likes, only read.
    Idempotent: repeated clicks do not duplicate writes."""
    s = _get(session_id)
    if s["liked_tracks"] and not s["round_finished"]:
        memory.append_evidence(s["user_id"], _final_prompt(s), s["liked_tracks"])
        memory.rewrite_memory(s["user_id"])
        s["round_finished"] = True
    return {"memory_md": memory.read_memory(s["user_id"]), "liked": s["liked_tracks"]}


def your_sound(user_id: str) -> str:
    """8. Memory summary, showing that recommendations improve with use."""
    return memory.read_memory(user_id)


def sounds_like_you(user_id: str) -> dict:
    """8b. "Sounds like you": faithfully translate the long-term profile into a search query and find a short
    candidate list for "you through the AI's eyes". Frontend plays them one by one; dislike flips to the next
    candidate and stops when exhausted. Without profile/key, or on retrieval failure, silently return cards=[];
    the profile still renders normally."""
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
    """Generate Why this track: current intent + user profile + Cyanite tags + optional historical similarity example."""
    s = _get(session_id)
    card = _visible_card(s, track_id)
    cyanite_id = card["cyanite_id"]
    profile_md = memory.read_memory(s["user_id"])
    evidence_md = memory.read_evidence(s["user_id"])
    provided_likes = user_profiles.liked_cyanite_ids(s["user_id"])
    recommended_tags = cyanite.model_tags(cyanite_id, config.EXPLAIN_TAG_MODELS)
    try:
        similar_rows = cyanite.find_similar(cyanite_id, limit=config.EXPLAIN_SIMILAR_LIMIT)
    except Exception:
        similar_rows = []      
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
        # If the seed track (the previous liked song) is outside the data pack, title/artist are empty and
        # explanations degrade to "(seed song)". Use track_id to fill it through Jamendo like other tracks,
        # then pass the real title/artist into the explanation.
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
    # Markers: dominant mood-over-time timeline. Timestamps come directly from Cyanite segments
    # already in recommended_tags, with zero extra requests.
    result["segments"] = explanation_builder.mood_timeline(recommended_tags)
    return result
