"""Regressions for remaining uploaded ArchiCord package subsystems."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,urlopen

import pytest

from tracker.community_features import (
    claim,claimed,release,slot_claims,profile,wish_add,wish_remove,wish_match,
    run_entry,run_begin,run_end,
)
from tracker.tracker_settings import (defaults,load_settings,save_settings,validate_settings,diagnose)
from tracker.room_checks_webui import render as render_checks
from tracker.tracker_ui import render as render_tracker
from tracker.overlay_events import append_event
from tracker.multi_instances import atomic_json
from overlay_sounds import resolve_sound,available_sounds
from overlay_studio import default_profiles,valid_profiles,save_profiles,load_profiles
from env_migration import merge_env
from screen_notifications import clip_text,position


def test_claims_are_per_discord_guild_and_seed():
    state={}
    assert claim(state,111,12,2,{1,2})[0]
    assert not claim(state,111,13,2,{1,2})[0]
    assert claim(state,222,13,2,{1,2})[0]
    assert claimed(state,111,12)==2
    assert claimed(state,222,13)==2
    assert not release(state,111,13,2)[0]
    assert release(state,111,12)[0]
    assert slot_claims(state,111)=={}


def test_wishlist_is_exact_not_fuzzy_and_deduplicates():
    state={}
    assert wish_add(state,111,12,2,"Small Key")[0]
    assert not wish_add(state,111,12,2,"small  key")[0]
    assert wish_add(state,111,13,3,"Small Key")[0]
    profile(state,111,12)["notify"]=True
    assert wish_match(state,2,"Key","Alice","Chest","a") == []
    matches=wish_match(state,2,"small key","Alice","Chest","b")
    assert len(matches)==1 and matches[0][:2]==(111,12)
    assert wish_match(state,2,"Small Key","Alice","Chest","b")==[]
    assert profile(state,111,12)["items"][0]["found"]
    assert wish_remove(state,111,12,"Small Key",2)[0]


def test_run_thread_ledger_seed_and_guild_isolation():
    state={}
    a=run_begin(state,111,"seed",0,987,123)
    assert a["status"]=="active"
    with pytest.raises(ValueError):run_begin(state,111,"seed",0,987,123)
    assert run_entry(state,222,"seed",0) is None
    assert run_entry(state,111,"seed",1) is None
    assert run_end(state,111,"seed",0,"archived")["status"]=="archived"
    with pytest.raises(ValueError):run_begin(state,111,"seed",0,987,234)
    assert run_begin(state,111,"seed",0,987,234,restart=True)["thread_id"]=="234"


def test_tracker_settings_paths_are_validated(tmp_path):
    p=tmp_path/"archipelago.exe";p.write_text("test")
    d=defaults(tmp_path,{"ARCHICORD_UT_LAUNCHER":str(p)})
    assert d["launcher_path"]==str(p)
    saved=save_settings(tmp_path,{"launcher_path":str(p)})
    assert load_settings(tmp_path)["launcher_path"]==str(p)
    assert diagnose(saved)[0]["status"]=="ok"
    for payload in ({"launcher_path":"../../bad.py"},{"launcher_path":"bad\nvalue"},
                    {"unknown":"x"},{"launcher_path":123}):
        with pytest.raises(ValueError):validate_settings(payload)


def test_overlay_profiles_are_bounded_and_isolated(tmp_path,monkeypatch):
    import overlay_studio
    monkeypatch.setattr(overlay_studio,"DATA_ROOT",tmp_path)
    base=default_profiles()
    assert load_profiles()==base
    assert save_profiles(base)==base
    assert load_profiles()==base
    with pytest.raises(ValueError):valid_profiles({"profiles":[{"id":"../x"}],"selected":"../x"})
    other=default_profiles()
    other["profiles"][0]["theme"]="unknown"
    with pytest.raises(ValueError):save_profiles(other)


def test_overlay_sound_paths_reject_traversal(tmp_path):
    d=tmp_path/"overlay_sounds";d.mkdir()
    wav=d/"ding.wav";wav.write_bytes(b"RIFFtest")
    assert available_sounds(tmp_path)==["ding.wav"]
    assert resolve_sound(tmp_path,"ding.wav")==wav
    assert resolve_sound(tmp_path,"../secret.wav") is None
    assert resolve_sound(tmp_path,"ding.mp3") is None


def test_env_migration_never_overwrites_existing_secrets(tmp_path):
    env=tmp_path/".env"
    env.write_text("# Credentials\nDISCORD_TOKEN=secret-token\n",encoding="utf-8")
    template=tmp_path/".env.example"
    template.write_text("DISCORD_TOKEN=not-real\nARCHICORD_BACKUP_INTERVAL_HOURS=24\n")
    result=merge_env(env,template,dry_run=True)
    assert result["added"]==["ARCHICORD_BACKUP_INTERVAL_HOURS"]
    assert "secret-token" in env.read_text()
    result=merge_env(env,template)
    assert result["backup"]
    assert env.read_text().count("DISCORD_TOKEN=")==1
    assert "DISCORD_TOKEN=secret-token" in env.read_text()
    assert merge_env(env,template)["added"]==[]


def test_trusted_tracker_ui_and_popup_helpers():
    assert "innerHTML" not in render_tracker(":root{}", "csrf")
    assert "textContent" in render_checks(":root{}", "room1")
    assert len(clip_text("a"*100))==84
    assert position(1920,1080)[0]>=0


def test_overlay_server_local_and_csrf_protected(tmp_path,monkeypatch):
    import overlay_studio
    monkeypatch.setattr(overlay_studio,"DATA_ROOT",tmp_path)
    server=ThreadingHTTPServer(("127.0.0.1",0),overlay_studio.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base="http://127.0.0.1:"+str(server.server_port)
    try:
        with urlopen(base+"/",timeout=3) as r:
            assert b"Overlay Studio" in r.read()
        with urlopen(base+"/api/profiles",timeout=3) as r:
            assert json.loads(r.read())["profiles"]["selected"]=="default"
        data=json.dumps(default_profiles()).encode()
        with pytest.raises(HTTPError) as err:
            urlopen(Request(base+"/api/profiles/save",data=data,headers={
                "Content-Type":"application/json"},method="POST"),timeout=3)
        assert err.value.code==403
        with urlopen(Request(base+"/api/profiles/save",data=data,method="POST",
            headers={"X-ArchiCord-Token":overlay_studio.TOKEN,
                     "Content-Type":"application/json"}),timeout=3) as r:
            assert json.loads(r.read())["ok"]
        with pytest.raises(HTTPError) as err:
            urlopen(Request(base+"/",headers={"Host":"not-local.example"}),timeout=3)
        assert err.value.code==403
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_room_tracker_module_uses_confirmed_ut_and_error_clears_stale_state():
    source=(Path(__file__).resolve().parents[1]/"tracker"/"room_tracker.py").read_text()
    assert "fetch_slot" in source
    assert "ut_checks.json" in source
    assert "unlink(missing_ok=True)" in source
    assert "room.seed==seed" in source
