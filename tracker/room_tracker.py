"""Opt-in Universal Tracker tasks for individual parallel Archipelago rooms.

Uses the existing fail-closed UT bridge. Location IDs come only from an exact
name match in that room's authenticated AP DataPackage; empty/ambiguous logic
must never be reported as playable checks.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time

from tracker.multi_instances import atomic_json
from tracker.ut_bridge import fetch_slot
from tracker.tracker_settings import load_settings


async def run_room_tracker(room, *, interval:int=180) -> None:
    interval=max(60,min(int(interval),3600))
    while not room.client.is_closed():
        try:
            launcher=load_settings(Path(__file__).resolve().parents[1])["launcher_path"].strip()
            game=room.game(room.own_slot) if room.own_slot is not None else ""
            names=room.locations.get(game,{})
            if launcher and room.connected and room.seed and room.own_slot is not None and names:
                seed,team=room.seed,room.team
                try:
                    matched=await fetch_slot(Path(launcher),room.current_url,
                        room.config["slot"],room.config.get("password",""),names,timeout=90)
                    if room.connected and room.seed==seed and room.team==team:
                        payload={"seed":seed,"team":team,"slot":room.own_slot,
                                 "updated_at":time.time(),"doable":matched,"known":True,
                                 "locations":{str(n):str(names[n])[:160] for n in matched}}
                        atomic_json(room.root/"ut_checks.json",payload)
                        room.tracker_status="confirmed"
                        room.tracker_doable=len(matched)
                except (OSError,ValueError,TimeoutError,asyncio.TimeoutError) as exc:
                    room.tracker_status="unavailable"
                    room.tracker_doable=None
                    # A stale successful tracker result must never survive failure.
                    (room.root/"ut_checks.json").unlink(missing_ok=True)
                    print(f"[Multiworld:{room.id}] Universal Tracker unavailable: {type(exc).__name__}")
                room.write_status()
            elif not launcher:
                room.tracker_status="disabled"
                room.tracker_doable=None
            else:
                room.tracker_status="waiting"
                room.tracker_doable=None
        except asyncio.CancelledError:
            raise
        except (OSError,TypeError,ValueError) as exc:
            print(f"[Multiworld:{room.id}] Tracker check error: {type(exc).__name__}")
        await asyncio.sleep(interval)
