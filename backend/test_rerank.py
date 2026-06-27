import rerank


def test_rank_refill_candidates_assumes_higher_similar_score_is_better():
    candidates = [
        {"cyanite_id": "low", "similar_score": 0.2, "source_liked_track": "seed"},
        {"cyanite_id": "high", "similar_score": 0.9, "source_liked_track": "seed"},
    ]

    best = rerank.rank_refill_candidates(candidates)

    assert best["cyanite_id"] == "high"
    assert best["final_score"] == 0.9
    assert best["ranking_basis"] == "similar_score_fallback"


def test_rank_refill_candidates_filters_visible_and_disliked_tracks():
    candidates = [
        {"cyanite_id": "visible", "similar_score": 0.99, "source_liked_track": "seed"},
        {"cyanite_id": "disliked", "similar_score": 0.98, "source_liked_track": "seed"},
        {"cyanite_id": "usable", "similar_score": 0.7, "source_liked_track": "seed"},
    ]

    best = rerank.rank_refill_candidates(
        candidates,
        visible_ids={"visible"},
        disliked_ids={"disliked"},
    )

    assert best["cyanite_id"] == "usable"
    assert best["final_score"] == 0.7


def test_rank_refill_candidates_treats_missing_similar_score_as_zero():
    candidates = [
        {"cyanite_id": "missing", "source_liked_track": "seed"},
        {"cyanite_id": "scored", "similar_score": 0.1, "source_liked_track": "seed"},
    ]

    best = rerank.rank_refill_candidates(candidates)

    assert best["cyanite_id"] == "scored"


def test_rank_refill_candidates_returns_none_when_no_usable_candidates():
    candidates = [{"cyanite_id": "only", "similar_score": 0.8, "source_liked_track": "seed"}]

    assert rerank.rank_refill_candidates(candidates, visible_ids={"only"}) is None
