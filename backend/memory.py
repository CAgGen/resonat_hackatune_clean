"""接缝 · 记忆系统（队友负责）。

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
    """注入 /intent 系统提示用的「感觉」版画像：只保留感觉叙事 + 核心 + 光谱，
    剔除「口味轨迹」时间线（那里含历史搜索词/曲风，会让检索被旧类型带跑）。
    /your-sound 给用户看的仍是完整 read_memory。"""
    md = read_memory(user_id)
    cut = md.find("**口味轨迹")
    return (md[:cut] if cut != -1 else md).strip()


def _feeling_tags(track_id: str) -> list[str]:
    """一首歌的「感觉」标签：mood + character + movement，去重。
    只请求这三个模型——不下载乐器/曲风/BPM（连 segment 大块都不取）。seam: 自检可替换。"""
    from profile import tags as tagmod
    try:
        t = tagmod.for_track(track_id, models=FEELING_MODELS) or {}
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
        p.write_text(f"# evidence · {user_id}\n\n## 反馈记录（每行：一首 like 的歌 + 它的感觉标签）\n",
                     encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        for cid in liked_track_ids:
            feel = ", ".join(_feeling_tags(cid)) or "-"
            f.write(f"- 👍 `{cid}` · 「{whiteboard_context}」 · feel: {feel} · {ts}\n")


# 每行尾部带 timestamp；同一轮（一次 finish_round）共享 prompt+ts。
_EV_RE = re.compile(r"`([^`]+)`\s*·\s*「(.*?)」\s*·\s*feel:\s*(.*?)\s*·\s*([\dT:\-]+)\s*$")


def _parse_rounds(user_id: str) -> list[dict]:
    """从 evidence.md 按「轮」分组（同一轮共享 prompt+timestamp），最旧→最新。
    每轮: {prompt, ts, feels: Counter, n}。保留每轮独立的感觉语境，不跨轮压平。"""
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
    """整理成演化感知的 grounding facts：每轮的主导感觉（时间序）+ 贯穿多轮的核心感觉
    + 感觉光谱（跨轮按频次）+ 统计（总数 / 轮数 / 日期跨度）。"""
    recent = rounds[-WINDOW_ROUNDS:]
    timeline = []
    feel_rounds: Counter = Counter()      # 每个感觉出现在多少轮 → 找贯穿核心
    spectrum: Counter = Counter()         # 跨轮按出现次数 → 感觉光谱
    for r in recent:
        timeline.append({"prompt": r["prompt"], "date": r["ts"][:10], "n": r["n"],
                         "feels": [t for t, _ in r["feels"].most_common(5)]})
        spectrum.update(r["feels"])
        for t in set(r["feels"]):
            feel_rounds[t] += 1
    core = [t for t, c in feel_rounds.most_common() if c >= 2][:6]   # 跨 ≥2 轮 = 持久核心
    dates = [r["date"] for r in timeline]
    return {"timeline": timeline, "core": core,
            "latest": timeline[-1] if timeline else None, "n_rounds": len(rounds),
            "spectrum": spectrum.most_common(12),
            "total_likes": sum(r["n"] for r in recent),
            "first_date": dates[0] if dates else "", "last_date": dates[-1] if dates else ""}


def _timeline_text(info: dict) -> str:
    lines = []
    for i, r in enumerate(info["timeline"], 1):
        lines.append(f"{i}. 「{r['prompt']}」（{r['date']}，{r['n']}首）→ "
                     f"{'、'.join(r['feels']) or '—'}")
    return "\n".join(lines)


def _spectrum_text(info: dict) -> str:
    return "、".join(f"{t} ×{c}" for t, c in info["spectrum"])


def _rounds_feel_text(info: dict) -> str:
    """喂 LLM 的每轮感觉（只感觉词，不带 prompt/曲风），最旧→最近。"""
    n = len(info["timeline"])
    out = []
    for i, r in enumerate(info["timeline"], 1):
        label = "最近一轮" if i == n else f"第 {i} 轮"
        out.append(f"{label}：{'、'.join(r['feels']) or '—'}")
    return "\n".join(out)


def _rule_profile(info: dict) -> str:
    """无 LLM key 时的确定性兜底：核心 + 最近转向（只用感觉词，不提曲风/类型）。"""
    parts = []
    if info["core"]:
        parts.append(f"你反复回到 **{'、'.join(info['core'][:4])}** 这样的感觉")
    latest = info["latest"]
    if latest and latest["feels"]:
        parts.append(f"最近你转向了 {'、'.join(latest['feels'][:3])}")
    return ("；".join(parts) + "。") if parts else "你的感觉画像正在成形。"


def _llm_profile(info: dict) -> str | None:
    """LLM 只措辞、不发明——只喂每轮的感觉词 + 核心 + 光谱（不喂 prompt/曲风）。
    无 OPENAI key 走兜底。"""
    import config
    if not config.OPENAI_API_KEY:
        return None
    try:
        import intent_agent
        facts = ("按时间顺序，每一轮你偏好的感觉（最旧→最近）：\n" + _rounds_feel_text(info) +
                 f"\n\n贯穿多轮的核心感觉：{'、'.join(info['core']) or '—'}"
                 f"\n感觉光谱（按出现频次）：{_spectrum_text(info) or '—'}")
        payload = intent_agent._responses(
            "你在为听者写一段关于「音乐感觉」的画像，这段会被放进推荐系统的系统提示里引导检索，"
            "所以只能谈情绪、氛围、律动这种纯感受层面的东西——绝对不要出现任何音乐类型、曲风、"
            "流派、乐器、BPM 或场景名词。要做三件事：(1) 点出贯穿多轮、稳定的核心感觉，并稍微"
            "展开它带来的听感画面；(2) 描述 ta 的口味随时间如何变化或切换，尤其最近偏向什么；"
            "(3) 顺带点出光谱里那些次要但反复出现的感觉，让画像更立体。用第二人称写 4-6 句中文，"
            "温暖、具体、有画面感、不浮夸。只能用给定的感觉词，绝不编造，也绝不提类型/曲风。",
            facts)
        return intent_agent._output_text(payload).strip()
    except Exception:
        return None


def rewrite_memory(user_id: str) -> str:
    """每轮结束后从 evidence raw 重建「感觉」画像。按轮分组、只看最近 WINDOW_ROUNDS 轮
    （防上下文爆炸），永远从 raw 重建（不在旧画像上改）→ 防漂移；画像既有贯穿核心、也有
    随时间的口味轨迹（不被某一轮的数量碾压）；只用感觉标签，不碰硬变量。"""
    rounds = _parse_rounds(user_id)
    if not rounds:
        txt = f"# memory · {user_id}\n\n## 你的感觉\n（还没有 like，先选几首喜欢的歌。）\n"
        _mem_path(user_id).write_text(txt, encoding="utf-8")
        return txt

    info = _facts(rounds)
    para = _llm_profile(info) or _rule_profile(info)
    span = (f"{info['first_date']} → {info['last_date']}"
            if info["first_date"] != info["last_date"] else info["first_date"])
    txt = (f"# memory · {user_id}\n\n## 你的感觉\n{para}\n\n"
           f"---\n**贯穿的核心感觉:** {'、'.join(info['core']) or '—'}\n\n"
           f"**感觉光谱（按频次）:** {_spectrum_text(info) or '—'}\n\n"
           f"**口味轨迹（最近 {len(info['timeline'])}/{info['n_rounds']} 轮）:**\n"
           f"{_timeline_text(info)}\n\n"
           f"_共 {info['total_likes']} 次 like · 跨 {info['n_rounds']} 轮 · {span} · "
           f"重写于 {_dt.datetime.now().isoformat(timespec='seconds')}_\n")
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

    assert "还没有 like" in rewrite_memory(u), "无 like 不应出画像"

    append_evidence(u, "sad music; 电子乐", [f"s{i}" for i in range(7)])   # 第 1 轮
    append_evidence(u, "开心; 古典", ["h1", "h2"])                          # 第 2 轮（最近，小众）
    assert read_evidence(u).count("\n- ") == 9, "9 首 like = 9 行，append 不覆盖"

    rounds = _parse_rounds(u)
    assert len(rounds) == 2, f"应按 prompt 分成两轮，得到 {len(rounds)}"

    out = rewrite_memory(u)
    assert "calm" in out and "flowing" in out, "第 1 轮的感觉应在轨迹里"
    assert "epic" in out and "stomping" in out, "第 2 轮（最近）的感觉不应被第 1 轮数量碾压"
    assert "「sad music; 电子乐」" in out and "「开心; 古典」" in out, "轨迹应保留两轮各自语境"
    assert "piano" not in out and "ambient" not in out, "不应出现硬变量（乐器/曲风）"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)
    print("memory self-check ok")
