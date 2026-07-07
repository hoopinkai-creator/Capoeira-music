"""Instagram comment-reply bot.

A small, dependency-light tool that reads comments on an Instagram reel/post
via the official Instagram Graph API and posts replies — from a template or an
optional AI model. Defaults to a dry run and never double-replies to the same
comment.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .api import Comment, GraphClient, list_comments, reply_to_comment, shortcode_from_url
from .bot import ReplyAction, RunResult, run
from .config import Config

__all__ = [
    "Comment",
    "Config",
    "GraphClient",
    "ReplyAction",
    "RunResult",
    "list_comments",
    "reply_to_comment",
    "run",
    "shortcode_from_url",
]
