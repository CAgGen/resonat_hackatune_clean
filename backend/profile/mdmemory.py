"""User-defined taste memory (PRD-night contract): two markdown files per user,
no database.

  memory/<user_id>.evidence.md  — APPEND-ONLY raw truth: one line per feedback
                                  event (prompt -> liked id). Doubles as the
                                  similarById seed pool and the profile basis.
  memory/<user_id>.memory.md    — natural-language profile, REWRITTEN each update
                                  (LLM if a key is set, else a rule-based fallback).
                                  /intent injects this verbatim into the system prompt.

  memory/<user_id>.state.json   — internal engine cache (affinities, anchors, IDF
                                  distinctiveness, scenarios). DERIVED — rebuildable
                                  by replaying evidence.md; not part of the contract.

The single entry point is record_feedback(); everything else is read views.

Design choices:
- Preferences are an interpretable per-tag affinity (EMA), never an opaque latent
  — every number traces back to liked tracks + their real Cyanite tags.
- Memory is built from likes (positive). dislike/skip push affinity down (and can
  surface "avoids"); free-text "note" is stored verbatim.
"""
import json
import os
import re
import time

from . import tags as tagmod
from . import salience
from . import config

MEM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
os.makedirs(MEM_DIR, exist_ok=True)

# how strongly each verdict moves affinity
SIGNAL = {"like": 1.0, "play": 0.3, "skip": -0.3, "dislike": -0.8, "note": 0.0}
ALPHA = 0.3          # EMA learning rate for tag affinities
NUM_ALPHA = 0.25     # EMA rate for numeric axes (bpm/valence/arousal)
CAT_DIMS = ["moods", "genres", "instruments", "character", "movement"]
AVOID_THRESHOLD = -0.25
REDUNDANT_OVERLAP = 0.6   # facet-overlap above which a new like is "redundant"
_EMOJI = {"like": "👍", "dislike": "👎", "skip": "⏭", "play": "▶", "note": "📝"}


# ---------------------------------------------------------------------------
# storage: three files per user (evidence.md truth, memory.md profile, state.json)
# ---------------------------------------------------------------------------
def _safe(user_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(user_id))


def _evidence_path(user_id):
    return os.path.join(MEM_DIR, f"{_safe(user_id)}.evidence.md")


def _memory_path(user_id):
    return os.path.join(MEM_DIR, f"{_safe(user_id)}.memory.md")


def _state_path(user_id):
    return os.path.join(MEM_DIR, f"{_safe(user_id)}.state.json")


def _empty(user_id):
    return {"user_id": str(user_id), "updated": None,
            "counts": {"like": 0, "dislike": 0, "skip": 0, "play": 0, "note": 0},
            "dims": {d: {} for d in CAT_DIMS},
            "numeric": {k: None for k in ("bpm", "valence", "arousal")},
            "tempo": {}, "vocals": {},
            "scenarios": {},          # mood -> {"bpm": [..], "genres": {..}}
            "exemplars": [],          # anchor tracks (CBR); redundant likes reinforce these
            "last_decision": None,    # explanation of the most recent write
            "history": [],            # affinity snapshots over time (taste evolution)
            "notes": [], "evidence": []}


def load(user_id):
    """Load the internal engine state from <uid>.state.json."""
    p = _state_path(user_id)
    if not os.path.exists(p):
        return _empty(user_id)
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty(user_id)


def save(state, use_llm=None):
    """Persist engine state (state.json) and re-render the memory.md profile.
    evidence.md is append-only and written separately by _append_evidence()."""
    state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(_state_path(state["user_id"]), "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    with open(_memory_path(state["user_id"]), "w") as f:
        f.write(render_memory_md(state, use_llm=use_llm))


# ---------------------------------------------------------------------------
# THE INTERFACE: record one feedback event
# ---------------------------------------------------------------------------
def record_feedback(user_id, track_id, verdict, prompt=None, note=None, track_tags=None):
    """Update a user's markdown taste memory from one feedback event.

    verdict: like | dislike | skip | play | note
    track_tags: optional normalized tags; fetched from Cyanite (cached) if absent.
    Returns the updated memory summary (see summary()).
    """
    state = load(user_id)
    s = SIGNAL.get(verdict, 0.0)
    state["counts"][verdict] = state["counts"].get(verdict, 0) + 1

    if note:
        state["notes"].append({"text": note, "track_id": track_id, "ts": time.time()})

    tags = None
    if verdict != "note":
        tags = track_tags or _safe_tags(track_id)

    if tags and s != 0:
        # categorical affinities (EMA toward the signal)
        for dim in CAT_DIMS:
            for tag in tags.get(dim) or []:
                cell = state["dims"][dim].get(tag, {"aff": 0.0, "n": 0})
                cell["aff"] = round(cell["aff"] + ALPHA * (s - cell["aff"]), 3)
                cell["n"] += 1
                state["dims"][dim][tag] = cell
        if tags.get("tempo"):
            _bump(state["tempo"], tags["tempo"], s)
        # numeric centers + scenario memory only from positive signals
        if s > 0:
            for k in ("bpm", "valence", "arousal"):
                v = tags.get(k)
                if v is not None:
                    cur = state["numeric"][k]
                    state["numeric"][k] = round(v if cur is None else cur + NUM_ALPHA * (v - cur), 2)
            for vc in tags.get("vocals") or []:
                _bump(state["vocals"], vc, 1.0)
            _scenario_update(state, tags)

    # novelty gate (only for likes): decide whether this track is worth storing as
    # a new anchor or just reinforces an existing one — and explain why.
    decision = None
    if verdict == "like" and tags:
        decision = _novelty_gate(state, track_id, tags, prompt)
        state["last_decision"] = decision

    # taste-evolution snapshot (every signal that moved affinity)
    if s != 0:
        _snapshot(state)

    # append-only raw truth -> evidence.md (and a rolling copy in state for views)
    event = {"track_id": track_id, "verdict": verdict, "prompt": prompt,
             "note": note, "brief": _brief(tags) if tags else None,
             "decision": decision["decision"] if decision else None,
             "reason": decision["reason"] if decision else None,
             "ts": time.time()}
    _append_evidence(user_id, event)
    state["evidence"].append(event)
    state["evidence"] = state["evidence"][-50:]

    save(state)
    return summary(user_id, _state=state)


def _append_evidence(user_id, event):
    """Append one line to <uid>.evidence.md. Never modifies existing lines."""
    p = _evidence_path(user_id)
    new_file = not os.path.exists(p)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(event.get("ts") or time.time()))
    em = _EMOJI.get(event["verdict"], "?")
    tid = f"`{event['track_id']}`" if event.get("track_id") else "—"
    pr = f" · 「{event['prompt']}」" if event.get("prompt") else ""
    nt = f" · note: 「{event['note']}」" if event.get("note") else ""
    line = f"- {em} {event['verdict']} · {tid}{pr}{nt} · {ts}\n"
    with open(p, "a") as f:
        if new_file:
            f.write(f"# Evidence — user {user_id}  (append-only · raw truth · seed pool)\n\n")
        f.write(line)


def _bump(d, key, s):
    cell = d.get(key, {"aff": 0.0, "n": 0})
    cell["aff"] = round(cell["aff"] + ALPHA * (s - cell["aff"]), 3)
    cell["n"] += 1
    d[key] = cell


def _snapshot(state):
    """Record a compact affinity snapshot for the taste-evolution timeline."""
    t = sum(state["counts"].values())
    pick = lambda dim: {tag: c["aff"] for tag, c in state["dims"][dim].items() if c["aff"] > 0.05}
    state.setdefault("history", []).append({
        "t": t, "valence": state["numeric"].get("valence"),
        "arousal": state["numeric"].get("arousal"), "bpm": state["numeric"].get("bpm"),
        "anchors": len(state.get("exemplars", [])),
        "moods": pick("moods"), "genres": pick("genres")})
    state["history"] = state["history"][-300:]


