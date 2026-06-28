"""接缝 · 推荐解释生成。

把用户画像、当前 Query Card、liked/recommended 曲目的 Cyanite tags 和排序元数据
合成英文 Why this track 文本。业务层可以直接 import 本模块；这里不接 FastAPI。
"""
from __future__ import annotations

import json
import re
import time

import requests

import config

# OpenAI 429 限流：退避重试，不降级。用尽仍抛真错。
_RETRY_ON = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4


def _post_with_retry(*args, **kwargs) -> requests.Response:
    for attempt in range(_MAX_RETRIES):
        resp = requests.post(*args, **kwargs)
        if getattr(resp, "status_code", None) not in _RETRY_ON or attempt == _MAX_RETRIES - 1:
            return resp
        # 优先听服务端的 Retry-After，否则指数退避 1/2/4 秒
        wait = float(resp.headers.get("Retry-After") or 2 ** attempt)
        time.sleep(wait)
    return resp  # ponytail: 循环必返回，这行只为类型完整


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
If recommendation_meta.source is "similar", explain the shared musical evidence between recommended_track and explanation_example. If recommendation_meta.source is "profile_semantic", explain why recommended_track is close to the supplied user_profile; do not claim it came from a specific liked track unless explanation_example is present.

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
    """从已抓取的 MoodSimpleV2 segments 里提取「主导情绪随时间」时间轴，给前端做角标。

    每个时间点取 argmax 情绪，折叠连续相同段 → 每次情绪切换落一个脚注 {t, label}。
    时间戳直接来自 Cyanite，零编造。拿不到 segments 就返回空（前端不渲染角标）。"""
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
        match = re.search(r"→\s*liked\s+(.+?)(?:\s+\(|$)", line)
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
    # 惊喜卡：固定写死这段「special treat」文案，不走 LLM。用户必须每次都看到我们的良苦用心，
    # 不能让模型改写或 429 把它吞掉。tag A 从画像里抽，让对比落到 ta 自己的口味上。
    if recommendation_meta.get("source") == "surprise":
        return _surprise_explanation(profile_md, query_card, recommendation_meta)
    if not config.OPENAI_API_KEY:
        return _fallback_explanation(query_card, recommendation_meta, explanation_example)
    try:
        return _explanation_from_openai(
            profile_md,
            query_card,
            liked_track_tags,
            recommended_track_tags,
            recommendation_meta,
            explanation_example,
            recommended_track,
        )
    except Exception:
        # OpenAI 不可用（429 退避用尽 / 超时 / 任何报错）→ 降级到确定性解释，绝不 500
        return _fallback_explanation(query_card, recommendation_meta, explanation_example)


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
            "Use explanation_example.example_type to distinguish whether the example came from the current session or the listener's liked history. "
            "If it is null, do not claim the recommendation resembles a specific liked track; explain using the current prompt, profile, recommended-track tags, and ranking metadata instead."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


# 从画像里抽「贯穿的核心感觉」那行的头几个标签当 tag A；抽不到就退到频次光谱行；
# 再抽不到就空（文案退化为「your usual taste」泛指）。
_CORE_TASTE_RE = re.compile(r"贯穿的核心感觉[:：]\s*(.+)")
_SPECTRUM_RE = re.compile(r"感觉光谱[^:：]*[:：]\s*(.+)")
_TAG_SPLIT_RE = re.compile(r"[、,，]\s*")


def _dominant_taste_tags(profile_md: str, limit: int = 2) -> list[str]:
    text = profile_md or ""
    match = _CORE_TASTE_RE.search(text) or _SPECTRUM_RE.search(text)
    if not match:
        return []
    tags = []
    for raw in _TAG_SPLIT_RE.split(match.group(1).strip()):
        tag = re.split(r"\s*[×x]\s*", raw.strip())[0].strip("*` ").strip()  # 去掉 "flowing ×12" 的计数
        if tag:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _surprise_explanation(profile_md: str, query_card: dict, recommendation_meta: dict) -> dict:
    """惊喜卡的固定文案：special treat + 点名 tag A + 在 tag A 上做突破。绝不依赖 LLM。"""
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


# 兜底：前端纯文本渲染，剥掉模型偶尔漏带的 markdown 符号。
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
