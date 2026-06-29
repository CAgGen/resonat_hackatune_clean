import json

import config
import explanation_builder


QUERY_CARD = {
    "interpretation_plain": "Restrained night-train music with minimal vocals.",
    "free_text_query": "lonely night train restrained low energy minimal vocals",
}

LIKED_TAGS = {
    "items": [
        {"version": "MoodSimpleV2", "tags": ["calm", "dark"], "scores": {"calm": 0.88, "dark": 0.72}},
        {"version": "InstrumentsV2", "tags": ["synth", "piano"], "scores": {"synth": 0.79, "piano": 0.61}},
    ]
}

RECOMMENDED_TAGS = {
    "items": [
        {"version": "MoodSimpleV2", "tags": ["calm", "sad"], "scores": {"calm": 0.82, "sad": 0.66}},
        {"version": "BpmV2", "tag": 76},
        {"version": "AutoDescriptionV2", "description": "A soft, restrained instrumental cue."},
    ]
}

META = {
    "source_liked_track": "liked_123",
    "similar_score": 0.91,
    "final_score": 0.91,
    "ranking_basis": "similar_score_fallback",
}

EXAMPLE = {
    "track_id": "liked_123",
    "example_type": "session_source",
    "similar_score": 0.91,
    "selection_basis": "source_liked_track",
}

DISPLAY_EXAMPLE = {
    **EXAMPLE,
    "title": "73rd Moon",
    "artist": "Reno Project",
}

RECOMMENDED_TRACK = {
    "track_id": "161536",
    "cyanite_id": "libtr_afterwork",
    "title": "Afterwork",
    "artist": "Reno Project",
}


def test_select_explanation_example_uses_source_liked_track_above_threshold():
    example = explanation_builder.select_explanation_example(
        liked_tracks=["liked_000", "liked_123"],
        recommendation_meta=META,
    )

    assert example == EXAMPLE


def test_extract_liked_track_ids_from_evidence_preserves_recent_order_without_duplicates():
    evidence_md = """# evidence · demo

## Feedback log
- "night drive" -> liked hist_1, hist_2   (2026-06-27T20:00:00)
- "quiet focus" -> liked hist_2, hist_3   (2026-06-27T21:00:00)
"""

    assert explanation_builder.extract_liked_track_ids_from_evidence(evidence_md) == [
        "hist_3",
        "hist_2",
        "hist_1",
    ]


def test_select_explanation_example_uses_historical_like_when_no_session_source():
    historical_candidates = [
        {"track_id": "hist_1", "similar_score": 0.7},
        {"track_id": "hist_2", "similar_score": 0.89, "title": "Old Light", "artist": "Past Self"},
    ]

    example = explanation_builder.select_explanation_example(
        liked_tracks=[],
        recommendation_meta={"ranking_basis": "free_text"},
        historical_candidates=historical_candidates,
    )

    assert example == {
        "track_id": "hist_2",
        "example_type": "historical_like",
        "similar_score": 0.89,
        "selection_basis": "historical_similarity",
        "title": "Old Light",
        "artist": "Past Self",
    }




def test_build_historical_candidates_from_similar_rows_keeps_only_historical_likes():
    evidence_md = """# evidence · demo

## Feedback log
- "night drive" -> liked hist_low, hist_high   (2026-06-27T20:00:00)
"""
    similar_rows = [
        {"cyanite_id": "not_liked", "score": 0.99},
        {"cyanite_id": "hist_low", "score": 0.82},
        {"cyanite_id": "hist_high", "score": 0.91},
    ]
    display_by_id = {
        "hist_high": {"title": "Old Light", "artist": "Past Self"},
        "hist_low": {"title": "Dim Track", "artist": "Past Self"},
    }

    candidates = explanation_builder.build_historical_candidates_from_similar_rows(
        evidence_md,
        similar_rows,
        display_by_id=display_by_id,
    )

    assert candidates == [
        {
            "track_id": "hist_high",
            "similar_score": 0.91,
            "selection_basis": "historical_similar_by_id_intersection",
            "title": "Old Light",
            "artist": "Past Self",
        },
        {
            "track_id": "hist_low",
            "similar_score": 0.82,
            "selection_basis": "historical_similar_by_id_intersection",
            "title": "Dim Track",
            "artist": "Past Self",
        },
    ]


def test_build_historical_candidates_from_similar_rows_includes_provided_user_likes():
    similar_rows = [
        {"cyanite_id": "provided_low", "score": 0.81},
        {"cyanite_id": "provided_high", "score": 0.92},
        {"cyanite_id": "not_liked", "score": 0.99},
    ]

    candidates = explanation_builder.build_historical_candidates_from_similar_rows(
        "",
        similar_rows,
        liked_track_ids=["provided_low", "provided_high"],
    )

    assert candidates == [
        {
            "track_id": "provided_high",
            "similar_score": 0.92,
            "selection_basis": "historical_similar_by_id_intersection",
        },
        {
            "track_id": "provided_low",
            "similar_score": 0.81,
            "selection_basis": "historical_similar_by_id_intersection",
        },
    ]


def test_build_historical_candidates_from_similar_rows_supports_id_aliases_and_limit():
    evidence_md = """# evidence · demo

## Feedback log
- "quiet focus" -> liked jam_1, libtr_2   (2026-06-27T21:00:00)
"""
    similar_rows = [
        {"track_id": "jam_1", "score": 0.84},
        {"id": "libtr_2", "score": 0.9},
    ]

    candidates = explanation_builder.build_historical_candidates_from_similar_rows(
        evidence_md,
        similar_rows,
        limit=1,
    )

    assert candidates == [{
        "track_id": "libtr_2",
        "similar_score": 0.9,
        "selection_basis": "historical_similar_by_id_intersection",
    }]