def _scenario_update(state, tags):
    mood = (tags.get("moods") or [None])[0]
    if not mood:
        return
    sc = state["scenarios"].setdefault(mood, {"n": 0, "bpm": [], "genres": {}})
    sc["n"] += 1
    if tags.get("bpm"):
        sc["bpm"].append(tags["bpm"])
        sc["bpm"] = sc["bpm"][-30:]
    for g in tags.get("genres") or []:
        sc["genres"][g] = sc["genres"].get(g, 0) + 1


# ---------------------------------------------------------------------------
# novelty gate: store-new vs reinforce, with an explainable reason
# ---------------------------------------------------------------------------
def _jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def _novelty_gate(state, track_id, tags, prompt):
    """Decide what to remember about a newly liked track (and explain it).

    A new ANCHOR is created only when the track occupies a genuinely new *facet*
    (genre/mood/character) region. Distinctive *texture* (rare instruments/
    movement) does not spawn an anchor — it ENRICHES the nearest one. This keeps
    the anchor set a small, meaningful map of the user's taste regions.

    - First like -> first anchor.
    - Redundant  -> high facet overlap AND no new distinctive facet tag
                    -> reinforce nearest anchor (count++), absorb any new texture.
    - Novel      -> new facet mix -> new anchor.
    """
    fs = salience.facet_set(tags)
    facet_dist = [d["tag"] for d in salience.distinctive_tags(tags, dims=salience.FACET_DIMS)]
    detail_dist = [d["tag"] for d in salience.distinctive_tags(tags, dims=salience.DETAIL_DIMS)]
    exemplars = state.setdefault("exemplars", [])

    if not exemplars:
        exemplars.append({"track_id": track_id, "count": 1, "facets": sorted(fs),
                          "distinctive": facet_dist, "texture": detail_dist,
                          "novelty": 1.0, "prompt": prompt})
        return {"decision": "store_first", "novelty": 1.0, "new_distinctive": facet_dist,
                "reason": f"first anchor — facet: {', '.join(facet_dist) or 'baseline'}"}

    max_ov, nearest = max(((_jaccard(fs, set(e["facets"])), e) for e in exemplars),
                          key=lambda x: x[0])
    known_facet = {t for e in exemplars for t in e.get("distinctive") or []}
    new_facet = [t for t in facet_dist if t not in known_facet]
    novelty = round(1 - max_ov, 2)

    if max_ov >= REDUNDANT_OVERLAP and not new_facet:
        nearest["count"] += 1
        absorbed = [t for t in detail_dist if t not in (nearest.get("texture") or [])]
        nearest["texture"] = (nearest.get("texture") or []) + absorbed
        extra = f"; noted new texture: {', '.join(absorbed)}" if absorbed else ""
        return {"decision": "reinforce", "novelty": novelty, "new_distinctive": [],
                "reason": (f"redundant — {max_ov:.0%} facet overlap with anchor "
                           f"`{nearest['track_id']}`; reinforced (×{nearest['count']}){extra}")}

    exemplars.append({"track_id": track_id, "count": 1, "facets": sorted(fs),
                      "distinctive": facet_dist, "texture": detail_dist,
                      "novelty": novelty, "prompt": prompt})
    extra = f" — new facet: {', '.join(new_facet)}" if new_facet else " — different facet mix"
    return {"decision": "store_new", "novelty": novelty, "new_distinctive": new_facet,
            "reason": f"new anchor (novelty {novelty:.0%}){extra}"}


def _safe_tags(track_id):
    try:
        return tagmod.for_track(track_id)
    except Exception:
        return None


def _brief(tags):
    g = (tags.get("genres") or ["?"])[0]
    m = "/".join((tags.get("moods") or [])[:2])
    return f"{g}/{m}" if m else g


# ---------------------------------------------------------------------------
# read views
# ---------------------------------------------------------------------------
def _top_pos(cells, n):
    pos = {t: c["aff"] for t, c in cells.items() if c["aff"] > 0.05}
    total = sum(pos.values()) or 1.0
    return [{"tag": t, "pct": round(100 * a / total), "aff": a}
            for t, a in sorted(pos.items(), key=lambda kv: -kv[1])[:n]]


