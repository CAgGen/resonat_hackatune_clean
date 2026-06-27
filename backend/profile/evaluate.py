"""Offline evaluation on the real user data (positive-only ground truth).

For each user we HOLD OUT 30% of their liked tracks, build the taste memory from
the other 70%, and ask three intuitive questions:

  1) RECOGNITION (recommendation is reasonable):
     Does the profile rank the user's held-out *real* likes ABOVE tracks they did
     not like?  -> AUC. 0.5 = chance, 1.0 = perfect. We report it with plain tags
     and with IDF (distinctiveness) weighting, to show distinctiveness helps.

  2) PERSONALIZATION (it's their taste, not generic):
     Is a user's held-out scored higher by THEIR OWN profile than by other users'
     profiles?  -> own-AUC vs cross-AUC. A gap proves the memory is personal,
     not just "everything is ambient".

  3) COMPRESSION FIDELITY (storage is reasonable):
     The novelty gate keeps only some likes as anchors. Does an ANCHORS-ONLY
     profile predict held-out likes about as well as using ALL likes, with fewer
     items?  -> AUC(anchors) vs AUC(all) + items-kept ratio.

All scoring uses cached Cyanite tags (cheap; no extra similarity-search quota).

    python -m backend.profile.evaluate
"""
import statistics
from collections import defaultdict

from . import data, tags as tagmod, salience

CAT_DIMS = ["moods", "genres", "instruments", "character", "movement"]


# ---- tag vectors + cosine ---------------------------------------------------
def vec(track_tags, idf_weight):
    v = {}
    for d in CAT_DIMS:
        for t in track_tags.get(d) or []:
            w = salience.idf(d, t) if idf_weight else 1.0
            v[f"{d}:{t}"] = w
    return v


def mean_vec(vecs):
    acc = defaultdict(float)
    for v in vecs:
        for k, w in v.items():
            acc[k] += w
    n = max(len(vecs), 1)
    return {k: w / n for k, w in acc.items()}


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na = sum(w * w for w in a.values()) ** 0.5
    nb = sum(w * w for w in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def auc(pos_scores, neg_scores):
    """P(pos > neg) over all pairs (Mann-Whitney)."""
    if not pos_scores or not neg_scores:
        return None
    wins = ties = 0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos_scores) * len(neg_scores))


# ---- pure novelty-gate anchor selection (mirrors mdmemory, no IO) -----------
def select_anchors(track_tag_list, redundant_overlap=0.6):
    anchors = []  # each: {facets:set, distinctive:set}
    kept = []
    for tags in track_tag_list:
        fs = salience.facet_set(tags)
        fdist = {d["tag"] for d in salience.distinctive_tags(tags, dims=salience.FACET_DIMS)}
        if not anchors:
            anchors.append({"facets": fs, "distinctive": set(fdist)}); kept.append(tags); continue
        max_ov = max(_jac(fs, a["facets"]) for a in anchors)
        known = set().union(*[a["distinctive"] for a in anchors])
        new_facet = fdist - known
        if max_ov >= redundant_overlap and not new_facet:
            continue                      # redundant -> not kept as anchor
        anchors.append({"facets": fs, "distinctive": set(fdist)}); kept.append(tags)
    return kept


def _jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


# ---- split helper (deterministic) ------------------------------------------
def split(ids, frac_test=0.3):
    ids = sorted(ids)
    k = max(1, int(len(ids) * frac_test))
    return ids[:-k], ids[-k:]            # train, test


# ---- main -------------------------------------------------------------------
def main():
    data.load()
    users = [(u, data.user_liked_cyanite(u)) for u in data.user_ids()[:20]]
    users = [(u, L) for u, L in users if len(L) >= 10]
    print(f"evaluating {len(users)} users (>=10 likes each)\n")

    # negative pool = all liked tracks across these users (cached tags)
    pool = sorted({t for _, L in users for t in L})
    tagcache = {t: tagmod.for_track(t) for t in pool}      # cached -> cheap

    rec_plain, rec_idf, own_auc, cross_auc, anchor_auc, keep_ratio = [], [], [], [], [], []
    profiles_idf = {}

    for u, liked in users:
        train, test = split(liked)
        train_vecs = [vec(tagcache[t], True) for t in train]
        prof_all_idf = mean_vec(train_vecs)
        prof_all_plain = mean_vec([vec(tagcache[t], False) for t in train])
        profiles_idf[u] = prof_all_idf

        # negatives: tracks not liked by this user, sampled deterministically
        liked_set = set(liked)
        negs = [t for t in pool if t not in liked_set][::3][:50]

        pos_idf = [cosine(prof_all_idf, vec(tagcache[t], True)) for t in test]
        neg_idf = [cosine(prof_all_idf, vec(tagcache[t], True)) for t in negs]
        pos_pl = [cosine(prof_all_plain, vec(tagcache[t], False)) for t in test]
        neg_pl = [cosine(prof_all_plain, vec(tagcache[t], False)) for t in negs]
        rec_idf.append(auc(pos_idf, neg_idf))
        rec_plain.append(auc(pos_pl, neg_pl))
        own_auc.append(auc(pos_idf, neg_idf))

        # anchors-only profile
        anchors = select_anchors([tagcache[t] for t in train])
        keep_ratio.append(len(anchors) / max(len(train), 1))
        prof_anchor = mean_vec([vec(a, True) for a in anchors])
        anchor_auc.append(auc([cosine(prof_anchor, vec(tagcache[t], True)) for t in test],
                              [cosine(prof_anchor, vec(tagcache[t], True)) for t in negs]))

    # personalization: score each user's test with OTHER users' profiles
    for u, liked in users:
        _, test = split(liked)
        tv = [vec(tagcache[t], True) for t in test]
        others = [cosine(profiles_idf[o], v) for o, _ in users if o != u for v in tv]
        own = [cosine(profiles_idf[u], v) for v in tv]
        # cross-AUC: own test ranked by own vs by others (use neg=others' scores)
        cross_auc.append(auc(own, others))

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.mean(xs), 3) if xs else None

    print("=== 1) RECOGNITION — held-out likes ranked above non-likes (AUC) ===")
    print(f"   plain tags     : {avg(rec_plain)}")
    print(f"   IDF-weighted   : {avg(rec_idf)}   <- distinctiveness weighting")
    print("   (0.5 = chance, higher = profile recognizes their real taste)\n")

    print("=== 2) PERSONALIZATION — own taste vs generic ===")
    print(f"   own-vs-others AUC : {avg(cross_auc)}")
    print("   (>0.5 = a user's held-out fits THEIR profile better than other users')\n")

    print("=== 3) COMPRESSION FIDELITY — anchors-only vs all likes ===")
    print(f"   AUC all likes   : {avg(rec_idf)}")
    print(f"   AUC anchors only: {avg(anchor_auc)}")
    print(f"   items kept      : {round(100*avg(keep_ratio))}% of likes")
    print("   (similar AUC with fewer items => dedup keeps the signal => storage is reasonable)")


if __name__ == "__main__":
    main()
