"""Regression tests for reconstructed modules and local HTTP protections."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from tracker.apworld_manager import (
    load_selection, save_selection, scan_worlds, selected_games,
    selection_fingerprint,
)
from tracker.ut_bridge import _connect_uri, parse_locations, write_snapshot
from webui import Handler


def _world(folder: Path, filename: str, manifest: object) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / filename, "w") as archive:
        archive.writestr("archipelago.json", json.dumps(manifest))
        archive.writestr("worlds/example/__init__.py", "raise RuntimeError('must never execute')")


def test_manifest_scan_without_executing_world_code(tmp_path: Path) -> None:
    _world(tmp_path / "tracker" / "apworlds", "example.apworld",
           {"game": "Example Game", "world_version": "1.2.3"})
    catalog = scan_worlds(tmp_path)
    assert len(catalog) == 1
    assert catalog[0]["game"] == "Example Game"
    assert catalog[0]["valid"] is True


def test_selection_persists_and_invalidates_tracker_snapshots(tmp_path: Path) -> None:
    _world(tmp_path / "tracker" / "apworlds", "example.apworld", {"game": "Example"})
    catalog = scan_worlds(tmp_path)
    assert selected_games(tmp_path) is None
    assert selection_fingerprint(tmp_path) == "legacy-all"
    save_selection(tmp_path, [{"id": catalog[0]["id"], "game_override": "Renamed"}], catalog)
    assert load_selection(tmp_path)["worlds"][0]["game"] == "Renamed"
    assert selected_games(tmp_path) == {"renamed"}
    before = selection_fingerprint(tmp_path)
    save_selection(tmp_path, [], catalog)
    assert selected_games(tmp_path) == set()
    assert before != selection_fingerprint(tmp_path)


def test_reject_unknown_and_duplicate_worlds(tmp_path: Path) -> None:
    _world(tmp_path / "tracker" / "apworlds", "example.apworld", {"game": "Example"})
    catalog = scan_worlds(tmp_path)
    row = {"id": catalog[0]["id"]}
    with pytest.raises(ValueError):
        save_selection(tmp_path, [{"id": "not-in-catalog"}], catalog)
    with pytest.raises(ValueError):
        save_selection(tmp_path, [row, row], catalog)


def test_unknown_and_broken_worlds_cannot_be_selected(tmp_path: Path) -> None:
    folder = tmp_path / "tracker" / "apworlds"
    folder.mkdir(parents=True)
    (folder / "broken.apworld").write_bytes(b"not an archive")
    catalog = scan_worlds(tmp_path)
    assert len(catalog) == 1 and catalog[0]["valid"] is False
    with pytest.raises(ValueError):
        save_selection(tmp_path, [{"id": catalog[0]["id"]}], catalog)


def test_cli_only_accepts_exact_unique_location_names() -> None:
    known = {10: "Village - Chest", 20: "Castle - Key"}
    assert parse_locations("[Tracker] Starting\nVillage - Chest\nConnecting\nCastle - Key", known) == [10, 20]
    with pytest.raises(ValueError):
        parse_locations("Connecting\nUnknown location", known)
    with pytest.raises(ValueError):
        parse_locations("Village - Chest", {10: "Village - Chest", 11: "Village - Chest"})


def test_cli_uri_encodes_credentials_and_ipv6() -> None:
    assert _connect_uri("wss://[::1]:1234", "My Slot", "a@b") == (
        "archipelago://My%20Slot:a%40b@[::1]:1234"
    )


def test_tracker_export_is_seed_scoped(tmp_path: Path) -> None:
    target = tmp_path / "tracker" / "exports" / "live_checks.json"
    write_snapshot(target, "seedA", 2, {"1": {"doable": [10]}}, {}, "rev1")
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["seed_name"] == "seedA"
    assert data["team"] == 2
    assert data["selection_revision"] == "rev1"
    assert data["players"]["1"]["doable"] == [10]


@pytest.mark.parametrize("host", [
    "evil.example:8765", "127.0.0.1.evil.example:8765",
    "evil.example@127.0.0.1:8765", "127.0.0.1:9999", "",
])
def test_webui_rejects_non_local_host(host: str) -> None:
    handler = object.__new__(Handler)
    handler.headers = {"Host": host}
    handler.server = SimpleNamespace(server_port=8765)
    assert not handler.valid_local_host()


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765"])
def test_webui_allows_local_host(host: str) -> None:
    handler = object.__new__(Handler)
    handler.headers = {"Host": host}
    handler.server = SimpleNamespace(server_port=8765)
    assert handler.valid_local_host()
