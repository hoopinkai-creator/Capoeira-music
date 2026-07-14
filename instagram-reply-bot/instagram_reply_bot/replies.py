"""Compose the reply text for a comment.

Two modes, chosen by ``reply_mode`` in config:

* ``template`` (default) — fill ``reply_template`` with ``{name}`` / ``{text}``.
* ``ai`` — ask an Anthropic model for one short, warm reply in the commenter's
  language. Requires the ``[ai]`` extra and ``ANTHROPIC_API_KEY``; if either is
  missing or the call fails, it silently falls back to the template so the bot
  never blocks on AI.
"""
from __future__ import annotations

import os
from typing import Any

from .api import Comment

_DEFAULT_AI_SYSTEM = (
    "You reply to comments on an Instagram reel. Keep replies to ONE short, "
    "warm, genuine sentence in the commenter's apparent language. Add one "
    "tasteful emoji when it fits. Never use hashtags. Return ONLY the reply "
    "text — no quotes, no preamble."
)


def _ai_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _ai_reply(comment: Comment, cfg: Any, name: str) -> str | None:
    import anthropic

    system = cfg.get("ai_system_prompt") or _DEFAULT_AI_SYSTEM
    user = f"Commenter @{name} wrote: {comment.text!r}\nWrite the reply text."
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=cfg.get("ai_model") or "claude-opus-4-8",
        max_tokens=120,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    )
    return text.strip().strip('"') or None


def compose_reply(comment: Comment, cfg: Any) -> str:
    """Return the reply text for ``comment`` given the loaded config."""
    name = comment.username or "amigo"
    template = cfg.get("reply_template") or "Axé! 🙏 Obrigado, @{name}!"
    fallback = template.format(name=name, text=comment.text)

    if cfg.get("reply_mode") == "ai" and _ai_available():
        try:
            text = _ai_reply(comment, cfg, name)
            if text:
                return text
        except Exception:
            # Any AI hiccup (network, quota, parse) degrades to the template.
            pass
    return fallback
