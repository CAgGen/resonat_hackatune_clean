"""Memory-curator agent.

On each like, it (1) measures how similar the new track is to the user's existing
profile, then (2) an AGENT decides whether and how to change the profile — choosing
one explainable operation:

  NOOP            already well-represented; remember nothing new
  REINFORCE       strengthen an existing taste region (anchor count++ + light learn)
  ADD_FACET       a genuinely new region; create an anchor + learn its tags
  UPDATE_SCENARIO adjust a scenario parameter ("your dark mood is now ~85 BPM")
  REVISE_PROFILE  rewrite the natural-language profile (memory.md)

The agent's brain is an LLM (activates when ANTHROPIC_API_KEY is set); without a
key it falls back to a deterministic policy so everything still runs. Either way
the decision is explainable and grounded in the similarity signal + real tags.

    python -m backend.profile.curator [user_id]
"""
import json
import sys
import time

from . import config, mdmemory, salience, tags as tagmod, data
from .evaluate import vec, cosine

CAT_DIMS = mdmemory.CAT_DIMS
OPS = {"NOOP", "REINFORCE", "ADD_FACET", "UPDATE_SCENARIO", "REVISE_PROFILE"}


# ---------------------------------------------------------------------------
# 1. similarity of the new track to the current profile
# ---------------------------------------------------------------------------
def analyze_similarity(state, track_tags):
    pv = mdmemory.taste_vector(state["user_id"], _state=state)
    fit = round(cosine(pv, vec(track_tags, idf_weight=True)), 3) if pv else 0.0
    fs = salience.facet_set(track_tags)
    facet_dist = [d["tag"] for d in salience.distinctive_tags(track_tags, dims=salience.FACET_DIMS)]
    known = {t for e in state.get("exemplars", []) for t in e.get("distinctive") or []}
    new_facet = [t for t in facet_dist if t not in known]
    nearest, best_ov = None, 0.0
    for e in state.get("exemplars", []):
        a = set(e["facets"])
        ov = len(fs & a) / max(len(fs | a), 1)
        if ov > best_ov:
            nearest, best_ov = e, ov
    return {"fit": fit, "nearest": nearest, "overlap": round(best_ov, 3),
            "new_facet": new_facet, "facets": sorted(fs)}


# ---------------------------------------------------------------------------
# 2. the agent decides the operation (LLM brain, deterministic fallback)
# ---------------------------------------------------------------------------
def decide(state, track_tags, sim):
    if config.ANTHROPIC_API_KEY:
        d = _decide_llm(state, track_tags, sim)
        if d:
            return d
    return _decide_rule(state, sim)


def _decide_rule(state, sim):
    if not state.get("exemplars"):
        return {"operation": "ADD_FACET", "target": "first-anchor",
                "reason": "first liked track — seed the profile"}
    if sim["new_facet"]:
        return {"operation": "ADD_FACET", "target": ", ".join(sim["new_facet"]),
                "reason": f"introduces a new taste facet ({', '.join(sim['new_facet'])}) "
                          f"not in the profile (similarity {int(sim['fit']*100)}%)"}
    if sim["overlap"] >= 0.8 and sim["nearest"] and sim["nearest"]["count"] >= 3:
        return {"operation": "NOOP", "target": sim["nearest"]["track_id"],
                "reason": f"already well-represented ({int(sim['overlap']*100)}% overlap with a "
                          f"strong anchor ×{sim['nearest']['count']}); nothing new to store"}
    tgt = sim["nearest"]["track_id"] if sim["nearest"] else "?"
    return {"operation": "REINFORCE", "target": tgt,
            "reason": f"fits an existing region ({int(sim['overlap']*100)}% overlap); "
                      f"reinforce it"}


