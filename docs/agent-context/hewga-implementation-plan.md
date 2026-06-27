# Hewga Implementation Plan

This plan covers Hewga's owner scope: intent compilation, refill ranking, and personalized explanation generation. It is owner-specific planning context, not a repo-wide engineering plan.

The product workflow source of truth remains `PRD-night.md`.

## Current Decisions

- Implementation language: Python.
- Integration style: build importable Python modules first; expose them through FastAPI only via thin integration hooks.
- LLM provider: OpenAI.
- LLM output format: decide after reviewing the official OpenAI API documentation and the Cyanite API input/response formats. The API docs are available to the team; they just have not been shared in this thread yet.
- Explanation language: English.
- Refill ranking: do not use an LLM to rank candidates. Ranking must use official Cyanite API scores and deterministic logic.
- Ranking target: the latest whiteboard context, meaning the initial prompt plus every follow-up steering prompt, compiled into the current Query Card / free-text query.

## Why Pure Python First

Start with pure Python functions instead of writing directly inside FastAPI endpoints.

Reasons:

- The backend already keeps HTTP routing thin in `backend/app.py`.
- The main workflow already imports owner-owned seams such as `backend/intent_compiler.py` and `backend/rerank.py`.
- Pure functions are easier to test with fixed examples before API credentials and live calls are stable.
- A's integration work can call these functions without taking ownership of the prompt, ranking, or explanation logic.
- FastAPI endpoints should remain adapters: validate request data, call orchestration, and return response shapes.

Practical rule: implement logic in importable modules; wire it into FastAPI only after function signatures and outputs are stable.

## Existing Backend Seams

The current backend already has useful handoff points:

- `backend/intent_compiler.py`
  - Current seam for whiteboard posts + memory profile -> Query Card.
  - Existing signature: `compile_query_card(posts, profile_md) -> dict`.
  - Keep this signature stable unless the integration owner agrees to change it.

- `backend/rerank.py`
  - Current seam for deterministic reranking.
  - Existing function: `thin_rerank(cards, ...)`.
  - Extend or add adjacent functions for refill candidate ranking; do not move ranking decisions into the LLM.

- `backend/orchestrator.py`
  - Current workflow state machine.
  - It currently handles like -> `find_similar`, dislike -> backfill, and visible-card reranking.
  - Treat this as integration territory. Add clean calls into owner modules rather than burying owner logic inside orchestration.

## Phase 1: Intent Compiler

Goal: turn the latest whiteboard context and the user's natural-language taste profile into a Cyanite-ready search input.

Inputs:

- `whiteboard_posts`: initial prompt plus follow-up steering posts in chronological order.
- `profile_md`: natural-language user profile / memory summary.
- Product constraints from `PRD-night.md`.

Core behavior:

- Build an OpenAI prompt template that merges the user's latest whiteboard context with their profile.
- Call OpenAI from Python.
- Convert the model response into the Query Card shape expected by the backend.

Expected output shape:

```python
{
    "interpretation_plain": str,
    "free_text_query": str,
    "soft_targets": list[dict],
    "negatives": list[dict],
}
```

Important constraints:

- `free_text_query` should be optimized for Cyanite free-text search, not for chatty explanation.
- Follow-up steering must be respected as part of the current intent, not treated as secondary history.
- The model output format should be chosen after reviewing the official OpenAI and Cyanite documentation.

First implementation target:

- Replace the placeholder body of `compile_query_card(posts, profile_md)` while keeping its public signature stable.
- Add fixed examples that cover abstract prompts, follow-up steering, and profile-vs-current-prompt tension.

## Phase 2: Refill Ranker

Goal: when a user dislikes a visible recommendation, choose the best refill track from candidates found through liked-track similarity.

Inputs:

- Similar candidates produced from liked tracks through Cyanite `similarById`.
- Candidate scores returned by Cyanite.
- The latest Query Card / `free_text_query`, compiled from all whiteboard posts.
- Optional tags when available, only for deterministic lightweight adjustments.

Core behavior:

- Use liked tracks as positive sound evidence.
- Use Cyanite similar search to collect candidates.
- Rank candidates by official Cyanite score signals.
- Do not ask an LLM to rank candidates.

Ranking rule:

1. If Cyanite provides a track-to-current-prompt match score, rank by that score.
2. If not, rank by Cyanite's similar-by-ID score.
3. Optional later step: add a small deterministic tag bonus, as long as the official score remains the dominant signal.

