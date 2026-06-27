"""跨会话记忆 = 两个 markdown 文件（PRD 第 3 节）。无 DB。

  <user>.evidence.md  仅追加，原始事实，唯一真相
  <user>.memory.md    自然语言画像，证据的派生物（这里先用模板拼，接 LLM 后换成总结）
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


def append_evidence(user_id: str, prompt: str, liked_track_ids: list[str]) -> None:
    """点赞时 append 一行，从不改旧行。"""
    p = _ev_path(user_id)
    if not p.exists():
        p.write_text(f"# evidence · {user_id}\n\n## 反馈记录\n", encoding="utf-8")
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    liked = ", ".join(liked_track_ids) or "-"
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- 「{prompt}」→ liked {liked}   ({ts})\n")


def read_evidence(user_id: str) -> str:
    p = _ev_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_memory(user_id: str) -> str:
    """/intent 把这段原样塞进系统 prompt；/your-sound 直接吐它。"""
    p = _mem_path(user_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def rewrite_memory(user_id: str) -> str:
    """从 evidence 重写画像。整段覆盖。

    # ponytail: 先用模板占位，B4 接 LLM 时把这函数体换成「喂 evidence → 出自然语言」即可，签名不变
    """
    ev = read_evidence(user_id)
    n = ev.count("\n- ")
    summary = (
        f"# memory · {user_id}\n\n## 你的声音\n"
        f"（占位：基于 {n} 条反馈。接 LLM 后这里是一段自然语言画像。）\n"
    )
    _mem_path(user_id).write_text(summary, encoding="utf-8")
    return summary


if __name__ == "__main__":
    # ponytail self-check: append 不覆盖、rewrite 跟着证据走
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
