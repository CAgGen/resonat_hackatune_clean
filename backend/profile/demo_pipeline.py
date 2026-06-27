"""One-shot demo: pick an information-rich user from the GT data and run the whole
user-profile pipeline on them.

  pick richest fully-cached user
    -> replay their likes through record_feedback  (evidence.md + memory.md + state + history)
    -> your-sound summary
    -> Taste Card + evolution Timeline + Year report  (PNGs)

Re-ranking (memory -> recommendation) needs the Cyanite similar endpoint, so run
that separately:  python -m backend.profile.recommend <user_id>

    python -m backend.profile.demo_pipeline [user_id]
"""
import os
import sys
from collections import Counter

from . import data, tags as tagmod, cyanite_tags, config, mdmemory, visualize


def _cached(cid):
    return os.path.exists(cyanite_tags._cache_path(cid, config.PROFILE_MODELS))


def pick_demo_user():
    """Richest fully-cached user: most distinct moods+genres+instruments, with a
    healthy like count (15-60). Zero API quota (only already-cached users)."""
    data.load()
    best, best_score = None, -1
    for u in data.user_ids():
        liked = data.user_liked_cyanite(u)
        if not (15 <= len(liked) <= 60) or not all(_cached(c) for c in liked):
            continue
        div = Counter()
        for c in liked:
            t = tagmod.for_track(c)
            div.update(set(t["moods"]) | set(t["genres"]) | set(t["instruments"]))
        score = len(div)
        if score > best_score:
            best, best_score = u, score
    return best


def run(user_id):
    # fresh memory for the demo
    for p in (mdmemory._evidence_path(user_id), mdmemory._memory_path(user_id),
              mdmemory._state_path(user_id)):
        if os.path.exists(p):
            os.remove(p)

    liked = data.user_liked_cyanite(user_id)
    print(f"=== DEMO USER {user_id} · {len(liked)} liked tracks ===\n")
    print("1) replaying likes through record_feedback ...")
    for i, cid in enumerate(liked):
        prompt = "(late night)" if i % 2 else "(focus)"   # 2 pseudo-sessions
        mdmemory.record_feedback(user_id, cid, "like", prompt=prompt)

    s = mdmemory.summary(user_id)
    print("\n2) your-sound:")
    print("   ", s["headline"])
    print("    distinctive:", ", ".join(d["tag"] for d in s["distinctive"]))
    print("    anchors:", len(s["exemplars"]), "| moods:",
          [x["tag"] for x in s["likes"]["moods"][:4]])

    print("\n3) rendering visuals ...")
    print("    card     :", visualize.render_card(user_id))
    print("    timeline :", visualize.render_timeline(user_id))
    from . import yearreport
    path, _ = yearreport.render_report(user_id)
    print("    year     :", path)

    print("\n4) files written:")
    print("    memory.md   :", mdmemory._memory_path(user_id))
    print("    evidence.md :", mdmemory._evidence_path(user_id))
    print("\nnext (needs network): python -m backend.profile.recommend", user_id)


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else pick_demo_user()
    if not uid:
        raise SystemExit("no fully-cached user found in 15-60 like range")
    run(uid)
