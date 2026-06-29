"""接缝 · 记忆系统。

═══════════════════════════════════════════════════════════════════
  跨会话记忆 = 两个 markdown 文件，无 DB（PRD §3）:
    memory/<user_id>.evidence.md   仅追加，原始事实（每行：一首 like 的歌 + 它的「感觉」标签）
    memory/<user_id>.memory.md     自然语言「感觉」画像，证据的派生物
═══════════════════════════════════════════════════════════════════

契约（编排层依赖，签名不变）:
    read_memory(user_id) -> str          画像（memory.md）；/intent 注入、/your-sound 直吐。没有则 ""。
    append_evidence(user_id, prompt, liked_track_ids) -> None
        一轮结束时调用：为每首 like 的歌取「感觉」标签并仅追加，绝不改旧行。
    rewrite_memory(user_id) -> str       从 evidence raw 重建画像，整段重写。

设计取向（用户定）:
- 只用「感觉」维度：mood / character / movement —— 不碰乐器、曲风、BPM 等硬变量。
- 取标签时只请求这三个模型，连乐器的 segment 大块都不下载 → 天然无上下文爆炸。
- 每轮（一个 prompt + 用户选的歌）结束才出画像；永远从 raw 重建，不在旧画像上改 → 防漂移。
"""
from __future__ import annotations
import datetime as _dt
import pathlib
import re
from collections import Counter

MEM_DIR = pathlib.Path(__file__).parent / "memory"
MEM_DIR.mkdir(exist_ok=True)

WINDOW_ROUNDS = 8    # 重建只看最近 N 轮 —— evidence.md 可无限增长，喂 LLM 的恒定有界
FEELING_DIMS = ("moods", "character", "movement")
FEELING_MODELS = ["MoodSimpleV2", "CharacterV2", "MovementV2"]   # 只取感觉，不下载硬变量


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
    """一轮结束时把这一轮 like 的每首歌 + 它的感觉标签追加进 evidence.md（仅追加）。"""
    p = _ev_path(user_id)
    if not p.exists():
        p.write_text(f"# evidence · {user_id}\n\n## Feedback log (one liked track + its feel tags per line)\n",
                     encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        for cid in liked_track_ids:
            feel = ", ".join(_feeling_tags(cid)) or "-"
            f.write(f"- 👍 `{cid}` · 「{whiteboard_context}」 · feel: {feel} · {ts}\n")


# 每行尾部带 timestamp；同一轮（一次 finish_round）共享 prompt+ts。
_EV_RE = re.compile(r"`([^`]+)`\s*·\s*「(.*?)」\s*·\s*feel:\s*(.*?)\s*·\s*([\dT:\-]+)\s*$")


def _parse_rounds(user_id: str) -> list[dict]:
    """Group evidence.md by round (same round shares prompt+timestamp), oldest → newest.
    Each round: {prompt, ts, feels: Counter, n}. Keeps each round's feel context independent, not flattened across rounds."""
    rounds: list[dict] = []
    key = None
    for line in read_evidence(user_id).splitlines():
        m = _EV_RE.search(line)
        if not m:
            continue
        prompt, feelstr, ts = m.group(2), m.group(3), m.group(4)
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
    feel_rounds: Counter = Counter()      # how many rounds each feel appears in → find persistent core
    spectrum: Counter = Counter()         # cross-round occurrence count → feel spectrum
    for r in recent:
        timeline.append({"prompt": r["prompt"], "date": r["ts"][:10], "n": r["n"],
                         "feels": [t for t, _ in r["feels"].most_common(5)]})
        spectrum.update(r["feels"])
        for t in set(r["feels"]):
            feel_rounds[t] += 1
    core = [t for t, c in feel_rounds.most_common() if c >= 2][:6]   # appears in ≥2 rounds = persistent core
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
    # self-check: evidence 内联存感觉标签；按轮分组；演化感知（小众的最近一轮不被大轮碾压）
    import config as _cfg
    _cfg.OPENAI_API_KEY = ""    # 强制确定性兜底，自检不打网络
    u = "__selftest__"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)

    # 第 1 轮 7 首 sad/calm 系，第 2 轮 2 首 epic/happy 系——数量悬殊，考验“最近轮不被碾压”
    fake = {f"s{i}": ["calm", "ethereal", "flowing", "chill"] for i in range(7)}
    fake.update({"h1": ["epic", "heroic", "stomping"], "h2": ["happy", "epic", "stomping"]})
    _feeling_tags = lambda cid: fake.get(cid, [])   # 替换 seam，不打网络

    assert "No likes yet" in rewrite_memory(u), "No likes: profile should not appear"

    append_evidence(u, "sad music; 电子乐", [f"s{i}" for i in range(7)])   # 第 1 轮
    append_evidence(u, "开心; 古典", ["h1", "h2"])                          # 第 2 轮（最近，小众）
    assert read_evidence(u).count("\n- ") == 9, "9 首 like = 9 行，append 不覆盖"

    rounds = _parse_rounds(u)
    assert len(rounds) == 2, f"应按 prompt 分成两轮，得到 {len(rounds)}"

    out = rewrite_memory(u)
    assert "calm" in out and "flowing" in out, "round 1 feels should be in timeline"
    assert "epic" in out and "stomping" in out, "round 2 (most recent) feels should not be buried by round 1 volume"
    assert '"sad music; 电子乐"' in out and '"开心; 古典"' in out, "timeline should preserve each round's context"
    assert "piano" not in out and "ambient" not in out, "hard variables (instruments/genre) should not appear"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)
    print("memory self-check ok")
