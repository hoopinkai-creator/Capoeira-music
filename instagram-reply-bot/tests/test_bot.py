"""Tests for reply composition, state, and the run() orchestrator."""
import json

import pytest

from instagram_reply_bot.api import Comment, GraphClient
from instagram_reply_bot.bot import run
from instagram_reply_bot.config import Config
from instagram_reply_bot.replies import compose_reply
from instagram_reply_bot.state import load_replied, save_replied


def _cfg(tmp_path, **overrides):
    cfg = Config.load()
    cfg.root = tmp_path
    cfg.settings["post_url"] = "https://www.instagram.com/reel/Dac_XkRBKzo/"
    cfg.settings.update(overrides)
    return cfg


def test_compose_reply_template_fills_name():
    c = Comment(id="1", text="linda!", username="joana", timestamp="t")
    cfg = Config.load()
    assert compose_reply(c, cfg) == "Axé! 🙏 Obrigado pelo comentário, @joana!"


def test_compose_reply_defaults_missing_username():
    c = Comment(id="1", text="", username="", timestamp="t")
    cfg = Config.load()
    assert "@amigo" in compose_reply(c, cfg)


def test_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    assert load_replied(path) == set()
    save_replied(path, {"a", "b"})
    assert load_replied(path) == {"a", "b"}


class ScriptedClient(GraphClient):
    """GraphClient that returns canned pages and records posted replies."""

    def __init__(self, media_pages, comment_pages):
        super().__init__("TOKEN", opener=lambda req: None)
        self._media = list(media_pages)
        self._comments = list(comment_pages)
        self.posted = []

    def get(self, path, params=None):
        if "/media" in path:
            return self._media.pop(0)
        if "/comments" in path:
            return self._comments.pop(0)
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, data):
        self.posted.append((path, data["message"]))
        return {"id": f"reply-{len(self.posted)}"}


def _client():
    media = [{"data": [{"id": "MEDIA", "permalink": ".../reel/Dac_XkRBKzo/"}]}]
    comments = [
        {
            "data": [
                {"id": "c1", "text": "oi", "username": "ana", "timestamp": "t1"},
                {"id": "c2", "text": "top", "username": "bia", "timestamp": "t2"},
            ]
        }
    ]
    return ScriptedClient(media, comments)


def test_run_dry_run_posts_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "T")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "USER")
    client = _client()
    result = run(_cfg(tmp_path), dry_run=True, client=client)
    assert result.total_comments == 2
    assert len(result.actions) == 2
    assert all(not a.sent for a in result.actions)
    assert client.posted == []


def test_run_send_posts_and_records_state(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "T")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "USER")
    cfg = _cfg(tmp_path)
    client = _client()
    result = run(cfg, dry_run=False, client=client)
    assert result.sent_count == 2
    assert len(client.posted) == 2
    # State persisted so a second run skips both.
    saved = json.loads(cfg.state_path().read_text())
    assert set(saved["replied"]) == {"c1", "c2"}


def test_run_skips_already_replied(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "T")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "USER")
    cfg = _cfg(tmp_path)
    save_replied(cfg.state_path(), {"c1"})
    client = _client()
    result = run(cfg, dry_run=False, client=client)
    assert len(client.posted) == 1
    assert client.posted[0][1]  # replied only to c2


def test_run_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "T")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "USER")
    client = _client()
    result = run(_cfg(tmp_path), dry_run=True, limit=1, client=client)
    assert len(result.actions) == 1


def test_run_without_credentials_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    with pytest.raises(RuntimeError):
        run(_cfg(tmp_path), dry_run=True, client=_client())
