import json

import config
import intent_compiler


POSTS = [
    {"role": "initial_prompt", "text": "music for a lonely night train scene"},
    {"role": "follow_up", "text": "less vocal, more restrained"},
]


def test_fallback_compiles_posts_and_profile_without_openai_key(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)

    card = intent_compiler.compile_query_card(
        POSTS,
        "User often likes warm analog synths and low energy acoustic textures.",
    )

    assert "night" in card["free_text_query"]
    assert "warm" in card["free_text_query"]
    assert "low energy" in card["free_text_query"]
    assert "instrumental" in card["free_text_query"]
    assert "I understand the target as" not in card["interpretation_plain"]
    assert {"dim": "vocals", "value": "vocal"} in card["negatives"]
    assert card["soft_targets"]


def test_fallback_interpretation_explains_inferred_work_music_traits(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)

    card = intent_compiler.compile_query_card(
        [{
            "role": "initial_prompt",
            "text": (
                "Find me something calm and cinematic for working late at night. "
                "I want soft piano or warm acoustic guitar, low energy, gentle rhythm, "
                "mostly instrumental, and a slightly hopeful mood."
            ),
        }],
        "User often likes warm acoustic textures and reflective background music.",
    )

    assert "background" in card["interpretation_plain"]
    assert "low distraction" in card["interpretation_plain"]
    assert "calm" in card["free_text_query"]
    assert "cinematic" in card["free_text_query"]
    assert "piano" in card["free_text_query"]
    assert "acousticGuitar" in card["free_text_query"]
    assert len(card["interpretation_plain"].split()) < 75


def test_openai_response_is_requested_as_query_card_json(monkeypatch):
    captured = {}
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-test", raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            output_text = json.dumps({
                "interpretation_plain": "A restrained night-train mood with little vocal presence.",
                "free_text_query": "restrained low energy night train music, warm analog synths, minimal vocals",
                "soft_targets": [{"dim": "mood", "value": "restrained", "weight": 0.8}],
                "negatives": [{"dim": "vocals", "value": "prominent vocals"}],
            })
            return {"output": [{"content": [{"type": "output_text", "text": output_text}]}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(intent_compiler.requests, "post", fake_post)

    card = intent_compiler.compile_query_card(
        POSTS,
        "User often likes warm analog synths.",
    )

    assert captured["url"].endswith("/responses")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"]["model"] == "gpt-test"
    assert captured["json"]["text"]["format"]["name"] == "cyanite_query_card"
    assert "Cyanite vocabulary guide" in captured["json"]["instructions"]
    assert "must not simply paraphrase" in captured["json"]["instructions"]
    user_input = captured["json"]["input"][0]["content"][0]["text"]
    assert "lonely night train scene" in user_input
    assert "less vocal" in user_input
    assert "warm analog synths" in user_input
    assert "do not restate the prompt" in user_input
    assert card["free_text_query"].startswith("restrained low energy")
    assert card["soft_targets"][0]["weight"] == 0.8
