"""Safe, read-only APWorld discovery and seed-game selection.

Manifests are read from ZIP members; APWorld Python code is never imported.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import zipfile

SELECTION_FILE = Path("tracker/settings/apworld_selection.json")
MAX_MANIFEST = 256 * 1024
MAX_WORLDS = 2000


def selection_path(root: Path) -> Path:
    return Path(root) / SELECTION_FILE


def load_selection(root: Path) -> dict | None:
    path = selection_path(root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("APWorld-Auswahl ist unlesbar") from exc
    if not isinstance(data, dict) or not isinstance(data.get("worlds"), list):
        raise ValueError("Ungültiges APWorld-Auswahlformat")
    rows = data["worlds"]
    if len(rows) > MAX_WORLDS or any(
        not isinstance(row, dict) or not isinstance(row.get("id"), str)
        or not isinstance(row.get("game"), str) or len(row["game"]) > 160
        for row in rows
    ):
        raise ValueError("Ungültige APWorld-Auswahldaten")
    return {"worlds": rows}


def selection_fingerprint(root: Path) -> str:
    config = load_selection(root)
    if config is None:
        return "legacy-all"
    rows = sorted((row["id"], row["game"]) for row in config["worlds"])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def selected_games(root: Path) -> set[str] | None:
    config = load_selection(root)
    if config is None:
        return None
    return {row["game"].strip().casefold() for row in config["worlds"] if row["game"].strip()}


def _directories(root: Path, install_dir: str | None, extra_dirs: str | None) -> list[tuple[str, Path]]:
    entries = [("ArchiCord/tracker/apworlds", Path(root) / "tracker" / "apworlds")]
    if install_dir:
        base = Path(install_dir).expanduser()
        entries.extend((f"Archipelago/{name}", base / name) for name in ("custom_worlds", "worlds"))
    if extra_dirs:
        for extra in extra_dirs.split(os.pathsep):
            if extra.strip():
                entries.append(("Zusätzlich", Path(extra.strip()).expanduser()))
    return entries


def _manifest(path: Path) -> tuple[str, str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            manifests = [n for n in archive.namelist()
                         if n.rsplit("/", 1)[-1] == "archipelago.json"
                         and not n.startswith("/") and ".." not in Path(n).parts]
            if len(manifests) != 1:
                raise ValueError("Kein eindeutiges archipelago.json-Manifest")
            info = archive.getinfo(manifests[0])
            if info.file_size > MAX_MANIFEST:
                raise ValueError("Manifest zu groß")
            with archive.open(info) as handle:
                data = json.loads(handle.read(MAX_MANIFEST + 1).decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Manifest ist kein Objekt")
        game = data.get("game") or data.get("game_name") or data.get("name")
        if not isinstance(game, str) or not game.strip():
            raise ValueError("Kein Spielname im Manifest")
        version = data.get("world_version") or data.get("version") or ""
        return game.strip()[:160], str(version)[:80], ""
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, UnicodeError, KeyError) as exc:
        return "", "", str(exc)[:160]


def scan_worlds(root: Path, install_dir: str | None = None, extra_dirs: str | None = None) -> list[dict]:
    results = []
    seen = set()
    for source, folder in _directories(root, install_dir, extra_dirs):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.apworld")):
            if len(results) >= MAX_WORLDS:
                return results
            try:
                resolved = path.resolve(strict=True)
                if not resolved.is_file() or resolved in seen:
                    continue
                seen.add(resolved)
                game, version, detail = _manifest(resolved)
                unique_id = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:24]
                results.append({"id": unique_id, "file": path.name, "source": source,
                                "game": game, "world_version": version,
                                "valid": bool(game), "detail": detail})
            except OSError:
                continue
    return results


def save_selection(root: Path, worlds: object, catalog: list[dict]) -> None:
    if not isinstance(worlds, list) or len(worlds) > MAX_WORLDS:
        raise ValueError("Ungültige APWorld-Auswahl")
    available = {row["id"]: row for row in catalog if row.get("valid")}
    saved = []
    ids = set()
    for row in worlds:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Ungültige APWorld-Auswahl")
        ident = row["id"]
        if ident not in available or ident in ids:
            raise ValueError("Unbekannte oder doppelte APWorld-ID")
        game = row.get("game_override") or available[ident]["game"]
        if not isinstance(game, str) or not game.strip() or len(game) > 160 or any(
            ord(c) < 32 for c in game
        ):
            raise ValueError("Ungültiger Spielname")
        saved.append({"id": ident, "game": game.strip()})
        ids.add(ident)
    path = selection_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump({"worlds": saved}, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
