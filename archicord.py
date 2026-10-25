"""ArchiCord 2.0 – Discord-Begleiter für Archipelago-Multiworld.

Abhängigkeiten: discord.py>=2.4,<3, websockets>=12,<17, python-dotenv>=1,<2
Start: python ArchiCord_2_0.py

Lokaler Zustand wird atomar und für jede Kombination aus AP-Server, Seed,
Team und Bot-Slot getrennt in ARCHICORD_DATA_DIR gespeichert.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from tracker.ut_bridge import fetch_slot, write_snapshot
from tracker.apworld_manager import selected_games, selection_fingerprint, load_selection
from pathlib import Path
from typing import Any, Literal

import discord
from discord import app_commands
import websockets
from dotenv import find_dotenv, load_dotenv

# Explizit dieselbe .env verwenden, die in der WebUI bearbeitet wird.
from pathlib import Path
_env_file = os.environ.get('ARCHICORD_ENV_FILE')
if _env_file:
    load_dotenv(_env_file, override=True)
else:
    _local_env = Path(__file__).resolve().parent / '.env'
    _parent_env = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(_local_env if _local_env.exists() else (_parent_env if _parent_env.exists() else find_dotenv()), override=True)

# --------------------------------------------------
# KONFIGURATION – alle bisherigen .env-Werte bleiben gültig
# --------------------------------------------------

def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"[Konfiguration] {name} fehlt oder ist leer.")
    return value


def required_id(name: str) -> int:
    value = required_env(name)
    if not value.isdigit():
        raise SystemExit(f"[Konfiguration] {name} muss eine numerische Discord-ID sein.")
    return int(value)


DISCORD_TOKEN = required_env("DISCORD_TOKEN").strip("\"' ")
if DISCORD_TOKEN.lower().startswith("bot "):
    DISCORD_TOKEN = DISCORD_TOKEN[4:].strip()
AP_URL = os.environ.get("AP_URL", "wss://archipelago.gg:61664").strip() or "wss://archipelago.gg:61664"
if not re.match(r"^wss?://\S+$", AP_URL):
    raise SystemExit(f"[Konfiguration] Ungültige AP_URL: {AP_URL!r}")
AP_SLOT = required_env("AP_SLOT")
AP_PASSWORD = os.environ.get("AP_PASSWORD", "")
AP_GAME = os.environ.get("AP_GAME", "")

ITEM_CHANNEL_ID = required_id("ITEM_CHANNEL_ID")
HINT_CHANNEL_ID = required_id("HINT_CHANNEL_ID")
DEATHLINK_CHANNEL_ID = required_id("DEATHLINK_CHANNEL_ID")


def optional_channel_env(key: str, default: int | None = None) -> int | None:
    value = os.environ.get(key, "").strip()
    return int(value) if value else default


# Vorhandener Status-Kanal bleibt optional, wie in der Originalversion.
STATUS_CHANNEL_ID = optional_channel_env("STATUS_CHANNEL_ID")

# Neue Optionen: Ohne Eintrag werden vorhandene Kanäle verwendet.
HINT_BOARD_CHANNEL_ID = optional_channel_env("HINT_BOARD_CHANNEL_ID", HINT_CHANNEL_ID)
DEATH_BOARD_CHANNEL_ID = optional_channel_env("DEATH_BOARD_CHANNEL_ID", DEATHLINK_CHANNEL_ID)
STATS_CHANNEL_ID = optional_channel_env("STATS_CHANNEL_ID", STATUS_CHANNEL_ID)
GOAL_CHANNEL_ID = optional_channel_env("GOAL_CHANNEL_ID", ITEM_CHANNEL_ID)
FEATURES_CHANNEL_ID = optional_channel_env("FEATURES_CHANNEL_ID", STATUS_CHANNEL_ID or ITEM_CHANNEL_ID)
FEATURES_ANNOUNCE = os.environ.get("ARCHICORD_FEATURES_ANNOUNCE", "true").lower() in ("true", "1", "yes")
DISCORD_GUILD_ID = optional_channel_env("DISCORD_GUILD_ID")

DATA_DIR = Path(os.environ.get("ARCHICORD_DATA_DIR", "archicord_data"))
POLL_INTERVAL = max(60, int(os.environ.get("AP_POLL_INTERVAL", "120")))
RECONNECT_DELAY = 5
STATUS_DEBOUNCE = 2
DEBUG = os.environ.get("ARCHICORD_DEBUG", "true").lower() in ("true", "1", "yes")

# ANSI-Farben werden nur in Desktop-Discord zuverlässig angezeigt.
USE_ANSI_ITEM_NAMES = os.environ.get("USE_ANSI_ITEM_NAMES", "true").lower() in (
    "true", "1", "yes"
)
ANSI_RESET = "\u001b[0m"
ANSI_PURPLE = "\u001b[1;35m"
ANSI_RED = "\u001b[1;31m"

COLOR_TRAP = 0xEF4444
COLOR_PROGRESSION = 0xA855F7
COLOR_HINT_OPEN = 0x3B82F6
COLOR_HINT_FOUND = 0x22C55E
COLOR_DEATHLINK = 0xB91C1C
COLOR_GOAL = 0xF59E0B
COLOR_STATUS_ONLINE = 0x22C55E
COLOR_STATUS_OFFLINE = 0xEF4444
COLOR_STATUS_DISCONNECTED = 0x94A3B8
COLOR_STATS = 0x06B6D4

PROGRESSION_FLAG = 0b001
TRAP_FLAG = 0b100
CLIENT_GOAL = 30
BOT_TAGS = ["DeathLink", "Tracker", "TextOnly"]
HELPER_TAGS = {"tracker", "textonly", "hintgame"}
SCAN_TAG = "__scan__"

# DeathLink-Dateien werden pro Seed in eigenen Ordnern abgelegt.
# Die alte flache Datei wird für Team 0 einmalig als Ausgangsstand gelesen.
LEGACY_DEATH_DIR = Path("deathlinks")
IMPORT_LEGACY_DEATH_COUNTS = True


# --------------------------------------------------
# FORMATIERUNG UND DATEI-SPEICHER
# --------------------------------------------------


def debug(title: str, data: Any) -> None:
    if not DEBUG:
        return
    try:
        print(f"{title}: {json.dumps(data, ensure_ascii=False)[:2000]}")
    except (TypeError, ValueError):
        print(f"{title}: {data}")


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fp:
            value = json.load(fp)
        if isinstance(value, type(default)):
            return value
        print(f"[Datei] Unerwarteter Datentyp: {path}")
    except (OSError, ValueError) as exc:
        print(f"[Datei] Laden fehlgeschlagen ({path}): {exc}")
    return default


def save_json_file(path: Path, data: Any) -> bool:
    """Atomare JSON-Speicherung ohne beschädigte Halbdateien."""
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
        return True
    except (OSError, TypeError, ValueError) as exc:
        print(f"[Datei] Speichern fehlgeschlagen ({path}): {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def seed_state_path(root: Path, seed_name: str, team: int) -> Path:
    """Kombination aus Seed, Server, Team und Bot-Slot verhindert Vermischung."""
    identity = json.dumps(
        [AP_URL, seed_name, team, AP_SLOT, AP_GAME],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", seed_name)[:48] or "seed"
    return root / f"{slug}-{digest}" / "state.json"


def legacy_death_path(seed_name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", seed_name) or "unbekannt"
    return LEGACY_DEATH_DIR / f"deathlink_{slug}.json"


def seed_death_path(seed_name: str, team: int = 0) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", seed_name) or "unbekannt"
    # Teams werden separat gehalten, da die alte Datei keine Team-ID hat.
    folder = slug if team == 0 else f"{slug}_team_{team}"
    return LEGACY_DEATH_DIR / folder / f"deathlink_{slug}.json"


def read_death_counts(path: Path) -> dict[str, int]:
    raw = load_json_file(path, {})
    return {str(k): v for k, v in raw.items()
            if isinstance(v, int) and not isinstance(v, bool) and v >= 0}


def reconcile_death_counts(state: dict, seed_name: str, team: int) -> bool:
    """Seed-Datei und Status synchronisieren, ohne Zähler aufzusummieren."""
    target = seed_death_path(seed_name, team)
    counts = state.setdefault("death_counts", {})
    disk = read_death_counts(target)
    # Eine alte Datei nur bei Team 0 und nur einmalig importieren.
    if team == 0 and not state.get("legacy_deaths_migrated", False):
        old = read_death_counts(legacy_death_path(seed_name))
        for player, count in old.items():
            disk[player] = max(disk.get(player, 0), count)
        state["legacy_deaths_migrated"] = True
    changed = False
    for player, count in disk.items():
        if count > int(counts.get(player, 0)):
            counts[player] = count
            changed = True
    # Max statt Addition: alte und neue Datei können dieselben Events enthalten.
    if not target.exists() or read_death_counts(target) != counts:
        save_json_file(target, counts)
    return changed


def create_seed_state(seed_name: str, team: int) -> dict:
    return {
        "schema": 2,
        "seed_name": seed_name,
        "team": team,
        "items_seen": [],
        "hints": {},
        "goals": {},
        "goal_announced": [],
        "features_announced": False,
        "death_counts": {},
        "death_event_keys": [],
        "stats": {"progression": 0, "traps": 0, "players": {}},
        "own_checks": {"known": False, "checked": [], "missing": []},
        "boards": {},
    }


def get_item_flags(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    try:
        return int(item.get("flags", 0))
    except (TypeError, ValueError):
        return 0


def is_progression_only(flags: int) -> bool:
    return bool(flags & PROGRESSION_FLAG) and not bool(flags & TRAP_FLAG)


def safe_text(value: Any, limit: int = 1024) -> str:
    cleaned = str(value if value is not None else "Unbekannt")
    cleaned = cleaned.replace("\x00", "").replace("\x1b", "").strip() or "Unbekannt"
    cleaned = discord.utils.escape_markdown(cleaned)
    return cleaned[: limit - 1] + "…" if len(cleaned) > limit else cleaned


def plain_text(value: Any, limit: int = 250) -> str:
    cleaned = str(value if value is not None else "Unbekannt")
    cleaned = " ".join(cleaned.replace("\x1b", "").replace("\x00", "").split())
    return cleaned[: limit - 1] + "…" if len(cleaned) > limit else cleaned


def format_item_name(name: Any, ansi_color: str) -> str:
    value = plain_text(name, 300).replace("```", "ˋˋˋ")
    if USE_ANSI_ITEM_NAMES:
        return f"```ansi\n{ansi_color}{value}{ANSI_RESET}\n```"
    return f"**{safe_text(value, 500)}**"


def make_item_embed(
    *, title: str, color: int, item_name: str, item_color: str,
    location_name: str, finder: str, receiver: str,
    finder_label: str = "Von", status: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"**Item**\n{format_item_name(item_name, item_color)}",
        color=color,
    )
    embed.add_field(name="📍 Fundort", value=safe_text(location_name), inline=False)
    embed.add_field(name=f"🌍 {finder_label}", value=safe_text(finder), inline=True)
    embed.add_field(name="🎯 Für", value=safe_text(receiver), inline=True)
    if status:
        embed.add_field(name="📌 Status", value=status, inline=False)
    embed.set_footer(text="ArchiCord • Archipelago")
    return embed


def render_lines(lines: list[str], max_chars: int = 3900, max_lines: int = 20) -> str:
    """Begrenzt Embed-Länge, ohne einzelne Zeilen abzuschneiden."""
    output = []
    length = 0
    for line in lines[:max_lines]:
        if length + len(line) + 1 > max_chars:
            break
        output.append(line)
        length += len(line) + 1
    omitted = len(lines) - len(output)
    if omitted > 0:
        message = f"… und {omitted} weitere. Details über `/archi hints` oder `/archi fortschritt`."
        if length + len(message) < max_chars:
            output.append(message)
    return "\n".join(output) or "Noch keine Daten."


def hint_key(receiver: Any, finder: Any, location: Any, item: Any) -> str:
    return json.dumps([receiver, finder, location, item], separators=(",", ":"))


def item_key(item: dict, receiver: Any) -> str:
    return json.dumps(
        [item.get("item"), item.get("location"), item.get("player"), receiver],
        separators=(",", ":"),
    )


def parse_read_hint(value: Any) -> dict | None:
    """Archipelago Hint kann als Array/NamedTuple oder dict ankommen."""
    if isinstance(value, dict):
        def pick(*keys: str):
            for key in keys:
                if key in value:
                    return value[key]
            return None
        rec = pick("receiving_player", "receiving")
        find = pick("finding_player", "player", "finding")
        location = pick("location")
        item = pick("item")
        found = pick("found")
        flags = pick("item_flags", "flags")
    elif isinstance(value, (list, tuple)) and len(value) >= 7:
        # Hint(receiving_player,finding_player,location,item,found,
        #      entrance,item_flags,status)
        rec, find, location, item, found = value[:5]
        flags = value[6]
    else:
        return None
    if None in (rec, find, location, item):
        return None
    try:
        flags = int(flags or 0)
    except (ValueError, TypeError):
        return None
    if not is_progression_only(flags):
        return None
    try:
        return {
            "receiver_slot": int(rec),
            "finder_slot": int(find),
            "location_id": int(location),
            "item_id": int(item),
            "found": bool(found),
            "flags": flags,
        }
    except (TypeError, ValueError):
        return None


# --------------------------------------------------
# SLASH-BEFEHLE – nur lesender Zugriff, keine Cheats
# --------------------------------------------------

class ArchiCommands(app_commands.Group):
    def __init__(self, bot: "ArchipelagoDiscordBot"):
        super().__init__(name="archi", description="Archipelago-Status und Statistiken")
        self.bot = bot

    async def reply(self, interaction: discord.Interaction, embed: discord.Embed) -> None:
        if not self.bot.commands_allowed(interaction):
            await interaction.response.send_message(
                "ArchiCord-Befehle sind auf dem konfigurierten Discord-Server verfügbar.",
                ephemeral=True,
            )
            return
        if not self.bot.state:
            await interaction.response.send_message(
                "Noch kein Archipelago-Seed verbunden.", ephemeral=True
            )
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Online-Status aller Spieler")
    async def status(self, interaction: discord.Interaction):
        await self.reply(interaction, self.bot.make_status_board())

    @app_commands.command(name="hints", description="Offene oder gefundene Progression-Hints")
    @app_commands.describe(status="Welche Hints anzeigen?", seite="Seite (ab 1)")
    async def hints(
        self,
        interaction: discord.Interaction,
        status: Literal["offen", "gefunden", "alle"] = "offen",
        seite: int = 1,
    ):
        if seite < 1 or seite > 10000:
            await interaction.response.send_message("Seite muss zwischen 1 und 10000 liegen.", ephemeral=True)
            return
        await self.reply(interaction, self.bot.make_hint_page(status, seite))

    @app_commands.command(name="deaths", description="DeathLink-Rangliste dieses Seeds")
    async def deaths(self, interaction: discord.Interaction):
        await self.reply(interaction, self.bot.make_death_board())

    @app_commands.command(name="fortschritt", description="Locations und beobachtete Items")
    @app_commands.describe(spieler="Name oder Slotnummer (optional)")
    async def fortschritt(self, interaction: discord.Interaction, spieler: str | None = None):
        await self.reply(interaction, self.bot.make_progress_embed(spieler))

    @app_commands.command(name="statistik", description="Seed-Statistik und Spielerfortschritt")
    async def statistik(self, interaction: discord.Interaction):
        await self.reply(interaction, self.bot.make_stats_board())

    @app_commands.command(name="funktionen", description="Alle Funktionen von ArchiCord")
    async def funktionen(self, interaction: discord.Interaction):
        await self.reply(interaction, self.bot.make_features_embed())


# --------------------------------------------------
# ARCHICORD BOT
# --------------------------------------------------

class ArchipelagoDiscordBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(ArchiCommands(self))

        self.ap_ws = None
        self.pending_seed_name: str | None = None
        self.seed_name: str | None = None
        self.state_path: Path | None = None
        self.state: dict = {}
        self.seen_item_keys: set[str] = set()

        self.player_names: dict[int, str] = {}
        self.slot_games: dict[int, str] = {}
        self.item_names: dict[str, dict[int, str]] = {}
        self.location_names: dict[str, dict[int, str]] = {}

        self.team = 0
        self.own_slot: int | None = None
        self.ap_connected = False
        self.status_slots: list[int] = []
        self.connections: dict[int, list[list[str]]] = {}
        self.dirty_boards: set[str] = set()
        self.board_event: asyncio.Event | None = None
        self.ut_wakeup: asyncio.Event | None = None

    async def setup_hook(self) -> None:
        self.board_event = asyncio.Event()
        self.ut_wakeup = asyncio.Event()
        # Für sofort sichtbare Kommandos in der gewünschten Guild DISCORD_GUILD_ID setzen.
        try:
            if DISCORD_GUILD_ID:
                guild = discord.Object(id=DISCORD_GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            print(f"Discord-Slash-Befehle synchronisiert: {len(synced)}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[Discord] Slash-Synchronisation fehlgeschlagen: {exc}")

        asyncio.create_task(self.archipelago_loop())
        asyncio.create_task(self.board_loop())
        asyncio.create_task(self.data_poll_loop())
        asyncio.create_task(self.universal_tracker_loop())

    async def on_ready(self) -> None:
        print(f"ArchiCord 2.0 eingeloggt als {self.user}")
        print(f"Item-Kanal: {ITEM_CHANNEL_ID} | Hint-Kanal: {HINT_CHANNEL_ID}")
        print(f"DeathLink-Kanal: {DEATHLINK_CHANNEL_ID} | Status: {STATUS_CHANNEL_ID}")

    def commands_allowed(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild_id:
            return False
        if DISCORD_GUILD_ID:
            return interaction.guild_id == DISCORD_GUILD_ID
        # Ohne Guild-ID keine Daten in fremde Server exportieren.
        for channel_id in (
            ITEM_CHANNEL_ID, HINT_CHANNEL_ID, DEATHLINK_CHANNEL_ID, STATUS_CHANNEL_ID
        ):
            if channel_id:
                channel = self.get_channel(channel_id)
                if channel and getattr(getattr(channel, "guild", None), "id", None) == interaction.guild_id:
                    return True
        return False

    @staticmethod
    def make_features_embed() -> discord.Embed:
        """Öffentliche Feature-Übersicht. Keine privaten Serverdaten enthalten."""
        embed = discord.Embed(
            title="🎮 ArchiCord – Das kann dein Multiworld-Begleiter",
            description="**Deine Archipelago-Runde im Blick – live in Discord.**",
            color=0x818CF8,
        )
        embed.add_field(
            name="🎯 Live-Fortschritt & Doable Checks",
            value="Spieler, erreichte Ziele und logisch machbare, noch offene Locations. "
                  "Für Doable Checks wird ein kompatibler Universal Tracker benötigt.",
            inline=False,
        )
        embed.add_field(
            name="🎁 Items, 🪤 Traps & 🔎 Hints",
            value="Farbige Item- und Trap-Meldungen, Hint-Benachrichtigungen "
                  "sowie ein aktualisiertes Hintboard.",
            inline=False,
        )
        embed.add_field(
            name="☠️ DeathLinks & 🏆 Ziele",
            value="Live-Todesrangliste, freche Meldungen bei 25/50/75… Toden "
                  "pro Spieler und Zielankündigungen.",
            inline=False,
        )
        embed.add_field(
            name="🧩 Universal Tracker & 🌐 WebUI",
            value="Auswahl der APWorlds, automatisierte Tracker-Abfragen sowie "
                  "lokale Bot-Steuerung mit Status, Logs und .env-Konfiguration.",
            inline=False,
        )
        embed.set_footer(text="Mehr über /archi status · hints · deaths · fortschritt · statistik · funktionen")
        return embed

    async def announce_features_if_needed(self) -> None:
        """Feature-Post höchstens einmal je Seed/Team/Server-Zustand senden."""
        if not FEATURES_ANNOUNCE or not FEATURES_CHANNEL_ID or not self.state:
            return
        current_state = self.state
        if current_state.get("features_announced", False):
            return
        if await self.send_to_channel(FEATURES_CHANNEL_ID, self.make_features_embed()):
            if self.state is current_state:
                current_state["features_announced"] = True
                self.persist()

    # --------------------------------------------------
    # PERSISTENZ / SEED-WECHSEL
    # --------------------------------------------------

    def activate_seed(self, name: str, team: int) -> None:
        path = seed_state_path(DATA_DIR, name, team)
        if path == self.state_path and self.state:
            # Gleiches Spiel nach Reconnect: vorhandenen Zustand behalten.
            self.request_board_update()
            return

        state = load_json_file(path, {})
        if not state or state.get("seed_name") != name or state.get("team") != team:
            state = create_seed_state(name, team)


        # Fehlende Felder aus älteren 2.x-Zuständen auffüllen.
        defaults = create_seed_state(name, team)
        for key, value in defaults.items():
            state.setdefault(key, value)
        self.seed_name = name
        self.state_path = path
        self.state = state
        reconcile_death_counts(self.state, name, team)
        self.seen_item_keys = set(state.get("items_seen", []))
        self.persist()
        print(f"[Seed] {name} / Team {team} -> {path}")
        self.request_board_update()

    def persist(self) -> bool:
        if not self.state_path:
            return False
        saved = save_json_file(self.state_path, self.state)
        if self.seed_name and "death_counts" in self.state:
            saved = save_json_file(seed_death_path(self.seed_name, self.team),
                                   self.state["death_counts"]) and saved
        return saved

    def request_board_update(self, *board_names: str) -> None:
        self.dirty_boards.update(board_names or ("status", "hints", "deaths", "stats"))
        if self.board_event:
            self.board_event.set()

    def request_ut_update(self) -> None:
        """Wecke Universal Tracker, sobald AP-Logikdaten bereitstehen."""
        if self.ut_wakeup is not None:
            self.ut_wakeup.set()

    # --------------------------------------------------
    # DISCORD-NACHRICHTEN
    # --------------------------------------------------

    def get_channel_or_none(self, channel_id: int | None):
        if not channel_id:
            return None
        return self.get_channel(channel_id) or self.get_partial_messageable(channel_id)

    async def send_to_channel(self, channel_id: int | None, text: str | discord.Embed) -> bool:
        channel = self.get_channel_or_none(channel_id)
        if channel is None:
            print(f"[Discord] Kanal {channel_id} nicht gefunden")
            return False
        try:
            if isinstance(text, discord.Embed):
                await channel.send(embed=text, allowed_mentions=discord.AllowedMentions.none())
            else:
                await channel.send(content=text, allowed_mentions=discord.AllowedMentions.none())
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[Discord] Nachricht fehlgeschlagen ({channel_id}): {exc}")
            return False

    async def send_item_message(self, text):
        return await self.send_to_channel(ITEM_CHANNEL_ID, text)

    async def send_hint_message(self, text):
        return await self.send_to_channel(HINT_CHANNEL_ID, text)

    async def send_deathlink_message(self, text):
        return await self.send_to_channel(DEATHLINK_CHANNEL_ID, text)

    async def upsert_board(self, key: str, channel_id: int | None, embed: discord.Embed) -> bool:
        if not self.state or not channel_id:
            return False
        channel = self.get_channel_or_none(channel_id)
        if channel is None:
            return False
        # Der AP-Seed kann während eines Discord-API-await wechseln.
        # Die Board-ID darf niemals im Zustand des neuen Seeds landen.
        board_state = self.state
        board_path = self.state_path
        current = board_state["boards"].get(key, {})
        message_id = current.get("message_id") if current.get("channel_id") == channel_id else None
        try:
            if message_id:
                try:
                    await channel.get_partial_message(int(message_id)).edit(
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    return True
                except discord.NotFound:
                    pass  # Gelöschte Nachricht neu erstellen.
            msg = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            board_state["boards"][key] = {"channel_id": channel_id, "message_id": msg.id}
            if board_path is not None:
                save_json_file(board_path, board_state)
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[Discord] Board {key} konnte nicht aktualisiert werden: {exc}")
            return False

    # --------------------------------------------------
    # NAMEN AUFLÖSEN
    # --------------------------------------------------

    def resolve_player_name(self, slot: Any) -> str:
        if slot is None:
            return "Unbekannt"
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            return str(slot)
        return self.player_names.get(slot, f"Spieler {slot}")

    def resolve_game(self, slot: Any) -> str | None:
        try:
            return self.slot_games.get(int(slot))
        except (TypeError, ValueError):
            return None

    def resolve_item_name(self, game: str | None, item_id: Any) -> str:
        if item_id is None:
            return "Unbekanntes Item"
        try:
            ident = int(item_id)
        except (TypeError, ValueError):
            return str(item_id)
        if game and ident in self.item_names.get(game, {}):
            return self.item_names[game][ident]
        for mapping in self.item_names.values():
            if ident in mapping:
                return mapping[ident]
        return f"Item {ident}"

    def resolve_location_name(self, game: str | None, location_id: Any) -> str:
        if location_id is None:
            return "Unbekannte Location"
        try:
            ident = int(location_id)
        except (TypeError, ValueError):
            return str(location_id)
        if game and ident in self.location_names.get(game, {}):
            return self.location_names[game][ident]
        for mapping in self.location_names.values():
            if ident in mapping:
                return mapping[ident]
        return f"Location {ident}"

    # --------------------------------------------------
    # ITEMS: PROGRESSION + TRAPS
    # --------------------------------------------------

    def register_item_stats(self, item: dict, receiver_slot: int, is_trap: bool) -> None:
        """Nur nach erfolgreichem Discord-Versand, damit Stats reproduzierbar sind."""
        stats = self.state["stats"]
        category = "traps" if is_trap else "progression"
        stats[category] = int(stats.get(category, 0)) + 1
        players = stats.setdefault("players", {})
        finder = str(item.get("player"))
        receiver = str(receiver_slot)
        for slot in (finder, receiver):
            players.setdefault(slot, {"sent": 0, "received": 0, "traps_received": 0})
        if not is_trap:
            players[finder]["sent"] += 1
            players[receiver]["received"] += 1
        else:
            players[receiver]["traps_received"] += 1

    async def handle_item(self, packet: dict) -> None:
        if not self.state:
            return
        item = packet.get("item")
        receiver_slot = packet.get("receiving")
        if not isinstance(item, dict) or receiver_slot is None:
            return
        flags = get_item_flags(item)
        is_trap = bool(flags & TRAP_FLAG)
        if not is_trap and not bool(flags & PROGRESSION_FLAG):
            return
        key = item_key(item, receiver_slot)
        if key in self.seen_item_keys:
            return

        finder_slot = item.get("player")
        name = self.resolve_item_name(self.resolve_game(receiver_slot), item.get("item"))
        location = self.resolve_location_name(self.resolve_game(finder_slot), item.get("location"))
        embed = make_item_embed(
            title="🪤 Trap-Item" if is_trap else "✨ Progression-Item ✨",
            color=COLOR_TRAP if is_trap else COLOR_PROGRESSION,
            item_name=name,
            item_color=ANSI_RED if is_trap else ANSI_PURPLE,
            location_name=location,
            finder=self.resolve_player_name(finder_slot),
            receiver=self.resolve_player_name(receiver_slot),
        )
        if await self.send_item_message(embed):
            self.state["items_seen"].append(key)
            self.seen_item_keys.add(key)
            self.register_item_stats(item, receiver_slot, is_trap)
            self.persist()
            self.request_board_update("stats")

    # --------------------------------------------------
    # HINTS + LIVE-BOARD
    # --------------------------------------------------

    def hint_details(self, hint: dict) -> tuple[str, str, str, str]:
        receiving = hint["receiver_slot"]
        finding = hint["finder_slot"]
        return (
            self.resolve_item_name(self.resolve_game(receiving), hint["item_id"]),
            self.resolve_location_name(self.resolve_game(finding), hint["location_id"]),
            self.resolve_player_name(finding),
            self.resolve_player_name(receiving),
        )

    def merge_hint(self, hint: dict) -> tuple[bool, bool]:
        """(neu, von offen zu gefunden); gefunden wird niemals wieder offen."""
        key = hint_key(hint["receiver_slot"], hint["finder_slot"],
                       hint["location_id"], hint["item_id"])
        old = self.state["hints"].get(key)
        newly_found = bool(hint["found"] and old is not None and not old.get("found"))
        if old is None:
            self.state["hints"][key] = hint
            return True, False
        if hint["found"] and not old.get("found"):
            old["found"] = True
            return False, newly_found
        return False, False

    async def handle_hint(self, packet: dict) -> None:
        if not self.state:
            return
        debug("ARCHIPELAGO HINT", packet)
        item = packet.get("item")
        if not isinstance(item, dict) or not is_progression_only(get_item_flags(item)):
            return
        try:
            hint = {
                "receiver_slot": int(packet["receiving"]),
                "finder_slot": int(item["player"]),
                "location_id": int(item["location"]),
                "item_id": int(item["item"]),
                "found": bool(item.get("found", packet.get("found", False))),
                "flags": get_item_flags(item),
            }
        except (KeyError, ValueError, TypeError):
            return
        key = hint_key(hint["receiver_slot"], hint["finder_slot"],
                       hint["location_id"], hint["item_id"])
        old = self.state["hints"].get(key)
        if old is not None and (old.get("found") or not hint["found"]):
            return
        item_name, location, finder, receiver = self.hint_details(hint)
        first = old is None
        embed = make_item_embed(
            title="🔎 Progression-Hint" if first else "🎉 Progression-Item gefunden!",
            color=COLOR_HINT_FOUND if hint["found"] else COLOR_HINT_OPEN,
            item_name=item_name,
            item_color=ANSI_PURPLE,
            location_name=location,
            finder=finder,
            receiver=receiver,
            finder_label="Welt",
            status=("✅ Bereits gefunden" if hint["found"] else "❓ Noch nicht gefunden")
                if first else "✅ Jetzt gefunden",
        )
        if await self.send_hint_message(embed):
            self.merge_hint(hint)
            self.persist()
            self.request_board_update("hints", "stats")

    def apply_retrieved_hints(self, keys: dict) -> bool:
        changed = False
        prefix = f"_read_hints_{self.team}_"
        for key, items in keys.items():
            if not key.startswith(prefix) or not isinstance(items, list):
                continue
            for value in items:
                hint = parse_read_hint(value)
                if hint is not None:
                    is_new, is_found = self.merge_hint(hint)
                    changed |= is_new or is_found
        if changed:
            self.persist()
            self.request_board_update("hints", "stats")
        return changed

    def hint_totals(self) -> tuple[int, int]:
        hints = list(self.state.get("hints", {}).values())
        return sum(not item.get("found") for item in hints), sum(bool(item.get("found")) for item in hints)

    def make_hint_page(self, status: str = "alle", page: int = 1) -> discord.Embed:
        selected = list(self.state.get("hints", {}).values())
        if status == "offen":
            selected = [h for h in selected if not h.get("found")]
        elif status == "gefunden":
            selected = [h for h in selected if h.get("found")]
        selected.sort(key=lambda h: (
            self.resolve_player_name(h["receiver_slot"]).lower(),
            self.resolve_item_name(self.resolve_game(h["receiver_slot"]), h["item_id"]).lower()
        ))
        per_page = 12
        pages = max(1, (len(selected) + per_page - 1) // per_page)
        page = min(max(1, page), pages)
        current = selected[(page - 1) * per_page:page * per_page]
        lines = []
        for hint in current:
            name, location, finder, receiver = self.hint_details(hint)
            icon = "✅" if hint.get("found") else "❔"
            lines.append(
                f"{icon} **{safe_text(name, 110)}** — {safe_text(location, 130)}\n"
                f"　Welt: {safe_text(finder, 75)} · Für: {safe_text(receiver, 75)}"
            )
        open_count, found_count = self.hint_totals()
        embed = discord.Embed(
            title="🔎 Archipelago – Hintboard",
            description=render_lines(lines, max_chars=3900, max_lines=12)
            if lines else "Keine passenden Progression-Hints vorhanden.",
            color=COLOR_HINT_OPEN if open_count else COLOR_HINT_FOUND,
        )
        embed.add_field(name="❔ Offen", value=str(open_count), inline=True)
        embed.add_field(name="✅ Gefunden", value=str(found_count), inline=True)
        embed.set_footer(text=f"{safe_text(self.seed_name, 60)} • {status} • Seite {page}/{pages} • /archi hints")
        return embed

    def make_live_hint_board(self) -> discord.Embed:
        open_hints = [h for h in self.state["hints"].values() if not h.get("found")]
        found_hints = [h for h in self.state["hints"].values() if h.get("found")]
        lines = []
        for hint in open_hints[:16]:
            name, location, finder, receiver = self.hint_details(hint)
            lines.append(f"❔ **{safe_text(name, 85)}** — {safe_text(location, 105)} · Für {safe_text(receiver, 60)}")
        for hint in found_hints[-4:]:
            name, _location, _finder, receiver = self.hint_details(hint)
            lines.append(f"✅ ~~{safe_text(name, 90)}~~ · Für {safe_text(receiver, 60)}")
        open_count, found_count = self.hint_totals()
        embed = discord.Embed(
            title="🔎 Live-Hintboard",
            description=render_lines(lines, max_chars=3900, max_lines=20)
            if lines else "Noch keine Progression-Hints für diesen Seed.",
            color=COLOR_HINT_OPEN if open_count else COLOR_HINT_FOUND,
        )
        embed.add_field(name="❔ Offen", value=str(open_count), inline=True)
        embed.add_field(name="✅ Gefunden", value=str(found_count), inline=True)
        embed.set_footer(text=f"Seed: {plain_text(self.seed_name, 70)} • weitere Einträge: /archi hints")
        return embed

    # --------------------------------------------------
    # GOAL – AUS SPIEL-EVENT UND STATUSABFRAGE
    # --------------------------------------------------

    async def handle_goal(self, packet: dict) -> None:
        if not self.state or packet.get("team") != self.team:
            return
        try:
            slot = int(packet["slot"])
        except (KeyError, ValueError, TypeError):
            return
        key = str(slot)
        self.state["goals"][key] = True
        if key in self.state["goal_announced"]:
            self.persist()
            self.request_board_update("stats")
            return
        name = self.resolve_player_name(slot)
        game = self.resolve_game(slot) or "Unbekanntes Spiel"
        embed = discord.Embed(
            title="🏆 Spielziel erreicht!",
            description=f"**{safe_text(name)}** hat das Ziel in **{safe_text(game)}** erreicht.",
            color=COLOR_GOAL,
        )
        embed.set_footer(text=f"Seed: {plain_text(self.seed_name, 90)} • ArchiCord")
        if await self.send_to_channel(GOAL_CHANNEL_ID, embed):
            self.state["goal_announced"].append(key)
        self.persist()
        self.request_board_update("stats")

    def apply_client_status(self, keys: dict) -> None:
        """Fallback-Status ohne künstliche Dauer-Online-Verbindungen.

        Ein echter Join hat Vorrang vor dem Status-Snapshot. Der synthetische
        Scan-Eintrag wird entfernt, sobald der Server nicht mehr 10/20 meldet.
        """
        changed = False
        for key, value in keys.items():
            match = re.fullmatch(r"_read_client_status_(\d+)_(\d+)", key)
            if not match or not isinstance(value, int):
                continue
            team, slot = int(match.group(1)), int(match.group(2))
            if team != self.team or slot not in self.status_slots:
                continue
            connections = self.connections.setdefault(slot, [])
            has_scan = any(tags == [SCAN_TAG] for tags in connections)
            has_real = any(
                tags != [SCAN_TAG] and not self.is_helper(tags)
                for tags in connections
            )
            if value in (10, 20):
                if not has_real and not has_scan:
                    connections.append([SCAN_TAG])
                    changed = True
            elif has_scan:
                self.connections[slot] = [tags for tags in connections if tags != [SCAN_TAG]]
                changed = True
            if value == CLIENT_GOAL and not self.state["goals"].get(str(slot)):
                self.state["goals"][str(slot)] = True
                # Historische Goals niemals als neue Ankündigung posten.
                changed = True
        if changed:
            self.persist()
            self.request_board_update("status", "stats")

    # --------------------------------------------------
    # DEATHLINK + LIVE-RANGLISTE
    # --------------------------------------------------

    def make_death_board(self) -> discord.Embed:
        counts = self.state.get("death_counts", {})
        ranking = sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0].lower()))
        lines = [
            f"**{index}.** {safe_text(name, 120)} — **{count}×**"
            for index, (name, count) in enumerate(ranking[:20], start=1)
        ]
        embed = discord.Embed(
            title="☠️ Live-DeathLink-Rangliste",
            description=render_lines(lines, max_chars=3800, max_lines=20)
            if lines else "Noch keine DeathLinks in diesem Seed.",
            color=COLOR_DEATHLINK,
        )
        embed.add_field(name="Gesamte DeathLinks", value=str(sum(counts.values())), inline=False)
        embed.set_footer(text=f"Seed: {plain_text(self.seed_name, 70)} • ArchiCord")
        return embed

    @staticmethod
    def death_milestone_text(name: str, count: int) -> str:
        taunts = [
            "Der Respawn-Button hat inzwischen eine eigene Gewerkschaft gegründet.",
            "Sogar die Gegner fragen langsam, ob alles okay ist.",
            "Der Friedhof verlangt jetzt eine Dauerkarte.",
            "Der Sensenmann hat deine Nummer als Favorit gespeichert.",
            "Das ist kein Speedrun mehr, das ist ein Sterbe-Abo.",
            "Dein Charakter kennt den Ladebildschirm besser als die Spielwelt.",
            "Die Todesstatistik hat mehr Fortschritt als dein Inventar.",
            "Du bist offiziell der Endgegner deiner eigenen Überlebenschancen.",
        ]
        # Stabile Auswahl je Spieler und Schwelle: keine Zufallsänderung nach Neustart.
        choice = int(hashlib.sha256(f"{name}:{count}".encode()).hexdigest(), 16) % len(taunts)
        return taunts[choice]

    async def announce_death_milestone(self, source: str, count: int) -> None:
        embed = discord.Embed(
            title=f"💀 {count} TODE! EIN NEUER TIEFPUNKT!",
            description=(f"**{safe_text(source, 160)}** ist jetzt **{count}×** gestorben!\n\n"
                         f"{self.death_milestone_text(source, count)}"),
            color=COLOR_DEATHLINK,
        )
        embed.set_footer(text="ArchiCord • Jeder 25. Tod wird gebührend geröstet")
        await self.send_deathlink_message(embed)

    async def handle_deathlink(self, packet: dict) -> None:
        if not self.state:
            return
        data = packet.get("data", {})
        if not isinstance(data, dict):
            return
        source = plain_text(data.get("source", "Unbekannt"), 180)
        cause = data.get("cause", "")
        # Bounce enthält meist eine Zeit. Falls nicht, KEINE deduplizierende
        # Signatur erfinden: Zwei identische DeathLinks können legitim sein.
        when = data.get("time")
        event_key = None if when is None else json.dumps([when, source, cause], ensure_ascii=False)
        if event_key is not None and event_key in self.state["death_event_keys"]:
            return

        previous_deaths = int(self.state["death_counts"].get(source, 0))
        self.state["death_counts"][source] = previous_deaths + 1
        if event_key is not None:
            self.state["death_event_keys"].append(event_key)
            self.state["death_event_keys"] = self.state["death_event_keys"][-500:]
        self.persist()
        self.request_board_update("deaths", "stats")

        # Einzelmeldungen sind deaktiviert: Das persistente Live-Board wird
        # oben über request_board_update("deaths") aktualisiert.
        # Nur bei jedem 25. Tod wird eine separate Nachricht verschickt.
        current_deaths = self.state["death_counts"][source]
        if current_deaths % 25 == 0:
            await self.announce_death_milestone(source, current_deaths)

    # --------------------------------------------------
    # SPIELERSTATUS, FORTSCHRITT UND STATISTIK
    # --------------------------------------------------

    @staticmethod
    def is_helper(tags: list[str] | None) -> bool:
        return bool({str(tag).lower() for tag in (tags or [])} & HELPER_TAGS)

    def slot_online(self, slot: int) -> bool:
        return any(not self.is_helper(tags) for tags in self.connections.get(slot, []))

    def handle_join(self, packet: dict) -> None:
        slot = packet.get("slot")
        if slot is None or packet.get("team", 0) != self.team:
            return
        slot = int(slot)
        tags = packet.get("tags") or []
        if slot == self.own_slot and set(BOT_TAGS) <= set(tags):
            return
        connections = self.connections.setdefault(slot, [])
        if not self.is_helper(tags):
            connections[:] = [existing for existing in connections if existing != [SCAN_TAG]]
        connections.append(list(tags))
        self.request_board_update("status")

    def handle_part(self, packet: dict) -> None:
        slot = packet.get("slot")
        if slot is None or packet.get("team", 0) != self.team:
            return
        connections = self.connections.get(int(slot), [])
        if not connections:
            return
        # Part enthält keine Tags. Synthetische Scans nicht als echten
        # Verbindungsabbruch behandeln; der nächste Poll korrigiert sie.
        for i, tags in enumerate(connections):
            if self.is_helper(tags):
                connections.pop(i)
                break
        else:
            for i, tags in enumerate(connections):
                if tags != [SCAN_TAG]:
                    connections.pop(i)
                    break
        self.request_board_update("status")

    async def init_status(self, packet: dict) -> None:
        self.ap_connected = True
        self.team = int(packet.get("team", 0))
        self.own_slot = int(packet["slot"])
        slot_info = packet.get("slot_info", {})
        self.status_slots = sorted({
            int(player["slot"]) for player in packet.get("players", [])
            if int(player.get("team", 0)) == self.team
            and (slot_info.get(str(player["slot"]), {}) or {}).get("type", 1) == 1
        })
        self.connections = {}

        checks = packet.get("checked_locations", [])
        missing = packet.get("missing_locations", [])
        if isinstance(checks, list) and isinstance(missing, list):
            self.state["own_checks"] = {
                "known": True,
                "checked": sorted({int(n) for n in checks}),
                "missing": sorted({int(n) for n in missing}),
            }
            self.persist()

        keys = [
            f"_read_client_status_{self.team}_{slot}" for slot in self.status_slots
        ] + [
            f"_read_hints_{self.team}_{slot}" for slot in self.status_slots
        ]
        if keys:
            await self.send_json([{"cmd": "Get", "keys": keys}])
        self.request_board_update()

    def update_own_checks(self, packet: dict) -> None:
        checks = packet.get("checked_locations")
        if not isinstance(checks, list) or not self.state:
            return
        own = self.state["own_checks"]
        if not own.get("known"):
            return
        old_checks = set(own["checked"])
        new_checks = old_checks | {int(n) for n in checks}
        if new_checks != old_checks:
            own["checked"] = sorted(new_checks)
            own["missing"] = sorted(set(own["missing"]) - new_checks)
            self.persist()
            self.request_board_update("stats")

    def own_progress(self) -> tuple[int, int] | None:
        checks = self.state.get("own_checks", {})
        if not checks.get("known"):
            return None
        checked = len(checks.get("checked", []))
        total = checked + len(checks.get("missing", []))
        return checked, total

    def player_item_stats(self, slot: int) -> dict:
        return self.state["stats"]["players"].get(str(slot), {})

    def find_player(self, player: str) -> tuple[int | None, str | None]:
        if player.isdigit():
            slot = int(player)
            return (slot, None) if slot in self.status_slots else (None, "Slot nicht gefunden.")
        matches = [slot for slot in self.status_slots if self.resolve_player_name(slot).casefold() == player.casefold()]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "Der Spielername ist nicht eindeutig. Bitte Slotnummer verwenden."
        return None, "Spieler nicht gefunden."

    def make_progress_embed(self, player: str | None) -> discord.Embed:
        if not player:
            return self.make_stats_board()
        slot, error = self.find_player(player.strip())
        if error:
            return discord.Embed(title="📈 Spielerfortschritt", description=error, color=COLOR_STATS)
        return self.make_single_player_progress(slot)

    def make_single_player_progress(self, slot: int) -> discord.Embed:
        name = self.resolve_player_name(slot)
        game = self.resolve_game(slot) or "Unbekannt"
        stats = self.player_item_stats(slot)
        embed = discord.Embed(
            title=f"📈 Fortschritt: {plain_text(name, 150)}",
            description=f"Spiel: **{safe_text(game)}**",
            color=COLOR_GOAL if self.state["goals"].get(str(slot)) else COLOR_STATS,
        )
        doable = self.slot_doable(slot)
        if doable is None:
            info = ("Nicht zum Tracking ausgewählt (APWorld-Verwaltung in der WebUI)."
                    if not self.slot_selected_for_tracking(slot)
                    else "Keine Logikdaten verfügbar. Der Tracker muss die erreichbaren, noch unerledigten Locations liefern.")
            embed.add_field(name="🎯 Aktuell machbare Checks", value=info, inline=False)
        else:
            embed.add_field(name="🎯 Aktuell machbare Checks", value=str(len(doable)), inline=False)
            game_locations = self.location_names.get(game, {})
            names = [safe_text(game_locations.get(loc, f"Location {loc}"), 130) for loc in doable]
            embed.add_field(name="📍 Jetzt erreichbar", value=render_lines(names, max_chars=1000, max_lines=12) if names else "Keine derzeit machbaren offenen Checks.", inline=False)
        embed.add_field(name="Empfangene Progression-Items*", value=str(stats.get("received", 0)), inline=True)
        embed.add_field(name="Gesendete Progression-Items*", value=str(stats.get("sent", 0)), inline=True)
        embed.add_field(name="Empfangene Traps*", value=str(stats.get("traps_received", 0)), inline=True)
        embed.add_field(name="Spielziel", value="🏆 Erreicht" if self.state["goals"].get(str(slot)) else "Noch nicht gemeldet", inline=False)
        embed.set_footer(text="* Nur vom Bot beobachtete und gespeicherte ItemSend-Ereignisse")
        return embed

    def make_stats_board(self) -> discord.Embed:
        open_hints, found_hints = self.hint_totals()
        complete = sum(bool(flag) for flag in self.state.get("goals", {}).values())
        deaths = sum(self.state.get("death_counts", {}).values())
        lines = []
        for slot in self.status_slots:
            name = safe_text(self.resolve_player_name(slot), 75)
            goal = "🏆" if self.state["goals"].get(str(slot)) else "·"
            doable = self.slot_doable(slot)
            check_label = ((" · 🎯 Nicht ausgewählt" if not self.slot_selected_for_tracking(slot)
                            else " · 🎯 Doable: keine Logikdaten") if doable is None
                           else f" · 🎯 {len(doable)} aktuell machbar")
            lines.append(f"{goal} **{name}**{check_label}")
        embed = discord.Embed(
            title="📈 Archipelago – Live-Fortschritt",
            description=render_lines(lines, max_chars=3850, max_lines=20),
            color=COLOR_STATS if self.ap_connected else COLOR_STATUS_DISCONNECTED,
        )
        embed.add_field(name="🏆 Ziele erreicht", value=f"{complete}/{len(self.status_slots)}", inline=True)
        embed.add_field(name="🔎 Hints offen / gefunden", value=f"{open_hints} / {found_hints}", inline=True)
        embed.add_field(name="☠️ DeathLinks", value=str(deaths), inline=True)
        embed.set_footer(text=f"Seed: {plain_text(self.seed_name, 55)} • Doable Checks benötigen Logikdaten für jeden Spieler")
        return embed

    async def universal_tracker_loop(self) -> None:
        """Run UT as soon as the AP DataPackage arrives, then periodically.

        Waiting for a connection must not consume the initial polling interval.
        """
        await self.wait_until_ready()
        interval = max(30, int(os.environ.get("ARCHICORD_UT_INTERVAL", "120")))
        launcher = os.environ.get("ARCHICORD_UT_LAUNCHER", "").strip()
        if not launcher:
            print("[UT] Nicht aktiviert: ARCHICORD_UT_LAUNCHER in .env setzen.")
            return
        output = Path(os.environ.get("ARCHICORD_CHECKS_FILE", "tracker/exports/live_checks.json"))
        print(f"[UT] Automatische Live-Abfrage aktiviert (alle {interval}s). Launcher: {launcher}")
        print("[UT] Warte auf AP-Verbindung und Spiele-Datenpaket für die erste Abfrage …")
        event = self.ut_wakeup
        if event is None:
            return
        while not self.is_closed():
            # Triggered from DataPackage (or again after reconnect). Do not
            # sleep 120s before the first run merely because AP was not yet ready.
            if not (self.ap_connected and self.seed_name and self.status_slots
                    and self.location_names):
                await event.wait()
                event.clear()
                continue
            seed, team = self.seed_name, self.team
            players = {}
            failures = {}
            try:
                allowed = selected_games(Path(__file__).resolve().parent)
                selection_rev = selection_fingerprint(Path(__file__).resolve().parent)
            except ValueError as exc:
                # Broken config must not accidentally enable every game.
                allowed, selection_rev = set(), 'invalid-selection'
                print(f"[UT] APWorld-Auswahl ungültig: {exc}")
            if allowed is None:
                print('[UT] Noch keine APWorld-Auswahl gespeichert: bisheriges Verhalten (alle Spieler).')
            else:
                print(f'[UT] APWorld-Auswahl: {len(allowed)} Spiel(e): {", ".join(sorted(allowed)) or "keine"}')
            print(f"[UT] Starte Abfrage: Seed {seed}, Team {team}, "
                  f"{len(self.status_slots)} Spieler")
            for slot in list(self.status_slots):
                if not self.ap_connected or self.seed_name != seed or self.team != team:
                    break
                name, game = self.resolve_player_name(slot), self.resolve_game(slot)
                if allowed is not None and (game or '').strip().casefold() not in allowed:
                    print(f"[UT] {name} ({game}): übersprungen – Spiel in der APWorld-Verwaltung nicht ausgewählt.")
                    continue
                known = self.location_names.get(game, {})
                if not known:
                    error = f"Keine AP-Location-Namen für Spiel {game} (DataPackage fehlt?)"
                    failures[str(slot)] = error
                    print(f"[UT] {name}: {error}")
                    continue
                print(f"[UT] {name} ({game}): frage erreichbare Locations ab …")
                try:
                    ids = await fetch_slot(Path(launcher), AP_URL, name, AP_PASSWORD, known)
                    checked = (self.state.get("own_checks", {}).get("checked", [])
                               if slot == self.own_slot else [])
                    players[str(slot)] = {"doable": ids, "checked": checked}
                    print(f"[UT] {name}: {len(ids)} erreichbare Locations erkannt.")
                except Exception as exc:
                    error = str(exc)
                    # Never leak the password/slot URI into web logs.
                    error = re.sub(r'archipelago://\S+', '[Adresse entfernt]', error)
                    failures[str(slot)] = error[:300]
                    print(f"[UT] {name}: FEHLER: {error}")
            if self.ap_connected and self.seed_name == seed and self.team == team:
                write_snapshot(output, seed, team, players, failures,
                               selection_revision=selection_rev)
                print(f"[UT] Fertig: {len(players)} von {len(self.status_slots)} "
                      f"Spielern erfolgreich; Export: {output}")
                self.request_board_update("stats")
            # Fast initial run, then scheduled polling. A new seed / DataPackage
            # can also trigger an immediate refresh.
            try:
                await asyncio.wait_for(event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            event.clear()

    def external_checks(self) -> dict:
        """Optionaler, seedgebundener Export eines Trackers mit allen Slots.

        Format: {"seed_name": "...", "team": 0,
                 "players": {"1": {"checked": [1], "missing": [2, 3]}}}
        """
        path = os.environ.get("ARCHICORD_CHECKS_FILE", "tracker/exports/live_checks.json").strip()
        if not path or not self.seed_name:
            return {}
        data = load_json_file(Path(path), {})
        if data.get("seed_name") != self.seed_name or data.get("team") != self.team:
            return {}
        try:
            revision = selection_fingerprint(Path(__file__).resolve().parent)
        except ValueError:
            return {}
        # Results from the previous selection must not be shown after changing
        # which games are tracked (including immediately after WebUI save).
        if data.get('selection_revision', 'legacy-all') != revision:
            return {}
        return data.get("players", {}) if isinstance(data.get("players"), dict) else {}

    def slot_selected_for_tracking(self, slot: int) -> bool:
        try:
            config = load_selection(Path(__file__).resolve().parent)
        except ValueError:
            return False
        if config is None:
            return True
        game = (self.resolve_game(slot) or '').strip().casefold()
        return any(row['game'].strip().casefold() == game for row in config['worlds'])

    def slot_doable(self, slot: int) -> list[int] | None:
        """Nur durch einen externen AP-Logiktracker bestätigte, offene Checks.

        Missing-Location-IDs allein sind ausdrücklich NICHT ausreichend.
        Trackerformat: players[slot].doable = [location_id, ...].
        """
        snapshot = self.external_checks().get(str(slot))
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("doable"), list):
            return None
        try:
            doable = {int(loc) for loc in snapshot["doable"]}
            checked = {int(loc) for loc in snapshot.get("checked", [])}
            if slot == self.own_slot and self.state.get("own_checks", {}).get("known"):
                checked |= {int(loc) for loc in self.state["own_checks"]["checked"]}
            return sorted(doable - checked)
        except (ValueError, TypeError):
            return None

    def slot_checks(self, slot: int) -> dict | None:
        if slot == self.own_slot and self.state.get("own_checks", {}).get("known"):
            return self.state["own_checks"]
        snapshot = self.external_checks().get(str(slot))
        if not isinstance(snapshot, dict):
            return None
        checked, missing = snapshot.get("checked"), snapshot.get("missing")
        if not isinstance(checked, list) or not isinstance(missing, list):
            return None
        try:
            return {"checked": sorted({int(n) for n in checked}),
                    "missing": sorted({int(n) for n in missing})}
        except (TypeError, ValueError):
            return None

    def make_status_board(self) -> discord.Embed:
        lines = []
        online = 0
        for slot in self.status_slots:
            active = self.slot_online(slot) if self.ap_connected else False
            online += int(active)
            game = self.resolve_game(slot)
            suffix = f" · {safe_text(game, 100)}" if game else ""
            lines.append(f"{'🟢' if active else '🔴'} **{safe_text(self.resolve_player_name(slot), 100)}** — {'Online' if active else 'Offline'}{suffix}")
        color = (COLOR_STATUS_DISCONNECTED if not self.ap_connected else
                 COLOR_STATUS_ONLINE if online else COLOR_STATUS_OFFLINE)
        embed = discord.Embed(
            title="👥 Spieler-Status",
            description=render_lines(lines, max_chars=3900, max_lines=30),
            color=color,
        )
        embed.add_field(name="🎮 Spieler online", value=f"{online}/{len(self.status_slots)}", inline=True)
        embed.add_field(name="📡 Archipelago", value="🟢 Verbunden" if self.ap_connected else "⚪ Getrennt", inline=True)
        embed.set_footer(text=f"Seed: {plain_text(self.seed_name, 70)} • Check-Zahlen im Live-Fortschritt • /archi fortschritt")
        return embed

    async def update_presence(self) -> None:
        online = sum(self.slot_online(slot) for slot in self.status_slots) if self.ap_connected else 0
        total = len(self.status_slots)
        if not self.ap_connected:
            status, label = discord.Status.idle, "Archipelago getrennt"
        elif online:
            status, label = discord.Status.online, f"🟢 {online}/{total} Spieler online"
        else:
            status, label = discord.Status.dnd, f"🔴 Niemand online (0/{total})"
        await self.change_presence(status=status, activity=discord.Activity(
            type=discord.ActivityType.watching, name=label,
        ))

    async def board_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await self.board_event.wait()
            await asyncio.sleep(STATUS_DEBOUNCE)
            self.board_event.clear()
            dirty = set(self.dirty_boards)
            self.dirty_boards.difference_update(dirty)
            if not self.state or not dirty:
                continue
            try:
                if "status" in dirty:
                    await self.update_presence()
                    if STATUS_CHANNEL_ID:
                        await self.upsert_board("status", STATUS_CHANNEL_ID, self.make_status_board())
                if "hints" in dirty:
                    await self.upsert_board("hints", HINT_BOARD_CHANNEL_ID, self.make_live_hint_board())
                if "deaths" in dirty:
                    await self.upsert_board("deaths", DEATH_BOARD_CHANNEL_ID, self.make_death_board())
                if "stats" in dirty and STATS_CHANNEL_ID:
                    await self.upsert_board("stats", STATS_CHANNEL_ID, self.make_stats_board())
            except Exception as exc:
                print(f"[Discord] Aktualisierung der Boards fehlgeschlagen: {exc}")

    # --------------------------------------------------
    # ARCHIPELAGO-PROTOKOLL + LIVE-DATEN-ABFRAGE
    # --------------------------------------------------

    async def send_json(self, packets: list[dict]) -> None:
        if self.ap_ws is not None:
            await self.ap_ws.send(json.dumps(packets))

    async def data_poll_loop(self) -> None:
        """Sichert Hint-/Goal-Synchronisierung nach Offlinezeiten ab."""
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(POLL_INTERVAL)
            # Externe Tracker-Dateien können sich ohne AP-Ereignis ändern.
            if self.state:
                # Auch extern aktualisierte Seed-DeathLink-Dateien live übernehmen.
                if self.seed_name and reconcile_death_counts(self.state, self.seed_name, self.team):
                    self.persist()
                    self.request_board_update("deaths", "stats")
                if STATS_CHANNEL_ID:
                    self.request_board_update("stats")
            if not self.ap_connected or not self.status_slots:
                continue
            keys = [
                f"_read_hints_{self.team}_{slot}" for slot in self.status_slots
            ] + [
                f"_read_client_status_{self.team}_{slot}" for slot in self.status_slots
            ]
            try:
                await self.send_json([{"cmd": "Get", "keys": keys}])
            except Exception as exc:
                print(f"[AP] Datenabfrage fehlgeschlagen: {exc}")

    async def handle_printjson(self, packet: dict) -> None:
        kind = packet.get("type")
        if kind == "ItemSend":
            await self.handle_item(packet)
        elif kind == "Hint":
            await self.handle_hint(packet)
        elif kind == "Join":
            self.handle_join(packet)
        elif kind == "Part":
            self.handle_part(packet)
        elif kind == "Goal":
            await self.handle_goal(packet)
        # ItemCheat und andere Servermeldungen bleiben ignoriert.

    async def handle_ap_packet(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "RoomInfo":
            name = packet.get("seed_name")
            if not isinstance(name, str) or not name.strip():
                # Fehlende Seed-ID niemals unbemerkt mit vorherigem Spiel vermischen.
                name = f"unbekannt-{uuid.uuid4()}"
                print("[Seed] WARNUNG: Server liefert keinen seed_name – Sitzung ist nicht dauerhaft zuordenbar")
            self.pending_seed_name = name
            await self.send_json([{
                "cmd": "Connect", "password": AP_PASSWORD, "game": AP_GAME,
                "name": AP_SLOT, "uuid": str(uuid.uuid4()),
                "version": {"class": "Version", "major": 0, "minor": 6, "build": 0},
                "items_handling": 0b111, "tags": BOT_TAGS, "slot_data": False,
            }])

        elif cmd == "Connected":
            team = int(packet.get("team", 0))
            self.activate_seed(self.pending_seed_name or f"unbekannt-{uuid.uuid4()}", team)
            self.player_names = {
                int(p["slot"]): (p.get("alias") or p.get("name") or f"Spieler {p['slot']}")
                for p in packet.get("players", [])
                if int(p.get("team", 0)) == team
            }
            self.slot_games = {
                int(slot): data.get("game")
                for slot, data in packet.get("slot_info", {}).items()
            }
            games = sorted({game for game in self.slot_games.values() if game})
            self.item_names = {}
            self.location_names = {}
            print(f"[AP] Als {AP_SLOT} verbunden, Seed {self.seed_name}, Spiele: {games}")
            await self.send_json([{"cmd": "GetDataPackage", "games": games}])
            await self.init_status(packet)
            await self.announce_features_if_needed()

        elif cmd == "ConnectionRefused":
            print(f"[AP] Verbindung abgelehnt: {packet.get('errors', packet)}")
            if self.ap_ws is not None:
                await self.ap_ws.close()

        elif cmd == "DataPackage":
            for game, data in packet.get("data", {}).get("games", {}).items():
                self.item_names[game] = {
                    int(item_id): name
                    for name, item_id in data.get("item_name_to_id", {}).items()
                }
                self.location_names[game] = {
                    int(location_id): name
                    for name, location_id in data.get("location_name_to_id", {}).items()
                }
                print(f"[AP] {game}: {len(self.item_names[game])} Items, {len(self.location_names[game])} Locations")
            # AP location IDs are now available: start the first UT run now.
            print("[UT] Spiele-Datenpaket empfangen, Tracker-Abfrage wird ausgelöst.")
            self.request_ut_update()
            self.request_board_update()

        elif cmd == "RoomUpdate":
            if "players" in packet:
                for player in packet["players"]:
                    slot = player.get("slot")
                    if slot is not None and int(player.get("team", self.team)) == self.team:
                        self.player_names[int(slot)] = (
                            player.get("alias") or player.get("name") or f"Spieler {slot}"
                        )
            self.update_own_checks(packet)
            self.request_board_update()

        elif cmd == "Retrieved" and self.state:
            keys = packet.get("keys", {})
            if isinstance(keys, dict):
                self.apply_client_status(keys)
                self.apply_retrieved_hints(keys)

        elif cmd == "SetReply" and self.state:
            # Falls der Server später SetNotify für Status/Hint-Keys nutzt.
            key = packet.get("key")
            if isinstance(key, str):
                keys = {key: packet.get("value")}
                self.apply_client_status(keys)
                self.apply_retrieved_hints(keys)

        elif cmd == "PrintJSON":
            debug("PRINTJSON", packet)
            await self.handle_printjson(packet)

        elif cmd == "Bounced":
            if "DeathLink" in packet.get("tags", []):
                await self.handle_deathlink(packet)

        elif cmd == "InvalidPacket":
            print(f"[AP] Ungültiges Paket: {packet.get('type')}: {packet.get('text')}")

    async def archipelago_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                print(f"[AP] Verbinde mit {AP_URL}")
                async with websockets.connect(
                    AP_URL, max_size=None, ping_interval=None, ping_timeout=None
                ) as ws:
                    self.ap_ws = ws
                    async for message in ws:
                        try:
                            packets = json.loads(message)
                        except json.JSONDecodeError:
                            print("[AP] Ungültige JSON-Nachricht ignoriert")
                            continue
                        if isinstance(packets, dict):
                            packets = [packets]
                        if not isinstance(packets, list):
                            continue
                        for packet in packets:
                            if isinstance(packet, dict):
                                try:
                                    await self.handle_ap_packet(packet)
                                except Exception as exc:
                                    print(f"[AP] Paketfehler ({packet.get('cmd')}): {exc}")
            except Exception as exc:
                print(f"[AP] Verbindungsfehler: {exc}")
            finally:
                self.ap_ws = None
                self.ap_connected = False
                self.connections.clear()
                self.request_board_update()
            await asyncio.sleep(RECONNECT_DELAY)


def main() -> None:
    bot = ArchipelagoDiscordBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
