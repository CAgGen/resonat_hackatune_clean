"""Simple test: simulate a user giving like/dislike/note feedback, watch the
markdown taste memory build up. Assumes feedback events are available (we fake
a stream here); the real /feedback endpoint would call record_feedback() the same way.

Run:
    python -m backend.profile.test_feedback           # uses a data-pack user's real tracks
"""
import os
import sys

from . import mdmemory, data

USER = "demo_user"   # write to a throwaway profile so we don't clobber real ones


def main():
    # start clean (evidence.md is append-only, so reruns would otherwise stack)
    import os
    for p in (mdmemory._evidence_path(USER), mdmemory._memory_path(USER),
              mdmemory._state_path(USER)):
        if os.path.exists(p):
            os.remove(p)

    # grab some real catalog track ids to react to (from a data-pack user)
    data.load()
    real = data.user_liked_cyanite("4006097")
    pool = real[:8] if real else [f"libtr_demo{i}" for i in range(8)]

    # a faked feedback stream: (verdict, track, prompt, note)
    events = [
        ("like",    pool[0], "late night focus",      None),
        ("like",    pool[1], "late night focus",      None),
        ("dislike", pool[2], "late night focus",      None),
        ("like",    pool[3], "late night focus",      "love the piano here"),
        ("skip",    pool[4], "late night focus",      None),
        ("like",    pool[5], "something darker",      None),
        ("like",    pool[6], "something darker",      None),
        ("note",    pool[0], None,                    "no aggressive stuff please"),
    ]

    print("=== feeding feedback ===")
    summ = None
    for verdict, tid, prompt, note in events:
        summ = mdmemory.record_feedback(USER, tid, verdict, prompt=prompt, note=note)
        print(f"  {verdict:7s} {tid}  -> like={summ['counts']['like']} "
              f"dislike={summ['counts']['dislike']}")

    print("\n=== summary (GET /your-sound) ===")
    print("headline:", summ["headline"])
    print("likes:", {d: [x["tag"] for x in v] for d, v in summ["likes"].items() if v})
    print("avoids:", summ["avoids"])
    print("scenarios:", summ["scenarios"])
    print("notes:", summ["notes"])

    print("\n=== seed_pool (for /feedback similarById) ===")
    print("all likes:", mdmemory.seed_pool(USER))
    print("'something darker' only:", mdmemory.seed_pool(USER, prompt="something darker"))

    print("\n=== prompt_injection (for /intent) ===")
    print(mdmemory.prompt_injection(USER))

    print(f"\n=== memory.md written to: {mdmemory._memory_path(USER)} ===")
    print(open(mdmemory._memory_path(USER)).read()[:1200])
    print(f"\n=== evidence.md written to: {mdmemory._evidence_path(USER)} ===")
    print(open(mdmemory._evidence_path(USER)).read()[:600])


if __name__ == "__main__":
    main()
