"""Private, bounded JSONL event bridge for ArchiCord OBS browser sources.

Implements the portable event-log subset of the supplied OBS/Log package.
No credentials, paths, server passwords or tokens enter event data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

MAX_WINDOW = 512 * 1024
MAX_LINE = 1024
EVENT_TYPES = frozenset(("progression", "hint", "goal", "deathlink"))


def event_path(instance_directory: Path) -> Path:
    return instance_directory / "obs_events.jsonl"


def clean(value: Any, maximum: int = 170) -> str:
    return " ".join(str(value if value is not None else "").split())[:maximum]


def append_event(directory: Path, *, category: str, seed: str, player: str,
                 recipient: str = "", item: str = "", location: str = "") -> dict:
    if category not in EVENT_TYPES:
        raise ValueError("Invalid overlay event category")
    event = {"id": time.time_ns() // 1000, "timestamp": time.strftime("%H:%M:%S"),
             "category": category, "seed": clean(seed, 120),
             "player": clean(player, 100), "recipient": clean(recipient, 100),
             "item": clean(item), "location": clean(location)}
    path = event_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_LINE:
        raise ValueError("Event too long")
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    return event


def recent_events(directory: Path, *, limit: int = 40, seed: str | None = None) -> list[dict]:
    path = event_path(directory)
    if not path.is_file() or path.is_symlink():
        return []
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        end = stream.tell()
        offset = max(0, end - MAX_WINDOW)
        stream.seek(offset)
        raw = stream.read(MAX_WINDOW)
    if offset:
        raw = raw.partition(b"\n")[2]
    items = []
    for line in raw.splitlines()[-400:]:
        try:
            event = json.loads(line.decode("utf-8"))
            if (isinstance(event, dict) and isinstance(event.get("id"), int)
                    and event.get("category") in EVENT_TYPES
                    and (seed is None or event.get("seed") == seed)):
                items.append({key: event.get(key, "") for key in
                              ("id", "timestamp", "category", "seed", "player",
                               "recipient", "item", "location")})
        except (ValueError, UnicodeError):
            continue
    return items[-max(1, min(int(limit), 200)):]
