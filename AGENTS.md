# Agent Coordination Notes

This repo is a hackathon prototype for the Cyanite audio-first recommendation workflow. Before changing behavior, read:

- `PRD-night.md` for the current product workflow.
- `docs/team-responsibilities.md` for responsibility boundaries.

## Responsibility Boundary Warning

If a requested change touches any of these areas, warn the user that it may overlap with the Prompt / Refill Ranking / Explainability owner before implementing broad changes:

- LLM prompt templates that compile the whiteboard context and user profile into the free-text query sent to Cyanite search.
- Candidate refill ranking after like / dislike feedback, including similar-by-ID expansion and prompt-aligned reordering.
- Explanation prompt templates that combine liked-track Cyanite tags, the current whiteboard prompt context, and the user's natural-language taste profile.

Small integration hooks are fine, but avoid redesigning those owned components without coordination.
