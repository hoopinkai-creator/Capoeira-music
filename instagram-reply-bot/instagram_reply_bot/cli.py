"""Command-line interface for the Instagram reply bot.

    ig-reply-bot check                 # verify credentials + resolve the post
    ig-reply-bot comments              # list comments on the configured post
    ig-reply-bot reply                 # DRY RUN: show replies it would send
    ig-reply-bot reply --send          # actually post the replies
    ig-reply-bot reply --send --limit 5

Configure the post + reply style in a YAML file (default: ./config.yaml, or
pass --config PATH). Secrets come from the environment; see the README.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .api import GraphClient, list_comments
from .bot import resolve_targets, run
from .config import Config


def _load_config(path: str | None) -> Config:
    if path:
        return Config.load(path)
    default = Path.cwd() / "config.yaml"
    return Config.load(default if default.exists() else None)


def _cmd_check(cfg: Config) -> int:
    if not Config.credentials_available():
        print(
            "✗ Missing credentials. Set INSTAGRAM_ACCESS_TOKEN and "
            "INSTAGRAM_USER_ID in your environment.",
            file=sys.stderr,
        )
        return 1
    token, user_id = cfg.require_credentials()
    client = GraphClient(token, api_version=cfg.get("graph_api_version"))
    targets = resolve_targets(cfg, client, user_id)
    if not targets:
        print("✗ Credentials OK, but no target post was found on this account.", file=sys.stderr)
        return 1
    print(f"✓ Credentials OK. Account {user_id} — {len(targets)} target post(s):")
    for t in targets:
        print(f"    {t.media_id}  {t.label}")
    return 0


def _cmd_comments(cfg: Config) -> int:
    token, user_id = cfg.require_credentials()
    client = GraphClient(token, api_version=cfg.get("graph_api_version"))
    targets = resolve_targets(cfg, client, user_id)
    if not targets:
        print("✗ No target post found on this account.", file=sys.stderr)
        return 1
    total = 0
    for t in targets:
        comments = list_comments(client, t.media_id)
        total += len(comments)
        print(f"{len(comments)} comment(s) on media {t.media_id}  {t.label}:")
        for c in comments:
            print(f"    [{c.timestamp}] @{c.username}: {c.text}")
    print(f"\n{total} comment(s) across {len(targets)} post(s).")
    return 0


def _cmd_reply(cfg: Config, send: bool, limit: int | None) -> int:
    result = run(cfg, dry_run=not send, limit=limit)
    mode = "SENT" if send else "DRY RUN (nothing posted; pass --send to post)"
    print(f"{mode} — {len(result.targets)} post(s), {result.total_comments} comment(s)")
    if not result.actions:
        print("  Nothing to do — all comments already answered (or no rule matched).")
        return 0
    for a in result.actions:
        status = "sent" if a.sent else ("ERROR" if a.error else "would send")
        tag = f" [rule:{a.plan.rule_name or 'match'}]" if a.plan.matched else ""
        print(f"  @{a.comment.username}: {a.comment.text}")
        print(f"      -> [{status}]{tag} {a.reply}")
        if a.plan.dm:
            dm_status = "sent" if a.dm_sent else ("ERROR" if a.error else "would send")
            print(f"      DM [{dm_status}]: {a.plan.dm}")
        if a.error:
            print(f"         {a.error}")
    if send:
        print(f"\nPosted {result.sent_count} repl(y/ies), {result.dm_count} DM(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ig-reply-bot", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help="Path to config YAML (default: ./config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Verify credentials and resolve the post.")
    sub.add_parser("comments", help="List comments on the configured post.")
    r = sub.add_parser("reply", help="Reply to unanswered comments (dry run by default).")
    r.add_argument("--send", action="store_true", help="Actually post replies.")
    r.add_argument("--limit", type=int, default=None, help="Max comments to reply to.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = _load_config(args.config)
    try:
        if args.command == "check":
            return _cmd_check(cfg)
        if args.command == "comments":
            return _cmd_comments(cfg)
        if args.command == "reply":
            return _cmd_reply(cfg, send=args.send, limit=args.limit)
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
