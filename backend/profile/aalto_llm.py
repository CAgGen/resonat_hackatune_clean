"""Thin client for the Aalto OpenAI API gateway (Azure APIM, Responses API).

Auth is a subscription key in the `Ocp-Apim-Subscription-Key` header, and every
request path is rewritten to `/v1/openai/responses` (mirrors AaltoML's repo).
Requires being on the Aalto network.
"""
import json

import httpx
from openai import OpenAI

from . import config


def _client():
    def _rewrite(req):
        req.url = req.url.copy_with(path="/v1/openai/responses")
    return OpenAI(
        base_url=config.AALTO_BASE_URL, api_key="unused",
        default_headers={"Ocp-Apim-Subscription-Key": config.AALTO_OPENAI_API_KEY},
        http_client=httpx.Client(event_hooks={"request": [_rewrite]}, timeout=90),
    )


def complete(user, system=None, model=None):
    """Single-turn completion -> text."""
    r = _client().responses.create(
        model=model or config.AALTO_MODEL,
        instructions=system or "",
        input=[{"role": "user", "content": [{"type": "input_text", "text": user}]}],
    )
    return r.output_text.strip()


def complete_json(user, system=None, model=None):
    """Completion expected to return JSON -> parsed dict (tolerant of fences/prose)."""
    txt = complete(user, system, model)
    a, b = txt.find("{"), txt.rfind("}")
    return json.loads(txt[a:b + 1])


def available():
    return bool(config.AALTO_OPENAI_API_KEY)
