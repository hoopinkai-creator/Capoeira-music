"""ManyChat-style keyword rules: comment text -> public reply (+ optional DM).

Each rule has a list of trigger keywords, a public ``reply``, and an optional
``dm`` (a private reply / direct message, like ManyChat's "send in DM"). The
first rule whose keyword is found in the comment wins. If no rule matches, the
default reply (template or AI, see :mod:`replies`) is used — unless
``only_rules`` is set, in which case unmatched comments are left alone.

Config shape (``rules:`` in the YAML)::

    rules:
      - name: pricing
        keywords: ["price", "preço", "quanto custa"]
        reply: "Oi @{name}! Te mandei os valores no direct 🙌"
        dm: "Class prices: ..."          # optional
        match: substring                 # substring (default) | word | exact
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .api import Comment
from .replies import compose_reply


@dataclass
class Rule:
    keywords: list[str]
    reply: str
    dm: str | None = None
    name: str = ""
    match: str = "substring"  # substring | word | exact

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rule":
        kws = data.get("keywords") or []
        if isinstance(kws, str):
            kws = [kws]
        return cls(
            keywords=[str(k).lower() for k in kws],
            reply=data.get("reply", ""),
            dm=data.get("dm"),
            name=data.get("name", ""),
            match=str(data.get("match", "substring")).lower(),
        )

    def matches(self, text: str) -> bool:
        low = text.lower()
        for kw in self.keywords:
            if not kw:
                continue
            if self.match == "exact":
                if low.strip() == kw:
                    return True
            elif self.match == "word":
                if re.search(rf"\b{re.escape(kw)}\b", low):
                    return True
            else:  # substring
                if kw in low:
                    return True
        return False


def load_rules(cfg: Any) -> list[Rule]:
    return [Rule.from_dict(r) for r in (cfg.get("rules") or [])]


@dataclass
class ReplyPlan:
    """What to do about one comment."""

    public_reply: str | None
    dm: str | None = None
    rule_name: str = ""
    matched: bool = False


def plan_reply(comment: Comment, cfg: Any, rules: list[Rule] | None = None) -> ReplyPlan:
    """Decide the public reply (and any DM) for a comment.

    1. First matching keyword rule wins -> its reply (+ optional DM).
    2. No match + ``only_rules`` true  -> do nothing (public_reply is None).
    3. No match otherwise              -> default template/AI reply, no DM.
    """
    rules = load_rules(cfg) if rules is None else rules
    name = comment.username or "amigo"
    send_dm = cfg.get("send_dm", True)

    for rule in rules:
        if rule.matches(comment.text):
            reply = (rule.reply or "").format(name=name, text=comment.text)
            dm = rule.dm.format(name=name, text=comment.text) if (rule.dm and send_dm) else None
            return ReplyPlan(public_reply=reply or None, dm=dm, rule_name=rule.name, matched=True)

    if cfg.get("only_rules", False):
        return ReplyPlan(public_reply=None, matched=False)

    return ReplyPlan(public_reply=compose_reply(comment, cfg), matched=False)