def _decide_llm(state, track_tags, sim):
    """LLM brain: choose an operation from the similarity signal + tags. Returns
    None on any failure so the caller falls back to the rule policy."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        s = mdmemory.summary(state["user_id"], _state=state)
        ctx = {
            "profile": {"moods": [x["tag"] for x in s["likes"]["moods"][:4]],
                        "genres": [x["tag"] for x in s["likes"]["genres"][:3]],
                        "distinctive": [d["tag"] for d in s["distinctive"]],
                        "anchors": len(s["exemplars"])},
            "new_track": {k: track_tags.get(k) for k in ("moods", "genres", "instruments", "bpm")},
            "similarity": {"fit_to_profile": sim["fit"], "nearest_overlap": sim["overlap"],
                           "new_facets": sim["new_facet"]},
        }
        msg = client.messages.create(
            model=config.LLM_MODEL, max_tokens=200,
            system=("You curate a music taste memory. Given the current profile, a newly "
                    "liked track, and similarity signals, choose ONE operation and explain "
                    f"briefly. Operations: {sorted(OPS)}. Return ONLY JSON "
                    '{"operation":...,"target":...,"reason":...}. Use only given facts.'),
            messages=[{"role": "user", "content": json.dumps(ctx)}])
        txt = msg.content[0].text
        d = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
        if d.get("operation") in OPS:
            return d
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# 3. apply the decision to the memory
# ---------------------------------------------------------------------------
def _learn(state, tags, s=1.0):
    """Light affinity/numeric/scenario update (same EMA as record_feedback)."""
    for dim in CAT_DIMS:
        for tag in tags.get(dim) or []:
            mdmemory._bump(state["dims"][dim], tag, s)
    if tags.get("tempo"):
        mdmemory._bump(state["tempo"], tags["tempo"], s)
    for k in ("bpm", "valence", "arousal"):
        v = tags.get(k)
        if v is not None:
            cur = state["numeric"][k]
            state["numeric"][k] = round(v if cur is None else cur + mdmemory.NUM_ALPHA * (v - cur), 2)
    for vc in tags.get("vocals") or []:
        mdmemory._bump(state["vocals"], vc, 1.0)
    mdmemory._scenario_update(state, tags)


def apply_decision(state, decision, track_id, tags, sim):
    op = decision["operation"]
    if op == "NOOP":
        pass                                              # remember nothing new
    elif op == "REINFORCE":
        _learn(state, tags, s=1.0)                        # a like is a positive signal
        if sim["nearest"]:
            sim["nearest"]["count"] += 1
    elif op in ("ADD_FACET", "UPDATE_SCENARIO"):
        _learn(state, tags, s=1.0)
        if op == "ADD_FACET":
            fdist = [d["tag"] for d in salience.distinctive_tags(tags, dims=salience.FACET_DIMS)]
            ddist = [d["tag"] for d in salience.distinctive_tags(tags, dims=salience.DETAIL_DIMS)]
            state.setdefault("exemplars", []).append(
                {"track_id": track_id, "count": 1, "facets": sim["facets"],
                 "distinctive": fdist, "texture": ddist, "novelty": round(1 - sim["overlap"], 2)})
    elif op == "REVISE_PROFILE":
        _learn(state, tags, s=1.0)
    return state


# ---------------------------------------------------------------------------
# orchestration: the agent on one like
# ---------------------------------------------------------------------------
def curate(user_id, track_id, track_tags=None, prompt=None):
    state = mdmemory.load(user_id)
    tags = track_tags or tagmod.for_track(track_id)
    sim = analyze_similarity(state, tags)
    decision = decide(state, tags, sim)
    decision["similarity"] = sim["fit"]
    apply_decision(state, decision, track_id, tags, sim)

    state["counts"]["like"] = state["counts"].get("like", 0) + 1
    state["last_decision"] = {"decision": decision["operation"], "reason": decision["reason"]}
    mdmemory._snapshot(state)
    event = {"track_id": track_id, "verdict": "like", "prompt": prompt, "note": None,
             "brief": mdmemory._brief(tags), "decision": decision["operation"],
             "reason": decision["reason"], "ts": time.time()}
    mdmemory._append_evidence(user_id, event)
    state["evidence"] = (state["evidence"] + [event])[-50:]
    mdmemory.save(state, use_llm=(decision["operation"] == "REVISE_PROFILE"))
    return decision


def main():
    uid = sys.argv[1] if len(sys.argv) > 1 else "curator_demo"
    for p in (mdmemory._evidence_path(uid), mdmemory._memory_path(uid), mdmemory._state_path(uid)):
        import os
        if os.path.exists(p):
            os.remove(p)
    data.load()
    src = data.user_liked_cyanite("3457621")[:14]
    print(f"=== curator agent on {len(src)} likes (brain: "
          f"{'LLM' if config.ANTHROPIC_API_KEY else 'rule-fallback'}) ===\n")
    for cid in src:
        d = curate(uid, cid)
        print(f"  sim={d['similarity']:.2f}  {d['operation']:14s}  {d['reason']}")
    print(f"\nanchors kept: {len(mdmemory.load(uid).get('exemplars', []))}")
    print("memory.md:", mdmemory._memory_path(uid))


if __name__ == "__main__":
    main()
