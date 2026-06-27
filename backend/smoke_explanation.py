"""Explanation 真连通自检（打 Cyanite + OpenAI 真 API）。

run: uv run python smoke_explanation.py
没 CYANITE_API_KEY 或 OPENAI_API_KEY 就跳过；连通则打印 English explanation。
"""
from __future__ import annotations

import json

import config
import cyanite
import explanation_builder


MODELS = [
    "MainGenreV2",
    "MoodSimpleV2",
    "InstrumentsV2",
    "BpmV2",
    "VocalsV2",
    "AutoDescriptionV2",
]

LIKED_ID = "libtr_01KVX1J122H6RS7K1F"
RECOMMENDED_ID = "libtr_01KVX1J1350XG8J4PG"


def main() -> None:
    if not config.CYANITE_API_KEY:
        print("跳过：.env 里没填 CYANITE_API_KEY")
        return
    if not config.OPENAI_API_KEY:
        print("跳过：.env 里没填 OPENAI_API_KEY")
        return

    liked_tags = cyanite.model_tags(LIKED_ID, MODELS)
    recommended_tags = cyanite.model_tags(RECOMMENDED_ID, MODELS)
    query_card = {
        "interpretation_plain": "Restrained, intimate night-drive music with minimal vocals.",
        "free_text_query": "lonely night drive restrained intimate low energy minimal vocals",
        "soft_targets": [{"dim": "mood", "value": "calm melancholy", "weight": 0.8}],
        "negatives": [{"dim": "vocals", "value": "prominent vocals"}],
    }
    recommendation_meta = {
        "source_liked_track": LIKED_ID,
        "similar_score": 0.91,
        "final_score": 0.91,
        "ranking_basis": "similar_score_fallback",
    }
    explanation = explanation_builder.build_explanation(
        "The listener tends to like calm, restrained, low-energy tracks for late-night focus.",
        query_card,
        liked_tags,
        recommended_tags,
        recommendation_meta,
    )

    print("liked:", cyanite.display(LIKED_ID))
    print("recommended:", cyanite.display(RECOMMENDED_ID))
    print(json.dumps(explanation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
