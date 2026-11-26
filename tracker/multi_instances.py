"""Validated, local-only configuration for parallel Archipelago rooms.

Inspired by the user's ArchiCord multi-seed package. The existing legacy seed
state is never migrated, overwritten, or deleted by this feature.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlsplit
from tracker.room_connection import validate_room_url

INSTANCE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
SNOWFLAKE = re.compile(r"^\d{15,22}$")
MAX_INSTANCES = 12
CHANNELS = ("item_channel_id", "hint_channel_id", "death_channel_id", "status_channel_id")
MAX_CONFIG_SIZE = 256 * 1024


def config_path(root: Path) -> Path:
    return Path(root) / "multi_instances.json"


def instance_directory(root: Path, instance_id: str) -> Path:
    if not INSTANCE_ID.fullmatch(instance_id):
        raise ValueError("Invalid Multiworld instance ID")
    return Path(root) / "instances" / instance_id


def seed_path(root: Path, instance_id: str, url: str, slot: str, seed: str, team: int) -> Path:
    identity = json.dumps([url, slot, seed, team], separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return instance_directory(root, instance_id) / "seeds" / digest / "state.json"


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def safe_read(path: Path, fallback: Any, *, limit: int = MAX_CONFIG_SIZE) -> Any:
    try:
        if path.stat().st_size > limit:
            raise ValueError("Configuration file too large")
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def read_instances(root: Path) -> list[dict]:
    data = safe_read(config_path(root), {"instances": []})
    if not isinstance(data, dict) or not isinstance(data.get("instances"), list):
        raise ValueError("Invalid Multiworld instance configuration")
    if len(data["instances"]) > MAX_INSTANCES:
        raise ValueError("Too many Multiworld instances")
    return data["instances"]


def validate_url(raw: str) -> str:
    value = str(raw).strip()
    if not 1 <= len(value) <= 300:
        raise ValueError("Invalid Archipelago URL")
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        port = None
    if (parts.scheme not in ("ws", "wss") or not parts.hostname
            or not port or not 1 <= port <= 65535
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("", "/")):
        raise ValueError("Archipelago URL must be ws(s)://host:port")
    return f"{parts.scheme}://{parts.netloc}"


def validate_instances(raw: Any, previous: list[dict] | None = None) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > MAX_INSTANCES:
        raise ValueError("Expected up to 12 Multiworld instances")
    older = {row["id"]: row for row in (previous or []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    output = []
    ids = set()
    connections = set()
    room_pages = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Instance must be a JSON object")
        ident = str(entry.get("id", "")).strip()
        if not INSTANCE_ID.fullmatch(ident) or ident in ids or ident == "primary":
            raise ValueError("Instance IDs must be unique and use a-z, 0-9, - or _")
        ids.add(ident)
        name = str(entry.get("name") or ident).strip()
        slot = str(entry.get("slot") or "").strip()
        game = str(entry.get("game") or "").strip()
        if any(not v or len(v) > max_len or any(ord(c) < 32 for c in v)
               for v, max_len in ((name, 55), (slot, 90), (game, 90))):
            raise ValueError("Instance name, slot and game are required")
        url = validate_url(str(entry.get("ap_url") or ""))
        if url in connections:
            raise ValueError("Duplicate Archipelago room URL")
        connections.add(url)
        room_page = validate_room_url(str(entry.get('room_url') or ''))
        if room_page and room_page in room_pages:
            raise ValueError('Duplicate official Archipelago room URL')
        if room_page:
            room_pages.add(room_page)
        guild = str(entry.get("guild_id") or "").strip()
        if not SNOWFLAKE.fullmatch(guild):
            raise ValueError("Each instance requires a Discord guild ID")
        old = older.get(ident, {})
        password = entry.get("password", "")
        if not isinstance(password, str) or len(password) > 250 or any(ord(c) < 32 for c in password):
            raise ValueError("Invalid Archipelago password")
        if not password:
            password = str(old.get("password", ""))
        channels = {}
        for key in CHANNELS:
            value = str(entry.get(key) or "").strip()
            if value and not SNOWFLAKE.fullmatch(value):
                raise ValueError(f"{key} must be a valid Discord channel ID")
            channels[key] = value
        if not any(channels.values()):
            raise ValueError("Each instance needs at least one Discord channel")
        output.append({
            "id": ident, "name": name, "slot": slot, "game": game,
            "ap_url": url, "room_url": room_page, "guild_id": guild, "password": password,
            "enabled": entry.get("enabled", True) is not False, **channels,
        })
    return output


def save_instances(root: Path, raw: Any) -> list[dict]:
    validated = validate_instances(raw, read_instances(root))
    atomic_json(config_path(root), {"version": 1, "instances": validated})
    return sanitized_instances(validated)


def sanitized_instances(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "password"} |
            {"password_configured": bool(row.get("password"))} for row in rows]


def statuses(root: Path) -> list[dict]:
    result = []
    for row in read_instances(root):
        path = instance_directory(root, row["id"]) / "status.json"
        value = safe_read(path, {})
        if not isinstance(value, dict):
            value = {}
        # A stopped bot must not appear connected from an old status file.
        if time.time() - float(value.get("updated_at", 0) or 0) > 90:
            value = {**value, "connected": False, "error": "Status is stale"}
        result.append({"id": row["id"], "name": row["name"],
                       "enabled": row["enabled"], "status": value})
    return result
