"""接缝 · 意图分析 Agent。

两段式，两次独立 LLM 调用，prompt 在 prompts/intent_agent.md，占位符用 str.replace 注入：
  ① interpret -> compile_query_card()：确认门生成给用户看的精简解读（~200字）。
                 白板每变一次重跑（重新解读），不碰检索。
  ② search    -> search_args()：用户确认后，编排层 confirm() 调一次，tool calling 让模型
                 发起 search_by_prompt(query, metadata_filter)，我们解析出参数；真正打
                 Cyanite 由 confirm() 执行（全链路单次检索调用）。

契约（编排层依赖）:
    compile_query_card(posts, profile_md="") -> dict   # ① 确认门的 Query Card（仅解读）
    search_args(posts, profile_md="")       -> dict    # ② 检索参数 {query, metadata_filter}

compile_query_card 返回:
    {
      "interpretation_plain": str,          # ① 解读
      "free_text_query": "",                # 留空，confirm 调 search_args 后回填
      "metadata_filter": None,              # 同上
    }
search_args 返回:
    {"query": str, "metadata_filter": dict | None}

有 OPENAI_API_KEY 走 LLM；没 key 走 deterministic fallback，离线编排/测试照跑。
"""
from __future__ import annotations

import json
import pathlib
import re

import requests

import config

# 兜底：前端纯文本渲染，剥掉模型偶尔漏带的 markdown（**加粗**、行首 - / # 列表/标题符号）。
_MD = re.compile(r"\*\*|__|`|^\s*[-*•#]+\s+", re.M)


def _plain(text: str) -> str:
    return _MD.sub("", text).strip()

_PROMPT_PATH = pathlib.Path(__file__).resolve().parent / "prompts" / "intent_agent.md"
_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# search_by_prompt 的工具 schema（Responses API function tool）。
# metadata_filter 是自由形态的 MongoDB 风格对象，不做 strict 约束。
_SEARCH_TOOL = {
    "type": "function",
    "name": "search_by_prompt",
    "description": "Search the Cyanite library with an English natural-language query and an "
                   "optional MongoDB-style metadata filter. Call exactly once.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Expanded English search query."},
            "limit": {"type": "integer", "description": "How many tracks to fetch."},
            "metadata_filter": {
                "type": ["object", "null"],
                "description": "MongoDB-style filter keyed by <ModelVersion>.<field>, or null.",
            },
        },
        "required": ["query"],
    },
}


def compile_query_card(posts: list[dict], profile_md: str = "") -> dict:
    """① 确认门：只出解读。检索参数留到 confirm 调 search_args 回填。"""
    return {
        "interpretation_plain": interpret(posts, profile_md),
        "free_text_query": "",
        "metadata_filter": None,
    }


def interpret(posts: list[dict], profile_md: str = "") -> str:
    """① 解读阶段：返回给用户看的 ~200字 精简解读。"""
    if not config.OPENAI_API_KEY:
        return f"I understand the target as: {_join(posts, profile_md)}"
    payload = _responses(_render("interpret", posts, profile_md), "Give the interpretation now.")
    return _plain(_output_text(payload))


def search_args(posts: list[dict], profile_md: str = "") -> dict:
    """② 检索阶段：tool calling，解析出 {query, metadata_filter}。"""
    if not config.OPENAI_API_KEY:
        return {"query": _join(posts, profile_md), "metadata_filter": None}
    payload = _responses(
        _render("search", posts, profile_md),
        "User confirmed. Fire the search now.",
        tools=[_SEARCH_TOOL],
        tool_choice={"type": "function", "name": "search_by_prompt"},
    )
    args = _tool_call_args(payload)
    return {"query": args.get("query", ""), "metadata_filter": args.get("metadata_filter") or None}


_SURPRISE_PROMPT = (pathlib.Path(__file__).resolve().parent / "prompts" / "surprise_agent.md").read_text("utf-8")
_SOUNDS_LIKE_YOU_PROMPT = (pathlib.Path(__file__).resolve().parent / "prompts" / "sounds_like_you.md").read_text("utf-8")


def sounds_like_you_args(profile_md: str = "") -> dict | None:
    """「听起来像你」检索参数：完全忠实长期画像、零偏移。无 key 或没画像 → None（不出专属卡）。"""
    if not config.OPENAI_API_KEY or not profile_md.strip():
        return None
    instructions = _SOUNDS_LIKE_YOU_PROMPT.replace("{{user_profile}}", profile_md.strip())
    payload = _responses(instructions, "Fire one search for the Sounds Like You dedicated slot.",
                         tools=[_SEARCH_TOOL],
                         tool_choice={"type": "function", "name": "search_by_prompt"})
    args = _tool_call_args(payload)
    query = args.get("query", "")
    return {"query": query, "metadata_filter": None} if query else None


