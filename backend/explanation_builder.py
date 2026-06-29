"""Seam · recommendation explanation generation.

Combines the user profile, current Query Card, Cyanite tags for liked/recommended tracks,
and ranking metadata into English "Why this track" text. Business code can import this
module directly; FastAPI does not connect here.
"""
from __future__ import annotations

import json
import re
import time

import requests

import config

# OpenAI 429 rate limits: back off and retry, with no downgrade. Raise the real error after exhaustion.
_RETRY_ON = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4


def _post_with_retry(*args, **kwargs) -> requests.Response:
    for attempt in range(_MAX_RETRIES):
        resp = requests.post(*args, **kwargs)
        if getattr(resp, "status_code", None) not in _RETRY_ON or attempt == _MAX_RETRIES - 1:
            return resp
        # Prefer server Retry-After; otherwise use exponential backoff: 1/2/4 seconds.
        wait = float(resp.headers.get("Retry-After") or 2 ** attempt)
        time.sleep(wait)
    return resp  # ponytail: the loop always returns; this line is only for type completeness.


SYSTEM_PROMPT = """You explain music recommendations in English.

Ground every claim in the supplied Cyanite tags, Query Card, user profile, or ranking metadata.
Do not invent genres, moods, instruments, BPM, user behavior, or popularity signals.
The recommended_track is the track being explained. The explanation_example is only a previous liked-track comparison; never call the explanation_example the recommended track.
Explain:
1. how the track fits the current prompt,
2. how it relates to the listener's taste,
3. why it was selected from the recommendation path.

Keep why_text concise: 2-4 sentences, user-facing, non-technical unless the evidence needs a tag name.
Write why_text as plain prose. Do not use any markdown: no asterisks, bold, bullet points, or headings (the UI renders raw text, so those symbols would show literally).
When explanation_example is present, mention it as a concrete liked-track example. If it has title/artist fields, use them instead of an opaque id. If explanation_example.example_type is "session_source", say it was liked earlier in this session. If it is "historical_like", say it connects back to a track already in the listener's liked history.
If recommendation_meta.source is "similar", the recommended_track was found by running an acoustic similarity search seeded on ONE specific song the listener liked. That seed song is the explanation_example. This is NON-NEGOTIABLE — you MUST:
  a) Open why_text by naming the seed song explicitly by its title and artist (from explanation_example.title / explanation_example.artist), e.g. start with "Because you liked <seed title> by <seed artist>, ...". The seed title AND artist must literally appear in why_text. Never use the raw id, and never refer to it vaguely as "a track you liked" or "your liked track".
  b) State plainly that recommended_track was surfaced by a similarity search run on that named seed song (e.g. "Because you liked <seed title> by <seed artist>, we searched for songs that sound like it and found <recommended title>").
  c) Only AFTER naming the seed song, explain WHY the two songs sound alike, by comparing concrete shared Cyanite evidence between liked_track_cyanite_tags (the seed) and recommended_track_cyanite_tags (the recommendation) — name the moods, genres, instruments, energy, or BPM they have in common. Only cite tags actually present in the supplied data.
If recommendation_meta.source is "profile_semantic", explain why recommended_track is close to the supplied user_profile; do not claim it came from a specific liked track unless explanation_example is present.

The "surprise" source is handled deterministically before this prompt is ever used, so you will not receive it here.
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

DEFAULT_EXAMPLE_SIMILARITY_THRESHOLD = 0.0  # ponytail: threshold disabled; any positive-score source/historical track can explain


def mood_timeline(recommended_tags: dict, max_points: int = 6) -> list[dict]:
    """Extract a "dominant mood over time" timeline from fetched MoodSimpleV2 segments for frontend markers.

    At each timestamp, take the argmax mood and collapse consecutive identical spans, leaving one
    marker {t, label} for each mood switch. Timestamps come directly from Cyanite with no invention.
    Return empty when segments are unavailable (frontend renders no markers)."""
    item = next((i for i in recommended_tags.get("items", [])
                 if str(i.get("version", "")).startswith("MoodSimpleV2")), None)
    seg = (item or {}).get("segments") or {}
    ts, vals = seg.get("timestampsSeconds"), seg.get("values")
    if not isinstance(ts, list) or not isinstance(vals, dict) or not vals:
        return []
    moods = list(vals)
    timeline, prev = [], None
    for i, t in enumerate(ts):
        top = max(moods, key=lambda m: vals[m][i] if i < len(vals[m]) else 0)
        if top != prev:
            timeline.append({"t": float(t), "label": top})
            prev = top
    return timeline[:max_points]


def extract_liked_track_ids_from_evidence(evidence_md: str) -> list[str]:
    """Extract historical liked ids from evidence.md, newest first, de-duplicated."""
    seen = set()
    liked_ids = []
    for line in reversed(evidence_md.splitlines()):
        match = re.search(r"(?:→|->)\s*liked\s+(.+?)(?:\s+\(|$)", line)
        if not match:
            continue
        for track_id in reversed([part.strip() for part in match.group(1).split(",")]):
            if track_id and track_id != "-" and track_id not in seen:
                seen.add(track_id)
                liked_ids.append(track_id)
    return liked_ids


def build_historical_candidates_from_similar_rows(evidence_md: str,
                                                  similar_rows: list[dict],
                                                  display_by_id: dict[str, dict] | None = None,
                                                  limit: int | None = None,
                                                  liked_track_ids: list[str] | None = None) -> list[dict]:
    """Convert recommended-track similarById rows into historical liked candidates."""
    historical_ids = set(extract_liked_track_ids_from_evidence(evidence_md))
    historical_ids.update(track_id for track_id in liked_track_ids or [] if track_id)
    display_by_id = display_by_id or {}
    candidates = []
    for row in similar_rows:
        track_id = _track_id_from(row)
        score = _score_from(row)
        if not track_id or track_id not in historical_ids or not isinstance(score, int | float):
            continue
        candidate = {
            "track_id": track_id,
            "similar_score": float(score),
            "selection_basis": "historical_similar_by_id_intersection",
        }
        display = display_by_id.get(track_id, {})
        for field in ("title", "artist"):
            if display.get(field):
                candidate[field] = display[field]
        candidates.append(candidate)
    candidates.sort(key=lambda candidate: candidate["similar_score"], reverse=True)
    return candidates[:limit] if limit is not None else candidates


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
    # Surprise card: hard-code this "special treat" copy instead of using the LLM.
    # Users must always see the intended positioning; do not let model rewrites or 429s swallow it.
    # Tag A comes from the profile so the contrast lands against their own taste.
    if recommendation_meta.get("source") == "surprise":
        return _surprise_explanation(profile_md, query_card, recommendation_meta)
    if not config.OPENAI_API_KEY:
        result = _fallback_explanation(query_card, recommendation_meta, explanation_example)
    else:
        try:
            result = _explanation_from_openai(
                profile_md,
                query_card,
                liked_track_tags,
                recommended_track_tags,
                recommendation_meta,
                explanation_example,
                recommended_track,
            )
        except Exception:
            # OpenAI unavailable (429 retries exhausted / timeout / any error) -> deterministic fallback, never 500.
            result = _fallback_explanation(query_card, recommendation_meta, explanation_example)
    return _ensure_seed_attribution(result, recommendation_meta, explanation_example)


def _explanation_from_openai(profile_md: str,
                             query_card: dict,
                             liked_track_tags: dict,
                             recommended_track_tags: dict,
                             recommendation_meta: dict,
                             explanation_example: dict | None,
                             recommended_track: dict | None) -> dict:
    response = _post_with_retry(
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
            "When recommendation_meta.source is 'similar', explanation_example is the seed song the similarity search ran on: name it by title and artist, say recommended_track was found by searching for songs that sound like it, and explain the shared tags that make them similar. "
            "Use explanation_example.example_type to distinguish whether the example came from the current session or the listener's liked history. "
            "If it is null, do not claim the recommendation resembles a specific liked track; explain using the current prompt, profile, recommended-track tags, and ranking metadata instead."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


# Extract the first tags from the "core feel" profile line as tag A; fall back to the spectrum line;
# if that also fails, leave it empty (copy falls back to generic "your usual taste").
_CORE_TASTE_RE = re.compile(r"Core feel[^:]*:\s*(.+)", re.IGNORECASE)
_SPECTRUM_RE = re.compile(r"Feel spectrum[^:]*:\s*(.+)", re.IGNORECASE)
_TAG_SPLIT_RE = re.compile(r"[,，]\s*")


def _dominant_taste_tags(profile_md: str, limit: int = 2) -> list[str]:
    text = profile_md or ""
    match = _CORE_TASTE_RE.search(text) or _SPECTRUM_RE.search(text)
    if not match:
        return []
    tags = []
    for raw in _TAG_SPLIT_RE.split(match.group(1).strip()):
        tag = re.split(r"\s*[×x]\s*", raw.strip())[0].strip("*` ").strip()  # strip "flowing x12" count suffixes
        if tag:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _surprise_explanation(profile_md: str, query_card: dict, recommendation_meta: dict) -> dict:
    """Fixed surprise-card copy: special treat + name tag A + break past tag A. Never depends on the LLM."""
    query = query_card.get("free_text_query") or query_card.get("interpretation_plain") or "your current search"
    tags = _dominant_taste_tags(profile_md)
    if tags:
        tag_a = " and ".join(tags)
        taste_clause = (
            f"you usually go for tracks that feel {tag_a} — "
            f"and this time we deliberately broke past that {tag_a} mold"
        )
    else:
        taste_clause = "this time we deliberately stepped past the kind of music you usually reach for"
    return {
        "why_text": (
            f"This one is a special treat, picked just for you. We know it sits a little outside your usual taste: "
            f"{taste_clause}, while still keeping it close to what you searched for ({query}). "
            f"We hope it helps you discover a different corner of the music world."
        ),
        "evidence": [{
            "source": "ranking",
            "detail": f"ranking_basis={recommendation_meta.get('ranking_basis', 'surprise_adjacent_shift')}; "
                      f"anchor_tags={', '.join(tags) if tags else '(profile empty)'}",
        }],
    }


def _fallback_explanation(query_card: dict,
                          recommendation_meta: dict,
                          explanation_example: dict | None) -> dict:
    query = query_card.get("free_text_query") or query_card.get("interpretation_plain") or "your current search"
    score = recommendation_meta.get("final_score", recommendation_meta.get("similar_score"))
    score_text = f" with score {score:.2f}" if isinstance(score, int | float) else ""
    if recommendation_meta.get("source") == "profile_semantic":
        return {
            "why_text": (
                f"This track is close to your user profile while still fitting your current search for {query}. "
                f"It was selected by a semantic search over your taste memory{score_text}, so the match comes from the profile you have built through feedback."
            ),
            "evidence": [{
                "source": "ranking",
                "detail": f"ranking_basis={recommendation_meta.get('ranking_basis', 'profile_semantic_search')}",
            }],
        }
    example_text = ""
    if explanation_example:
        label = _example_label(explanation_example)
        if explanation_example.get("example_type") == "historical_like":
            example_text = f" It is close enough to a track already in your liked history ({label}) to use that as a concrete taste example."
        else:
            example_text = f" It is close enough to a track you liked earlier in this session ({label}) to use that as a concrete taste example."
    # Only tracks truly found from a liked seed (with source_liked_track) can say they came from near liked songs.
    # free_text cards recalled from the prompt (first batch / backlog fallback) have no seed, so they can only say
    # they directly match the search brief, not claim similarity.
    if recommendation_meta.get("source_liked_track"):
        selection = f"It was selected from music near your liked tracks using Cyanite acoustic similarity{score_text}."
        ranking_basis = recommendation_meta.get("ranking_basis", "similar_score_fallback")
    else:
        selection = f"It was retrieved directly from your search brief by Cyanite semantic search{score_text}."
        ranking_basis = recommendation_meta.get("ranking_basis", "free_text_search")
    return {
        "why_text": f"This track fits your current search for {query}. {selection}{example_text}",
        "evidence": [{"source": "ranking", "detail": f"ranking_basis={ranking_basis}"}],
    }


def _ensure_seed_attribution(result: dict,
                             recommendation_meta: dict,
                             explanation_example: dict | None) -> dict:
    """Hard constraint for similarById cards: why_text must name the seed song as "title by artist".

    The LLM may occasionally omit the seed title/artist (fallback copy can too) and say only "a track you liked".
    This deterministic fallback prepends explicit attribution when source=='similar', a seed title is available,
    and why_text does not already mention it."""
    if recommendation_meta.get("source") != "similar" or not explanation_example:
        return result
    title = str(explanation_example.get("title", "")).strip()
    artist = str(explanation_example.get("artist", "")).strip()
    if not title:
        return result
    why = str(result.get("why_text", ""))
    if title.lower() in why.lower():
        return result
    lead = (f"Because you liked {title} by {artist}, we searched for songs that sound like it"
            if artist else
            f"Because you liked {title}, we searched for songs that sound like it")
    result["why_text"] = f"{lead}. {why}".strip()
    return result


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


def _track_id_from(row: dict) -> str:
    return str(row.get("cyanite_id") or row.get("track_id") or row.get("id") or "").strip()


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


# Fallback: frontend renders plain text, so strip occasional markdown symbols leaked by the model.
_MD = re.compile(r"\*\*|__|`|^\s*[-*•#]+\s+", re.M)


def _normalize_explanation(raw: dict) -> dict:
    return {
        "why_text": _MD.sub("", str(raw.get("why_text", ""))).strip(),
        "evidence": [_normalize_evidence(x) for x in raw.get("evidence", []) if isinstance(x, dict)],
    }


def _normalize_evidence(raw: dict) -> dict:
    return {
        "source": str(raw.get("source", "")).strip(),
        "detail": str(raw.get("detail", "")).strip(),
    }


_SOUNDS_LIKE_YOU_SYSTEM = """You explain why a music track sounds like a specific person — their musical identity, not a recommendation.

