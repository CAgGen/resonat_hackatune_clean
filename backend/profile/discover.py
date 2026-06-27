"""Profile -> text prompt -> Cyanite prompt search -> NEW track recommendations.

Turns the user's taste memory into a natural-language query, sends it to Cyanite's
free-text recommendation API, drops tracks the user already liked (so results are
genuine discoveries), then re-ranks the rest by the memory and explains each pick.

    python -m backend.profile.discover [user_id] [limit]
"""
import sys

import requests

from . import config, mdmemory, data
from .recommend import rerank

CAT = ["moods", "genres", "instruments"]


def build_search_prompt(user_id):
    """Compose a concise Cyanite free-text query from the taste profile."""
    s = mdmemory.summary(user_id)
    moods = [x["tag"] for x in s["likes"]["moods"][:3]]
    genres = [x["tag"] for x in s["likes"]["genres"][:2]]
    insts = [x["tag"] for x in s["likes"]["instruments"][:3]]
    distinct = [d["tag"] for d in s["distinctive"][:3]]
    bpm = s["numeric"].get("bpm")
    tempo = ("slow" if bpm and bpm < 80 else "mid-tempo" if bpm and bpm < 110 else "upbeat") if bpm else None
    voc = s["vocals"][0]["tag"] if s["vocals"] else None

    parts = []
    if moods:
        parts.append(", ".join(moods))
    if genres:
        parts.append(" & ".join(genres))
    if insts:
        parts.append("built on " + ", ".join(insts))
    if tempo:
        parts.append(f"{tempo}" + (f" around {round(bpm)} BPM" if bpm else ""))
    if voc:
        parts.append(voc)
    if distinct:
        parts.append("with " + ", ".join(distinct) + " textures")
    return ", ".join(parts)


def search(query, limit=30):
    """Cyanite free-text / prompt recommendation."""
    r = requests.post(f"{config.CYANITE_BASE_URL}/private-alpha/library-tracks/search",
                      headers={"x-api-key": config.CYANITE_API_KEY},
                      params={"limit": limit}, json={"query": query}, timeout=60)
    r.raise_for_status()
    return [(it["track"]["id"], it.get("score")) for it in r.json().get("items", [])]


def discover(user_id, limit=10, exclude_liked=True):
    prompt = build_search_prompt(user_id)
    results = search(prompt, limit=max(limit * 3, 30))
    liked = set(mdmemory.seed_pool(user_id)) | set(data.user_liked_cyanite(user_id))
    cand = [cid for cid, _ in results if not (exclude_liked and cid in liked)]
    ranked = rerank(user_id, cand, limit=limit)
    return {"user_id": user_id, "prompt": prompt, "results": ranked}


def main():
    uid = sys.argv[1] if len(sys.argv) > 1 else "3457621"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    out = discover(uid, limit=limit)
    print(f"=== DISCOVER for user {uid} ===")
    print(f"\ninferred prompt → Cyanite text search:\n  \"{out['prompt']}\"\n")
    print(f"=== TOP {len(out['results'])} NEW tracks (excluding already-liked) ===")
    for r in out["results"]:
        disp = data.track_display(r["track_id"])
        name = disp.get("name") or r["track_id"][-6:]
        artist = f" — {disp['artist']}" if disp.get("artist") else ""
        print(f"\n  fit={r['taste_fit']:.3f}  {name}{artist}  [{r['tags_brief']}]")
        print(f"      why: {r['why']}")


if __name__ == "__main__":
    main()
