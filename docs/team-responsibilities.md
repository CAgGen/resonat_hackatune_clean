# Team Responsibility Notes

This document captures the current responsibility boundary for the teammate owning the LLM prompt, refill-ranking, and personalized explanation work. It is intentionally product-facing rather than implementation-specific, so coding agents can detect overlap risk when helping other teammates.

This is not a repo-wide agent instruction file. Treat it as owner-specific context and coordination guidance.

For the overall product flow, use `PRD-night.md` as the source of truth.

## Owner Scope

The owner is responsible for three connected parts of the recommendation loop.

### 1. Intent-to-Search Prompt Template

The owner designs the detailed first-stage LLM template used before Cyanite search.

That template takes:

- the user's current prompt context from the whiteboard, including the initial prompt and later follow-up steering;
- the natural-language description of the user's taste profile;
- any relevant product constraints from the PRD.

The expected LLM output is a zero-hop natural-language search text that can be sent directly to the Cyanite search API.

This owner is not merely formatting UI copy. They own how user intent and taste memory are translated into the free-text query that drives the initial music search.

### 2. Similar-Music Refill Ranking

After the user expresses like / dislike feedback, the owner is responsible for the logic that uses liked tracks to find similar music and rank those similar tracks for refill.

This includes:

- taking user-liked tracks as positive sound evidence;
- using Cyanite similar-by-ID search to find acoustically similar tracks;
- reranking those similar tracks before they are used to replace disliked tracks in the visible recommendation list;
- keeping the ranking aligned with the latest whiteboard context, not only the user's first prompt.

If Cyanite supports a direct track-to-prompt match score, the ideal refill ranking should use the latest Query Card / free-text prompt compiled from all whiteboard posts. If Cyanite does not support that score, the fallback is to rank by the similar-by-ID score returned by Cyanite.

### 3. Personalized Explanation Prompt Template

The owner designs the LLM prompt template for personalized recommendation explanations.

That template combines:

- the user's liked tracks;
- Cyanite tags fetched for those liked tracks through the Tagging API;
- the user's current prompt / whiteboard context;
- the natural-language description of the user's taste profile;
- the Cyanite attributes of the recommended track.

The intended output is a personalized explanation text that can tell the user why a recommendation fits them, grounded in Cyanite's music understanding rather than popularity or collaborative-filtering logic.

The exact wording of this template is not specified here. This document only records ownership and interface expectations.

## Overlap Warnings For Agents

Coding agents should flag a possible responsibility overlap before making broad changes in these cases:

- changing how whiteboard prompts, follow-up steering, or taste profiles are merged into the search query;
- changing the ranking formula or fallback strategy for refill candidates;
- changing the explanation prompt format, inputs, or expected output;
- replacing personalized explanations with generic tag summaries;
- treating only the initial user prompt as the ranking target while ignoring later follow-up steering.

Safe adjacent work includes:

- exposing backend endpoints that call these components;
- wiring frontend controls to these components;
- adding cache or API client infrastructure around Cyanite calls;
- displaying returned explanations or ranking metadata without changing their generation logic.
