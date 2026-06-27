"""Faithfulness check: does our explainable tag-overlap track Cyanite's black-box
similarity score?

For several seed tracks we call Cyanite similar-by-ID (their trained model's
similarity score per neighbor), then compute OUR tag-based similarity (IDF-cosine
and facet-Jaccard) for the same (seed, neighbor) pairs, and correlate the two.

A positive correlation means: when we explain "this is similar because it shares
calm/ambient/piano", that explanation faithfully reflects what Cyanite's model
actually measured — our explanations aren't post-hoc fiction.

    python -m backend.profile.faithfulness
"""
import os
import statistics

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config, data, tags as tagmod, salience
from .evaluate import vec, cosine

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

_session = requests.Session()
_session.headers.update({"x-api-key": config.CYANITE_API_KEY})


def find_similar(cyanite_id, limit=15):
    r = _session.post(
        f"{config.CYANITE_BASE_URL}/private-alpha/library-tracks/{cyanite_id}/similar",
        params={"limit": limit}, json={}, timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])


def _jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def pearson(x, y):
    return round(statistics.correlation(x, y), 3) if len(x) > 1 else None


def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    return pearson(rank(x), rank(y))


def main():
    data.load()
    seeds = data.user_liked_cyanite("4006097")[:6]
    print(f"probing {len(seeds)} seeds via Cyanite similar-by-ID...\n")

    cy, cos, jac = [], [], []
    for sd in seeds:
        sd_tags = tagmod.for_track(sd)
        sd_vec = vec(sd_tags, idf_weight=True)
        sd_facets = salience.facet_set(sd_tags)
        for it in find_similar(sd, limit=15):
            nb = it["track"]["id"]
            score = it.get("score")
            if score is None:
                continue
            nb_tags = tagmod.for_track(nb)
            cy.append(score)
            cos.append(cosine(sd_vec, vec(nb_tags, idf_weight=True)))
            jac.append(_jac(sd_facets, salience.facet_set(nb_tags)))
        print(f"  {sd[-6:]}: collected {len(cy)} pairs so far")

    print(f"\n=== FAITHFULNESS over {len(cy)} (seed, neighbor) pairs ===")
    print(f"Cyanite score  vs  our IDF tag-cosine : Pearson {pearson(cy, cos)}  Spearman {spearman(cy, cos)}")
    print(f"Cyanite score  vs  our facet-Jaccard  : Pearson {pearson(cy, jac)}  Spearman {spearman(cy, jac)}")
    print("(positive => our tag-based explanation faithfully tracks Cyanite's model)")

    # scatter for the demo
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(cy, cos, s=22, alpha=0.6)
    if len(cy) > 1:
        b1, b0 = _fit(cy, cos)
        xs = [min(cy), max(cy)]
        ax.plot(xs, [b0 + b1 * x for x in xs], "r-", lw=2,
                label=f"Pearson r={pearson(cy, cos)}")
        ax.legend()
    ax.set_xlabel("Cyanite similarity score (black-box model)")
    ax.set_ylabel("our IDF tag-cosine (explainable)")
    ax.set_title("Faithfulness: explainable tag-overlap vs Cyanite's similarity")
    out = os.path.join(OUT_DIR, "faithfulness.png")
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print("\nscatter ->", out)


def _fit(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    b1 = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / sum((v - mx) ** 2 for v in x)
    return b1, my - b1 * mx


if __name__ == "__main__":
    main()
