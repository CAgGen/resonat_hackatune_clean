"""Orchestration · refill candidate selection. Pick the most similar track by Cyanite similar_score."""
from __future__ import annotations


def rank_refill_candidates(candidates: list[dict],
                           visible_ids: set[str] | None = None,
                           disliked_ids: set[str] | None = None) -> dict | None:
    """Pick the best refill candidate.

    Assumption for the current Cyanite similarity API: higher similar_score means
    more similar. The sponsor API does not expose track+prompt scoring, so the
    first version uses similar_score as the final decision score.
    """
    visible_ids = visible_ids or set()
    disliked_ids = disliked_ids or set()
    usable = []
    for candidate in candidates:
        cid = candidate.get("cyanite_id")
        if cid in visible_ids or cid in disliked_ids:
            continue
        ranked = dict(candidate)
        ranked["final_score"] = float(ranked.get("similar_score") or 0.0)
        ranked["ranking_basis"] = "similar_score_fallback"
        usable.append(ranked)
    if not usable:
        return None
    return max(usable, key=lambda c: c["final_score"])
