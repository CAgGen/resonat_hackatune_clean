"""LLM Memory-Curator demo (Aalto GPT) — update-profile then validate it.

For one user (default 3457621, 41 likes), split the likes 20 / 16 / 5:
  STAGE 1  build a taste profile from the first 20 likes              (LLM)
  STAGE 2  stream the next 16 likes one by one, each with a mocked
           timestamp + user opinion; an AGENT decides how to update    (LLM)
  STAGE 3  from the final profile, the LLM writes a Cyanite search
           query, we run it, and check overlap with the held-out 5     (eval)

    python -m backend.profile.llm_curator_demo [user_id]
"""
import json
import sys

from . import data, tags as tagmod, cyanite_tags, aalto_llm, discover
from .evaluate import vec, cosine

# richer model set just for the LLM workflow (kept separate from PROFILE_MODELS so
# the global tag cache isn't invalidated): adds fine moods, use-cases, free/sub genre, key
ENRICHED_MODELS = ["MainGenreV2", "SubgenreV2", "FreeGenreV3", "MoodSimpleV2",
                   "MoodAdvancedV2", "InstrumentsV2", "CharacterV2", "MovementV2",
                   "BpmV2", "TempoV1", "KeyV2", "ValenceArousalV2", "MusicalEraV2",
                   "MusicForV1", "VocalsV2", "AutoDescriptionV2"]


def etags(cid):
    return tagmod.normalize(cyanite_tags.get_model_outputs(cid, ENRICHED_MODELS))


CAPS = {"moods": 8, "genres": 6, "instruments": 8, "distinctive": 6}


def trim_profile(p):
    """Deterministic guard: keep the whole profile under ~200 words."""
    for k, n in CAPS.items():
        if isinstance(p.get(k), list):
            p[k] = p[k][:n]
    if isinstance(p.get("summary"), str):
        p["summary"] = " ".join(p["summary"].split()[:60])
    return p


def wc(p):
    """Rough word count of the whole profile (for display)."""
    import json as _j
    return len(_j.dumps(p, ensure_ascii=False).replace(",", " ").split())

OPINIONS = [
    "love the piano here", "perfect for late-night focus", "a bit repetitive but the mood is right",
    "this one really hit me", "great on a rainy day", "feels like a film score",
    "calming after a long day", "would put this on a study playlist", "the strings give me chills",
    "good but a little too slow", "instant favourite", "reminds me of someone",
    "nice for the morning commute", "dreamy, I zoned out", "darker than usual but I liked it",
    "wholesome, made me smile",
]
HOURS = [23, 1, 9, 22, 14, 0, 20, 16, 2, 19, 8, 21, 7, 3, 23, 11]
MONTHS = ["Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
          "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"]


def desc(cid):
    t = etags(cid)
    d = data.track_display(cid)
    return {"name": d.get("name") or cid[-6:], "artist": d.get("artist"),
            "mood": t["moods"], "mood_fine": (t["moodAdvanced"] or [])[:5],
            "genre": t["genres"], "subgenre": t["subgenres"],
            "free_genre": t["freeGenres"], "instruments": (t["instruments"] or [])[:5],
            "character": t["character"], "music_for": (t["musicFor"] or [])[:6],
            "bpm": t["bpm"], "tempo": t["tempo"], "key": t["key"], "era": t["era"],
            "valence": t["valence"], "arousal": t["arousal"],
            "energy": t["energy"], "emotion": t["emotion"],
            "description": t.get("description")}


