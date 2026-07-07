"""Orchestrate: resolve target posts, read comments, apply rules, post replies.

Works on one post, an explicit list of posts, or **every post on the account**
(``auto_discover``). For each unanswered comment it applies the ManyChat-style
keyword rules to pick a public reply and an optional DM (private reply).

Defaults to a **dry run** — it composes everything and reports what it *would*
send without posting. Pass ``dry_run=False`` to actually reply. Comments already
handled (tracked in the state file) are skipped every run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .api import (
    Comment,
    GraphClient,
    find_media_id,
    list_comments,
    list_media,
    reply_to_comment,
    send_private_reply,
    shortcode_from_url,
)
from .config import Config
from .rules import ReplyPlan, load_rules, plan_reply
from .state import load_replied, save_replied


@dataclass
class Target:
    media_id: str
    label: str = ""


@dataclass
class ReplyAction:
    comment: Comment
    media_id: str
    plan: ReplyPlan
    sent: bool = False
    dm_sent: bool = False
    reply_id: str = ""
    error: str = ""

    @property
    def reply(self) -> str | None:
        return self.plan.public_reply


@dataclass
class RunResult:
    targets: list[Target]
    total_comments: int
    dry_run: bool
    actions: list[ReplyAction] = field(default_factory=list)

    @property
    def sent_count(self) -> int:
        return sum(1 for a in self.actions if a.sent)

    @property
    def dm_count(self) -> int:
        return sum(1 for a in self.actions if a.dm_sent)


def resolve_targets(cfg: Config, client: GraphClient, user_id: str) -> list[Target]:
    """Figure out which media to operate on, from config.

    Priority: ``auto_discover`` (all posts) > ``posts`` list > single
    ``media_id``/``post_url``.
    """
    if cfg.get("auto_discover"):
        media = list_media(client, user_id, limit=cfg.get("max_posts"))
        return [Target(media_id=m["id"], label=m.get("permalink", "")) for m in media]

    urls = cfg.get("posts")
    if urls:
        targets: list[Target] = []
        for url in urls:
            mid = find_media_id(client, user_id, shortcode_from_url(url))
            if mid:
                targets.append(Target(media_id=mid, label=url))
        return targets

    if cfg.get("media_id"):
        return [Target(media_id=cfg.get("media_id"), label="(configured media_id)")]

    post_url = cfg.get("post_url")
    if post_url:
        mid = find_media_id(client, user_id, shortcode_from_url(post_url))
        return [Target(media_id=mid, label=post_url)] if mid else []

    return []


def run(
    cfg: Config,
    *,
    dry_run: bool = True,
    limit: int | None = None,
    client: GraphClient | None = None,
) -> RunResult:
    """Reply to not-yet-answered comments across the configured post(s)."""
    if not (cfg.get("auto_discover") or cfg.get("posts") or cfg.get("media_id") or cfg.get("post_url")):
        raise RuntimeError(
            "Nothing to target. Set 'post_url', a 'posts' list, 'media_id', or "
            "'auto_discover: true' in your config file."
        )

    token, user_id = cfg.require_credentials()
    client = client or GraphClient(token, api_version=cfg.get("graph_api_version"))

    targets = resolve_targets(cfg, client, user_id)
    if not targets:
        raise RuntimeError(
            "No target media found on this account. The post(s) must be owned by "
            "INSTAGRAM_USER_ID and the token must have instagram_manage_comments."
        )

    own_username = os.environ.get("INSTAGRAM_USERNAME", "").lstrip("@").lower()
    skip_own = cfg.get("skip_own_comments", True)
    rules = load_rules(cfg)

    replied = load_replied(cfg.state_path())
    result = RunResult(targets=targets, total_comments=0, dry_run=dry_run)

    for target in targets:
        comments = list_comments(client, target.media_id)
        result.total_comments += len(comments)
        for comment in comments:
            if comment.id in replied:
                continue
            if skip_own and own_username and comment.username.lower() == own_username:
                continue
            if limit is not None and len(result.actions) >= limit:
                break

            plan = plan_reply(comment, cfg, rules)
            if plan.public_reply is None and plan.dm is None:
                continue  # only_rules mode with no matching rule

            action = ReplyAction(comment=comment, media_id=target.media_id, plan=plan)
            if dry_run:
                result.actions.append(action)
                continue
            try:
                if plan.public_reply:
                    action.reply_id = reply_to_comment(client, comment.id, plan.public_reply)
                    action.sent = True
                if plan.dm:
                    send_private_reply(client, user_id, comment.id, plan.dm)
                    action.dm_sent = True
                replied.add(comment.id)
            except Exception as exc:  # pragma: no cover - network failure path
                action.error = str(exc)
            result.actions.append(action)

    if not dry_run and result.sent_count:
        save_replied(cfg.state_path(), replied)
    return result
