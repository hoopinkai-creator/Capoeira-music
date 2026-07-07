"""Orchestrate: resolve the post, read comments, compose + post replies.

Defaults to a **dry run** — it composes replies and reports what it *would*
send without posting. Pass ``dry_run=False`` to actually reply. Already-answered
comments (tracked in the state file) are skipped every run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .api import (
    Comment,
    GraphClient,
    find_media_id,
    list_comments,
    reply_to_comment,
    shortcode_from_url,
)
from .config import Config
from .replies import compose_reply
from .state import load_replied, save_replied


@dataclass
class ReplyAction:
    comment: Comment
    reply: str
    sent: bool
    reply_id: str = ""
    error: str = ""


@dataclass
class RunResult:
    media_id: str
    total_comments: int
    dry_run: bool
    actions: list[ReplyAction] = field(default_factory=list)

    @property
    def sent_count(self) -> int:
        return sum(1 for a in self.actions if a.sent)


def run(
    cfg: Config,
    *,
    dry_run: bool = True,
    limit: int | None = None,
    client: GraphClient | None = None,
) -> RunResult:
    """Reply to not-yet-answered comments on the configured post."""
    post_url = cfg.get("post_url")
    if not post_url and not cfg.get("media_id"):
        raise RuntimeError("Set 'post_url' (or 'media_id') in your config file.")

    token, user_id = cfg.require_credentials()
    client = client or GraphClient(token, api_version=cfg.get("graph_api_version"))

    media_id = cfg.get("media_id")
    if not media_id:
        shortcode = shortcode_from_url(post_url)
        media_id = find_media_id(client, user_id, shortcode)
    if not media_id:
        raise RuntimeError(
            "Could not find the media on this account. The reel/post must be "
            "owned by INSTAGRAM_USER_ID and the token must have the "
            "instagram_manage_comments permission. You can also set 'media_id' "
            "directly in the config."
        )

    own_username = os.environ.get("INSTAGRAM_USERNAME", "").lstrip("@").lower()
    skip_own = cfg.get("skip_own_comments", True)

    comments = list_comments(client, media_id)
    replied = load_replied(cfg.state_path())

    result = RunResult(media_id=media_id, total_comments=len(comments), dry_run=dry_run)
    for comment in comments:
        if comment.id in replied:
            continue
        if skip_own and own_username and comment.username.lower() == own_username:
            continue
        if limit is not None and len(result.actions) >= limit:
            break

        text = compose_reply(comment, cfg)
        if dry_run:
            result.actions.append(ReplyAction(comment, text, sent=False))
            continue
        try:
            reply_id = reply_to_comment(client, comment.id, text)
            replied.add(comment.id)
            result.actions.append(
                ReplyAction(comment, text, sent=True, reply_id=reply_id)
            )
        except Exception as exc:  # pragma: no cover - network failure path
            result.actions.append(ReplyAction(comment, text, sent=False, error=str(exc)))

    if not dry_run and result.sent_count:
        save_replied(cfg.state_path(), replied)
    return result
