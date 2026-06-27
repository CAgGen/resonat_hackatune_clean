import json

import config
import explanation_builder


QUERY_CARD = {
    "interpretation_plain": "Restrained night-train music with minimal vocals.",
    "free_text_query": "lonely night train restrained low energy minimal vocals",
    "soft_targets": [{"dim": "mood", "value": "calm melancholy", "weight": 0.8}],
    "negatives": [{"dim": "vocals", "value": "prominent vocals"}],
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


def test_select_explanation_example_returns_none_below_similarity_threshold():
    low_meta = {**META, "similar_score": 0.62, "final_score": 0.62}

    assert explanation_builder.select_explanation_example(
        liked_tracks=["liked_123"],
        recommendation_meta=low_meta,
    ) is None


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
    assert "Explain recommended_track, not explanation_example" in user_input
    assert result["why_text"].startswith("This track fits")
    assert result["evidence"][1]["source"] == "ranking"
