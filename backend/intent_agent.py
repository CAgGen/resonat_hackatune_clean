"""Seam · intent analysis agent.

Two-stage flow with two independent LLM calls. The prompt lives in prompts/intent_agent.md,
and placeholders are injected with str.replace:
  1. interpret -> compile_query_card(): the confirmation gate creates a concise user-facing
     interpretation (~200 words). Rerun whenever the whiteboard changes; no retrieval.
  2. search -> search_args(): after user confirmation, orchestrator.confirm() calls this once.
     Tool calling asks the model to issue search_by_prompt(query, metadata_filter); we parse
     the arguments, and confirm() performs the real Cyanite call (one retrieval call end to end).

Contract (used by orchestration):
    compile_query_card(posts, profile_md="") -> dict   # confirmation-gate Query Card (interpretation only)
    search_args(posts, profile_md="")       -> dict    # retrieval args {query, metadata_filter}

compile_query_card returns:
    {
      "interpretation_plain": str,          # interpretation
      "free_text_query": "",                # left empty; confirm fills after search_args
      "metadata_filter": None,              # same
    }
search_args returns:
    {"query": str, "metadata_filter": dict | None}

Use the LLM when OPENAI_API_KEY is present; otherwise use a deterministic fallback so offline orchestration/tests run.
"""
from __future__ import annotations

import json
import pathlib
import re

import requests

import config

# Fallback: frontend renders plain text, so strip occasional markdown leaked by the model
# (bold markers, leading list/header symbols).
_MD = re.compile(r"\*\*|__|`|^\s*[-*•#]+\s+", re.M)


def _plain(text: str) -> str:
    return _MD.sub("", text).strip()

_PROMPT_PATH = pathlib.Path(__file__).resolve().parent / "prompts" / "intent_agent.md"
_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# search_by_prompt tool schema (Responses API function tool).
# metadata_filter is a free-form MongoDB-style object, so do not constrain it strictly.
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
    """1. Confirmation gate: only produce interpretation. Retrieval args are filled by confirm after search_args."""
    return {
        "interpretation_plain": interpret(posts, profile_md),
        "free_text_query": "",
        "metadata_filter": None,
    }


def interpret(posts: list[dict], profile_md: str = "") -> str:
    """1. Interpretation stage: return a concise ~200-word user-facing interpretation."""
    if not config.OPENAI_API_KEY:
        return f"I understand the target as: {_join(posts, profile_md)}"
    payload = _responses(_render("interpret", posts, profile_md), "Give the interpretation now.")
    return _plain(_output_text(payload))


def search_args(posts: list[dict], profile_md: str = "") -> dict:
    """2. Retrieval stage: use tool calling and parse {query, metadata_filter}."""
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
    """Sounds-like-you retrieval args: faithful to the long-term profile, with zero offset.
    No key or no profile -> None (no dedicated card)."""
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
    """Surprise-slot retrieval args: faithful to this round's need, deliberately offset from the profile.
    No key or no profile to offset from -> None (no surprise card)."""
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


# ─────────────────────────── Internals ───────────────────────────
def _render(stage: str, posts: list[dict], profile_md: str) -> str:
    """Inject placeholders with str.replace. User text may contain {}, and str.replace will not explode."""
    history, request = _split(posts)
    return (
        _PROMPT
        .replace("{{stage}}", stage)
        .replace("{{history}}", history)
        .replace("{{user_profile}}", profile_md.strip() or "(none yet)")
        .replace("{{request}}", request)
    )


def _split(posts: list[dict]) -> tuple[str, str]:
    """Split notes into (history, current request). Current is the last note; all others go into history."""
    clean = [(str(p.get("role", "post")), str(p.get("text", "")).strip())
             for p in posts if str(p.get("text", "")).strip()]
    if not clean:
        return "(none)", "(empty)"
    *hist, last = clean
    history = "\n".join(f"- {r}: {t}" for r, t in hist) or "(none)"
    return history, last[1]


def _join(posts: list[dict], profile_md: str) -> str:
    """Fallback helper: combine notes + profile into one search query."""
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
    """Extract search_by_prompt function_call args from Responses output."""
    for item in payload.get("output", []):
        if item.get("type") == "function_call" and item.get("name") == "search_by_prompt":
            return json.loads(item.get("arguments") or "{}")
    raise ValueError("OpenAI response did not contain a search_by_prompt tool call")


if __name__ == "__main__":  # Self-check: fallback + str.replace injection + tool-call parsing.
    config.OPENAI_API_KEY = ""  # Force offline fallback; self-check does not touch the network.
    posts = [{"role": "initial_prompt", "text": "good for workouts"}, {"role": "follow_up", "text": "make it energetic {x}"}]

    # Fallback (no key): interpret returns interpretation and search_args returns query; neither breaks on {}.
    assert interpret(posts, "likes electronic") == "I understand the target as: good for workouts; make it energetic {x}; taste profile: likes electronic"
    assert search_args(posts, "likes electronic") == {"query": "good for workouts; make it energetic {x}; taste profile: likes electronic",
                                                      "metadata_filter": None}

    card = compile_query_card(posts, "likes electronic")
    assert card["free_text_query"] == "" and card["metadata_filter"] is None  # Retrieval args are left for confirm.

    r = _render("search", posts, "likes electronic {y}")
    assert "{{stage}}" not in r and "{{request}}" not in r and "{{user_profile}}" not in r
    assert "make it energetic {x}" in r and "likes electronic {y}" in r  # Preserve user-provided {} literally.

    h, req = _split(posts)
    assert req == "make it energetic {x}" and "good for workouts" in h

    args = _tool_call_args({"output": [
        {"type": "function_call", "name": "search_by_prompt",
         "arguments": '{"query": "high energy workout", "metadata_filter": {"BpmV2.tag": {"$gte": 120}}}'},
    ]})
    assert args["query"] == "high energy workout"
    assert args["metadata_filter"] == {"BpmV2.tag": {"$gte": 120}}

    # sounds_like_you / surprise: no key or empty profile -> None (no network).
    assert sounds_like_you_args("flowing ethereal calm") is None  # No key.
    assert sounds_like_you_args("") is None and surprise_args(posts, "") is None  # Empty profile.

    print("intent_agent self-check OK")