def _avoids(state):
    out = {}
    for dim, cells in state["dims"].items():
        neg = [t for t, c in cells.items() if c["aff"] < AVOID_THRESHOLD]
        if neg:
            out[dim] = neg
    return out


def _distinctive_signature(st, n=6):
    """Globally distinctive (high-IDF) tags the user keeps liking — what makes
    their taste characteristic vs the catalog average."""
    scored = []
    for dim in CAT_DIMS:
        for tag, cell in st["dims"][dim].items():
            if cell["aff"] > 0.1:
                scored.append({"dim": dim, "tag": tag,
                               "idf": salience.idf(dim, tag), "aff": cell["aff"]})
    scored.sort(key=lambda x: -(x["idf"] * x["aff"]))
    return [s for s in scored if s["idf"] >= 1.0][:n]


def summary(user_id, _state=None):
    """Structured memory summary (for GET /your-sound)."""
    st = _state or load(user_id)
    likes = {d: _top_pos(st["dims"][d], 5) for d in CAT_DIMS}
    import statistics
    scen = {}
    for mood, sc in st["scenarios"].items():
        if sc["n"] >= 2 and sc["bpm"]:
            top_g = sorted(sc["genres"], key=sc["genres"].get, reverse=True)[:2]
            scen[mood] = {"n": sc["n"], "median_bpm": round(statistics.median(sc["bpm"])),
                          "genres": top_g}
    return {"user_id": st["user_id"], "counts": st["counts"],
            "likes": likes, "avoids": _avoids(st),
            "numeric": st["numeric"], "vocals": _top_pos(st["vocals"], 2),
            "scenarios": scen, "headline": _headline(st, likes),
            "exemplars": st.get("exemplars", []),
            "distinctive": _distinctive_signature(st),
            "last_decision": st.get("last_decision"),
            "notes": [n["text"] for n in st["notes"]]}


def _headline(st, likes):
    if not any(likes.values()):
        return "No taste memory yet — like a few tracks first."
    m = ", ".join(x["tag"] for x in likes["moods"][:3])
    g = ", ".join(x["tag"] for x in likes["genres"][:2])
    inst = ", ".join(x["tag"] for x in likes["instruments"][:3])
    bpm = st["numeric"].get("bpm")
    return f"You lean {m} {g}, built on {inst}{f', around {bpm} BPM' if bpm else ''}."


_EV_LINE = re.compile(r"^- \S+ (\w+) · `([^`]+)`(?: · 「([^」]*)」)?")


def _parse_evidence(user_id):
    """Read the append-only evidence.md back into events (the raw truth)."""
    p = _evidence_path(user_id)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        m = _EV_LINE.match(line.rstrip("\n"))
        if m:
            out.append({"verdict": m.group(1), "track_id": m.group(2), "prompt": m.group(3)})
    return out


def taste_vector(user_id, idf=True, _state=None):
    """Machine view for re-ranking: {f'{dim}:{tag}': weight} from positive
    affinities, optionally weighted by IDF distinctiveness."""
    st = _state or load(user_id)
    v = {}
    for dim, cells in st["dims"].items():
        for tag, c in cells.items():
            if c["aff"] > 0.05:
                v[f"{dim}:{tag}"] = c["aff"] * (salience.idf(dim, tag) if idf else 1.0)
    return v


def seed_pool(user_id, prompt=None, limit=None):
    """Liked track ids for similarById seeds (PRD seed pool), read from the
    append-only evidence.md. prompt=None -> cross-session; prompt=<text> -> that
    prompt's pool. Most-recent first, de-duplicated."""
    ids = [e["track_id"] for e in reversed(_parse_evidence(user_id))
           if e["verdict"] == "like" and (prompt is None or e["prompt"] == prompt)]
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i); out.append(i)
    return out[:limit] if limit else out


def prompt_injection(user_id):
    """The text /intent prepends to its system prompt = the memory.md body, read
    verbatim (PRD: inject memory.md, don't parse). Falls back to rendering if the
    file is missing."""
    p = _memory_path(user_id)
    if os.path.exists(p):
        return open(p).read().strip()
    return render_memory_md(load(user_id))


