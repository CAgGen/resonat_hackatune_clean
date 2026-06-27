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

    assert "lonely night train scene" in card["free_text_query"]
    assert "less vocal" in card["free_text_query"]
    assert "warm analog synths" in card["free_text_query"]
    assert {"dim": "vocals", "value": "vocal"} in card["negatives"]


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
    user_input = captured["json"]["input"][0]["content"][0]["text"]
    assert "lonely night train scene" in user_input
    assert "less vocal" in user_input
    assert "warm analog synths" in user_input
    assert card["free_text_query"].startswith("restrained low energy")
    assert card["soft_targets"][0]["weight"] == 0.8
