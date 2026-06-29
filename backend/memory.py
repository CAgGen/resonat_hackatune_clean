"""Seam · memory system.

═══════════════════════════════════════════════════════════════════
  Cross-session memory = two markdown files, no DB (PRD §3):
    memory/<user_id>.evidence.md   append-only raw facts (one liked song + its feel tags per line)
    memory/<user_id>.memory.md     natural-language feel profile derived from evidence
═══════════════════════════════════════════════════════════════════

Contract (used by orchestration; signatures stay unchanged):
    read_memory(user_id) -> str          profile (memory.md); injected into /intent and returned by /your-sound. Empty if missing.
    append_evidence(user_id, prompt, liked_track_ids) -> None
        called at the end of a round: fetch feel tags for each liked song and append only; never edit old lines.
    rewrite_memory(user_id) -> str       rebuild profile from raw evidence and rewrite the whole section.

Design choices (user-defined):
- Use only feel dimensions: mood / character / movement; avoid hard variables like instruments, genre, BPM.
- Request only those three models; do not download large instrument segments, avoiding context blow-up naturally.
- Produce a profile only after each round (one prompt + selected songs); always rebuild from raw evidence instead
  of editing the old profile, preventing drift.
"""
from __future__ import annotations
import datetime as _dt
import pathlib
import re
from collections import Counter

MEM_DIR = pathlib.Path(__file__).parent / "memory"
MEM_DIR.mkdir(exist_ok=True)

WINDOW_ROUNDS = 8    # Rebuild from only the latest N rounds; evidence.md can grow forever while LLM input stays bounded.
FEELING_DIMS = ("moods", "character", "movement")
FEELING_MODELS = ["MoodSimpleV2", "CharacterV2", "MovementV2"]   # Fetch only feelings, not hard variables.


def _ev_path(user_id: str) -> pathlib.Path:
    return MEM_DIR / f"{user_id}.evidence.md"


def _mem_path(user_id: str) -> pathlib.Path:
    return MEM_DIR / f"{user_id}.memory.md"


def read_evidence(user_id: str) -> str:
    p = _ev_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_memory(user_id: str) -> str:
    p = _mem_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def feeling_injection(user_id: str) -> str:
    """Feel-only profile for injection into the /intent system prompt: keeps the feel narrative,
    core, and spectrum but drops the taste timeline (which contains historical search terms and
    genres that would bias searches toward old styles). /your-sound still serves the full read_memory."""
    md = read_memory(user_id)
    cut = md.find("**Taste timeline")
    return (md[:cut] if cut != -1 else md).strip()


def _feeling_tags(track_id: str) -> list[str]:
    """Feel tags for one track: mood + character + movement, deduplicated.
    Only requests these three models — no instruments / genre / BPM segments downloaded. seam: replaceable in self-check."""
    import cyanite
    try:
        t = cyanite.feel_tags(track_id, FEELING_MODELS) or {}
    except Exception:
        return []
    out = []
    for d in FEELING_DIMS:
        for tag in t.get(d) or []:
            if tag not in out:
                out.append(tag)
    return out


