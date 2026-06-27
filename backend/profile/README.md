# `backend/profile` — User-defined Taste Memory

The **user-profile** module for Cochlea. It turns a listener's feedback
(like / dislike / skip / free-text note) into an **explainable, per-user taste
memory** stored as Markdown, and serves it to the rest of the backend.

Maps to PRD §7 (the two memory consumers) and the `/feedback` + `/your-sound`
endpoints. Memory is built from **likes** (positive signal); dislike/skip push
affinities down; notes are stored verbatim. Every preference traces back to real
Cyanite tags — **no opaque latent vector**, so it stays explainable.

---

## Structure

```
backend/profile/
  api.py           FastAPI routes (router + standalone app)
  mdmemory.py      core: record_feedback() + two-file md storage + read views
  salience.py      tag distinctiveness (IDF) — the "what to remember" filter
  cyanite_tags.py  minimal Cyanite tagging client (disk cache + rate limit)
  tags.py          normalize raw model outputs -> flat tags
  data.py          data-pack id mapping + audio url (for demo/seed/eval)
  config.py        env / paths (reads repo-root .env)
  visualize.py     render a user's memory as a "Taste Card" PNG
  tag_base_rates.json  catalog tag frequencies for IDF (aggregate only)
  test_feedback.py / experiment_novelty.py / evaluate.py / faithfulness.py
  memory/          per-user memory files (runtime; git-ignored):
                     <uid>.evidence.md  append-only raw truth (seed pool)
                     <uid>.memory.md    natural-language profile (-> /intent)
                     <uid>.state.json   internal engine cache (derived)
  .cache/          cached Cyanite tags (runtime; git-ignored)
```

## Run

```bash
# from the repo root, with the `hackatune` conda env
uvicorn backend.profile.api:app --reload --port 8001   # docs at /docs

# or run the simulated feedback demo
python -m backend.profile.test_feedback
```

Needs `CYANITE_API_KEY` in the repo-root `.env`. With no key it runs in **MOCK**
mode (deterministic fake tags) so the module is testable offline.

---

## The one interface

```python
from backend.profile import mdmemory

mdmemory.record_feedback(
    user_id, track_id, verdict,      # verdict: like | dislike | skip | play | note
    prompt=None,                     # the search/Query the track came from
    note=None,                       # free-text "other info" from the user
    track_tags=None,                 # optional; fetched from Cyanite (cached) if absent
) -> summary_dict
```

Read views:

```python
mdmemory.summary(user_id)               # headline + structured prefs (for /your-sound)
mdmemory.seed_pool(user_id, prompt=...) # liked track ids -> similarById seeds
mdmemory.prompt_injection(user_id)      # taste block to prepend to the /intent system prompt
```

## HTTP endpoints

| Method | Path | Purpose | Consumer |
|---|---|---|---|
| POST | `/feedback` | record one event → updated summary | `/feedback` loop |
| POST | `/feedback/batch` | record a list of events | replay / batch |
| GET | `/your-sound/{user_id}` | memory summary | `GET /your-sound` |
| GET | `/profile/{user_id}/seeds?prompt=&limit=` | liked-track seed pool | search side |
| GET | `/profile/{user_id}/injection` | system-prompt taste block (memory.md body) | `/intent` |
| GET | `/profile/{user_id}/memory` | natural-language profile (memory.md) | demo / `/intent` |
| GET | `/profile/{user_id}/evidence` | append-only raw log (evidence.md) | demo |
| GET | `/profile/{user_id}/card.png` | rendered "Taste Card" image | demo / frontend |
| GET | `/health` | `{ok, mock}` | — |

## Integrate (two ways)

```python
# 1) mount the router in the main app (preferred)
from backend.profile.api import router as profile_router
main_app.include_router(profile_router)

# 2) or call the functions directly from your own /feedback handler
from backend.profile import mdmemory
mdmemory.record_feedback(uid, tid, "like", prompt=prompt)   # persist the like
seeds = mdmemory.seed_pool(uid, prompt=prompt)              # for similarById
inject = mdmemory.prompt_injection(uid)                     # for /intent
```

> ⚠️ In the PRD, `POST /feedback` also does neighbourhood **pruning/backfill/rerank**
> (search side, owned by another teammate). This module only persists memory.
> Pick one: have the main `/feedback` call `record_feedback()` internally, or use
> integration (2) — so two owners don't both register `POST /feedback`.

## Storage format (PRD-night: two markdown files, no DB)

Per user, under `memory/`:

- **`<uid>.evidence.md`** — append-only raw truth. One line per feedback event
  (`- 👍 like · \`libtr_…\` · 「prompt」 · ts`). Never modified. Doubles as the
  similarById **seed pool** and the basis for the profile.
- **`<uid>.memory.md`** — natural-language taste profile, **rewritten** on each
  update (LLM if `ANTHROPIC_API_KEY` is set, else a deterministic rule-based
  paragraph) plus a grounded "Facts" block. `/intent` injects this **verbatim**.
- **`<uid>.state.json`** — internal engine cache (affinities, anchors, IDF,
  scenarios). Derived/rebuildable from evidence; not part of the contract.

This matches the PRD-night contract exactly: `/feedback` appends to evidence.md
then rewrites memory.md; `/intent` reads memory.md; no database. The novelty gate
+ IDF distinctiveness decide *what* goes into the profile, so memory.md is sharper
than dumping all evidence at an LLM.

## Notes

- **Quota is shared across all teams** → tags are fetched once and cached in
  `.cache/`; the client stays under ~110 tagging calls/min.
- Per the challenge license, **Cyanite model outputs (`.cache/`) and runtime
  memories are git-ignored** — do not commit them.
- Optional LLM phrasing for `/your-sound` activates only if `ANTHROPIC_API_KEY`
  is set; it rephrases, never invents preferences.

---

## Design references

The memory design borrows established ideas from explainable / case-based
recommendation, so the "what to remember" and "why this track" decisions rest on
known methods rather than ad-hoc heuristics:

- **Explainable recommendation & tag-based justification** — Zhang & Chen,
  *Explainable Recommendation: A Survey and New Perspectives*
  ([arXiv:1804.11192](https://arxiv.org/pdf/1804.11192)). Basis for justifying
  every pick through the tags a user likes.
- **Scrutable natural-language user profiles** — *On Natural Language User
  Profiles for Transparent and Scrutable Recommendation*
  ([arXiv:2205.09403](https://arxiv.org/pdf/2205.09403),
  [v2](https://arxiv.org/html/2402.05810v1)). Motivates storing the profile as a
  human-readable, editable Markdown artifact instead of an opaque vector.
- **Case-based recommendation (exemplars)** — Smyth, *Case-Based Recommendation*
  ([overview](https://www.researchgate.net/publication/220800382_Case-Based_Recommendation)).
  Basis for the **anchor tracks**: explain a pick as "similar to these cases you liked".
- **Critiquing-based recommenders** — *Critiquing-based recommenders: survey and
  emerging trends*
  ([Springer](https://link.springer.com/article/10.1007/s11257-011-9108-6)).
  Theory behind directional feedback ("more X / less Y").
- **Memory activation (frequency + recency)** — the reinforcement-count + EMA
  weighting follows activation models of human memory, where reuse probability
  rises with usage frequency and recency.

Novelty/redundancy gating and salience-by-rarity (IDF) are standard
information-retrieval ideas applied here to decide *what is worth remembering*.
