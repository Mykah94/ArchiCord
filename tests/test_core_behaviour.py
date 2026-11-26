"""Small regression tests for pure ArchiCord helpers.

The Discord bot validates environment variables during import. Extracting these
pure functions avoids logging into Discord or requiring personal credentials in
CI. These are smoke tests, not a full end-to-end Archipelago integration test.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_pure_functions(filename: str, *function_names: str) -> dict:
    path = ROOT / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set(function_names)
    definitions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in definitions} == names, "Expected helper was renamed or removed"
    context = {
        "Any": Any,
        "json": json,
        "urlsplit": urlsplit,
        "PROGRESSION_FLAG": 0b001,
        "TRAP_FLAG": 0b100,
    }
    isolated = ast.Module(body=definitions, type_ignores=[])
    exec(compile(isolated, str(path), "exec"), context)
    return context


@pytest.mark.parametrize(
    ("input_url", "expected"),
    [
        ("archipelago.gg:56851", "wss://archipelago.gg:56851"),
        ("wss://archipelago.gg:56851", "wss://archipelago.gg:56851"),
        ("ws://localhost:38281", "ws://localhost:38281"),
    ],
)
def test_archipelago_address_normalization(input_url: str, expected: str) -> None:
    parser = load_pure_functions("webui.py", "parse_address")["parse_address"]
    assert parser(input_url) == expected


@pytest.mark.parametrize(
    "bad_url",
    [
        "", "https://archipelago.gg:56851", "wss://archipelago.gg",
        "wss://archipelago.gg:0", "wss://archipelago.gg:65536",
        "wss://someone:secret@archipelago.gg:56851",
        "wss://archipelago.gg:56851/room/abc", "wss://archipelago.gg:56851\nBAD=1",
    ],
)
def test_archipelago_address_rejects_unsafe_inputs(bad_url: str) -> None:
    parser = load_pure_functions("webui.py", "parse_address")["parse_address"]
    with pytest.raises(ValueError):
        parser(bad_url)


def test_progression_and_trap_flags() -> None:
    functions = load_pure_functions("archicord.py", "get_item_flags", "is_progression_only")
    read_flags = functions["get_item_flags"]
    is_progression = functions["is_progression_only"]
    assert read_flags({"flags": "1"}) == 1
    assert read_flags({"flags": "invalid"}) == 0
    assert read_flags(None) == 0
    assert is_progression(0b001)
    assert not is_progression(0b000)
    assert not is_progression(0b100)
    assert not is_progression(0b101)  # Trap takes priority over progression-only


def test_seed_state_starts_without_deaths_or_seen_items() -> None:
    make_state = load_pure_functions("archicord.py", "create_seed_state")["create_seed_state"]
    state = make_state("example-seed", 0)
    assert state["seed_name"] == "example-seed"
    assert state["team"] == 0
    assert state["death_counts"] == {}
    assert state["items_seen"] == []
    assert state["features_announced"] is False


def test_item_fingerprint_separates_receivers() -> None:
    make_key = load_pure_functions("archicord.py", "item_key")["item_key"]
    item = {"item": 1001, "location": 2002, "player": 3}
    assert make_key(item, 4) == make_key(item, 4)
    assert make_key(item, 4) != make_key(item, 5)
