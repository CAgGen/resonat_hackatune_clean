"""接缝 · 推荐解释生成。

把用户画像、当前 Query Card、liked/recommended 曲目的 Cyanite tags 和排序元数据
合成英文 Why this track 文本。业务层可以直接 import 本模块；这里不接 FastAPI。
"""
from __future__ import annotations

import json
import re

import requests

import config


SYSTEM_PROMPT = """You explain music recommendations in English.

Ground every claim in the supplied Cyanite tags, Query Card, user profile, or ranking metadata.
Do not invent genres, moods, instruments, BPM, user behavior, or popularity signals.
The recommended_track is the track being explained. The explanation_example is only a previous liked-track comparison; never call the explanation_example the recommended track.
Explain:
1. how the track fits the current prompt,
2. how it relates to the listener's taste,
3. why it was selected from the recommendation path.

Keep why_text concise: 2-4 sentences, user-facing, non-technical unless the evidence needs a tag name.
When explanation_example is present, mention it as a concrete liked-track example. If it has title/artist fields, use them instead of an opaque id. If explanation_example.example_type is "session_source", say it was liked earlier in this session. If it is "historical_like", say it connects back to a track the listener liked in a previous session.
"""

EXPLANATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["why_text", "evidence"],
    "properties": {
        "why_text": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "detail"],
                "properties": {
                    "source": {"type": "string"},
                    "detail": {"type": "string"},
                },
            },
        },
    },
}

DEFAULT_EXAMPLE_SIMILARITY_THRESHOLD = 0.85


def extract_liked_track_ids_from_evidence(evidence_md: str) -> list[str]:
    """Extract historical liked ids from evidence.md, newest first, de-duplicated."""
    seen = set()
    liked_ids = []
    for line in reversed(evidence_md.splitlines()):
        match = re.search(r"→\s*liked\s+(.+?)(?:\s+\(|$)", line)
        if not match:
            continue
        for track_id in reversed([part.strip() for part in match.group(1).split(",")]):
            if track_id and track_id != "-" and track_id not in seen:
                seen.add(track_id)
                liked_ids.append(track_id)
    return liked_ids


def select_explanation_example(liked_tracks: list[str],
                               recommendation_meta: dict,
                               min_similarity: float = DEFAULT_EXAMPLE_SIMILARITY_THRESHOLD,
                               historical_candidates: list[dict] | None = None) -> dict | None:
    """Pick a liked track as an explanation example only when similarity is strong."""
    score = _score_from(recommendation_meta)
    source_ids = _source_liked_tracks(recommendation_meta.get("source_liked_track"))
    if isinstance(score, int | float) and score >= min_similarity and source_ids:
        liked = set(liked_tracks)
        selected = next((track_id for track_id in source_ids if track_id in liked), source_ids[0])
        return {
            "track_id": selected,
            "example_type": "session_source",
            "similar_score": float(score),
            "selection_basis": "source_liked_track",
        }
    historical = _best_historical_candidate(historical_candidates or [], min_similarity)
    if historical:
        return historical
    return None


def build_explanation(profile_md: str,
                      query_card: dict,
                      liked_track_tags: dict,
                      recommended_track_tags: dict,
                      recommendation_meta: dict,
                      explanation_example: dict | None = None,
                      recommended_track: dict | None = None) -> dict:
    """Return an English explanation grounded in provided Cyanite/user evidence."""
    if not config.OPENAI_API_KEY:
        return _fallback_explanation(query_card, recommendation_meta, explanation_example)
    return _explanation_from_openai(
        profile_md,
        query_card,
        liked_track_tags,
        recommended_track_tags,
        recommendation_meta,
        explanation_example,
        recommended_track,
    )


def _explanation_from_openai(profile_md: str,
                             query_card: dict,
                             liked_track_tags: dict,
                             recommended_track_tags: dict,
                             recommendation_meta: dict,
                             explanation_example: dict | None,
                             recommended_track: dict | None) -> dict:
    response = requests.post(
        f"{config.OPENAI_BASE_URL.rstrip('/')}/responses",
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.OPENAI_MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": [{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": _build_user_prompt(
                        profile_md,
                        query_card,
                        liked_track_tags,
                        recommended_track_tags,
                        recommendation_meta,
                        explanation_example,
                        recommended_track,
                    ),
                }],
            }],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "recommendation_explanation",
                    "strict": True,
                    "schema": EXPLANATION_SCHEMA,
                }
            },
        },
        timeout=config.OPENAI_TIMEOUT,
    )
    response.raise_for_status()
    return _normalize_explanation(json.loads(_extract_output_text(response.json())))


