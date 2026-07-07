"""Thin Instagram Graph API client (stdlib only — no third-party deps).

The Graph API is the only supported way to read and reply to comments
programmatically. To use it you need:

* an Instagram **Business or Creator** account that owns the reel/post,
* that account linked to a Facebook Page,
* a long-lived access token with ``instagram_manage_comments`` +
  ``instagram_basic`` permissions.

Docs: https://developers.facebook.com/docs/instagram-api/guides/comment-moderation
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_API_VERSION = "v21.0"
GRAPH_BASE = "https://graph.facebook.com"


# --- url / shortcode helpers ---------------------------------------------------
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")


def shortcode_from_url(url: str) -> str:
    """Extract the media shortcode from a reel/post URL.

    ``https://www.instagram.com/reel/Dac_XkRBKzo/?igsh=...`` -> ``Dac_XkRBKzo``.
    Raises ValueError if the URL doesn't look like an Instagram media link.
    """
    match = _SHORTCODE_RE.search(url)
    if not match:
        raise ValueError(f"Could not find an Instagram shortcode in URL: {url!r}")
    return match.group(1)


# --- data ----------------------------------------------------------------------
@dataclass
class Comment:
    id: str
    text: str
    username: str
    timestamp: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Comment":
        return cls(
            id=data["id"],
            text=data.get("text", ""),
            username=data.get("username", ""),
            timestamp=data.get("timestamp", ""),
        )


class GraphAPIError(RuntimeError):
    """Raised when the Graph API returns an error payload or HTTP error."""


# --- client --------------------------------------------------------------------
class GraphClient:
    """Minimal Instagram Graph API client."""

    def __init__(
        self,
        token: str,
        api_version: str = DEFAULT_API_VERSION,
        *,
        opener: Callable[[urllib.request.Request], Any] | None = None,
    ) -> None:
        self.token = token
        self.api_version = api_version
        # Injectable so tests can stub the network entirely.
        self._opener = opener or urllib.request.urlopen

    def _url(self, path: str) -> str:
        return f"{GRAPH_BASE}/{self.api_version}/{path.lstrip('/')}"

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["access_token"] = self.token
        url = self._url(path) + "?" + urllib.parse.urlencode(query)
        return self._read(urllib.request.Request(url, method="GET"))

    def post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        payload = dict(data)
        payload["access_token"] = self.token
        body = urllib.parse.urlencode(payload).encode()
        return self._read(urllib.request.Request(self._url(path), data=body, method="POST"))

    def _read(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener(req) as resp:
                parsed = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode(errors="replace")
            raise GraphAPIError(f"HTTP {exc.code} from Graph API: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise GraphAPIError(f"Network error calling Graph API: {exc.reason}") from exc
        if isinstance(parsed, dict) and "error" in parsed:
            raise GraphAPIError(str(parsed["error"]))
        return parsed


# --- media + comments ----------------------------------------------------------
def find_media_id(client: GraphClient, user_id: str, shortcode: str) -> str | None:
    """Resolve a shortcode to a media id by scanning the account's own media.

    The Graph API has no public shortcode->id lookup, so we page through the
    authenticated account's media and match on the permalink. This only finds a
    reel/post owned by ``user_id`` — which is exactly the media you're allowed
    to reply on.
    """
    path = f"{user_id}/media"
    params = {"fields": "id,permalink", "limit": "50"}
    while True:
        page = client.get(path, params)
        for media in page.get("data", []):
            if shortcode in media.get("permalink", ""):
                return media["id"]
        after = page.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            return None
        params = {**params, "after": after}


def list_comments(client: GraphClient, media_id: str) -> list[Comment]:
    """Return all top-level comments on a media, following pagination."""
    comments: list[Comment] = []
    path = f"{media_id}/comments"
    params = {"fields": "id,text,username,timestamp", "limit": "50"}
    while True:
        page = client.get(path, params)
        comments.extend(Comment.from_api(c) for c in page.get("data", []))
        after = page.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            break
        params = {**params, "after": after}
    return comments


def reply_to_comment(client: GraphClient, comment_id: str, message: str) -> str:
    """Post a reply to a comment; return the new reply's id."""
    resp = client.post(f"{comment_id}/replies", {"message": message})
    return resp.get("id", "")
