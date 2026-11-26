"""ArchiCord 3.0 regression, security and local-only integration tests."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import zipfile

import pytest

from archicord_core import (
    MESSAGES, achievements, add_activity, atomic_json, checks_view, compatibility,
    create_backup, health, history, item_routes, list_backups,
    notification_config, notification_decision, read_json,
    restore_backup, save_notification_config, summarize_seed, verify_backup,
)
from archicord_dashboard import PAGES, render_dashboard
import webui


def example_state(seed="demo"):
    return {
        "schema": 2, "seed_name": seed, "team": 0, "items_seen": [],
        "hints": {}, "goals": {"2": True}, "goal_announced": ["2"],
        "death_counts": {"Player": 25}, "death_event_keys": [],
        "stats": {"progression": 10, "traps": 2, "players": {}},
        "own_checks": {"known": True, "checked": list(range(100)), "missing": [101, 102]},
        "boards": {}, "features_announced": True
    }


def test_v3_activity_retains_all_legacy_fields():
    state = example_state()
    old_fields = set(state)
    add_activity(state, "item", player="Alice", recipient="Bob", item="Key", key="1:2:3")
    add_activity(state, "item", player="Alice", recipient="Bob", item="Key", key="1:2:3")
    assert len(state["activity_v3"]) == 1
    assert set(state) == old_fields | {"activity_v3"}
    assert state["death_counts"]["Player"] == 25
    assert item_routes(state)[0]["recipient"] == "Bob"


def test_activity_is_bounded():
    state = example_state()
    for i in range(680):
        add_activity(state, "item", player=f"Player {i}")
    assert len(state["activity_v3"]) == 600


def test_achievement_counts_and_history(tmp_path):
    state = example_state()
    assert {item["id"] for item in achievements(state)} >= {
        "first-item", "item-runner", "goal-reached", "check-hunter", "deathlink-25"
    }
    target = tmp_path / "seed-A" / "state.json"
    atomic_json(target, state)
    rows = history(tmp_path)
    assert len(rows) == 1
    assert rows[0]["seed"] == "demo"
    assert rows[0]["deaths"] == 25
    assert rows[0]["checks"]["checked"] == 100
    assert rows[0]["achievements"]


def test_history_keeps_seed_team_isolation(tmp_path):
    for directory, name, team in [("one", "seed1", 0), ("two", "seed1", 2), ("three", "seed2", 0)]:
        state = example_state(name)
        state["team"] = team
        atomic_json(tmp_path / directory / "state.json", state)
    result = history(tmp_path)
    assert len(result) == 3
    assert {item["team"] for item in result if item["seed"] == "seed1"} == {0, 2}


def test_checks_are_fail_closed_with_no_tracker_doable():
    snap = {"own_checks": {"known": True, "checked": [1], "missing": [2, 3]},
            "locations": {"1": "Old chest", "2": "Forest cave"}}
    rows = checks_view(snap)
    assert [r["status"] for r in rows] == ["checked", "missing", "missing"]
    snap["doable"] = [2]
    assert checks_view(snap, "Forest", "doable") == [
        {"id": 2, "name": "Forest cave", "status": "doable"}
    ]
    assert checks_view({"own_checks": {"known": False, "checked": [], "missing": []}}) == []


def test_apworld_compatibility_does_not_claim_unsupported_versions():
    worlds = [
        {"valid": True, "game": "Example", "world_version": "1.0"},
        {"valid": True, "game": "Example", "world_version": "2.0"},
        {"valid": False, "game": "", "detail": "broken"},
    ]
    result = compatibility(worlds)
    assert result[0]["compatibility"] == "unknown"
    assert "duplicate-game" in result[0]["issues"]
    assert "invalid-manifest" in result[2]["issues"]


def test_notification_defaults_and_overrides(tmp_path):
    path = tmp_path / "notification.json"
    config = notification_config(path)
    assert config["language"] == "de"
    assert notification_decision("item", config, {}, 100) == (True, None)
    settings = {"language": "en", "enabled": {"trap": False},
                "channels": {"item": "123456789012345678"}, "cooldown_seconds": {"item": 30}}
    saved = save_notification_config(path, settings)
    assert saved["language"] == "en"
    assert notification_decision("item", saved, {}, 100) == (True, 123456789012345678)
    assert notification_decision("item", saved, {"item": 99}, 100) == (False, None)
    assert notification_decision("trap", saved, {}, 100) == (False, None)
    assert notification_config(path) == saved


@pytest.mark.parametrize("value", [
    {"language": "fr"}, {"enabled": {"item": "yes"}},
    {"channels": {"item": "abc"}}, {"cooldown_seconds": {"item": -1}},
    {"cooldown_seconds": {"item": 3601}}, []
])
def test_invalid_notifications_rejected_without_overwriting(tmp_path, value):
    path = tmp_path / "settings.json"
    save_notification_config(path, {"language": "de"})
    before = path.read_bytes()
    with pytest.raises(ValueError):
        save_notification_config(path, value)
    assert path.read_bytes() == before


def test_bilingual_titles_present():
    for lang in ("en", "de"):
        for key in ("dashboard", "history", "health", "achievements", "checks", "routes"):
            assert MESSAGES[lang].get(key)


def test_health_never_invents_online_for_missing_or_stale_data():
    assert health(None)["status"] == "unavailable"
    stale = health({"updated_at_epoch": 1, "ap_connected": True}, now=400)
    assert stale["status"] == "stale"
    recent = health({"updated_at_epoch": 330, "ap_connected": True, "discord": "online"},
                    now=400)
    assert recent["status"] == "online"


def test_backup_roundtrip_with_pre_restore_safety_copy(tmp_path):
    (tmp_path / ".env").write_text("DISCORD_TOKEN=private", encoding="utf-8")
    state = example_state()
    state_path = tmp_path / "archicord_data" / "seed" / "state.json"
    atomic_json(state_path, state)
    saved = create_backup(tmp_path)
    assert len(list_backups(tmp_path)) == 1
    verified = verify_backup(tmp_path, saved["name"])
    assert verified["files"] == 2
    state["death_counts"]["Player"] = 999
    atomic_json(state_path, state)
    with pytest.raises(ValueError):
        restore_backup(tmp_path, saved["name"], stopped=False)
    result = restore_backup(tmp_path, saved["name"], stopped=True)
    assert result["restored"] == 2
    assert read_json(state_path)["death_counts"]["Player"] == 25
    assert len(list_backups(tmp_path)) == 2


def test_invalid_backup_name_rejected(tmp_path):
    with pytest.raises(ValueError):
        verify_backup(tmp_path, "../../.env")
    with pytest.raises(ValueError):
        verify_backup(tmp_path, "archicord-not-valid.zip")


def test_tampered_backup_and_zip_slip_rejected(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    p = folder / "archicord-20261126T000000-abc123.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("_archicord_manifest.json", json.dumps({
            "schema": 1, "files": {"../secrets.txt": "not-a-real-hash"}}))
        z.writestr("../secrets.txt", "secret")
    with pytest.raises(ValueError):
        verify_backup(tmp_path, p.name)


def test_symlink_source_never_backed_up(tmp_path):
    (tmp_path / ".env").symlink_to(tmp_path / "nonexistent")
    # Symlink exists but Path.exists is False: no usable source -> rejected.
    with pytest.raises(ValueError):
        create_backup(tmp_path)


def test_dashboard_pages_keep_legacy_control_urls():
    assert len(PAGES) == 10
    for page in PAGES:
        document = render_dashboard(page, webui.BASE_STYLE, "csrf-token")
        assert 'href="/"' in document
        assert 'href="/apworlds"' in document
        assert 'href="/resources"' in document
        assert "__TOKEN__" not in document
        assert "csrf-token" in document
        assert "textContent" in document
    assert "/dashboard" in webui.HTML
    assert "/dashboard" in webui.APWORLD_HTML


def test_webui_v3_post_endpoints_keep_host_and_csrf_checks():
    source = webui.Handler.do_POST.__code__.co_consts
    assert any("ARCHIPELAGO" not in str(c) for c in source)
    assert "valid_local_host" in webui.Handler.do_POST.__code__.co_names
    assert "compare_digest" in webui.Handler.do_POST.__code__.co_names


def test_live_snapshot_reads_tracker_once_and_never_invents_checks(tmp_path):
    import ast
    import os
    from types import SimpleNamespace
    from archicord_core import item_routes as routes
    source = (Path(__file__).resolve().parents[1] / "archicord.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ArchipelagoDiscordBot")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "publish_live_snapshot")
    context = {"DATA_DIR": tmp_path, "os": os, "atomic_json": atomic_json,
               "summarize_seed": summarize_seed, "item_routes": routes, "checks_view": checks_view}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "archicord.py", "exec"), context)
    calls = []
    bot = SimpleNamespace(
        seed_name="seed-A", state=example_state(), own_slot=1, team=0, ap_connected=True,
        status_slots=[1,2], location_names={"Game A": {101: "Forest chest", 102: "Secret cave"},
                                            "Game B": {501: "Tower"}},
        resolve_game=lambda slot: "Game A" if slot == 1 else "Game B",
        resolve_player_name=lambda slot: "Alice" if slot == 1 else "Bob",
        slot_online=lambda slot: slot == 1,
        is_ready=lambda: True,
    )
    def get_tracker():
        calls.append(1)
        return {"1": {"doable": [101, 102], "checked": [101]},
                "2": {"doable": [501], "checked": []}}
    bot.external_checks = get_tracker
    bot.state["own_checks"] = {"known": True, "checked": [101], "missing": [102]}
    context["publish_live_snapshot"](bot)
    payload = read_json(tmp_path / "live_v3.json")
    assert len(calls) == 1
    assert payload["players"][0]["doable_label"] == "1"
    assert payload["player_checks"]["1"][0]["status"] == "checked"
    assert payload["player_checks"]["2"][0]["status"] == "doable"
    assert "DISCORD_TOKEN" not in (tmp_path / "live_v3.json").read_text()
