"""Optional official Archipelago webhost room URL -> current port resolution.

Room URLs are tightly restricted to the official website. Never fetch
arbitrary URLs or redirects from the WebUI configuration.
"""
from __future__ import annotations

from html import unescape
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOM = re.compile(r"^/room/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/?$")
PORT = re.compile(r"(?:/connect\s+archipelago\.gg:|address/ip\s+is\s+archipelago\.gg\s+and\s+port\s+is\s+)(\d{1,5})\b", re.I)


def validate_room_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "archipelago.gg"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not ROOM.fullmatch(parsed.path)):
        raise ValueError("Expected official https://archipelago.gg/room/<room-id>")
    return "https://archipelago.gg" + parsed.path.rstrip("/")


def current_room_port(html: str) -> int | None:
    match = PORT.search(unescape(html))
    if not match:
        return None
    port = int(match.group(1))
    return port if 1 <= port <= 65535 else None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def resolve_room_url(raw: str) -> str:
    url = validate_room_url(raw)
    if not url:
        raise ValueError("Room URL is missing")
    opener = build_opener(NoRedirect())
    request = Request(url, headers={
        "User-Agent": "ArchiCord-MultiRoom/1.0", "Accept": "text/html"})
    with opener.open(request, timeout=7) as response:
        raw = response.read(250001)
    if len(raw) > 250000:
        raise ValueError("Room page too large")
    port = current_room_port(raw.decode("utf-8", errors="replace"))
    if not port:
        raise ValueError("Official Archipelago room page did not expose a port")
    return f"wss://archipelago.gg:{port}"
