"""Private Windows Credential Manager Discord bot setup regressions."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import discord_credentials as credentials
import webui


def test_token_normalization_and_placeholders():
    assert credentials.normalize_token(" Bot real.token.example ") == "real.token.example"
    for value in ("", "YOUR_TOKEN", "foo bar", "foo\nbar", "PLACEHOLDER", "\x00"):
        with pytest.raises(ValueError):
            credentials.normalize_token(value)


def test_non_windows_store_requires_no_new_dependency(monkeypatch):
    monkeypatch.setattr(credentials, "supported", lambda: False)
    assert credentials.get_saved_token() is None
    with pytest.raises(credentials.CredentialStoreUnavailable):
        credentials.store_token("something.valid")
    monkeypatch.setenv("DISCORD_TOKEN", "old.legacy.token")
    assert credentials.resolve_bot_token() == "old.legacy.token"


@pytest.fixture
def windows_vault(tmp_path, monkeypatch):
    vault = {}
    monkeypatch.setattr(webui, "ENV", tmp_path / ".env")
    monkeypatch.setattr(webui, "ENV_EXAMPLE", tmp_path / ".env.example")
    monkeypatch.setattr(webui, "secure_token_supported", lambda: True)
    monkeypatch.setattr(webui, "get_saved_token", lambda: vault.get("token"))
    monkeypatch.setattr(webui, "store_token", lambda token: vault.__setitem__("token", token))
    return vault, tmp_path / ".env"


def test_auto_migrate_old_env_token_without_rewriting_other_settings(windows_vault):
    vault, env = windows_vault
    env.write_text("# existing settings\nDISCORD_TOKEN=old.legacy.token\nAP_URL=wss://example.org:12345\n",
                   encoding="utf-8")
    assert webui.ensure_env() is None
    assert vault["token"] == "old.legacy.token"
    content = env.read_text()
    assert "DISCORD_TOKEN=\n" in content
    assert "old.legacy.token" not in content
    assert "AP_URL=wss://example.org:12345" in content
    assert webui.token_configured()
    assert not webui.migrate_legacy_token()


def test_webui_save_token_keeps_env_secret_free(windows_vault):
    vault, env = windows_vault
    env.write_text("DISCORD_TOKEN=\nAP_URL=wss://archipelago.gg:61664\n", encoding="utf-8")
    webui.save_settings({"DISCORD_TOKEN": "new.valid.token"})
    assert vault["token"] == "new.valid.token"
    assert "new.valid.token" not in env.read_text()
    assert webui.token_configured()
    assert webui.read_settings().get("DISCORD_TOKEN") is None


def test_replace_existing_legacy_token_with_new_vault_token(windows_vault):
    vault, env = windows_vault
    env.write_text("DISCORD_TOKEN=old.token\n", encoding="utf-8")
    webui.save_settings({"DISCORD_TOKEN": "replacement.token"})
    assert vault["token"] == "replacement.token"
    assert "old.token" not in env.read_text()
    assert "replacement.token" not in env.read_text()


def test_windows_bot_uses_vault_over_legacy_env(monkeypatch):
    monkeypatch.setattr(credentials, "get_saved_token", lambda: "stored.in.windows")
    monkeypatch.setenv("DISCORD_TOKEN", "legacy.in.env")
    assert credentials.resolve_bot_token() == "stored.in.windows"


def test_missing_token_gives_setup_instruction(monkeypatch):
    monkeypatch.setattr(credentials, "get_saved_token", lambda: None)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="WebUI"):
        credentials.resolve_bot_token()


def test_token_not_leaked_in_logs(windows_vault):
    vault, env = windows_vault
    vault["token"] = "my.secret.bot.token"
    env.write_text("DISCORD_TOKEN=\n", encoding="utf-8")
    assert webui.redact_text("Failure: my.secret.bot.token") == (
        "Failure: [DISCORD_TOKEN_VERBORGEN]"
    )


def test_bot_launch_uses_credential_store_not_child_env(windows_vault, monkeypatch, tmp_path):
    vault, env = windows_vault
    vault["token"] = "credential.token"
    env.write_text("DISCORD_TOKEN=\n", encoding="utf-8")
    bot_file = tmp_path / "archicord.py"
    bot_file.write_text("print('hello')\n", encoding="utf-8")
    monkeypatch.setattr(webui, "ROOT", tmp_path)
    monkeypatch.setattr(webui, "BOT", bot_file)
    monkeypatch.setattr(webui, "PROCESS", None)
    monkeypatch.setattr(webui, "READER", None)
    monkeypatch.setattr(webui, "env_url", lambda: "wss://archipelago.gg:61664")
    monkeypatch.setenv("DISCORD_TOKEN", "plaintext.in.parent")
    class FakeProcess:
        pid = 123
        stdout = []
        def poll(self):
            return 0
    received = {}
    def fake_popen(*args, **kwargs):
        received.update(kwargs)
        return FakeProcess()
    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            pass
    monkeypatch.setattr(webui.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(webui.threading, "Thread", FakeThread)
    assert "gestartet" in webui.start_bot()
    assert "DISCORD_TOKEN" not in received["env"]
    assert received["env"]["ARCHICORD_ENV_FILE"] == str(env.resolve())
    assert "credential.token" not in json.dumps(received, default=str)


def test_token_only_http_endpoint_is_csrf_protected_and_independent_of_ap_slot(windows_vault):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

    vault, env = windows_vault
    env.write_text("AP_SLOT=\\nDISCORD_TOKEN=\\n", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), webui.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        payload = json.dumps({"token": "token.saved.only.once"}).encode("utf-8")
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + "/api/token/save", data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST"), timeout=3)
        assert error.value.code == 403
        request = Request(base + "/api/token/save", data=payload, method="POST",
                          headers={"Content-Type": "application/json",
                                   "X-ArchiCord-Token": webui.CSRF})
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
        assert result["ok"] and result["token_configured"]
        assert vault["token"] == "token.saved.only.once"
        assert "token.saved.only.once" not in env.read_text()
        with urlopen(base + "/api/status", timeout=3) as response:
            body = response.read().decode("utf-8")
        assert "token.saved.only.once" not in body
        assert '"token_storage": "windows_credential_manager"' in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.skipif(not credentials.supported(), reason="Windows Credential Manager only")
def test_real_windows_credential_manager_roundtrip(monkeypatch):
    """Use a unique disposable credential; never overwrite a real ArchiCord token."""
    import ctypes
    import uuid
    target = "ArchiCord/CredentialStoreCI-" + uuid.uuid4().hex
    monkeypatch.setattr(credentials, "TARGET", target)
    try:
        assert credentials.get_saved_token() is None
        credentials.store_token("CI.fake.bot.secret")
        assert credentials.get_saved_token() == "CI.fake.bot.secret"
        credentials.store_token("CI.replaced.bot.secret")
        assert credentials.get_saved_token() == "CI.replaced.bot.secret"
    finally:
        lib = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        lib.CredDeleteW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
        lib.CredDeleteW.restype = ctypes.c_int
        lib.CredDeleteW(target, credentials.CRED_TYPE_GENERIC, 0)