def main():
    uid = sys.argv[1] if len(sys.argv) > 1 else "3457621"
    data.load()
    liked = data.user_liked_cyanite(uid)
    build, update, held = liked[:20], liked[20:36], liked[36:41]
    print(f"user {uid}: {len(liked)} likes  →  build {len(build)} / update {len(update)} / "
          f"eval {len(held)}\n")

    # ---------- STAGE 1: build profile from 20 likes ----------
    print("=" * 70 + "\nSTAGE 1 — build taste profile from 20 likes (LLM)\n" + "=" * 70)
    sys1 = ("You are a music taste analyst. From the user's liked tracks (each with "
            "Cyanite audio tags + an auto description), infer a concise taste profile. "
            "Return ONLY JSON: moods[], genres[], instruments[], tempo, energy, "
            "distinctive[] (standout traits), summary (second person). "
            "HARD LIMIT: the whole profile must stay UNDER 200 words — "
            "moods<=8, genres<=6, instruments<=8, distinctive<=6, summary<=60 words.")
    profile = trim_profile(aalto_llm.complete_json(json.dumps([desc(c) for c in build]), system=sys1))
    print(json.dumps(profile, ensure_ascii=False, indent=1)[:1200])
    print(f"  [profile ~{wc(profile)} words]")

    # ---------- STAGE 2: agent updates the profile per like ----------
    print("\n" + "=" * 70 + "\nSTAGE 2 — agent updates the profile over 16 more likes (LLM)\n" + "=" * 70)
    sys2 = ("You curate a user's music taste profile. Given the CURRENT profile JSON and a "
            "NEW liked track (audio tags + the user's note + timestamp), decide whether and "
            "how to update the profile. Be STABLE and CONCISE: do NOT just append — merge or "
            "replace so the whole profile stays UNDER 200 words (moods<=8, genres<=6, "
            "instruments<=8, distinctive<=6, summary<=60 words). Prefer refining existing "
            "entries over adding new ones. Return ONLY JSON: {\"profile\": <updated full "
            "profile, same schema>, \"change\": <one short line: what changed and why, or "
            "'no change'>}.")
    for i, cid in enumerate(update):
        ctx = {"current_profile": profile, "new_track": desc(cid),
               "user_note": OPINIONS[i % len(OPINIONS)],
               "timestamp": f"{MONTHS[i]} {1+i}, {HOURS[i % len(HOURS)]}:00"}
        out = aalto_llm.complete_json(json.dumps(ctx, ensure_ascii=False), system=sys2)
        profile = trim_profile(out.get("profile", profile))
        print(f"  +like {i+1:2d} «{desc(cid)['name'][:26]:26}» [{wc(profile):3d}w]"
              f"  → {out.get('change','?')[:90]}")

    print("\n--- FINAL profile summary ---")
    print(" ", profile.get("summary"))
    print("  moods:", profile.get("moods"), "| genres:", profile.get("genres"))

    # ---------- STAGE 3: profile -> Cyanite query -> overlap with held-out 5 ----------
    print("\n" + "=" * 70 + "\nSTAGE 3 — recommend from the profile, check overlap with 5 held-out\n" + "=" * 70)
    sys3 = ("Given this music taste profile, write ONE short natural-language search "
            "query — a single sentence a person would actually type (max 20 words), "
            "capturing the CORE vibe. No tag dumps, no lists, no semicolons. "
            "Return ONLY JSON: {\"query\": <string>}.")
    q = aalto_llm.complete_json(json.dumps(profile, ensure_ascii=False), system=sys3)["query"]
    q = q.strip()[:300]
    print(f'  LLM-generated Cyanite query:\n   "{q}"\n')

    try:
        recs = [cid for cid, _ in discover.search(q, limit=50)]
    except Exception as e:
        print(f"  (search failed: {str(e)[:80]}; retrying with a trimmed query)")
        recs = [cid for cid, _ in discover.search(" ".join(q.split()[:12]), limit=50)]
    held_set = set(held)
    exact = [c for c in recs if c in held_set]

    # soft overlap: a held-out track is "covered" if some rec is tag-close to it
    covered = []
    for h in held:
        ht = vec(tagmod.for_track(h), idf_weight=True)
        best = max((cosine(ht, vec(tagmod.for_track(r), idf_weight=True)) for r in recs[:30]),
                   default=0.0)
        covered.append((desc(h)["name"], round(best, 2)))

    print(f"  recommended {len(recs)} tracks (full catalog)")
    print(f"  EXACT overlap with held-out 5 : {len(exact)}  {[e[-6:] for e in exact]}")
    print(f"  SOFT coverage (nearest rec tag-cosine per held-out track):")
    for name, sc in covered:
        mark = "✓" if sc >= 0.6 else " "
        print(f"     [{mark}] {name[:34]:34} closest rec = {sc}")
    soft = sum(1 for _, sc in covered if sc >= 0.6)
    print(f"\n  → exact hits {len(exact)}/5 · soft-covered {soft}/5  "
          f"(recommendations land in the held-out taste region)")


if __name__ == "__main__":
    main()