def test_select_explanation_example_prefers_session_source_over_historical_like():
    example = explanation_builder.select_explanation_example(
        liked_tracks=["liked_123"],
        recommendation_meta=META,
        historical_candidates=[{"track_id": "hist_2", "similar_score": 0.99}],
    )

    assert example["track_id"] == "liked_123"
    assert example["example_type"] == "session_source"


def test_fallback_explanation_is_grounded_and_english(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)

    result = explanation_builder.build_explanation(
        "The listener likes calm, dark, low-energy music.",
        QUERY_CARD,
        LIKED_TAGS,
        RECOMMENDED_TAGS,
        META,
        DISPLAY_EXAMPLE,
        RECOMMENDED_TRACK,
    )

    assert "fits your current search" in result["why_text"]
    assert "73rd Moon by Reno Project" in result["why_text"]
    assert "Cyanite acoustic similarity" in result["why_text"]
    assert result["evidence"][0]["source"] == "ranking"


def test_fallback_prompt_pool_track_does_not_claim_similarity(monkeypatch):
    # free_text cards without source_liked_track (first batch / backlog fallback) must not claim liked-track similarity.
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)
    result = explanation_builder.build_explanation(
        "The listener likes calm, dark, low-energy music.",
        QUERY_CARD,
        LIKED_TAGS,
        RECOMMENDED_TAGS,
        {"source": "free_text", "score": 0.8, "ranking_basis": "visible_card_score"},
        None,
        RECOMMENDED_TRACK,
    )
    assert "Cyanite acoustic similarity" not in result["why_text"]
    assert "near your liked tracks" not in result["why_text"]
    assert "your search brief" in result["why_text"]


def test_similar_source_forces_seed_title_and_artist_when_llm_omits_it(monkeypatch):
    # similarById cards: if the model omits the seed title, deterministic fallback must prepend "title by artist".
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test", raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output": [{"content": [{"type": "output_text", "text": json.dumps({
                "why_text": "This track shares calm, dark moods with a track you liked.",
                "evidence": [{"source": "ranking", "detail": "score 0.91"}],
            })}]}]}

    monkeypatch.setattr(explanation_builder.requests, "post",
                        lambda *a, **k: FakeResponse())

    result = explanation_builder.build_explanation(
        "The listener likes calm, dark, low-energy music.",
        QUERY_CARD,
        LIKED_TAGS,
        RECOMMENDED_TAGS,
        {**META, "source": "similar"},
        DISPLAY_EXAMPLE,
        RECOMMENDED_TRACK,
    )

    assert "73rd Moon" in result["why_text"]
    assert "Reno Project" in result["why_text"]
    assert result["why_text"].startswith("Because you liked 73rd Moon by Reno Project")


def test_similar_source_does_not_duplicate_seed_when_llm_already_named_it(monkeypatch):
    # Do not duplicate the prepended sentence when the model already named the seed song.
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test", raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output": [{"content": [{"type": "output_text", "text": json.dumps({
                "why_text": "Because you liked 73rd Moon by Reno Project, we found this calm, dark match.",
                "evidence": [{"source": "ranking", "detail": "score 0.91"}],
            })}]}]}

    monkeypatch.setattr(explanation_builder.requests, "post",
                        lambda *a, **k: FakeResponse())

    result = explanation_builder.build_explanation(
        "The listener likes calm, dark, low-energy music.",
        QUERY_CARD,
        LIKED_TAGS,
        RECOMMENDED_TAGS,
        {**META, "source": "similar"},
        DISPLAY_EXAMPLE,
        RECOMMENDED_TRACK,
    )

    assert result["why_text"].count("73rd Moon") == 1


def test_openai_explanation_request_contains_grounding_inputs(monkeypatch):
    captured = {}
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-test", raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            output_text = json.dumps({
                "why_text": "This track fits because it shares calm, dark moods with your liked track while matching the restrained night-train prompt.",
                "evidence": [
                    {"source": "recommended_track_tags", "detail": "MoodSimpleV2 tags include calm and sad."},
                    {"source": "ranking", "detail": "Ranked by Cyanite acoustic similarity score 0.91."},
                ],
            })
            return {"output": [{"content": [{"type": "output_text", "text": output_text}]}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(explanation_builder.requests, "post", fake_post)

    result = explanation_builder.build_explanation(
        "The listener likes calm, dark, low-energy music.",
        QUERY_CARD,
        LIKED_TAGS,
        RECOMMENDED_TAGS,
        META,
        DISPLAY_EXAMPLE,
        RECOMMENDED_TRACK,
    )

    assert captured["url"].endswith("/responses")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"]["model"] == "gpt-test"
    assert captured["json"]["text"]["format"]["name"] == "recommendation_explanation"
    user_input = captured["json"]["input"][0]["content"][0]["text"]
    assert "lonely night train" in user_input
    assert "MoodSimpleV2" in user_input
    assert "similar_score" in user_input
    assert "similar_score_fallback" in user_input
    assert "explanation_example" in user_input
    assert "liked_123" in user_input
    assert "73rd Moon" in user_input
    assert "recommended_track" in user_input
    assert "Afterwork" in user_input
    assert "example_type" in user_input
    assert "Explain recommended_track, not explanation_example" in user_input
    assert result["why_text"].startswith("This track fits")
    assert result["evidence"][1]["source"] == "ranking"