The key product interpretation:

> The best refill is not merely the track most similar to a liked song. It is the best-scoring candidate within the liked-song neighborhood that also matches the user's current whiteboard intent.

First implementation target:

- Add a deterministic refill-ranking function that sorts by official score.
- Return debug metadata that explains which score was used.

Suggested debug shape:

```python
{
    "track_id": str,
    "source_liked_track": str,
    "similar_score": float | None,
    "prompt_match_score": float | None,
    "final_score": float,
    "ranking_basis": "prompt_match_score" | "similar_score_fallback",
}
```

## Phase 3: Explanation Builder

Goal: generate English personalized explanations for recommended tracks.

Inputs:

- User profile text.
- Latest whiteboard context / Query Card.
- Tags for liked tracks from Cyanite Tagging API.
- Tags for the recommended track from Cyanite Tagging API.
- Recommendation source and score metadata.

Core behavior:

- Build an OpenAI prompt template for explanation generation.
- Call OpenAI from Python.
- Return English user-facing explanation text plus evidence metadata where useful.

Prompt constraints:

- Ground every claim in provided Cyanite tags, scores, or supplied user profile text.
- Do not invent genres, moods, instruments, BPM, or user behavior.
- Mention how the track fits the current prompt and how it relates to the user's taste.
- Prefer clear English over technical jargon.

First implementation target:

- Build the prompt template after the intent and ranking data structures stabilize.
- Use fixture tag payloads before depending on live Tagging API responses.

## Future Feature: Explainable Surprise Recommendations

Goal: occasionally recommend a track that is not the closest match to the user's existing taste, while keeping the surprise reasonable, audio-grounded, and proactively explained.

Product motivation:

- Avoid trapping the listener in a narrow taste bubble.
- Give users a controlled opportunity to discover music just outside their established pattern.
- Make the product stance visible: discovery should not only reinforce what the user already knows they like.

Core behavior:

- Add a small number of "surprise" recommendations to the list only when they still fit the current whiteboard intent.
- A surprise track should be different from the user's liked tracks in at least one meaningful Cyanite dimension, such as mood, instrumentation, genre, energy, era, or vocal profile.
- The surprise must remain explainable through Cyanite tags and the current Query Card. It should never be random, popularity-based, or collaborative-filtering-based.
- The UI should proactively label the recommendation as exploratory instead of waiting for the user to ask "Why this track?".

Example user-facing explanation:

> This one is a small step outside your usual sound. You often like restrained, low-energy instrumental tracks, and this keeps that late-night focus use case, but adds a brighter synth texture and more movement. I included it as a controlled discovery pick rather than a pure similarity match.

Likely implementation direction:

- Keep the normal refill ranker focused on similarity.
- Add a separate exploration selector that works over candidate tracks already retrieved through Cyanite search or similarity calls.
- Use deterministic tag contrast, not an LLM, to choose surprise candidates.
- Use the Explanation Builder to generate the proactive explanation, with explicit inputs for:
  - current Query Card,
  - user profile,
  - representative liked-track tags,
  - surprise-track tags,
  - shared attributes,
  - intentionally different attributes.

Guardrails:

- Surprise recommendations should be occasional, not the default.
- They must still satisfy the user's current prompt strongly enough to be defensible.
- They must not use popularity or co-listening signals.
- They should be easy to dismiss; a dislike should reduce this exploration direction.

## Recommended Work Order

1. Confirm official OpenAI and Cyanite API response/input formats.
2. Stabilize Python data shapes for Query Card, refill candidates, ranking debug output, and explanation inputs.
3. Implement `compile_query_card(posts, profile_md)` with OpenAI behind the existing backend seam.
4. Add fixed examples for prompt compilation.
5. Implement deterministic refill candidate ranking using official Cyanite scores.
6. Add ranking debug metadata.
7. Implement the explanation prompt template and OpenAI call.
8. Add an owner-level demo script or examples that run the three modules together with fixture data.
9. After the modules are stable, rename owner-scoped paths or functions into product-semantic module names if needed.

## Non-Goals

- Do not use collaborative filtering or popularity signals.
- Do not use an LLM to rank refill candidates.
- Do not treat only the initial prompt as the ranking target; later follow-up steering is part of the current query.
- Do not move business logic directly into FastAPI route handlers.
- Do not finalize the LLM response parsing strategy before reviewing official API docs.
