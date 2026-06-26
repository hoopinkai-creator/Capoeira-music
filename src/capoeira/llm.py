"""Thin Anthropic helper for translation + transcript structuring.

Enabled when the ``anthropic`` package is installed (``[ai]`` extra) and
``ANTHROPIC_API_KEY`` is set. Every caller has an offline fallback, so the
pipeline still runs (with reduced glossary/notes quality) when AI is unavailable.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from .deps import have


def available() -> bool:
    return have("anthropic") and bool(os.environ.get("ANTHROPIC_API_KEY"))


def ask_json(system: str, user: str, model: str, max_tokens: int = 2000) -> Any:
    """Call the model and parse a JSON object/array from its reply.

    Raises RuntimeError if AI is unavailable; callers should check
    :func:`available` first or catch and fall back.
    """
    if not available():
        raise RuntimeError("Anthropic AI not available (install [ai] extra + set ANTHROPIC_API_KEY)")
    import anthropic  # noqa: imported lazily

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    return _extract_json(text)


def _extract_json(text: str) -> Any:
    text = text.strip()
    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost {...} or [...].
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise
