"""Exercise reconstructed integration boundaries without external credentials or services."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

from tracker.ut_bridge import fetch_slot, write_snapshot
from tracker.apworld_manager import scan_worlds


@pytest.mark.skipif(sys.platform == "win32", reason="The fixture uses a POSIX executable script")
def test_tracker_bridge_runs_local_launcher_without_shell(tmp_path: Path) -> None:
    launcher = tmp_path / "fake_launcher"
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1:5] != ['Universal Tracker', '--', '--nogui', '--list']:\n"
        "    sys.exit(2)\n"
        "print('Progress - Check 1')\n"
        "print('[UT] diagnostic line')\n"
        "print('Progress - Check 2')\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    actual = asyncio.run(fetch_slot(
        launcher, "wss://127.0.0.1:38281", "Tester", "",
        {101: "Progress - Check 1", 202: "Progress - Check 2"}, timeout=10
    ))
    assert actual == [101, 202]


@pytest.mark.skipif(sys.platform == "win32", reason="The fixture uses a POSIX executable script")
def test_tracker_bridge_fails_closed_on_bad_cli_output(tmp_path: Path) -> None:
    launcher = tmp_path / "fake_launcher"
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "print('some unrelated launcher output')\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    with pytest.raises(ValueError, match="keine eindeutig"):
        asyncio.run(fetch_slot(
            launcher, "ws://127.0.0.1:38281", "Tester", "",
            {101: "Progress - Check 1"}, timeout=10
        ))


def test_snapshot_overwrites_atomically_without_carrying_other_seeds(tmp_path: Path) -> None:
    target = tmp_path / "export.json"
    write_snapshot(target, "first", 1, {"1": {"doable": [10]}}, {}, "one")
    write_snapshot(target, "second", 2, {"2": {"doable": [20]}}, {}, "two")
    import json
    latest = json.loads(target.read_text(encoding="utf-8"))
    assert latest["seed_name"] == "second"
    assert latest["team"] == 2
    assert latest["players"] == {"2": {"doable": [20]}}
    assert list(tmp_path.iterdir()) == [target]


def test_new_artwork_assets_are_present_and_svg(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("archicord-logo.svg", "archicord-bg.svg"):
        content = (root / "webui_assets" / name).read_text(encoding="utf-8")
        assert content.startswith("<svg")
        assert "http://www.w3.org/2000/svg" in content
        assert "<script" not in content.lower()
    banner = (root / "docs" / "assets" / "archicord-banner.svg")
    assert banner.exists()
    source = (root / "webui.py").read_text(encoding="utf-8")
    assert "/assets/archicord-bg.svg" in source
    assert "/assets/archicord-logo.svg" in source


def test_readme_discloses_missing_live_verification() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "Live validation still required" in readme
    assert "not" in readme.lower()
    assert "No license has been granted" in readme


def test_approved_multiworld_palette_and_headphone_free_logo() -> None:
    root = Path(__file__).resolve().parents[1]
    logo = (root / "webui_assets" / "archicord-logo.svg").read_text(encoding="utf-8")
    banner = (root / "docs" / "assets" / "archicord-banner.svg").read_text(encoding="utf-8")
    theme = (root / "webui.py").read_text(encoding="utf-8")
    for shade in ("#ff4b8e", "#ffdb54", "#50e282", "#22d3ef", "#318cf8"):
        assert shade in logo.lower()
        assert shade in theme.lower()
    assert "archicord-logo.svg" in theme
    assert "archicord-bg.svg" in theme
    assert "Archipelago Multiworld" in banner
    assert 'font-family:Inter, Poppins, "Avenir Next"' in theme
    assert 'headphones' not in logo.lower()
