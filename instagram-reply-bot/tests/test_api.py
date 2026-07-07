"""Tests for URL parsing and the Graph client (network fully stubbed)."""
import io
import json

import pytest

from instagram_reply_bot.api import (
    GraphAPIError,
    GraphClient,
    find_media_id,
    list_comments,
    list_media,
    reply_to_comment,
    send_private_reply,
    shortcode_from_url,
)


def test_shortcode_from_reel_url():
    url = "https://www.instagram.com/reel/Dac_XkRBKzo/?igsh=MXN0a2QwZDkyaHRiMA=="
    assert shortcode_from_url(url) == "Dac_XkRBKzo"


def test_shortcode_from_post_url():
    assert shortcode_from_url("https://instagram.com/p/AbC-123_x/") == "AbC-123_x"


def test_shortcode_bad_url_raises():
    with pytest.raises(ValueError):
        shortcode_from_url("https://example.com/not-instagram")


class FakeOpener:
    """Stub urlopen: returns queued JSON responses and records requests."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def __call__(self, req):
        self.requests.append(req)
        body = self._responses.pop(0)
        resp = io.BytesIO(json.dumps(body).encode())
        resp.__enter__ = lambda: resp
        resp.__exit__ = lambda *a: False
        return resp


def _client(responses):
    opener = FakeOpener(responses)
    return GraphClient("TOKEN", opener=opener), opener


def test_get_injects_token_and_parses():
    client, opener = _client([{"data": []}])
    out = client.get("123/comments", {"fields": "id"})
    assert out == {"data": []}
    assert "access_token=TOKEN" in opener.requests[0].full_url


def test_error_payload_raises():
    client, _ = _client([{"error": {"message": "bad token"}}])
    with pytest.raises(GraphAPIError):
        client.get("me")


def test_find_media_id_matches_permalink_across_pages():
    responses = [
        {
            "data": [{"id": "1", "permalink": "https://instagram.com/reel/AAA/"}],
            "paging": {"cursors": {"after": "CURSOR"}},
        },
        {
            "data": [{"id": "2", "permalink": "https://instagram.com/reel/Dac_XkRBKzo/"}],
        },
    ]
    client, _ = _client(responses)
    assert find_media_id(client, "USER", "Dac_XkRBKzo") == "2"


def test_find_media_id_returns_none_when_absent():
    client, _ = _client([{"data": [{"id": "1", "permalink": ".../reel/ZZZ/"}]}])
    assert find_media_id(client, "USER", "Dac_XkRBKzo") is None


def test_list_comments_follows_pagination():
    responses = [
        {
            "data": [{"id": "c1", "text": "oi", "username": "a", "timestamp": "t1"}],
            "paging": {"cursors": {"after": "NEXT"}},
        },
        {"data": [{"id": "c2", "text": "nice", "username": "b", "timestamp": "t2"}]},
    ]
    client, _ = _client(responses)
    comments = list_comments(client, "MEDIA")
    assert [c.id for c in comments] == ["c1", "c2"]
    assert comments[0].text == "oi"


def test_reply_posts_message_and_returns_id():
    client, opener = _client([{"id": "reply-1"}])
    assert reply_to_comment(client, "c1", "Axé!") == "reply-1"
    posted = opener.requests[0]
    assert posted.method == "POST"
    assert b"message=" in posted.data


def test_list_media_respects_limit_across_pages():
    responses = [
        {
            "data": [{"id": "1", "permalink": "p1"}, {"id": "2", "permalink": "p2"}],
            "paging": {"cursors": {"after": "NEXT"}},
        },
        {"data": [{"id": "3", "permalink": "p3"}]},
    ]
    client, _ = _client(responses)
    media = list_media(client, "USER", limit=3)
    assert [m["id"] for m in media] == ["1", "2", "3"]


def test_send_private_reply_posts_json_body():
    client, opener = _client([{"message_id": "dm-1"}])
    assert send_private_reply(client, "USER", "c1", "Prices: R$120") == "dm-1"
    req = opener.requests[0]
    assert req.method == "POST"
    assert req.get_header("Content-type") == "application/json"
    payload = json.loads(req.data.decode())
    assert payload["recipient"] == {"comment_id": "c1"}
    assert payload["message"] == {"text": "Prices: R$120"}
