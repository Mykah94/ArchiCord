"""Parallel Archipelago room observers using one existing Discord login.

Each room owns one WebSocket task, its own seed state and Discord channels.
None of the legacy bot's AP state, commands or saved seeds are replaced.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
import uuid

import discord
import websockets

from tracker.room_connection import resolve_room_url
from tracker.overlay_events import append_event
from tracker.community_features import wish_match,run_entry,run_begin
from tracker.room_tracker import run_room_tracker
from tracker.multi_instances import (
    atomic_json, instance_directory, read_instances, safe_read, seed_path,
)


def text(value: object, limit: int = 170) -> str:
    return str(value if value is not None else "Unknown").replace("\n", " ").replace("\r", " ").replace("\x00", "")[:limit]


def item_key(item: dict, receiver: object) -> str:
    return json.dumps([item.get("item"), item.get("location"), item.get("player"), receiver], separators=(",", ":"))


def progression_only(flags: object) -> bool:
    try:
        value = int(flags)
        return bool(value & 1) and not bool(value & 4)
    except (ValueError, TypeError):
        return False


def fresh_state(seed: str, team: int) -> dict:
    return {"seed": seed, "team": team, "items_seen": [], "death_event_keys": [],
            "death_counts": {}, "goals": [], "hints_seen": [], "observed_items": [], "started_at": int(time.time())}


class RoomObserver:
    def __init__(self, client: discord.Client, config: dict, data_dir: Path):
        self.client, self.config, self.data_dir = client, dict(config), data_dir
        self.id = config["id"]
        self.root = instance_directory(data_dir, self.id)
        self.seed = ""
        self.pending_seed = ""
        self.team = 0
        self.own_slot: int | None = None
        self.connected = False
        self.error = ""
        self.ws = None
        self.current_url = config['ap_url']
        self.room_checked = 0.0
        self.players: dict[int, str] = {}
        self.games: dict[int, str] = {}
        self.items: dict[str, dict[int, str]] = {}
        self.locations: dict[str, dict[int, str]] = {}
        self.online: set[int] = set()
        self.pending_items: list[dict] = []
        self.state = fresh_state("", 0)
        self._board_lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()
        self.tracker_status = 'waiting'
        self.tracker_doable = None

    def status(self) -> dict:
        return {
            "id": self.id, "connected": self.connected, "seed": self.seed,
            "team": self.team, "players": len(self.players),
            "online": len(self.online), "deaths": sum(self.state.get("death_counts", {}).values()),
            "goals": len(self.state.get("goals", [])), "error": self.error[:180],
            "tracker_status": self.tracker_status, "tracker_doable": self.tracker_doable,
            "updated_at": int(time.time()),
        }

    def write_status(self) -> None:
        atomic_json(self.root / "status.json", self.status())

    def save_state(self) -> None:
        if self.seed:
            target = seed_path(self.data_dir, self.id, self.config["ap_url"],
                               self.config["slot"], self.seed, self.team)
            atomic_json(target, self.state)
        self.write_status()

    def player(self, slot: object) -> str:
        try:
            return self.players.get(int(slot), f"Slot {slot}")
        except (ValueError, TypeError):
            return f"Slot {slot}"

    def game(self, slot: object) -> str:
        try:
            return self.games.get(int(slot), "")
        except (ValueError, TypeError):
            return ""

    async def send(self, channel_key: str, embed: discord.Embed) -> bool:
        raw = self.config.get(channel_key) or self.config.get("status_channel_id")
        if not raw:
            return False
        try:
            ident = int(raw)
            channel = self.client.get_channel(ident)
            if channel is None:
                channel = await self.client.fetch_channel(ident)
            if not hasattr(channel, "send"):
                return False
            if str(getattr(getattr(channel, "guild", None), "id", "")) != str(self.config["guild_id"]):
                print(f"[Multiworld:{self.id}] Refused channel belonging to a different Discord guild")
                return False
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return True
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, ValueError) as exc:
            print(f"[Multiworld:{self.id}] Discord delivery failed: {type(exc).__name__}")
            return False

    def embed(self, title: str, description: str, color: int = 0x9972f9) -> discord.Embed:
        result = discord.Embed(title=title, description=description[:3800], color=color)
        result.set_footer(text=f"ArchiCord · {text(self.config['name'], 55)} · Seed: {text(self.seed, 65)}")
        return result

    async def on_connected(self, packet: dict) -> None:
        seed = self.pending_seed
        if not seed:
            seed = "unknown-" + str(uuid.uuid4())
        team = int(packet.get("team", 0))
        target = seed_path(self.data_dir, self.id, self.config["ap_url"],
                           self.config["slot"], seed, team)
        stored = safe_read(target, {}, limit=4 * 1024 * 1024)
        self.state = stored if (isinstance(stored, dict)
                    and stored.get("seed") == seed and stored.get("team") == team) else fresh_state(seed, team)
        for key, value in fresh_state(seed, team).items():
            self.state.setdefault(key, value)
        self.seed, self.team = seed, team
        self.tracker_status = 'waiting'
        self.tracker_doable = None
        (self.root / 'ut_checks.json').unlink(missing_ok=True)
        self.own_slot = int(packet['slot'])
        self.players = {int(p["slot"]): text(p.get("alias") or p.get("name") or p["slot"])
                        for p in packet.get("players", [])
                        if isinstance(p, dict) and "slot" in p and int(p.get("team", 0)) == team}
        self.games = {int(k): text(v.get("game", ""), 120)
                      for k, v in packet.get("slot_info", {}).items() if isinstance(v, dict)}
        self.items.clear()
        self.locations.clear()
        self.pending_items.clear()
        self.online.clear()
        self.connected = True
        self.error = ""
        self.save_state()
        if self.config.get('thread_enabled'):
            await self.ensure_run_thread()
        await self.ws.send(json.dumps([{"cmd": "GetDataPackage",
              "games": sorted(set(self.games.values()) - {""})}]))
        print(f"[Multiworld:{self.id}] Connected to seed {text(seed)} ({len(self.players)} players)")

    async def process_item(self, packet: dict) -> None:
        """Only real progression items get Discord embeds. Traps never do."""
        item = packet.get("item")
        if not self.connected or not isinstance(item, dict):
            return
        try:
            receiver = int(packet["receiving"])
            finder = int(item["player"])
            item_id = int(item["item"])
            location_id = int(item["location"])
        except (KeyError, TypeError, ValueError):
            return
        key = item_key(item, receiver)
        game = self.game(receiver)
        name = self.items.get(game, {}).get(item_id)
        if not name:
            if len(self.pending_items) < 400:
                self.pending_items.append(packet)
            return
        location = self.locations.get(self.game(finder), {}).get(location_id, f"Location {location_id}")
        try:
            flags = int(item.get('flags', 0) or 0)
        except (ValueError, TypeError):
            flags = 0
        if key not in self.state.get('observed_items', []):
            category = 'trap' if flags & 4 else 'progression' if progression_only(flags) else 'item'
            try:
                append_event(self.root, category=category, seed=self.seed,
                             player=self.player(finder), recipient=self.player(receiver),
                             item=name, location=location)
                self.state.setdefault('observed_items', []).append(key)
                self.state['observed_items'] = self.state['observed_items'][-15000:]
                self.save_state()
            except OSError as exc:
                print(f'[Multiworld:{self.id}] OBS event log: {type(exc).__name__}')
        if key in self.state.get('observed_items', []):
            for guild, user, wish in wish_match(self.state,receiver,name,
                    self.player(finder),location,key):
                if str(guild)!=str(self.config['guild_id']):
                    continue
                try:
                    recipient=await self.client.fetch_user(user)
                    await recipient.send('🎁 Wishlist item found: '+text(name,120)+
                         ' · '+text(self.seed,80),allowed_mentions=discord.AllowedMentions.none())
                except (discord.Forbidden,discord.HTTPException,discord.NotFound):
                    pass
            self.save_state()
        if not progression_only(flags) or key in self.state.get('items_seen', []):
            return
        embed = self.embed("✨ Progression Item", f"**{text(name)}**", 0xa94cf7)
        embed.add_field(name="📍 Location", value=text(location, 280), inline=False)
        embed.add_field(name="🌍 From", value=text(self.player(finder)), inline=True)
        embed.add_field(name="🎯 For", value=text(self.player(receiver)), inline=True)
        # Keep a failed send eligible for retry; never increment counters twice.
        if await self.send("item_channel_id", embed):
            self.state.setdefault("items_seen", []).append(key)
            self.state["items_seen"] = self.state["items_seen"][-15000:]
            self.save_state()

    async def process_hint(self, packet: dict) -> None:
        """Only progression hints are announced; persisted per room and seed."""
        item = packet.get("item")
        if not self.connected or not isinstance(item, dict) or not progression_only(item.get("flags", 0)):
            return
        try:
            receiver = int(packet["receiving"])
            finder = int(item["player"])
            item_id = int(item["item"])
            location_id = int(item["location"])
        except (KeyError, TypeError, ValueError):
            return
        key = item_key(item, receiver)
        found = bool(item.get("found", packet.get("found", False)))
        marker = key + ("-found" if found else "-open")
        if marker in self.state.get("hints_seen", []):
            return
        name = self.items.get(self.game(receiver), {}).get(item_id, f"Item {item_id}")
        location = self.locations.get(self.game(finder), {}).get(location_id, f"Location {location_id}")
        embed = self.embed("🔎 Progression Hint",
            f"**{text(name)}** · {text(location)}\\n"
            f"From **{text(self.player(finder))}** → **{text(self.player(receiver))}**"
            + (" · ✅ Found" if found else " · ❓ Open"), 0x318cf8)
        if await self.send("hint_channel_id", embed):
            self.state.setdefault("hints_seen", []).append(marker)
            self.state["hints_seen"] = self.state["hints_seen"][-5000:]
            self.save_state()

    async def deathlink(self, packet: dict) -> None:
        data = packet.get("data")
        if not self.connected or not isinstance(data, dict):
            return
        name = text(data.get("source", "Unknown"))
        stamp = data.get("time")
        key = json.dumps([stamp, name, data.get("cause")], ensure_ascii=False) if stamp is not None else None
        if key is not None and key in self.state.get("death_event_keys", []):
            return
        counts = self.state.setdefault("death_counts", {})
        counts[name] = counts.get(name, 0) + 1
        if key is not None:
            self.state.setdefault("death_event_keys", []).append(key)
            self.state["death_event_keys"] = self.state["death_event_keys"][-500:]
        self.save_state()
        await self.update_death_board()
        if counts[name] % 25 == 0:
            await self.send("death_channel_id", self.embed(
                "💀 DeathLink milestone", f"**{text(name)}** has died **{counts[name]}** times.", 0xff4b8e))

    async def ensure_run_thread(self) -> None:
        """Create at most one Discord thread for the current seed/guild/team."""
        parent_id=self.config.get("thread_parent_channel_id") or self.config.get("status_channel_id")
        if not parent_id or not self.seed:
            return
        async with self._run_lock:
            guild=self.config["guild_id"]
            existing=run_entry(self.state,guild,self.seed,self.team)
            if existing is not None:
                return  # A manually closed run must not be reopened on reconnect.
            try:
                channel=self.client.get_channel(int(parent_id)) or await self.client.fetch_channel(int(parent_id))
                if not isinstance(channel,discord.TextChannel) or str(channel.guild.id)!=str(guild):
                    return
                thread=await channel.create_thread(
                    name=("🌈 "+self.config["name"][:26]+" · "+self.seed[:40]),
                    type=discord.ChannelType.public_thread,auto_archive_duration=1440,
                    reason="ArchiCord automatic Multiworld run")
                run_begin(self.state,guild,self.seed,self.team,parent_id,thread.id)
                self.save_state()
                await thread.send(embed=self.embed("🌈 Multiworld run",
                     "Seed: "+text(self.seed,110)+" · Team: "+str(self.team)),
                     allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden,discord.NotFound,discord.HTTPException,ValueError) as exc:
                print(f"[Multiworld:{self.id}] Run thread not created: {type(exc).__name__}")

    async def update_death_board(self) -> None:
        raw = self.config.get("death_channel_id")
        if not raw:
            return
        async with self._board_lock:
            try:
                channel = self.client.get_channel(int(raw)) or await self.client.fetch_channel(int(raw))
                if str(getattr(getattr(channel, "guild", None), "id", "")) != self.config["guild_id"]:
                    return
                counts = self.state.get("death_counts", {})
                ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
                description = "\n".join(f"**{i}.** {text(name)} — {count}×"
                                        for i, (name, count) in enumerate(ranked[:20], 1)) or "No DeathLinks yet"
                embed = self.embed("☠️ DeathLink leaderboard", description, 0xff4b8e)
                boards = self.state.setdefault("boards", {})
                existing = boards.get("deathlinks", {})
                if existing.get("channel_id") == str(raw):
                    try:
                        message = channel.get_partial_message(int(existing["message_id"]))
                        await message.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                        return
                    except (discord.NotFound, discord.HTTPException, ValueError, KeyError):
                        pass
                sent = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                boards["deathlinks"] = {"channel_id": str(raw), "message_id": sent.id}
                self.save_state()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass

    async def handle(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "RoomInfo":
            self.pending_seed = text(packet.get("seed_name") or "unknown-" + str(uuid.uuid4()), 160)
            await self.ws.send(json.dumps([{
                "cmd": "Connect", "password": self.config.get("password", ""),
                "game": self.config["game"], "name": self.config["slot"],
                "uuid": str(uuid.uuid4()),
                "version": {"class": "Version", "major": 0, "minor": 6, "build": 0},
                "items_handling": 0b111, "tags": ["DeathLink", "Tracker", "TextOnly"],
                "slot_data": False,
            }]))
        elif cmd == "Connected":
            await self.on_connected(packet)
            await self.update_death_board()
        elif cmd == "ConnectionRefused":
            self.error = "Room refused connection: check slot, game and password"
            if self.ws:
                await self.ws.close()
        elif cmd == "DataPackage":
            games = packet.get("data", {}).get("games", {})
            for game, package in games.items():
                self.items[game] = {int(v): text(k, 180)
                                    for k, v in package.get("item_name_to_id", {}).items()}
                self.locations[game] = {int(v): text(k, 180)
                                        for k, v in package.get("location_name_to_id", {}).items()}
            queued = self.pending_items[:]
            self.pending_items.clear()
            for item in queued:
                await self.process_item(item)
        elif cmd == "PrintJSON":
            kind = packet.get("type")
            if kind == "ItemSend":
                await self.process_item(packet)
            elif kind == "Hint":
                await self.process_hint(packet)
            elif kind == "Goal" and packet.get("team", self.team) == self.team:
                slot = str(packet.get("slot", ""))
                if slot and slot not in self.state.setdefault("goals", []):
                    self.state["goals"].append(slot)
                    self.save_state()
                    await self.send("status_channel_id", self.embed(
                        "🏆 Goal reached", f"**{text(self.player(slot))}** completed their goal.", 0xffdb54))
            elif kind == "Join" and packet.get("team", self.team) == self.team:
                if packet.get("slot") is not None:
                    self.online.add(int(packet["slot"]))
                    self.write_status()
            elif kind == "Part" and packet.get("team", self.team) == self.team:
                if packet.get("slot") is not None:
                    self.online.discard(int(packet["slot"]))
                    self.write_status()
        elif cmd == "Bounced" and "DeathLink" in packet.get("tags", []):
            await self.deathlink(packet)
        elif cmd == "RoomUpdate" and isinstance(packet.get("players"), list):
            for player in packet["players"]:
                if isinstance(player, dict) and player.get("slot") is not None and int(player.get("team", 0)) == self.team:
                    self.players[int(player["slot"])] = text(player.get("alias") or player.get("name") or player["slot"])
            self.write_status()

    async def check_room_port(self) -> None:
        room_page = self.config.get('room_url')
        if not room_page:
            return
        self.room_checked = time.monotonic()
        try:
            candidate = await asyncio.to_thread(resolve_room_url, room_page)
        except (OSError, ValueError, TimeoutError) as exc:
            self.error = f'Room URL temporarily unavailable: {type(exc).__name__}'
            return
        if candidate != self.current_url:
            self.current_url = candidate
            self.error = ''
            self.write_status()
            if self.ws is not None:
                await self.ws.close()

    async def room_port_watcher(self) -> None:
        while not self.client.is_closed():
            if self.config.get('room_url') and time.monotonic() - self.room_checked >= 60:
                await self.check_room_port()
            await asyncio.sleep(10)

    async def run(self) -> None:
        await self.client.wait_until_ready()
        watcher = asyncio.create_task(self.room_port_watcher())
        tracker_task = asyncio.create_task(run_room_tracker(self))
        try:
            while not self.client.is_closed():
                try:
                    if self.config.get('room_url') and time.monotonic() - self.room_checked >= 60:
                        await self.check_room_port()
                    async with websockets.connect(self.current_url, max_size=32 * 1024 * 1024,
                                                 ping_interval=20, ping_timeout=20) as ws:
                        self.ws = ws
                        async for raw in ws:
                            try:
                                packets = json.loads(raw)
                                if isinstance(packets, dict):
                                    packets = [packets]
                                if isinstance(packets, list):
                                    for packet in packets[:200]:
                                        if isinstance(packet, dict):
                                            try:
                                                await self.handle(packet)
                                            except (TypeError, ValueError, KeyError, OSError) as exc:
                                                self.error = f"Packet error: {type(exc).__name__}"
                            except (ValueError, UnicodeError):
                                self.error = "Malformed Archipelago packet"
                except asyncio.CancelledError:
                    raise
                except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as exc:
                    self.error = f"Connection error: {type(exc).__name__}"
                finally:
                    self.ws = None
                    self.connected = False
                    self.online.clear()
                    self.write_status()
                await asyncio.sleep(5)
        finally:
            watcher.cancel()
            tracker_task.cancel()
            await asyncio.gather(watcher, tracker_task, return_exceptions=True)


class MultiSeedManager:
    """Hot-reload additional rooms without reconnecting the shared Discord bot."""
    def __init__(self, client: discord.Client, data_dir: Path):
        self.client = client
        self.data_dir = data_dir
        self.observers: dict[str, RoomObserver] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.supervisor: asyncio.Task | None = None
        self._synced_guilds: set[int] = set()

    def start(self) -> None:
        if self.supervisor is None or self.supervisor.done():
            self.supervisor = asyncio.create_task(self.watch())

    async def watch(self) -> None:
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                configs = read_instances(self.data_dir)
                wanted = {row["id"]: row for row in configs if row.get("enabled", True)}
                # Other Discord guilds receive /archi commands through the same login.
                for guild_id in {int(row["guild_id"]) for row in wanted.values()} - self._synced_guilds:
                    try:
                        guild = discord.Object(id=guild_id)
                        self.client.tree.copy_global_to(guild=guild)
                        await self.client.tree.sync(guild=guild)
                        self._synced_guilds.add(guild_id)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        print(f"[Multiworld] Cannot sync guild commands: {type(exc).__name__}")
                for ident in set(self.observers) - set(wanted):
                    await self.stop(ident)
                for ident, config in wanted.items():
                    current = self.observers.get(ident)
                    if current and not self.tasks[ident].done():
                        if current.config == config:
                            continue
                        # Channel labels and guild assignments can change
                        # without tearing down the Archipelago WebSocket.
                        connection_fields = ("ap_url", "room_url", "slot", "game", "password")
                        if all(current.config.get(k) == config.get(k) for k in connection_fields):
                            current.config = dict(config)
                            current.write_status()
                            continue
                    if current:
                        await self.stop(ident)
                    current = RoomObserver(self.client, config, self.data_dir)
                    self.observers[ident] = current
                    self.tasks[ident] = asyncio.create_task(current.run(), name="archicord-room-" + ident)
                    print(f"[Multiworld:{ident}] Instance launched")
            except (ValueError, OSError, TypeError) as exc:
                print(f"[Multiworld] Cannot load instances: {type(exc).__name__}")
            await asyncio.sleep(3)

    async def stop(self, ident: str) -> None:
        task = self.tasks.pop(ident, None)
        observer = self.observers.pop(ident, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if observer:
            observer.connected = False
            observer.write_status()

    def for_guild(self, guild_id: int | None) -> list[RoomObserver]:
        return [room for room in self.observers.values()
                if guild_id and str(room.config["guild_id"]) == str(guild_id)]
