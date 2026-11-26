"""Local HTTP integration and language regression tests for ArchiCord 3.0."""
from __future__ import annotations

import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import stat
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

import discord
import pytest

import webui
from archicord_core import notification_config, save_notification_config, verify_backup
from archicord_dashboard import render_dashboard
from archicord_i18n import localize_embed


def test_discord_translation_is_opt_in_and_does_not_mutate_original():
    source = discord.Embed(title="✨ Progression-Item ✨", description="**Item**\nKey")
    source.add_field(name="📍 Fundort", value="Forest chest")
    source.add_field(name="🎯 Für", value="Alice")
    german = localize_embed(source, "de")
    english = localize_embed(source, "en")
    assert german is source
    assert english is not source
    assert english.title == "✨ Progression Item ✨"
    assert english.fields[0].name == "📍 Location"
    assert english.fields[1].name == "🎯 For"
    assert source.fields[0].name == "📍 Fundort"


def test_language_config_independent_with_legacy_compatibility(tmp_path):
    path = tmp_path / "notifications_v3.json"
    saved = save_notification_config(path, {"language": "de", "web_language": "en",
                                          "discord_language": "de"})
    assert saved["web_language"] == "en"
    assert saved["discord_language"] == "de"
    assert notification_config(path) == saved
    earlier = save_notification_config(path, {"language": "en"})
    assert earlier["web_language"] == "en"
    assert earlier["discord_language"] == "en"


def test_new_pages_include_language_controls_and_no_dom_html_injection():
    page = render_dashboard("notifications", webui.BASE_STYLE, "a-csrf-token")
    assert "web_language" in page
    assert "discord_language" in page
    assert "textContent" in page
    assert "innerHTML" not in page
    assert "a-csrf-token" in page


@pytest.fixture
def local_ui(tmp_path, monkeypatch):
    monkeypatch.setattr(webui, "ROOT", tmp_path)
    monkeypatch.setattr(webui, "ENV", tmp_path / ".env")
    monkeypatch.setattr(webui, "ENV_EXAMPLE", tmp_path / ".env.example")
    monkeypatch.setattr(webui, "PROCESS", None)
    (tmp_path / ".env").write_text(
        "DISCORD_TOKEN=secret-do-not-publish\n"
        "ARCHICORD_BACKUP_INTERVAL_HOURS=24\n", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), webui.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def get_json(url):
    with urlopen(url, timeout=3) as resp:
        return json.loads(resp.read())


def post_json(url, body, *, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-ArchiCord-Token"] = token
    request = Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=3) as resp:
        return json.loads(resp.read())


def test_dashboard_http_pages_return_real_html(local_ui):
    base, _ = local_ui
    for page in ("dashboard", "players", "checks", "history", "item-routes",
                 "health", "backups", "compatibility", "notifications", "achievements"):
        with urlopen(base + "/" + page, timeout=3) as resp:
            text = resp.read().decode()
            assert "<!doctype html>" in text.lower()
            assert "ArchiCord" in text
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy")


def test_dashboard_api_excludes_tokens_and_rejects_cross_origin_host(local_ui):
    base, _ = local_ui
    data = get_json(base + "/api/v3/history")
    assert data == {"ok": True, "history": []}
    data = get_json(base + "/api/v3/dashboard")
    assert data["snapshot"] is None
    for endpoint in ("dashboard", "history", "health", "backups", "notifications"):
        with urlopen(base + "/api/v3/" + endpoint, timeout=3) as resp:
            assert b"secret-do-not-publish" not in resp.read()
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(base + "/dashboard", headers={"Host": "attacker.example"}), timeout=3)
    assert exc.value.code == 403


def test_notifications_post_requires_csrf_and_persists_settings(local_ui):
    base, root = local_ui
    target = base + "/api/v3/notifications/save"
    payload = {"config": {"language": "en", "web_language": "en",
                          "discord_language": "de", "enabled": {"item": False}}}
    with pytest.raises(HTTPError) as exc:
        post_json(target, payload)
    assert exc.value.code == 403
    result = post_json(target, payload, token=webui.CSRF)
    assert result["config"]["enabled"]["item"] is False
    assert (root / "archicord_data" / "notifications_v3.json").exists()


def test_backup_actions_are_local_csrf_guarded_and_restore_requires_confirmation(local_ui):
    base, root = local_ui
    with pytest.raises(HTTPError) as exc:
        post_json(base + "/api/v3/backup/create", {})
    assert exc.value.code == 403
    result = post_json(base + "/api/v3/backup/create", {}, token=webui.CSRF)
    archive_name = result["backup"]["name"]
    assert verify_backup(root, archive_name)["files"] == 1
    assert b"secret-do-not-publish" not in json.dumps(get_json(base + "/api/v3/backups")).encode()
    with pytest.raises(HTTPError) as exc:
        post_json(base + "/api/v3/backup/restore", {"name": archive_name}, token=webui.CSRF)
    assert exc.value.code == 400


def test_zip_symlinks_rejected(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    name = "archicord-20261126T140000-ab1234.zip"
    with zipfile.ZipFile(folder / name, "w") as archive:
        info = zipfile.ZipInfo("archicord_data/secret")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "/etc/passwd")
        archive.writestr("_archicord_manifest.json", json.dumps({
            "schema": 1, "files": {"archicord_data/secret": "dummy"}}))
    with pytest.raises(ValueError, match="Unsafe backup entry"):
        verify_backup(tmp_path, name)


def test_automatic_backup_creates_private_archive(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ARCHICORD_BACKUP_INTERVAL_HOURS=24\\nDISCORD_TOKEN=secret", encoding="utf-8")
    monkeypatch.setattr(webui, "ROOT", tmp_path)
    monkeypatch.setattr(webui, "ENV", tmp_path / ".env")
    class FakeStop:
        calls = 0
        def is_set(self):
            return False
        def wait(self, duration):
            self.calls += 1
            return self.calls >= 2
    monkeypatch.setattr(webui, "BACKUP_STOP", FakeStop())
    webui.auto_backup_loop()
    files = list((tmp_path / "backups").glob("archicord-*.zip"))
    assert len(files) == 1
    assert verify_backup(tmp_path, files[0].name)["files"] == 1
    if os.name != "nt":
        assert files[0].stat().st_mode & 0o077 == 0


def test_automatic_backups_can_be_disabled(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ARCHICORD_BACKUP_INTERVAL_HOURS=0\\n", encoding="utf-8")
    monkeypatch.setattr(webui, "ROOT", tmp_path)
    monkeypatch.setattr(webui, "ENV", tmp_path / ".env")
    class FakeStop:
        calls = 0
        def is_set(self):
            return False
        def wait(self, duration):
            self.calls += 1
            return self.calls >= 2
    monkeypatch.setattr(webui, "BACKUP_STOP", FakeStop())
    webui.auto_backup_loop()
    assert not (tmp_path / "backups").exists()
