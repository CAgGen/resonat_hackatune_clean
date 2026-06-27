"""Memory -> recommendation: re-rank candidate tracks by the user's taste memory
and explain each pick from what we remember.

This closes the loop: the search side (teammate) produces candidate track ids
(prompt / similarById); we re-order them by taste fit and attach a grounded
"why this track" that points back to the user's stored profile.

    rerank(user_id, candidate_ids) -> [{track_id, score, why, tags_brief}, ...]

Demo (pulls candidates via Cyanite similar from the user's seed pool):
    python -m backend.profile.recommend [user_id]
"""
import sys

import requests

from . import config, mdmemory, tags as tagmod, salience
from .evaluate import vec, cosine

CAT_DIMS = ["moods", "genres", "instruments", "character", "movement"]
AVOID_PENALTY = 0.12


def _why(track_tags, s, avoids):
    """Explain a candidate from the stored profile. Returns (text, penalty)."""
    likes = {d: {x["tag"] for x in s["likes"][d]} for d in CAT_DIMS}
    bits = []
    for dim, label in [("moods", "mood"), ("genres", "genre"), ("instruments", "instruments")]:
        shared = [t for t in (track_tags.get(dim) or []) if t in likes[dim]]
        if shared:
            bits.append(f"your {label} {', '.join(shared[:2])}")
    distinct = {d["tag"] for d in s["distinctive"]}
    matched_dist = [t for d in CAT_DIMS for t in (track_tags.get(d) or []) if t in distinct]
    if matched_dist:
        bits.append(f"your signature {', '.join(sorted(set(matched_dist))[:2])}")
    # nearest anchor
    fs = salience.facet_set(track_tags)
    best = None
    for e in s.get("exemplars", []):
        ov = len(fs & set(e["facets"])) / max(len(fs | set(e["facets"])), 1)
        if not best or ov > best[0]:
            best = (ov, e)
    if best and best[0] >= 0.5:
        d = ", ".join((best[1].get("distinctive") or [])[:2]) or best[1]["track_id"][-6:]
        bits.append(f"close to your anchor «{d}»")
    avoid_hits = sorted({t for d in CAT_DIMS for t in (track_tags.get(d) or []) if t in avoids})
    text = "Matches " + ("; ".join(bits) if bits else "your overall sound")
    if avoid_hits:
        text += f" — but has {', '.join(avoid_hits)} you usually avoid"
    return text + ".", AVOID_PENALTY * len(avoid_hits)


def rerank(user_id, candidate_ids, limit=None):
    """Re-rank candidates by taste fit (IDF tag-cosine) minus avoid penalties,
    each with a memory-grounded explanation."""
    st = mdmemory.load(user_id)
    pv = mdmemory.taste_vector(user_id, _state=st)
    s = mdmemory.summary(user_id, _state=st)
    avoids = {v for vs in s["avoids"].values() for v in vs}
    out = []
    for cid in candidate_ids:
        try:
            t = tagmod.for_track(cid)
        except Exception:
            continue
        fit = cosine(pv, vec(t, idf_weight=True))
        why, pen = _why(t, s, avoids)
        out.append({"track_id": cid, "score": round(max(fit - pen, 0.0), 3),
                    "taste_fit": round(fit, 3), "penalty": round(pen, 3),
                    "why": why,
                    "tags_brief": f"{(t.get('genres') or ['?'])[0]}/"
                                  f"{'/'.join((t.get('moods') or [])[:2])}"})
    out.sort(key=lambda r: -r["score"])
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# demo: pull candidates from Cyanite and compare raw order vs memory re-rank
# ---------------------------------------------------------------------------
def _candidates_via_cyanite(seed_ids, limit=20):
    r = requests.post(f"{config.CYANITE_BASE_URL}/private-alpha/library-tracks/similar",
                      headers={"x-api-key": config.CYANITE_API_KEY},
                      params={"limit": limit},
                      json={"tracks": [{"id": s} for s in seed_ids[:10]]}, timeout=60)
    r.raise_for_status()
    return [(it["track"]["id"], it.get("score")) for it in r.json().get("items", [])]


def main():
    uid = sys.argv[1] if len(sys.argv) > 1 else "exp_4006097"
    seeds = mdmemory.seed_pool(uid)
    if not seeds:
        raise SystemExit(f"no memory for {uid}; run experiment_novelty first")
    print(f"user {uid}: {len(seeds)} seeds → Cyanite similar → memory re-rank\n")

    cands = _candidates_via_cyanite(seeds, limit=20)
    cyrank = {cid: i for i, (cid, _) in enumerate(cands)}
    ranked = rerank(uid, [cid for cid, _ in cands], limit=8)

    print("=== TOP 8 after memory re-rank (vs Cyanite raw rank) ===")
    for r in ranked:
        moved = cyrank.get(r["track_id"], 0)
        print(f"  fit={r['taste_fit']:.3f}  (cyanite #{moved+1:>2})  {r['track_id'][-6:]}  {r['tags_brief']}")
        print(f"      why: {r['why']}")


if __name__ == "__main__":
    main()
