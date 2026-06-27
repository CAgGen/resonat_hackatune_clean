# Taste Memory — Experiments & Evaluation

How we decide **what to remember** about a listener, and evidence (on the real
user data) that the storage, the recommendations, and the explanations are sound.

All numbers use cached Cyanite tags; reproduce with the commands at the bottom.

---

## The mechanism (one paragraph)

Each like is passed through a **novelty gate**. A track becomes a new *anchor*
only if it occupies a genuinely new **facet** (genre / mood / character) of the
user's taste; a like that overlaps an existing anchor just **reinforces** it
(count ++), and rare instruments/textures **enrich** the nearest anchor instead
of spawning a new one. What we store per track is filtered by **distinctiveness**
(IDF): rare-in-catalog tags like `asianFlute` are kept; ubiquitous ones like
`drums` are skipped. Every write emits a human-readable reason — the memory is a
Markdown file you can read.

---

## Experiment 1 — Novelty gate dedups without losing the picture

Replayed user **4006097**'s 25 liked tracks through the gate:

> **25 likes → 14 anchors stored, 11 reinforced (44% deduped).**

Sample decisions (each is the reason written into memory):

| like | decision | reason |
|---|---|---|
| metal track | ▲ store | `new facet: metal, aggressive, rock` |
| another ambient | · dedup | `83% facet overlap with anchor …; reinforced (×3)` |
| ambient + oboe | · dedup | `reinforced (×2); noted new texture: oboe, strings, woodwinds` |

The 14 anchors form a small, legible map of the user's taste regions; the most
reinforced anchors (`×4`) are the core, single-count anchors are the edges
(metal, asian). → memory stores *information*, not duplicates.

---

## Experiment 2 — Offline evaluation on real likes (hold-out)

For 16 users (≥10 likes each) we hold out 30% of likes, build the profile from
the rest, and measure (AUC: 0.5 = chance). Negatives are **other ambient-leaning
users' tracks** (hard negatives), so these numbers are not inflated by an easy
"ambient vs non-ambient" split.

| Question | Metric | Result |
|---|---|---|
| **Are recommendations reasonable?** Does the profile rank held-out *real* likes above non-likes? | Recognition AUC | **0.705** plain → **0.759** with IDF |
| **Is it their taste, not generic?** Own profile vs other users' on the same held-out | Personalization AUC | **0.799** |
| **Is the storage reasonable?** Anchors-only vs all-likes profile | Compression | **0.777** (anchors) vs 0.759 (all), keeping only **57%** of likes |

**Takeaways**
- Recognition **0.76** on hard negatives → the profile genuinely captures taste.
- IDF (distinctiveness) weighting **beats plain tags (0.76 > 0.71)** → storing
  *rare/characteristic* tags is the right call.
- Personalization **0.80** → memory is personal, not "everyone is ambient".
- Anchors-only **matches/slightly beats** all-likes with **43% fewer items** →
  the novelty gate removes redundancy *and noise* — storage is justified.

---

## Experiment 3 — Faithfulness: do our explanations track the black box?

We can't see Cyanite's embeddings, so we explain similarity via shared tags.
Is that faithful? Over **60 (seed, neighbor) pairs** from Cyanite similar-by-ID,
we correlate Cyanite's similarity score with our tag-overlap:

| our explainable metric | Pearson | Spearman |
|---|---|---|
| **IDF tag-cosine** | **0.363** | **0.379** |
| facet-Jaccard | 0.21 | 0.215 |

Positive and consistent → when we say *"similar because it shares calm / ambient
/ piano"*, that reflects what Cyanite's model actually measured. IDF-cosine again
beats raw overlap. The correlation is moderate (not 1.0) for two honest reasons:
(a) Cyanite's audio model hears production/texture that tags don't encode, and
(b) **range restriction** — similar-by-ID only returns already-similar tracks, so
the score band is narrow, which attenuates correlation. So 0.36 is a *lower bound*
on how well tags explain the model.

See `analysis/faithfulness.png`.

---

## What the three experiments together establish

1. **Storage is reasonable** — novelty-gated dedup keeps 57% of likes with **equal
   or better** predictive power (Exp 1 + Exp 2 compression).
2. **Recommendations are reasonable** — profiles recognize real held-out likes at
   AUC 0.76 and are personalized at 0.80 (Exp 2).
3. **Explanations are faithful** — our tag-based "why" positively tracks Cyanite's
   own similarity (Exp 3), so the explanations aren't post-hoc fiction.
4. **Distinctiveness (IDF) helps everywhere** — recognition 0.71→0.76 and the
   strongest faithfulness correlation.

---

## Reproduce

```bash
# from repo root, hackatune env
python -m backend.profile.experiment_novelty   # Exp 1: novelty gate on user 4006097
python -m backend.profile.evaluate             # Exp 2: hold-out AUC over 16 users
python -m backend.profile.faithfulness         # Exp 3: tag-overlap vs Cyanite score (+ scatter)
```

Catalog base rates for IDF live in `tag_base_rates.json` (aggregate tag
frequencies over 844 tracks; no raw model outputs, per the challenge license).