# ---------------------------------------------------------------------------
# memory.md — natural-language profile (LLM if a key is set, else rule-based)
# ---------------------------------------------------------------------------
def render_memory_md(state, use_llm=None):
    """Render the natural-language taste profile injected into /intent.

    use_llm: None -> auto (LLM iff ANTHROPIC_API_KEY set); True/False to force.
    The LLM only *phrases* the facts the engine distilled; it never invents them.
    """
    s = summary(state["user_id"], _state=state)
    if not any(s["likes"].values()):
        return f"# 🎧 Your sound — user {s['user_id']}\n\n_(No taste memory yet — like a few tracks first.)_\n"

    facts = _facts_block(s)
    if use_llm is None:
        use_llm = bool(config.ANTHROPIC_API_KEY)
    nl = (_llm_paragraph(facts) if use_llm else None) or _rule_paragraph(s)

    L = [f"# 🎧 Your sound — user {s['user_id']}", "", nl, "", "---", "", facts,
         "", f"_(derived from evidence.md · {s['counts'].get('like',0)} likes · "
         f"rewritten {state.get('updated')})_", ""]
    return "\n".join(L)


def _rule_paragraph(s):
    """Deterministic natural-language summary (no LLM needed)."""
    m = ", ".join(x["tag"] for x in s["likes"]["moods"][:3])
    g = " & ".join(x["tag"] for x in s["likes"]["genres"][:2])
    inst = ", ".join(x["tag"] for x in s["likes"]["instruments"][:3])
    bpm = s["numeric"].get("bpm")
    voc = s["vocals"][0]["tag"] if s["vocals"] else None
    dist = ", ".join(d["tag"] for d in s["distinctive"][:3])
    avoid = ", ".join(v for vs in s["avoids"].values() for v in vs)
    out = f"You lean **{m}** {g}, built on {inst}"
    out += f", around {bpm} BPM" if bpm else ""
    out += f", mostly {voc}" if voc else ""
    out += "."
    if dist:
        out += f" What's distinctive about your taste: **{dist}**."
    if avoid:
        out += f" You steer away from {avoid}."
    if s["scenarios"]:
        sc = "; ".join(f"{mood} ≈ {d['median_bpm']} BPM" for mood, d in list(s["scenarios"].items())[:3])
        out += f" By mood: {sc}."
    return out


def _facts_block(s):
    L = ["**Facts (grounded in Cyanite tags):**"]
    for dim in CAT_DIMS:
        items = s["likes"][dim]
        if items:
            L.append(f"- {dim}: " + ", ".join(f"{x['tag']} {x['pct']}%" for x in items[:4]))
    if s["distinctive"]:
        L.append("- distinctive (rare): " + ", ".join(d["tag"] for d in s["distinctive"]))
    if s["avoids"]:
        L.append("- avoids: " + ", ".join(v for vs in s["avoids"].values() for v in vs))
    if s.get("exemplars"):
        L.append(f"- anchors: {len(s['exemplars'])} taste regions kept")
    if s["notes"]:
        L.append("- notes from you: " + "; ".join(f"“{n}”" for n in s["notes"][-3:]))
    return "\n".join(L)


def _llm_paragraph(facts):
    """Let an LLM phrase the profile in one warm paragraph. Uses ONLY the facts."""
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.LLM_MODEL, max_tokens=160,
            system=("Write a 2-3 sentence second-person taste profile ('You ...') "
                    "from these facts. Warm, specific, no hype. Use ONLY the given "
                    "facts; invent nothing."),
            messages=[{"role": "user", "content": facts}])
        return msg.content[0].text.strip()
    except Exception:
        return None


def refresh_memory(user_id, use_llm=True):
    """Re-render memory.md (e.g. LLM-rewrite before /intent). Returns the text."""
    state = load(user_id)
    txt = render_memory_md(state, use_llm=use_llm)
    with open(_memory_path(user_id), "w") as f:
        f.write(txt)
    return txt