def _build_user_prompt(profile_md: str,
                       query_card: dict,
                       liked_track_tags: dict,
                       recommended_track_tags: dict,
                       recommendation_meta: dict,
                       explanation_example: dict | None,
                       recommended_track: dict | None) -> str:
    payload = {
        "user_profile": profile_md.strip() or "(none yet)",
        "query_card": query_card,
        "recommended_track": recommended_track,
        "liked_track_cyanite_tags": liked_track_tags,
        "recommended_track_cyanite_tags": recommended_track_tags,
        "recommendation_meta": recommendation_meta,
        "explanation_example": explanation_example,
        "explanation_style_instruction": (
            "Explain recommended_track, not explanation_example. If explanation_example is present, use it only as a concrete previous liked-track example and compare shared Cyanite evidence. "
            "Use explanation_example.example_type to distinguish whether the example came from the current session or previous-session evidence. "
            "If it is null, do not claim the recommendation resembles a specific liked track; explain using the current prompt, profile, recommended-track tags, and ranking metadata instead."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _fallback_explanation(query_card: dict,
                          recommendation_meta: dict,
                          explanation_example: dict | None) -> dict:
    query = query_card.get("free_text_query") or query_card.get("interpretation_plain") or "your current search"
    score = recommendation_meta.get("final_score", recommendation_meta.get("similar_score"))
    score_text = f" with score {score:.2f}" if isinstance(score, int | float) else ""
    example_text = ""
    if explanation_example:
        label = _example_label(explanation_example)
        if explanation_example.get("example_type") == "historical_like":
            example_text = f" It is close enough to a track you liked in a previous session ({label}) to use that as a concrete taste example."
        else:
            example_text = f" It is close enough to a track you liked earlier in this session ({label}) to use that as a concrete taste example."
    return {
        "why_text": (
            f"This track fits your current search for {query}. "
            f"It was selected from music near your liked tracks using Cyanite acoustic similarity{score_text}."
            f"{example_text}"
        ),
        "evidence": [{
            "source": "ranking",
            "detail": f"ranking_basis={recommendation_meta.get('ranking_basis', 'similar_score_fallback')}",
        }],
    }


def _source_liked_tracks(source: object) -> list[str]:
    if isinstance(source, str):
        return [part.strip() for part in source.split(",") if part.strip()]
    if isinstance(source, list):
        return [str(part).strip() for part in source if str(part).strip()]
    return []


def _best_historical_candidate(candidates: list[dict], min_similarity: float) -> dict | None:
    ranked = []
    for candidate in candidates:
        score = _score_from(candidate)
        if not isinstance(score, int | float) or score < min_similarity:
            continue
        track_id = str(candidate.get("track_id") or candidate.get("cyanite_id") or "").strip()
        if not track_id:
            continue
        ranked.append({**candidate, "track_id": track_id, "similar_score": float(score)})
    if not ranked:
        return None
    best = max(ranked, key=lambda c: c["similar_score"])
    example = {
        "track_id": best["track_id"],
        "example_type": "historical_like",
        "similar_score": best["similar_score"],
        "selection_basis": "historical_similarity",
    }
    for field in ("title", "artist", "similarity_evidence"):
        if best.get(field):
            example[field] = best[field]
    return example


def _score_from(row: dict) -> float | None:
    score = row.get("similar_score")
    if not isinstance(score, int | float):
        score = row.get("score")
    if not isinstance(score, int | float):
        score = row.get("final_score")
    return float(score) if isinstance(score, int | float) else None


def _example_label(example: dict) -> str:
    title = str(example.get("title", "")).strip()
    artist = str(example.get("artist", "")).strip()
    if title and artist:
        return f"{title} by {artist}"
    if title:
        return title
    return str(example.get("track_id", "a liked track"))


def _extract_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                return text
    raise ValueError("OpenAI response did not contain output text")


def _normalize_explanation(raw: dict) -> dict:
    return {
        "why_text": str(raw.get("why_text", "")).strip(),
        "evidence": [_normalize_evidence(x) for x in raw.get("evidence", []) if isinstance(x, dict)],
    }


def _normalize_evidence(raw: dict) -> dict:
    return {
        "source": str(raw.get("source", "")).strip(),
        "detail": str(raw.get("detail", "")).strip(),
    }
