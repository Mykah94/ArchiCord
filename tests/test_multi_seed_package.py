"""Regression tests for the uploaded multi-seed requirements."""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tracker.multi_instances import (
    read_instances, save_instances, sanitized_instances, seed_path, statuses, validate_instances
)
from tracker.multi_seed_sessions import RoomObserver, MultiSeedManager, progression_only


def room(ident="room1", port=54001):
    return {"id": ident, "name": "Room " + ident, "slot": "ArchiCord",
            "game": "Game A", "ap_url": f"wss://archipelago.gg:{port}",
            "guild_id": "111111111111111111", "password": "do-not-share",
            "item_channel_id": "222222222222222222", "hint_channel_id": "",
            "death_channel_id": "", "status_channel_id": ""}


@pytest.mark.parametrize("flag,expected", [(0,False),(1,True),(2,False),(3,True),
                                             (4,False),(5,False),(6,False),(7,False)])
def test_progression_only_filter(flag, expected):
    assert progression_only(flag) is expected


def test_independent_multi_seed_configuration_and_no_password_leak(tmp_path):
    a=room()
    b=room("room2", 54002)
    saved=save_instances(tmp_path,[a,b])
    assert len(saved)==2
    assert "password" not in saved[0]
    assert "do-not-share" not in json.dumps(saved)
    assert read_instances(tmp_path)[0]["password"] == "do-not-share"
    a["password"]=""
    save_instances(tmp_path,[a,b])
    assert read_instances(tmp_path)[0]["password"] == "do-not-share"
    first=seed_path(tmp_path,"room1",a["ap_url"],a["slot"],"shared-seed",0)
    second=seed_path(tmp_path,"room2",b["ap_url"],b["slot"],"shared-seed",0)
    different_team=seed_path(tmp_path,"room1",a["ap_url"],a["slot"],"shared-seed",1)
    assert len({first,second,different_team}) == 3


def test_instance_validation_prevents_room_duplicates_and_invalid_channels():
    with pytest.raises(ValueError):
        validate_instances([room(),room("room2")])
    with pytest.raises(ValueError):
        validate_instances([room("../escape")])
    with pytest.raises(ValueError):
        validate_instances([{**room(), "ap_url":"http://bad.example"}])
    with pytest.raises(ValueError):
        validate_instances([{**room(), "item_channel_id":"broken"}])
    with pytest.raises(ValueError):
        validate_instances([{**room(), "password":"bad\nvalue"}])
    with pytest.raises(ValueError):
        validate_instances([room()]*13)


def test_progression_only_embeds_for_parallel_observers(tmp_path):
    class StubClient:
        def is_closed(self): return False
    first=RoomObserver(StubClient(),room(),tmp_path)
    second=RoomObserver(StubClient(),room("room2",54002),tmp_path)
    for observer in (first,second):
        observer.connected=True
        observer.seed="demo"
        observer.players={1:"Sender",2:"Receiver"}
        observer.games={1:"Game A",2:"Game A"}
        observer.items={"Game A":{20:"Progression key"}}
        observer.locations={"Game A":{30:"Forest chest"}}
        observer.send=AsyncMock(return_value=True)
    async def run():
        for flag in (0,2,4,5,6,7):
            event={"receiving":2,"item":{"player":1,"item":20,"location":30,"flags":flag}}
            await first.process_item(event)
            await second.process_item(event)
        assert not first.send.called and not second.send.called
        assert first.state["items_seen"] == []
        await first.process_item({"receiving":2,"item":{"player":1,"item":20,"location":30,"flags":1}})
        await first.process_item({"receiving":2,"item":{"player":1,"item":20,"location":30,"flags":1}})
        await second.process_item({"receiving":2,"item":{"player":1,"item":20,"location":30,"flags":1}})
    asyncio.run(run())
    assert first.send.call_count == second.send.call_count == 1
    assert first.state["items_seen"] == second.state["items_seen"]


def test_parallel_rooms_statuses_are_separate_and_stale_offline(tmp_path):
    rows=[room(),room("room2",54002)]
    save_instances(tmp_path,rows)
    import time
    from tracker.multi_instances import atomic_json, instance_directory
    for ident,fresh in [("room1",True),("room2",False)]:
        atomic_json(instance_directory(tmp_path,ident)/"status.json",
                    {"connected":True,"seed":ident,"updated_at":time.time() if fresh else 1})
    found=statuses(tmp_path)
    assert found[0]["status"]["connected"]
    assert not found[1]["status"]["connected"]
    assert "password" not in json.dumps(found)


