"""Additive local backups and read-only health diagnostics for ArchiCord.

No Discord/AP connections are initiated. Importing this module has no side
effects. The WebUI can start a scheduler and expose the snapshots locally.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

BACKUP_PATTERN = re.compile(r"^archicord-\d{8}-\d{6}(?:-\d+)?\.zip$")
SECRET_FIELD = re.compile(r"(?:password|token|secret|api[_-]?key|authorization|credential)", re.I)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_FILES = 5000
MAX_INSTANCES = 100
DEFAULT_INTERVAL_HOURS = 24
DEFAULT_KEEP = 14


def _clean(value: Any) -> Any:
    """Drop credential values from backup JSON recursively, without touching originals."""
    if isinstance(value, dict):
        return {key: ("" if SECRET_FIELD.search(str(key)) else _clean(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _safe_json(path: Path) -> bytes | None:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return (json.dumps(_clean(data), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def _source_paths(root: Path, data_dir: Path | None = None):
    """Only allowlisted JSON; never .env, raw seeds, worlds or sound binaries."""
    root = root.resolve()
    base = data_dir or root / "archicord_data"
    trees = ((base, "archicord_data"), (root / "deathlinks", "deathlinks"),
             (root / "tracker" / "settings", "tracker/settings"))
    for folder, prefix in trees:
        if not folder.is_dir() or folder.is_symlink():
            continue
        for path in sorted(folder.rglob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            # Prevent traversing symlinked subdirectories.
            if any(parent.is_symlink() for parent in path.parents
                   if parent != folder and folder in parent.parents):
                continue
            try:
                relative = path.relative_to(folder)
            except ValueError:
                continue
            if len(relative.parts) > 12:
                continue
            yield path, prefix + "/" + relative.as_posix()


def _settings(root: Path) -> tuple[int, int, bool]:
    """Optional config/maintenance.json: interval_hours, keep, enabled."""
    path = root / "config" / "maintenance.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not path.is_symlink() else {}
    except (ValueError, OSError, UnicodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    try:
        interval = max(1, min(168, int(data.get("interval_hours", DEFAULT_INTERVAL_HOURS))))
        keep = max(1, min(100, int(data.get("keep", DEFAULT_KEEP))))
    except (TypeError, ValueError):
        interval, keep = DEFAULT_INTERVAL_HOURS, DEFAULT_KEEP
    return interval, keep, data.get("enabled", True) is not False


class BackupManager:
    """Thread-safe rolling snapshots of selected runtime JSON files."""

    def __init__(self, root: Path, data_dir: Path | None = None):
        self.root = Path(root).resolve()
        self.data_dir = Path(data_dir).resolve() if data_dir is not None else None
        self.folder = self.root / "backups"
        self._lock = threading.Lock()
        self.last_error = ""

    def archives(self) -> list[Path]:
        if not self.folder.is_dir():
            return []
        return sorted((p for p in self.folder.iterdir()
                       if p.is_file() and not p.is_symlink() and BACKUP_PATTERN.fullmatch(p.name)),
                      key=lambda p: (p.stat().st_mtime, p.name), reverse=True)

    def status(self) -> dict:
        interval, keep, enabled = _settings(self.root)
        files = self.archives()
        return {"enabled": enabled, "interval_hours": interval, "keep": keep,
                "count": len(files),
                "last_backup": datetime.fromtimestamp(files[0].stat().st_mtime, timezone.utc).isoformat() if files else None,
                "last_size_bytes": files[0].stat().st_size if files else 0,
                "last_error": self.last_error}

    def create(self) -> dict:
        """Safely create a ZIP and rotate only ArchiCord's own archives."""
        with self._lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            name = f"archicord-{stamp}.zip"
            i = 1
            while (self.folder / name).exists():
                name = f"archicord-{stamp}-{i}.zip"
                i += 1
            dest = self.folder / name
            temp = self.folder / ("." + name + ".tmp")
            included = 0
            total = 0
            try:
                with ZipFile(temp, mode="x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                    for path, arcname in _source_paths(self.root, self.data_dir):
                        if included >= MAX_FILES:
                            break
                        content = _safe_json(path)
                        if content is None or len(content) > MAX_FILE_BYTES or total + len(content) > MAX_TOTAL_BYTES:
                            continue
                        archive.writestr(arcname, content)
                        total += len(content)
                        included += 1
                    if included:
                        manifest = {"format": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                                    "files": included, "credential_fields_redacted": True,
                                    "warning": "Credentials, .env, APWorlds, YAMLs and seed archives are excluded."}
                        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
                if not included:
                    temp.unlink(missing_ok=True)
                    return {"created": False, "reason": "no_data", "files": 0}
                with ZipFile(temp, "r") as check:
                    if check.testzip() is not None:
                        raise OSError("Archive integrity check failed")
                os.replace(temp, dest)
                if os.name != "nt":
                    os.chmod(dest, 0o600)
                _, keep, _ = _settings(self.root)
                for old in self.archives()[keep:]:
                    old.unlink(missing_ok=True)
                self.last_error = ""
                return {"created": True, "name": dest.name, "files": included,
                        "size_bytes": dest.stat().st_size}
            except (OSError, ValueError, RuntimeError):
                self.last_error = "Backup konnte nicht erstellt werden. Speicherplatz und Zugriffsrechte prüfen."
                raise
            finally:
                temp.unlink(missing_ok=True)

    def run_if_due(self, now: float | None = None) -> dict:
        interval, _, enabled = _settings(self.root)
        if not enabled:
            return {"created": False, "reason": "disabled"}
        files = self.archives()
        now = time.time() if now is None else now
        if files and now - files[0].stat().st_mtime < interval * 3600:
            return {"created": False, "reason": "not_due"}
        return self.create()


def health_snapshot(root: Path, *, bot_running: bool, discord_status: str,
                    ap_status: str = "unknown", data_dir: Path | None = None,
                    now: float | None = None) -> dict:
    """Read-only status; never claim a connection without a fresh heartbeat."""
    root = Path(root).resolve()
    data_dir = (Path(data_dir) if data_dir is not None else root / "archicord_data").resolve()
    now = time.time() if now is None else now
    instances = []
    folder = data_dir / "instances"
    if folder.is_dir() and not folder.is_symlink():
        for path in sorted(folder.glob("*/status.json"))[:MAX_INSTANCES]:
            if path.is_symlink() or path.parent.is_symlink():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    continue
                updated = float(value.get("updated_at") or 0)
                fresh = 0 <= now - updated <= 120
                connected = bool(value.get("connected")) and bot_running and fresh
                status = ("online" if connected else
                          "stale" if bot_running and updated and not fresh else
                          "offline" if bot_running else "stopped")
                instances.append({"id": path.parent.name[:80],
                                  "name": str(value.get("name", path.parent.name))[:80],
                                  "status": status,
                                  "age_seconds": int(max(0, now - updated)) if updated else None})
            except (OSError, ValueError, TypeError, OverflowError):
                continue
    try:
        free = shutil.disk_usage(root).free
    except OSError:
        free = None
    # Universal Tracker: a recent export is evidence of recent data, not a
    # guarantee that APWorld logic was successfully evaluated for every slot.
    export = root / "tracker" / "exports" / "live_checks.json"
    if export.is_file() and not export.is_symlink():
        try:
            export_age = max(0, int(now - export.stat().st_mtime))
            tracker = {"status": "recent_data" if export_age <= 300 else "stale_data",
                       "last_export_age_seconds": export_age}
        except OSError:
            tracker = {"status": "unknown", "last_export_age_seconds": None}
    else:
        tracker = {"status": "no_export", "last_export_age_seconds": None}
    return {"bot": "running" if bot_running else "stopped",
            "discord": discord_status if bot_running and discord_status in ("online", "starting", "error") else "offline",
            "archipelago_reported": ap_status if bot_running else "offline",
            "universal_tracker": tracker,
            "instances": instances,
            "online_instances": sum(1 for inst in instances if inst["status"] == "online"),
            "free_disk_bytes": free,
            "disk_status": "unknown" if free is None else "low" if free < 500 * 1024 * 1024 else "ok",
            "updated_utc": datetime.fromtimestamp(now, timezone.utc).isoformat()}


def backup_scheduler(manager: BackupManager, stop: threading.Event, period_seconds: float = 60) -> None:
    """Runs while WebUI runs, without modifying the bot or AP state."""
    while not stop.is_set():
        try:
            manager.run_if_due()
        except (OSError, ValueError, RuntimeError):
            pass
        stop.wait(period_seconds)
