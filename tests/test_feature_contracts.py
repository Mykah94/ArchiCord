"""Contract tests for user-visible features without Discord login."""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "archicord.py").read_text(encoding="utf-8"))


def bot_method(name):
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "ArchipelagoDiscordBot")
    node = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ctx = {"json": json, "plain_text": lambda x, limit=180: str(x)[:limit]}
    exec(compile(module, "archicord.py", "exec"), ctx)
    return ctx[name]


def test_all_six_public_slash_commands_remain_present():
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "ArchiCommands")
    names = set()
    for func in cls.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in func.decorator_list:
            if isinstance(decorator, ast.Call) and any(k.arg == "name" for k in decorator.keywords):
                names.add(next(k.value.value for k in decorator.keywords if k.arg == "name"))
    assert names == {"status", "hints", "deaths", "fortschritt", "statistik", "funktionen"}


def test_deathlink_dedupe_and_milestones_do_not_emit_every_death():
    events = []
    class Bot:
        state = {"death_event_keys": [], "death_counts": {"Player": 24}}
        def persist(self):
            pass
        def request_board_update(self, *types):
            events.append(("board", types))
        async def announce_death_milestone(self, source, count):
            events.append(("milestone", source, count))
    bot = Bot()
    handle = bot_method("handle_deathlink")
    packet = {"data": {"source": "Player", "time": 100, "cause": "trap"}}
    asyncio.run(handle(bot, packet))
    assert bot.state["death_counts"]["Player"] == 25
    assert events[-1] == ("milestone", "Player", 25)
    asyncio.run(handle(bot, packet))
    assert bot.state["death_counts"]["Player"] == 25
    assert events.count(("milestone", "Player", 25)) == 1
    asyncio.run(handle(bot, {"data": {"source": "Player", "time": 101, "cause": "trap"}}))
    assert bot.state["death_counts"]["Player"] == 26
    assert events.count(("milestone", "Player", 25)) == 1


def test_doable_checks_exclude_completed_checks_without_using_missing():
    method = bot_method("slot_doable")
    bot = SimpleNamespace(
        own_slot=3,
        state={"own_checks": {"known": True, "checked": [10]}},
        external_checks=lambda: {"3": {"doable": [10, 20, 30], "checked": [30],
                                       "missing": [10, 20, 30, 40]}},
    )
    assert method(bot, 3) == [20]
    bot.external_checks = lambda: {"3": {"missing": [10, 20, 30]}}
    assert method(bot, 3) is None
