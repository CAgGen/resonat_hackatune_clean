# Hewga Agent Context

This is owner-specific context for agents working directly with Hewga. It is not a repo-wide instruction file, and it should not be treated as a universal rule for every teammate's agent.

For the overall product flow, read `PRD-night.md`.
For team responsibility boundaries, read `docs/team-responsibilities.md`.

## Owned Areas To Protect

If a requested change touches any of these areas, warn that it may overlap with Hewga's Prompt / Refill Ranking / Explainability ownership before implementing broad changes:

- LLM prompt templates that compile the whiteboard context and user profile into the free-text query sent to Cyanite search.
- Candidate refill ranking after like / dislike feedback, including similar-by-ID expansion and prompt-aligned reordering.
- Explanation prompt templates that combine liked-track Cyanite tags, the current whiteboard prompt context, and the user's natural-language taste profile.

Small integration hooks are fine, but avoid redesigning those owned components without coordination.

## Git / Commit Workflow Preference

When working in Hewga's thread, use small, feature-level commits. After finishing each small feature or coherent documentation update, create a commit instead of accumulating unrelated work.

Commit messages should use:

1. A short, simple summary line.
2. A more detailed explanatory paragraph in the commit body when the change needs context.

Before committing:

1. Check whether teammates have pushed new work.
2. Pull the latest `origin/main` and rebase or otherwise integrate it before creating the local commit.
3. If any conflict appears, stop and ask Hewga to resolve or decide the conflict strategy. Do not guess or silently choose one side.
4. After the conflict is resolved, continue with the commit.

Do not force-push or rewrite shared history unless Hewga explicitly asks for it.
