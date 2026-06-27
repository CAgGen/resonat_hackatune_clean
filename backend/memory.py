"""接缝 · 记忆系统（队友负责）。

═══════════════════════════════════════════════════════════════════
  这个文件归同伴。编排层只依赖下面三个函数签名，内部实现随你换。
  跨会话记忆 = 两个 markdown 文件，无 DB（PRD §3）:
    memory/<user_id>.evidence.md   仅追加，原始事实
    memory/<user_id>.memory.md     自然语言画像，证据的派生物
═══════════════════════════════════════════════════════════════════

契约（编排层依赖，不要改签名）:
    read_memory(user_id) -> str
        返回该用户的画像（memory.md 内容）。/intent 编译时注入 prompt；
        /your-sound 直接吐它。没有就返回 ""。

    append_evidence(user_id, whiteboard_context, liked_track_ids) -> None
        用户点赞时追加一条证据。仅追加，绝不改旧行。

    rewrite_memory(user_id) -> str
        ★ 你的主战场：把该用户的 evidence 喂 LLM，总结成一段自然语言画像，
          整段重写 memory.md。下面是模板占位，换成 LLM 调用即可。

下面给的是能跑通的文件版占位：append/read 是纯文件 IO（不用动），
rewrite_memory 现在只填个计数模板——这一格是你接 LLM 的地方。
"""
from __future__ import annotations
import datetime as _dt
import pathlib

MEM_DIR = pathlib.Path(__file__).parent / "memory"
MEM_DIR.mkdir(exist_ok=True)


def _ev_path(user_id: str) -> pathlib.Path:
    return MEM_DIR / f"{user_id}.evidence.md"


def _mem_path(user_id: str) -> pathlib.Path:
    return MEM_DIR / f"{user_id}.memory.md"


def append_evidence(user_id: str, whiteboard_context: str, liked_track_ids: list[str]) -> None:
    p = _ev_path(user_id)
    if not p.exists():
        p.write_text(f"# evidence · {user_id}\n\n## 反馈记录\n", encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    liked = ", ".join(liked_track_ids) or "-"
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- 「{whiteboard_context}」→ liked {liked}   ({ts})\n")


def read_evidence(user_id: str) -> str:
    p = _ev_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_memory(user_id: str) -> str:
    p = _mem_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def rewrite_memory(user_id: str) -> str:
    # TODO(partner): 把 read_evidence(user_id) 喂 LLM，出一段自然语言画像，整段重写。
    ev = read_evidence(user_id)
    n = ev.count("\n- ")
    summary = (
        f"# memory · {user_id}\n\n## 你的声音\n"
        f"（占位：基于 {n} 条反馈。接 LLM 后这里是一段自然语言画像。）\n"
    )
    _mem_path(user_id).write_text(summary, encoding="utf-8")
    return summary


if __name__ == "__main__":
    # self-check: append 不覆盖、rewrite 跟着证据走
    u = "__selftest__"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)
    append_evidence(u, "背叛", ["t1", "t7"])
    append_evidence(u, "深夜独处", ["t12"])
    assert read_evidence(u).count("\n- ") == 2, "append 应保留两行"
    assert "2 条反馈" in rewrite_memory(u), "rewrite 应反映证据条数"
    for p in (_ev_path(u), _mem_path(u)):
        p.unlink(missing_ok=True)
    print("memory self-check OK")
