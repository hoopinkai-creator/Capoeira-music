"""Configuration + credentials for the Instagram reply bot.

Settings come from a small YAML file (see ``config.example.yaml``); secrets come
from the environment and are never written to disk:

    INSTAGRAM_ACCESS_TOKEN   long-lived Graph API token
    INSTAGRAM_USER_ID        numeric IG business account id (owner of the reel)
    ANTHROPIC_API_KEY        optional — enables AI-composed replies
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - yaml is a core dependency
    yaml = None

from .api import DEFAULT_API_VERSION

_DEFAULTS: dict[str, Any] = {
    "post_url": None,
    "media_id": None,          # set to skip the media lookup entirely
    "graph_api_version": DEFAULT_API_VERSION,
    "reply_mode": "template",  # "template" | "ai"
    "reply_template": "Axé! 🙏 Obrigado pelo comentário, @{name}!",
    "ai_model": "claude-opus-4-8",
    "ai_system_prompt": None,  # override the default AI persona if you like
    "state_file": "instagram_replies.json",
    "skip_own_comments": True,
}


@dataclass
class Config:
    settings: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULTS))
    root: Path = field(default_factory=Path.cwd)

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Config":
        root = Path.cwd()
        settings = dict(_DEFAULTS)
        if path:
            p = Path(path)
            root = p.resolve().parent
            if p.exists():
                if yaml is None:  # pragma: no cover
                    raise RuntimeError("PyYAML is required to read a config file.")
                loaded = yaml.safe_load(p.read_text()) or {}
                settings.update(loaded)
        return cls(settings=settings, root=root)

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    # --- credentials ----------------------------------------------------------
    @staticmethod
    def credentials_available() -> bool:
        return bool(os.environ.get("INSTAGRAM_ACCESS_TOKEN")) and bool(
            os.environ.get("INSTAGRAM_USER_ID")
        )

    @staticmethod
    def require_credentials() -> tuple[str, str]:
        token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
        user_id = os.environ.get("INSTAGRAM_USER_ID")
        if not token or not user_id:
            raise RuntimeError(
                "Instagram API not configured. Set INSTAGRAM_ACCESS_TOKEN and "
                "INSTAGRAM_USER_ID (a Business/Creator account with the "
                "instagram_manage_comments permission)."
            )
        return token, user_id

    def state_path(self) -> Path:
        rel = self.get("state_file") or "instagram_replies.json"
        p = Path(rel)
        return p if p.is_absolute() else self.root / p
