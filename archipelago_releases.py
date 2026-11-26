"""Official Archipelago stable release watcher.

Checks GitHub's official latest-release endpoint. No Discord integration or
private tokens are required to obtain release metadata.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

OFFICIAL_SITE = "https://archipelago.gg/"
OFFICIAL_RELEASES = "https://github.com/ArchipelagoMW/Archipelago/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/ArchipelagoMW/Archipelago/releases/latest"
MAX_RESPONSE = 128 * 1024
VERSION = re.compile(r"^v?\d+\.\d+\.\d+(?:[._-][A-Za-z0-9.]+)?$")
RELEASE_URL = re.compile(r"^https://github\.com/ArchipelagoMW/Archipelago/releases/tag/[A-Za-z0-9._-]+$")


def parse_latest_release(payload: object) -> dict[str, str]:
    """Accept only a public stable version from the expected GitHub repository."""
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise ValueError("Not a stable Archipelago release")
    version = payload.get("tag_name")
    url = payload.get("html_url")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Invalid Archipelago release version")
    if not isinstance(url, str) or not RELEASE_URL.fullmatch(url):
        raise ValueError("Unexpected Archipelago release URL")
    if url.rsplit("/", 1)[-1] != version:
        raise ValueError("Release URL does not match the version")
    return {"version": version, "url": url}


def fetch_latest_release() -> dict[str, str]:
    """Fetch official GitHub metadata with a strict response bound and timeout."""
    request = Request(LATEST_RELEASE_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ArchiCord-ReleaseWatcher/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=12) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_RESPONSE:
            raise ValueError("Release response too large")
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Release response too large")
    return parse_latest_release(json.loads(raw.decode("utf-8")))


def load_announced_version(path: Path, channel_id: int) -> str | None:
    """Release tracking is global, not tied to the currently active AP seed."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError):
        # Fail closed: malformed state must not trigger historical notifications.
        raise ValueError("Release tracking state is not readable")
    if not isinstance(data, dict) or not isinstance(data.get("channels"), dict):
        raise ValueError("Release tracking state is invalid")
    version = data["channels"].get(str(channel_id))
    if version is None:
        return None
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Release tracking version is invalid")
    return version


def save_announced_version(path: Path, channel_id: int, version: str) -> None:
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid release version")
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("Release tracking state is not readable") from exc
    if not isinstance(data, dict) or not isinstance(data.get("channels", {}), dict):
        raise ValueError("Release tracking state is invalid")
    data.setdefault("channels", {})[str(channel_id)] = version
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def is_new_release(latest: str, previous: str) -> bool:
    """Only announce increases; never reannounce old or equal release tags."""
    def version_parts(tag: str) -> tuple[int, int, int]:
        return tuple(int(n) for n in re.match(r"^v?(\d+)\.(\d+)\.(\d+)", tag).groups())
    return version_parts(latest) > version_parts(previous)


async def check_release_once(
    channel_id: int,
    state_path: Path,
    send_announcement,
    *,
    fetch=fetch_latest_release,
) -> str:
    """Return baseline/unchanged/announced/send-failed without spamming on restart."""
    if not channel_id:
        return "disabled"
    # Read state before network access, so a damaged file never causes a repost.
    previous = load_announced_version(state_path, channel_id)
    release = await asyncio.to_thread(fetch)
    version = release["version"]
    if previous is None:
        save_announced_version(state_path, channel_id, version)
        return "baseline"
    if not is_new_release(version, previous):
        return "unchanged"
    delivered = await send_announcement(release)
    if not delivered:
        return "send-failed"
    save_announced_version(state_path, channel_id, version)
    return "announced"
