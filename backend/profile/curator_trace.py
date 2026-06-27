"""Trace ONE like through the curator agent: show the memory BEFORE, the agent's
decision, and the memory AFTER — so you can see exactly how the profile updates.

    python -m backend.profile.curator_trace [user_id] [k_base] [x_index]
"""
import copy
import os
import sys

from . import mdmemory, tags as tagmod, data, salience, curator


def snap(uid):
    s = mdmemory.summary(uid)
    return {
        "moods": {x["tag"]: x["aff"] for x in s["likes"]["moods"]},
        "genres": {x["tag"]: x["aff"] for x in s["likes"]["genres"]},
        "bpm": s["numeric"].get("bpm"),
        "anchors": len(s["exemplars"]),
        "headline": s["headline"],
    }


def main():
    uid = (sys.argv[1] if len(sys.argv) > 1 else "trace_demo")
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    xi = int(sys.argv[3]) if len(sys.argv) > 3 else 9

    for p in (mdmemory._evidence_path(uid), mdmemory._memory_path(uid), mdmemory._state_path(uid)):
        if os.path.exists(p):
            os.remove(p)

    data.load()
    src = data.user_liked_cyanite("3457621")
    base, track_x = src[:k], src[xi]
    disp = data.track_display(track_x)
    name, artist = disp.get("name") or track_x[-6:], disp.get("artist") or "?"

    # build the base profile
    for cid in base:
        curator.curate(uid, cid)

    before = snap(uid)
    xt = tagmod.for_track(track_x)
    state = mdmemory.load(uid)
    sim = curator.analyze_similarity(state, xt)

    print("=" * 72)
    print(f"BEFORE this like — profile is still INCOMPLETE (built from {k} of "
          f"{len(src)} likes)")
    print("=" * 72)
    print(f"  headline : {before['headline']}")
    print(f"  top moods : {_fmt(before['moods'])}")
    print(f"  top genres: {_fmt(before['genres'])}")
    print(f"  ~BPM={before['bpm']}   anchors={before['anchors']}")

    print(f"\n>>> USER LIKES (#{xi+1} of {len(src)}):  «{name}» — {artist}")
    print(f"    track id : {track_x}")
    print(f"    audio    : {disp.get('audio_url')}")
    print(f"    Cyanite tags:")
    print(f"       mood        : {xt['moods']}")
    print(f"       genre       : {xt['genres']}")
    print(f"       instruments : {(xt['instruments'] or [])[:4]}")
    print(f"       character   : {xt['character']}")
    print(f"       bpm/tempo   : {xt['bpm']} / {xt['tempo']}   "
          f"valence={xt['valence']} arousal={xt['arousal']}")

    print(f"\n--- SIMILARITY to current profile ---")
    print(f"    taste-fit (cosine)      : {sim['fit']:.2f}")
    print(f"    nearest-anchor overlap  : {sim['overlap']:.2f}"
          f"{'  («'+', '.join((sim['nearest'].get('distinctive') or [])[:2])+'»)' if sim['nearest'] else ''}")
    print(f"    new facets introduced   : {sim['new_facet'] or '—'}")

    # the agent decides
    decision = curator.decide(state, xt, sim)
    print(f"\n--- AGENT DECISION ({'LLM' if False else 'rule'}) ---")
    print(f"    operation: {decision['operation']}")
    print(f"    reason   : {decision['reason']}")

    # apply (via curate, which persists)
    curator.curate(uid, track_x)
    after = snap(uid)

    print("\n" + "=" * 72)
    print("AFTER this like — what changed")
    print("=" * 72)
    print(f"  anchors : {before['anchors']} -> {after['anchors']}"
          f"   {'(＋new anchor)' if after['anchors']>before['anchors'] else '(reinforced, no new anchor)'}")
    print(f"  ~BPM    : {before['bpm']} -> {after['bpm']}")
    print("  affinity moves for this track's tags:")
    for dim in ("moods", "genres"):
        for tag in xt[dim]:
            b = before[dim].get(tag, 0.0)
            a = after[dim].get(tag, 0.0)
            if abs(a - b) > 1e-6 or tag not in before[dim]:
                arrow = "NEW" if tag not in before[dim] else f"{b:+.2f}→{a:+.2f}"
                print(f"     {dim[:-1]:6s} {tag:14s} {arrow}")
    print(f"\n  headline BEFORE: {before['headline']}")
    print(f"  headline AFTER : {after['headline']}")


def _fmt(d):
    return ", ".join(f"{k}({v:+.2f})" for k, v in list(d.items())[:4])


if __name__ == "__main__":
    main()
