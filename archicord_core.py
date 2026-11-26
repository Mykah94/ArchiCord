"""ArchiCord 3.0 additive data features.

The existing seed schema and Discord behaviors remain authoritative. All new
state is opt-in or supplementary; clients never receive tokens or passwords.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
import zipfile

MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 600
MAX_SNAPSHOTS = 250
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 5000
BACKUP_PARTS = (".env", "archicord_data", "deathlinks", "tracker/settings")
EVENT_TYPES = frozenset(("item", "trap", "hint", "goal", "deathlink", "status", "release"))
SUPPORTED_LANGUAGES = frozenset(("en", "de"))

MESSAGES = {
    "en": {"dashboard": "Dashboard", "players": "Players", "checks": "Checks",
           "history": "History", "routes": "Item routes", "health": "Health",
           "backups": "Backups", "notifications": "Notifications",
           "achievements": "Achievements", "compatibility": "APWorld compatibility",
           "settings": "Settings", "unavailable": "No data available",
           "stale": "Connection data may be outdated"},
    "de": {"dashboard": "Übersicht", "players": "Spieler", "checks": "Checks",
           "history": "Verlauf", "routes": "Item-Routen", "health": "Verbindungen",
           "backups": "Sicherungen", "notifications": "Benachrichtigungen",
           "achievements": "Erfolge", "compatibility": "APWorld-Kompatibilität",
           "settings": "Einstellungen", "unavailable": "Keine Daten verfügbar",
           "stale": "Verbindungsdaten möglicherweise veraltet"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default=None, limit: int = MAX_STATE_BYTES):
    try:
        if path.stat().st_size > limit:
            raise ValueError("State file exceeds size limit")
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with target.open("x", encoding="utf-8") as fp:
            json.dump(value, fp, ensure_ascii=False, indent=2)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(target, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        target.unlink(missing_ok=True)


def add_activity(state: dict, kind: str, *, player: str = "", recipient: str = "",
                 item: str = "", location: str = "", key: str = "") -> None:
    """Append an already accepted event; bound growth and preserve legacy keys."""
    if kind not in EVENT_TYPES:
        raise ValueError("Unsupported activity type")
    events = state.setdefault("activity_v3", [])
    if not isinstance(events, list):
        state["activity_v3"] = events = []
    entry = {"type": kind, "at": utc_now(), "player": str(player)[:120],
             "recipient": str(recipient)[:120], "item": str(item)[:180],
             "location": str(location)[:180]}
    if key:
        entry["key"] = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        if any(isinstance(e, dict) and e.get("key") == entry["key"] for e in events):
            return
    events.append(entry)
    del events[:-MAX_EVENTS]


def achievements(state: dict) -> list[dict]:
    """Deterministic badges, computed from durable seed data, never broadcast."""
    result = []
    def award(id_, title, reached):
        if reached:
            result.append({"id": id_, "title": title})
    stats = state.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    progression = int(stats.get("progression", 0) or 0)
    death = sum(int(v) for v in state.get("death_counts", {}).values() if isinstance(v, int) and v >= 0)
    goals = sum(bool(v) for v in state.get("goals", {}).values())
    own = state.get("own_checks", {})
    checks = len(own.get("checked", [])) if isinstance(own, dict) else 0
    award("first-item", "First delivery", progression >= 1)
    award("item-runner", "10 progression items", progression >= 10)
    award("goal-reached", "First goal completed", goals >= 1)
    award("check-hunter", "100 checked locations", checks >= 100)
    award("deathlink-25", "25 total DeathLinks", death >= 25)
    return result


def summarize_seed(state: dict, *, filename: str = "") -> dict:
    own = state.get("own_checks", {})
    if not isinstance(own, dict):
        own = {}
    checked = own.get("checked", [])
    missing = own.get("missing", [])
    if not isinstance(checked, list):
        checked = []
    if not isinstance(missing, list):
        missing = []
    activity = state.get("activity_v3", [])
    if not isinstance(activity, list):
        activity = []
    stats = state.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    return {
        "key": filename[:100], "seed": str(state.get("seed_name", ""))[:160],
        "team": state.get("team", 0), "goals": sum(bool(v) for v in state.get("goals", {}).values()),
        "deaths": sum(v for v in state.get("death_counts", {}).values() if isinstance(v, int) and v >= 0),
        "progression": int(stats.get("progression", 0) or 0),
        "traps": int(stats.get("traps", 0) or 0),
        "checks": {"checked": len(checked), "missing": len(missing),
                   "known": bool(own.get("known", False))},
        "last_activity": activity[-1]["at"] if activity and isinstance(activity[-1], dict) else None,
        "achievements": achievements(state),
    }


def history(data_root: Path, limit: int = 100) -> list[dict]:
    if not data_root.exists():
        return []
    result = []
    for path in sorted(data_root.glob("*/state.json"))[:2000]:
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            continue
        try:
            state = read_json(path)
            if isinstance(state, dict):
                record = summarize_seed(state, filename=path.parent.name)
                record["updated"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                result.append(record)
        except (ValueError, OSError, TypeError, OverflowError):
            continue
    result.sort(key=lambda x: x["updated"], reverse=True)
    return result[:max(1, min(limit, 200))]


def item_routes(state: dict, limit: int = 250) -> list[dict]:
    events = state.get("activity_v3", [])
    if not isinstance(events, list):
        return []
    return [dict(e) for e in reversed(events) if isinstance(e, dict) and e.get("type") in ("item", "trap")][:limit]


def checks_view(snapshot: dict, query: str = "", status: str = "all") -> list[dict]:
    """Display checked/missing IDs only for the bot slot; doable never inferred."""
    own = snapshot.get("own_checks", {})
    if not isinstance(own, dict) or not own.get("known"):
        return []
    done = {int(v) for v in own.get("checked", [])}
    missing = {int(v) for v in own.get("missing", [])}
    doable = snapshot.get("doable")
    valid_doable = {int(v) for v in doable} if isinstance(doable, list) else set()
    names = snapshot.get("locations", {})
    if not isinstance(names, dict):
        names = {}
    rows = []
    for ident in sorted(done | missing):
        state = "checked" if ident in done else "doable" if ident in valid_doable else "missing"
        name = str(names.get(str(ident), f"Location {ident}"))[:180]
        if (status == "all" or status == state) and query.casefold() in name.casefold():
            rows.append({"id": ident, "name": name, "status": state})
    return rows[:2000]


def compatibility(catalog: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for world in catalog:
        if world.get("valid"):
            groups[str(world.get("game", "")).casefold()].append(world)
    result = []
    for world in catalog:
        issues = []
        if not world.get("valid"):
            issues.append("invalid-manifest")
        if world.get("valid") and not world.get("world_version"):
            issues.append("unknown-version")
        if world.get("valid") and len(groups[str(world.get("game", "")).casefold()]) > 1:
            issues.append("duplicate-game")
        result.append({**world, "issues": issues,
                       "compatibility": "unknown" if world.get("valid") else "invalid"})
    return result


def notification_config(path: Path) -> dict:
    raw = read_json(path, {})
    if not isinstance(raw, dict):
        return {}
    enabled = raw.get("enabled", {})
    cooldown = raw.get("cooldown_seconds", {})
    channels = raw.get("channels", {})
    lang = raw.get("language", "de")
    return {
        "enabled": {kind: enabled.get(kind, True) is not False for kind in EVENT_TYPES}
                   if isinstance(enabled, dict) else {},
        "cooldown_seconds": {kind: min(3600, max(0, int(cooldown.get(kind, 0))))
                             for kind in EVENT_TYPES} if isinstance(cooldown, dict) else {},
        "channels": {kind: str(channels.get(kind, "")) for kind in EVENT_TYPES}
                    if isinstance(channels, dict) else {},
        "language": lang if lang in SUPPORTED_LANGUAGES else "de",
    }


def save_notification_config(path: Path, config: object) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Invalid configuration")
    enabled = config.get("enabled", {})
    cooldown = config.get("cooldown_seconds", {})
    channels = config.get("channels", {})
    lang = config.get("language", "de")
    if not isinstance(enabled, dict) or not isinstance(cooldown, dict) or not isinstance(channels, dict):
        raise ValueError("Invalid notification configuration")
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language")
    result = {"language": lang, "enabled": {}, "cooldown_seconds": {}, "channels": {}}
    for kind in EVENT_TYPES:
        value = enabled.get(kind, True)
        if not isinstance(value, bool):
            raise ValueError("Enabled flags must be booleans")
        seconds = cooldown.get(kind, 0)
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 <= seconds <= 3600:
            raise ValueError("Cooldown out of bounds")
        channel = str(channels.get(kind, ""))
        if channel and not re.fullmatch(r"\d{15,22}", channel):
            raise ValueError("Invalid Discord channel ID")
        result["enabled"][kind] = value
        result["cooldown_seconds"][kind] = seconds
        result["channels"][kind] = channel
    atomic_json(path, result)
    return result


def notification_decision(kind: str, config: dict, last_sent: dict, now: float) -> tuple[bool, int | None]:
    """Disabled messages are treated as handled; throttling never blocks core state."""
    if kind not in EVENT_TYPES:
        raise ValueError("Unsupported notification type")
    enabled = config.get("enabled", {}).get(kind, True)
    duration = config.get("cooldown_seconds", {}).get(kind, 0)
    if not enabled or now - last_sent.get(kind, float("-inf")) < duration:
        return False, None
    destination = config.get("channels", {}).get(kind, "")
    return True, (int(destination) if destination else None)


def health(snapshot: dict | None, *, now: float | None = None, stale_after: int = 180) -> dict:
    if not isinstance(snapshot, dict):
        return {"status": "unavailable", "reason": "No live snapshot", "components": {}}
    timestamp = snapshot.get("updated_at_epoch")
    now = time.time() if now is None else now
    stale = not isinstance(timestamp, (int, float)) or now - timestamp > stale_after
    components = {
        "discord": snapshot.get("discord", "unknown"),
        "archipelago": "online" if snapshot.get("ap_connected") else "offline",
        "universal_tracker": snapshot.get("tracker_status", "unknown"),
    }
    return {"status": "stale" if stale else "online", "reason": "stale" if stale else "",
            "components": components, "updated_at": snapshot.get("updated_at")}


def backup_directory(root: Path) -> Path:
    return root / "backups"


def list_backups(root: Path) -> list[dict]:
    folder = backup_directory(root)
    if folder.is_symlink() or not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.glob("archicord-*.zip"), reverse=True):
        if not path.is_file() or path.is_symlink():
            continue
        rows.append({"name": path.name, "bytes": path.stat().st_size})
    return rows[:40]


def _safe_sources(root: Path):
    base = root.resolve()
    files = []
    for item in BACKUP_PARTS:
        path = root / item
        if not path.exists():
            continue
        if path.is_symlink():
            raise ValueError("Backup source contains symlink")
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError("Backup source contains symlink")
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if not resolved.is_relative_to(base):
                raise ValueError("Backup source escapes root")
            rel = candidate.relative_to(root).as_posix()
            if candidate.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError("Backup source file too large")
            files.append((rel, candidate))
            if len(files) > MAX_ARCHIVE_MEMBERS:
                raise ValueError("Too many files to back up")
    return files


def create_backup(root: Path, *, keep: int = 10) -> dict:
    """Local-only backup; zip can contain tokens and must never be served by HTTP."""
    folder = backup_directory(root)
    if folder.is_symlink() or not folder.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe backup directory")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    name = f"archicord-{stamp}-{os.urandom(3).hex()}.zip"
    destination = folder / name
    candidates = _safe_sources(root)
    total = sum(path.stat().st_size for _, path in candidates)
    if total > MAX_ARCHIVE_BYTES or not candidates:
        raise ValueError("Backup is empty or exceeds 64 MiB")
    tmp = folder / ("." + name + ".tmp")
    try:
        with tmp.open("xb") as stream:
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                metadata = {}
                for relative, path in candidates:
                    raw = path.read_bytes()
                    archive.writestr(relative, raw)
                    metadata[relative] = hashlib.sha256(raw).hexdigest()
                archive.writestr("_archicord_manifest.json", json.dumps({"schema": 1, "files": metadata}))
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)
    for old in list_backups(root)[max(1, keep):]:
        (folder / old["name"]).unlink(missing_ok=True)
    return {"name": name, "files": len(candidates), "bytes": destination.stat().st_size}


def verify_backup(root: Path, name: str) -> dict:
    if not re.fullmatch(r"archicord-[A-Za-z0-9T-]+\.zip", name):
        raise ValueError("Invalid backup filename")
    folder = backup_directory(root)
    if folder.is_symlink() or not folder.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe backup directory")
    path = folder / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Backup unavailable or too large")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS + 1 or len({i.filename for i in infos}) != len(infos):
            raise ValueError("Invalid backup entries")
        manifest_info = archive.getinfo("_archicord_manifest.json")
        if manifest_info.file_size > 1024 * 1024:
            raise ValueError("Backup manifest too large")
        manifest = json.loads(archive.read("_archicord_manifest.json"))
        expected = manifest.get("files", {})
        if manifest.get("schema") != 1 or not isinstance(expected, dict):
            raise ValueError("Invalid backup manifest")
        total = 0
        for info in infos:
            name_ = info.filename
            if name_ == "_archicord_manifest.json":
                continue
            path_parts = Path(name_).parts
            if (name_.startswith("/") or ".." in path_parts or "\\" in name_ or
                not any(name_ == part or name_.startswith(part + "/") for part in BACKUP_PARTS) or
                info.is_dir() or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError("Unsafe backup entry")
            total += info.file_size
            if total > MAX_ARCHIVE_BYTES or info.file_size > MAX_ARCHIVE_BYTES:
                raise ValueError("Backup expanded size exceeds limit")
            digest = hashlib.sha256(archive.read(info)).hexdigest()
            if expected.get(name_) != digest:
                raise ValueError("Backup checksum mismatch")
        if len(expected) != len(infos) - 1:
            raise ValueError("Backup manifest incomplete")
        return {"name": name, "files": len(expected), "bytes": total}


def restore_backup(root: Path, name: str, *, stopped: bool) -> dict:
    """Stopped-bot-only restore with pre-restore backup and rollback on error."""
    if not stopped:
        raise ValueError("Stop the bot before restoring a backup")
    preview = verify_backup(root, name)
    safety = create_backup(root, keep=20)
    archive_path = backup_directory(root) / name
    written = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.filename == "_archicord_manifest.json":
                    continue
                dest = root / info.filename
                if not dest.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Backup entry escapes root")
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_name(f".{dest.name}.{os.getpid()}.restore")
                try:
                    with tmp.open("xb") as stream:
                        stream.write(archive.read(info))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp, dest)
                finally:
                    tmp.unlink(missing_ok=True)
                written.append(info.filename)
    except Exception:
        # Reapply the known-good, locally created safety backup without recursion.
        with zipfile.ZipFile(backup_directory(root) / safety["name"]) as archive:
            old_names = set(archive.namelist())
            for filename in written:
                target = root / filename
                if filename in old_names:
                    replacement = target.with_name(f".{target.name}.{os.getpid()}.rollback")
                    try:
                        with replacement.open("xb") as handle:
                            handle.write(archive.read(filename))
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(replacement, target)
                    finally:
                        replacement.unlink(missing_ok=True)
                else:
                    target.unlink(missing_ok=True)
        raise
    return {"restored": preview["files"], "safety_backup": safety["name"]}