def surprise_args(posts: list[dict], profile_md: str = "") -> dict | None:
    """惊喜位检索参数：忠于本轮需求、刻意偏离画像。无 key 或没画像可偏离 → None（不出惊喜卡）。"""
    if not config.OPENAI_API_KEY or not profile_md.strip():
        return None
    history, request = _split(posts)
    instructions = (_SURPRISE_PROMPT
                    .replace("{{history}}", history)
                    .replace("{{user_profile}}", profile_md.strip())
                    .replace("{{request}}", request))
    payload = _responses(instructions, "Fire one search for the surprise slot.",
                         tools=[_SEARCH_TOOL],
                         tool_choice={"type": "function", "name": "search_by_prompt"})
    args = _tool_call_args(payload)
    query = args.get("query", "")
    return {"query": query, "metadata_filter": args.get("metadata_filter") or None} if query else None


# ─────────────────────────── 内部 ───────────────────────────
def _render(stage: str, posts: list[dict], profile_md: str) -> str:
    """str.replace 注入占位符。用户文本可能含 {} ，str.replace 不会炸。"""
    history, request = _split(posts)
    return (
        _PROMPT
        .replace("{{stage}}", stage)
        .replace("{{history}}", history)
        .replace("{{user_profile}}", profile_md.strip() or "(none yet)")
        .replace("{{request}}", request)
    )


def _split(posts: list[dict]) -> tuple[str, str]:
    """便签拆成 (history, 当前 request)。当前 = 最后一条，其余进 history。"""
    clean = [(str(p.get("role", "post")), str(p.get("text", "")).strip())
             for p in posts if str(p.get("text", "")).strip()]
    if not clean:
        return "(none)", "(empty)"
    *hist, last = clean
    history = "\n".join(f"- {r}: {t}" for r, t in hist) or "(none)"
    return history, last[1]


def _join(posts: list[dict], profile_md: str) -> str:
    """fallback 用：把便签 + 画像拼成一句检索词。"""
    parts = [str(p.get("text", "")).strip() for p in posts if str(p.get("text", "")).strip()]
    if profile_md.strip():
        parts.append(f"taste profile: {profile_md.strip()}")
    return "; ".join(parts)


def _responses(instructions: str, user_text: str, tools=None, tool_choice=None) -> dict:
    body = {
        "model": config.OPENAI_MODEL,
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": user_text}]}],
    }
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice
    r = requests.post(
        f"{config.OPENAI_BASE_URL.rstrip('/')}/responses",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=config.OPENAI_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                return content["text"]
    raise ValueError("OpenAI response did not contain output text")


def _tool_call_args(payload: dict) -> dict:
    """从 Responses 输出里抠出 search_by_prompt 的 function_call 参数。"""
    for item in payload.get("output", []):
        if item.get("type") == "function_call" and item.get("name") == "search_by_prompt":
            return json.loads(item.get("arguments") or "{}")
    raise ValueError("OpenAI response did not contain a search_by_prompt tool call")


if __name__ == "__main__":  # 自检：fallback + str.replace 注入 + tool-call 解析
    config.OPENAI_API_KEY = ""  # 强制走离线 fallback，自检不打网络
    posts = [{"role": "initial_prompt", "text": "适合健身的"}, {"role": "follow_up", "text": "要带劲 {x}"}]

    # fallback（无 key）：interpret 出解读、search_args 出 query，均不炸 {}
    assert interpret(posts, "喜欢电子") == "I understand the target as: 适合健身的; 要带劲 {x}; taste profile: 喜欢电子"
    assert search_args(posts, "喜欢电子") == {"query": "适合健身的; 要带劲 {x}; taste profile: 喜欢电子",
                                              "metadata_filter": None}

    card = compile_query_card(posts, "喜欢电子")
    assert card["free_text_query"] == "" and card["metadata_filter"] is None  # 检索参数留到 confirm

    r = _render("search", posts, "喜欢电子 {y}")
    assert "{{stage}}" not in r and "{{request}}" not in r and "{{user_profile}}" not in r
    assert "要带劲 {x}" in r and "喜欢电子 {y}" in r  # 用户文本里的 {} 原样保留

    h, req = _split(posts)
    assert req == "要带劲 {x}" and "适合健身的" in h

    args = _tool_call_args({"output": [
        {"type": "function_call", "name": "search_by_prompt",
         "arguments": '{"query": "high energy workout", "metadata_filter": {"BpmV2.tag": {"$gte": 120}}}'},
    ]})
    assert args["query"] == "high energy workout"
    assert args["metadata_filter"] == {"BpmV2.tag": {"$gte": 120}}

    # sounds_like_you / surprise：无 key 或空画像 → None（不打网络）
    assert sounds_like_you_args("flowing ethereal calm") is None  # 无 key
    assert sounds_like_you_args("") is None and surprise_args(posts, "") is None  # 空画像

    print("intent_agent self-check OK")
