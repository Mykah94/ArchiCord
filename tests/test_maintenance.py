"""Offline maintenance regression tests. No Discord token or AP server is required."""
import json
import time
from zipfile import ZipFile

from archicord_maintenance import BackupManager, health_snapshot


def put_json(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(content), encoding="utf8")
    return target


def test_backup_preserves_original_and_redacts_secrets(tmp_path):
    original = put_json(tmp_path, "archicord_data/multi_instances.json", {
        "instances": [{"name": "Room1", "ap_password": "hidden-123",
                       "nested": {"discord_token": "abc"}}]
    })
    put_json(tmp_path, "archicord_data/overlay_studio/layouts.json", {"profiles": []})
    put_json(tmp_path, "deathlinks/seed/deathlink_seed.json", {"DoomTest": 25})
    put_json(tmp_path, "tracker/settings/ut_paths.json", {"launcher": "launcher.exe"})
    (tmp_path / ".env").write_text("DISCORD_TOKEN=actual-secret", encoding="utf8")
    result = BackupManager(tmp_path).create()
    assert result["created"] and result["files"] == 4
    assert json.loads(original.read_text())["instances"][0]["ap_password"] == "hidden-123"
    with ZipFile(tmp_path / "backups" / result["name"]) as archive:
        assert archive.testzip() is None
        contents = archive.namelist()
        assert ".env" not in contents
        assert "archicord_data/overlay_studio/layouts.json" in contents
        assert "deathlinks/seed/deathlink_seed.json" in contents
        data = archive.read("archicord_data/multi_instances.json").decode()
        assert "hidden-123" not in data and '"abc"' not in data
        assert json.loads(data)["instances"][0]["name"] == "Room1"


def test_never_archives_raw_seed_files(tmp_path):
    put_json(tmp_path, "archicord_data/seed/state.json", {"goals": []})
    (tmp_path / "archicord_data" / "world.apworld").write_text("raw-data")
    (tmp_path / "archicord_data" / "room.zip").write_text("raw-data")
    (tmp_path / "tracker" / "yamls").mkdir(parents=True)
    (tmp_path / "tracker" / "yamls" / "player.yaml").write_text("private")
    result = BackupManager(tmp_path).create()
    with ZipFile(tmp_path / "backups" / result["name"]) as archive:
        assert set(archive.namelist()) == {"archicord_data/seed/state.json", "manifest.json"}


def test_do_not_follow_symlink_sources(tmp_path):
    folder = tmp_path / "archicord_data"
    folder.mkdir()
    external = put_json(tmp_path, "other/key.json", {"secret": "other"})
    put_json(tmp_path, "archicord_data/real.json", {"ok": True})
    try:
        (folder / "linked.json").symlink_to(external)
        (folder / "linked_directory").symlink_to(external.parent, target_is_directory=True)
    except (NotImplementedError, OSError):
        return
    result = BackupManager(tmp_path).create()
    with ZipFile(tmp_path / "backups" / result["name"]) as archive:
        assert archive.namelist() == ["archicord_data/real.json", "manifest.json"]


def test_retention_and_due_interval(tmp_path):
    put_json(tmp_path, "archicord_data/state.json", {"count": 1})
    put_json(tmp_path, "config/maintenance.json", {"keep": 2, "interval_hours": 24})
    manager = BackupManager(tmp_path)
    assert manager.run_if_due()["created"]
    assert manager.run_if_due()["reason"] == "not_due"
    manager.create()
    manager.create()
    assert len(manager.archives()) == 2


def test_disable_automatic_backups(tmp_path):
    put_json(tmp_path, "config/maintenance.json", {"enabled": False})
    put_json(tmp_path, "archicord_data/state.json", {"ok": True})
    assert BackupManager(tmp_path).run_if_due()["reason"] == "disabled"


def test_empty_data_directory_does_not_create_empty_archive(tmp_path):
    assert BackupManager(tmp_path).create()["reason"] == "no_data"


def test_health_rejects_stale_connections_and_does_not_expose_passwords(tmp_path):
    now = time.time()
    put_json(tmp_path, "archicord_data/instances/active/status.json", {
        "name": "Active", "updated_at": now - 10, "connected": True, "ap_password": "secret"
    })
    put_json(tmp_path, "archicord_data/instances/inactive/status.json", {
        "name": "Inactive", "updated_at": now - 600, "connected": True
    })
    status = health_snapshot(tmp_path, bot_running=True, discord_status="online", now=now)
    assert status["online_instances"] == 1
    assert {x["id"]: x["status"] for x in status["instances"]} == {"active": "online", "inactive": "stale"}
    assert "secret" not in json.dumps(status)
    stopped = health_snapshot(tmp_path, bot_running=False, discord_status="online", now=now)
    assert stopped["online_instances"] == 0 and stopped["discord"] == "offline"


def test_health_without_instances(tmp_path):
    status = health_snapshot(tmp_path, bot_running=True, discord_status="starting")
    assert status["instances"] == []
    assert status["online_instances"] == 0