def test_primary_bot_remains_and_uses_same_progression_filter():
    tree=ast.parse((Path(__file__).resolve().parents[1]/"archicord.py").read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="ArchipelagoDiscordBot")
    methods={n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert "archipelago_loop" in methods
    assert "setup_hook" in methods
    assert "handle_item" in methods
    assert "multi_seed" in ast.unparse(methods["setup_hook"]) or "multi_seed" in ast.unparse(cls)
    assert "is_progression_only(flags)" in ast.unparse(methods["handle_item"])


def test_webui_has_multi_seed_manager_and_guarded_posts():
    import webui
    assert "instanzen" in webui.Handler.do_GET.__code__.co_consts or "render_instances" in webui.Handler.do_GET.__code__.co_names
    assert "save_instances" in webui.Handler.do_POST.__code__.co_names
    assert "compare_digest" in webui.Handler.do_POST.__code__.co_names
    assert "valid_local_host" in webui.Handler.do_POST.__code__.co_names
    assert "/instanzen" in webui.HTML


def test_official_room_url_only_and_port_extraction():
    from tracker.room_connection import validate_room_url, current_room_port
    url="https://archipelago.gg/room/0123456789abcdef0123456789abcdef"
    assert validate_room_url(url)==url
    assert current_room_port("Connect with /connect archipelago.gg:54321") == 54321
    assert current_room_port("The address/ip is archipelago.gg and port is 52001") == 52001
    assert current_room_port("No port here") is None
    for bad in ["https://evil.example/room/0123456789abcdef0123456789abcdef",
                "http://archipelago.gg/room/0123456789abcdef0123456789abcdef",
                "https://archipelago.gg/room/0123456789abcdef0123456789abcdef?next=evil",
                "https://archipelago.gg/room/no"]:
        with pytest.raises(ValueError):
            validate_room_url(bad)


def test_overlay_event_log_redacts_and_bounds(tmp_path):
    from tracker.overlay_events import append_event, recent_events
    folder=tmp_path/"instances"/"room1"
    append_event(folder,category="item",seed="A",player="Sender",
                 recipient="Receiver",item="Useful",location="Here")
    append_event(folder,category="progression",seed="B",player="Sender",
                 recipient="Receiver",item="Progression",location="Forest")
    recent=recent_events(folder,seed="B")
    assert len(recent)==1
    assert recent[0]["item"] == "Progression"
    assert "password" not in json.dumps(recent)
    with pytest.raises(ValueError):
        append_event(folder,category="unknown",seed="A",player="X")


def test_multiroom_slash_commands_use_guild_guard():
    tree=ast.parse((Path(__file__).resolve().parents[1]/"archicord.py").read_text())
    commands=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="ArchiCommands")
    method=next(n for n in commands.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="multi_room_reply")
    text=ast.unparse(method)
    assert "primary_guild_allowed" in text
    assert "for_guild" in text
    for name in ("status","hints","deaths","fortschritt","statistik"):
        func=next(n for n in commands.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
        assert "instanz" in ast.unparse(func)


def test_obs_routes_return_html_and_redacted_json(tmp_path,monkeypatch):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen
    import webui
    from tracker.overlay_events import append_event
    monkeypatch.setattr(webui,"ROOT",tmp_path)
    monkeypatch.setattr(webui,"ENV",tmp_path/".env")
    (tmp_path/".env").write_text("DISCORD_TOKEN=private_token_never_expose",encoding="utf-8")
    save_instances(tmp_path/"archicord_data",[room()])
    folder=tmp_path/"archicord_data"/"instances"/"room1"
    append_event(folder,category="progression",seed="One",player="Alice",item="Sword")
    server=ThreadingHTTPServer(("127.0.0.1",0),webui.Handler)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        base=f"http://127.0.0.1:{server.server_port}"
        with urlopen(base+"/obs-log?instance=room1",timeout=3) as response:
            html=response.read().decode()
            assert "ArchiCord Live Log" in html
        with urlopen(base+"/api/obs-log?instance=room1",timeout=3) as response:
            body=response.read().decode()
            assert "Sword" in body
            assert "private_token_never_expose" not in body
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
