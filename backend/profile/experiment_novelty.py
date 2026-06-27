"""Experiment: feed a real user's liked tracks through the novelty gate one by one
and watch what the memory decides to STORE vs treat as REDUNDANT — with reasons.

Shows the explainable 'what to remember' behaviour on user 4006097.

    python -m backend.profile.experiment_novelty
"""
from . import mdmemory, data

USER = "exp_4006097"   # fresh memory


def main():
    # start clean
    import os
    for p in (mdmemory._evidence_path(USER), mdmemory._memory_path(USER),
              mdmemory._state_path(USER)):
        if os.path.exists(p):
            os.remove(p)

    data.load()
    liked = data.user_liked_cyanite("4006097")
    print(f"feeding {len(liked)} liked tracks through the novelty gate\n")

    n_new = n_reinf = 0
    for i, tid in enumerate(liked, 1):
        summ = mdmemory.record_feedback(USER, tid, "like", prompt="(replay likes)")
        d = summ["last_decision"]
        if d["decision"] == "reinforce":
            n_reinf += 1
            mark = "·  redundant"
        else:
            n_new += 1
            mark = "▲  STORED   "
        print(f"{i:2d}. {mark}  {tid[-6:]}  nov={int(d['novelty']*100):3d}%  {d['reason']}")

    print(f"\n→ {len(liked)} likes  =>  {n_new} anchors stored,  {n_reinf} reinforced (deduped)")

    s = mdmemory.summary(USER)
    print(f"\n=== ANCHOR TRACKS (the memory kept {len(s['exemplars'])} of {len(liked)}) ===")
    for e in s["exemplars"]:
        print(f"  ×{e['count']:2d}  {e['track_id'][-6:]}  distinctive: {', '.join(e['distinctive']) or '—'}")

    print("\n=== DISTINCTIVE TO THIS USER (high-IDF, recurring) ===")
    print("  " + ", ".join(f"{d['tag']}(idf {d['idf']})" for d in s["distinctive"]))

    print("\n=== headline ===")
    print(" ", s["headline"])
    print(f"\nmemory.md   -> {mdmemory._memory_path(USER)}")
    print(f"evidence.md -> {mdmemory._evidence_path(USER)}")


if __name__ == "__main__":
    main()