The AI has listened to everything this person has gravitated toward and identified one track that best represents who they ARE musically. This is a self-portrait in sound.

You are given:
- user_profile: The listener's long-term taste profile (dominant moods, textures, musical tendencies built from their feedback history)
- track: title and artist of the identified track
- track_tags: Cyanite acoustic/mood/genre tags for this track

Write 2-4 sentences explaining why THIS track sounds like this specific person. Ground every claim in user_profile and track_tags. Do not invent anything.

Frame it as the AI reflecting the person's musical identity back at them — intimate, observational, honest. Not "we recommend this" but "this IS you."

Plain prose only. No markdown, no bullet points, no asterisks. Warm but precise."""


def build_sounds_like_you_explanation(profile_md: str, track: dict, track_tags: dict) -> dict:
    """Why this track IS the user, not why it was recommended."""
    if not config.OPENAI_API_KEY:
        tags_summary = ", ".join(list(track_tags.keys())[:4]) if track_tags else "various qualities"
        return {
            "why_text": (
                f"Based on your taste profile, {track.get('title', 'this track')} by {track.get('artist', 'this artist')} "
                f"captures the sound you keep returning to — {tags_summary} are woven through everything you've loved."
            ),
            "evidence": [],
        }
    payload = {
        "user_profile": profile_md.strip() or "(no profile yet)",
        "track": {"title": track.get("title", ""), "artist": track.get("artist", "")},
        "track_tags": track_tags,
    }
    resp = _post_with_retry(
        f"{config.OPENAI_BASE_URL.rstrip('/')}/responses",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": config.OPENAI_MODEL,
            "instructions": _SOUNDS_LIKE_YOU_SYSTEM,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}],
            "text": {"format": {"type": "json_schema", "name": "sounds_like_you_explanation", "strict": True, "schema": EXPLANATION_SCHEMA}},
        },
        timeout=config.OPENAI_TIMEOUT,
    )
    resp.raise_for_status()
    return _normalize_explanation(json.loads(_extract_output_text(resp.json())))
