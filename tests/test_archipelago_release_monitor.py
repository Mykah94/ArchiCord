"""Official Archipelago release monitoring and Resources tab regression tests."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from archipelago_releases import (
    check_release_once, is_new_release, load_announced_version,
    parse_latest_release, save_announced_version,
)
from webui import FIELDS, RESOURCES_HTML, HTML, APWORLD_HTML, Handler


def release(version: str) -> dict:
    return {"tag_name": version,
            "html_url": f"https://github.com/ArchipelagoMW/Archipelago/releases/tag/{version}",
            "draft": False, "prerelease": False}


def test_release_parser_accepts_official_stable_release():
    assert parse_latest_release(release("0.6.8"))["version"] == "0.6.8"


@pytest.mark.parametrize("bad", [
    {**release("0.6.8"), "prerelease": True},
    {**release("0.6.8"), "draft": True},
    {**release("0.6.8"), "html_url": "https://evil.example/download"},
    {**release("0.6.8"), "html_url": "https://github.com/ArchipelagoMW/Archipelago/releases/tag/0.6.7"},
    {**release("0.6.8"), "tag_name": "anything"},
])
def test_reject_invalid_or_nonstable_release(bad):
    with pytest.raises(ValueError):
        parse_latest_release(bad)


def test_first_check_baselines_second_announces_once(tmp_path):
    state = tmp_path / "release-state.json"
    calls = []
    latest = {"value": release("0.6.8")}

    def fetch():
        return parse_latest_release(latest["value"])

    async def send(value):
        calls.append(value["version"])
        return True

    async def scenario():
        assert await check_release_once(123, state, send, fetch=fetch) == "baseline"
        assert await check_release_once(123, state, send, fetch=fetch) == "unchanged"
        latest["value"] = release("0.6.9")
        assert await check_release_once(123, state, send, fetch=fetch) == "announced"
        assert await check_release_once(123, state, send, fetch=fetch) == "unchanged"

    asyncio.run(scenario())
    assert calls == ["0.6.9"]
    assert load_announced_version(state, 123) == "0.6.9"


def test_failed_discord_send_retries_then_stores(tmp_path):
    state = tmp_path / "release-state.json"
    save_announced_version(state, 99, "0.6.8")
    attempts = []

    async def send(item):
        attempts.append(item["version"])
        return len(attempts) > 1

    async def scenario():
        fetch = lambda: parse_latest_release(release("0.7.0"))
        assert await check_release_once(99, state, send, fetch=fetch) == "send-failed"
        assert load_announced_version(state, 99) == "0.6.8"
        assert await check_release_once(99, state, send, fetch=fetch) == "announced"

    asyncio.run(scenario())
    assert attempts == ["0.7.0", "0.7.0"]


def test_release_state_scoped_to_channel_not_seed(tmp_path):
    state = tmp_path / "release-state.json"
    save_announced_version(state, 100, "0.6.8")
    save_announced_version(state, 200, "0.6.9")
    assert load_announced_version(state, 100) == "0.6.8"
    assert load_announced_version(state, 200) == "0.6.9"


def test_do_not_announce_older_version():
    assert is_new_release("0.6.9", "0.6.8")
    assert is_new_release("0.7.0", "0.6.9")
    assert not is_new_release("0.6.8", "0.6.9")
    assert not is_new_release("0.6.8", "0.6.8")


def test_corrupted_state_fails_closed(tmp_path):
    path = tmp_path / "release-state.json"
    path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_announced_version(path, 1)


def test_webui_resources_are_consistent_and_channel_is_editable():
    assert "ARCHIPELAGO_RELEASE_CHANNEL_ID" in FIELDS
    assert "ARCHIPELAGO_RELEASE_CHANNEL_ID" in HTML
    assert "/resources" in HTML and "/resources" in APWORLD_HTML
    assert "https://archipelago.gg/" in RESOURCES_HTML
    assert "https://github.com/ArchipelagoMW/Archipelago/releases/latest" in RESOURCES_HTML
    assert 'rel="noopener noreferrer"' in RESOURCES_HTML
    assert "RESOURCES_HTML" in Handler.do_GET.__code__.co_names