def append_evidence(user_id: str, whiteboard_context: str, liked_track_ids: list[str]) -> None:
    """Append each liked song from this round + its feel tags to evidence.md (append-only)."""
    p = _ev_path(user_id)
    if not p.exists():
        p.write_text(f"# evidence · {user_id}\n\n## Feedback log (one liked track + its feel tags per line)\n",
                     encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        for cid in liked_track_ids:
            feel = ", ".join(_feeling_tags(cid)) or "-"
            f.write(f"- 👍 `{cid}` · \"{whiteboard_context}\" · feel: {feel} · {ts}\n")


# Each line ends with a timestamp; one round (one finish_round call) shares prompt+ts.
# Accept both the old corner-quote format and the current ASCII quote format for existing memory files.
_EV_RE = re.compile(r"`([^`]+)`\s*·\s*(?:「(.*?)」|\"(.*?)\")\s*·\s*feel:\s*(.*?)\s*·\s*([\dT:\-]+)\s*$")


def _parse_rounds(user_id: str) -> list[dict]:
    """Group evidence.md by round (same round shares prompt+timestamp), oldest → newest.
    Each round: {prompt, ts, feels: Counter, n}. Keeps each round's feel context independent, not flattened across rounds."""
    rounds: list[dict] = []
    key = None
    for line in read_evidence(user_id).splitlines():
        m = _EV_RE.search(line)
        if not m:
            continue
        prompt, feelstr, ts = m.group(2) or m.group(3), m.group(4), m.group(5)
        feel = [x.strip() for x in feelstr.split(",") if x.strip() and x.strip() != "-"]
        rkey = (prompt, ts)
        if rkey != key:
            rounds.append({"prompt": prompt, "ts": ts, "feels": Counter(), "n": 0})
            key = rkey
        rounds[-1]["feels"].update(feel)
        rounds[-1]["n"] += 1
    return rounds


def _facts(rounds: list[dict]) -> dict:
    """Compile evolution-aware grounding facts: dominant feel per round (chronological) +
    core feels that run across multiple rounds + feel spectrum (cross-round by frequency) +
    stats (total likes / rounds / date span)."""
    recent = rounds[-WINDOW_ROUNDS:]
    timeline = []
    feel_rounds: Counter = Counter()      # how many rounds each feel appears in -> find persistent core
    spectrum: Counter = Counter()         # cross-round occurrence count -> feel spectrum
    for r in recent:
        timeline.append({"prompt": r["prompt"], "date": r["ts"][:10], "n": r["n"],
                         "feels": [t for t, _ in r["feels"].most_common(5)]})
        spectrum.update(r["feels"])
        for t in set(r["feels"]):
            feel_rounds[t] += 1
    core = [t for t, c in feel_rounds.most_common() if c >= 2][:6]   # appears in >=2 rounds = persistent core
    dates = [r["date"] for r in timeline]
    return {"timeline": timeline, "core": core,
            "latest": timeline[-1] if timeline else None, "n_rounds": len(rounds),
            "spectrum": spectrum.most_common(12),
            "total_likes": sum(r["n"] for r in recent),
            "first_date": dates[0] if dates else "", "last_date": dates[-1] if dates else ""}


def _timeline_text(info: dict) -> str:
    lines = []
    for i, r in enumerate(info["timeline"], 1):
        lines.append(f"{i}. \"{r['prompt']}\" ({r['date']}, {r['n']} tracks) → "
                     f"{', '.join(r['feels']) or '—'}")
    return "\n".join(lines)


def _spectrum_text(info: dict) -> str:
    return ", ".join(f"{t} x{c}" for t, c in info["spectrum"])


def _rounds_feel_text(info: dict) -> str:
    n = len(info["timeline"])
    out = []
    for i, r in enumerate(info["timeline"], 1):
        label = "most recent round" if i == n else f"round {i}"
        out.append(f"{label}: {', '.join(r['feels']) or '—'}")
    return "\n".join(out)


def _rule_profile(info: dict) -> str:
    parts = []
    if info["core"]:
        parts.append(f"You keep returning to feelings like **{', '.join(info['core'][:4])}**")
    latest = info["latest"]
    if latest and latest["feels"]:
        parts.append(f"recently you have been leaning toward {', '.join(latest['feels'][:3])}")
    return ("; ".join(parts) + ".") if parts else "Your feel profile is still taking shape."


def _llm_profile(info: dict) -> str | None:
    import config
    if not config.OPENAI_API_KEY:
        return None
    try:
        import intent_agent
        facts = ("In chronological order, the feels you preferred each round (oldest → most recent):\n"
                 + _rounds_feel_text(info) +
                 f"\n\nCore feels that run across multiple rounds: {', '.join(info['core']) or '—'}"
                 f"\nFeel spectrum (by frequency): {_spectrum_text(info) or '—'}")
        payload = intent_agent._responses(
            "You are writing a musical feel profile for a listener. This profile will be injected into "
            "a recommendation system's system prompt to guide searches, so it must only discuss "
            "emotion, atmosphere, and rhythm — the purely sensory layer. Never mention any music genre, "
            "style, subgenre, instrument, BPM, or scene label. Do three things: (1) name the stable core "
            "feelings that run across multiple rounds and briefly paint the listening picture they create; "
            "(2) describe how the listener's taste shifts or evolves over time, especially what they have "
            "been leaning toward recently; (3) note the secondary feels that recur across the spectrum to "
            "make the profile more vivid. Write 4-6 sentences in second person, in English. Warm, concrete, "
            "evocative but not overwrought. Only use the feel words you were given; never invent, and never "
            "mention genre or style.",
            facts)
        return intent_agent._output_text(payload).strip()
    except Exception:
        return None


def rewrite_memory(user_id: str) -> str:
    """Rebuild the feel profile from raw evidence after each round. Groups by round, looks only at
    the last WINDOW_ROUNDS (prevents context explosion), always rebuilds from raw (never edits the
    old profile) to prevent drift. The profile captures both the persistent core and the taste
    timeline over time (no single large round can dominate); only feel tags, no hard variables."""
    rounds = _parse_rounds(user_id)
    if not rounds:
        txt = f"# memory · {user_id}\n\n## Your Feel\n(No likes yet — pick a few tracks you enjoy.)\n"
        _mem_path(user_id).write_text(txt, encoding="utf-8")
        return txt

    info = _facts(rounds)
    para = _llm_profile(info) or _rule_profile(info)
    span = (f"{info['first_date']} → {info['last_date']}"
            if info["first_date"] != info["last_date"] else info["first_date"])
    txt = (f"# memory · {user_id}\n\n## Your Feel\n{para}\n\n"
           f"---\n**Core feel (runs across rounds):** {', '.join(info['core']) or '—'}\n\n"
           f"**Feel spectrum (by frequency):** {_spectrum_text(info) or '—'}\n\n"
           f"**Taste timeline (last {len(info['timeline'])}/{info['n_rounds']} rounds):**\n"
           f"{_timeline_text(info)}\n\n"
           f"_{info['total_likes']} likes · {info['n_rounds']} rounds · {span} · "
           f"rewritten {_dt.datetime.now().isoformat(timespec='seconds')}_\n")
    _mem_path(user_id).write_text(txt, encoding="utf-8")
    return txt


if __name__ == "__main__":
    # Self-check: evidence stores feel tags inline; groups by round; evolution-aware
    # (a smaller recent round is not buried by a larger older round).
    import config as _cfg
    _cfg.OPENAI_API_KEY = ""    # Force deterministic fallback; self-check does not touch the network.
    u = "__selftest__"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)

    # Round 1 has seven sad/calm-ish tracks; round 2 has two epic/happy-ish tracks.
    # The volume difference tests that the recent round is not buried.
    fake = {f"s{i}": ["calm", "ethereal", "flowing", "chill"] for i in range(7)}
    fake.update({"h1": ["epic", "heroic", "stomping"], "h2": ["happy", "epic", "stomping"]})
    _feeling_tags = lambda cid: fake.get(cid, [])   # Replace seam; no network.

    assert "No likes yet" in rewrite_memory(u), "No likes: profile should not appear"

    append_evidence(u, "sad music; electronic", [f"s{i}" for i in range(7)])   # Round 1.
    append_evidence(u, "happy; classical", ["h1", "h2"])                       # Round 2 (recent, niche).
    assert read_evidence(u).count("\n- ") == 9, "9 liked tracks = 9 lines; append does not overwrite"

    rounds = _parse_rounds(u)
    assert len(rounds) == 2, f"should split into two rounds by prompt, got {len(rounds)}"

    out = rewrite_memory(u)
    assert "calm" in out and "flowing" in out, "round 1 feels should be in timeline"
    assert "epic" in out and "stomping" in out, "round 2 (most recent) feels should not be buried by round 1 volume"
    assert '"sad music; electronic"' in out and '"happy; classical"' in out, "timeline should preserve each round's context"
    assert "piano" not in out and "ambient" not in out, "hard variables (instruments/genre) should not appear"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)
    print("memory self-check ok")
