# ArchiCord: parallel Multiworlds and OBS logs

This feature set was selectively adapted from the user's uploaded
**ArchiCord_OBS_Log_Scharf_Komplettpaket(1).zip**. It preserves current
ArchiCord 3.0 data, the existing WebUI and Archipelago integration.

## Configure additional Multiworld rooms

1. Open the local WebUI (http://127.0.0.1:8765/).
2. Open **Multiworlds** at /instanzen and select **Add Multiworld**.
3. Enter a permanent unique instance ID, display name, AP WebSocket URL,
   existing bot slot, game, Discord server/guild ID, and at least one Discord
   channel ID. The bot must be invited to that Discord server.
4. Optionally enter the official Archipelago room page URL so ArchiCord can
   verify port changes after the room wakes up. Only official Archipelago
   /room/<ID> links are accepted.
5. Save all rooms. If the Discord bot is running, added/changed rooms are
   applied automatically within a few seconds. Do not copy passwords into
   screenshots, GitHub issues or chat messages.

The bot uses **one Discord token/login** for all configured rooms. Every
additional room uses a separate AP connection task, status.json and
instance/seed/team-specific state.json. Up to **12 additional** rooms can
run simultaneously.

**Discord-first:** When at least one additional room is configured, blank
AP_SLOT in .env to disable the unused legacy primary AP connection. Existing
installations with AP_SLOT set retain their legacy primary room as well.
Do not delete or overwrite the old .env or archicord_data directory when
upgrading. Store a full local backup before updating.

## Item message policy

- Flag **1** (progression) sends a Discord progression item embed.
- Flag **3** (useful + progression) sends a progression item embed.
- Flags **0**, **2**, **4**, **5**, **6**, and **7** do **not** send item embeds.
- Progression hints, goals and DeathLink milestones are not item embeds;
  they retain their separate notification behavior.
- Normal and trap item events may be written to the **local OBS log**, but
  do not generate Discord item messages.
- Events are deduplicated within the specific room and seed. The same item
  from different seeds is independently tracked.

## Discord commands

Existing commands remain. For /archi status, hints, deaths, fortschritt and
statistik, use the optional **instanz** parameter to select an additional
room. When a guild has exactly one room and no authorized legacy primary
room, it is selected automatically. With multiple rooms, specify an ID.
A guild may not read another guild's private seed information.

Additional room commands currently provide room/player, DeathLink, goal and
hint-event summaries. Full per-room UT/Doable calculations are not yet
implemented; no logical reachability is guessed from missing IDs.

## OBS browser source

Each room card has an **OBS Live Log** link. For OBS running on the same PC
as ArchiCord, add its address as a *Browser Source*, e.g.:

    http://127.0.0.1:8765/obs-log?instance=room1

The browser layer has a transparent background, crisp large text, a rainbow
accent and a separate room event feed. It refreshes every two seconds and
shows recent local item events. Room names and OBS events can contain private
player/seed information, so **never expose the WebUI port publicly**.

The original ZIP's **Windows Desktop Overlay Studio**, screen pop-ups, sound
designer, profiles, and advanced run-thread/slot-claim/wishlist components
were **not** transplanted in this release. These need independent integration
and security/live testing. The original ZIP is not substituted for the main
repository because it predates the newer ArchiCord 3.0 modules.

## Tests and verification

CI checks Python 3.11/3.13, HTTP origin/host/CSRF, seeded instance
isolation, password redaction, official room-link validation, event routing
and the progression-only flag matrix. Manual live validation is still required
on Windows with real Discord guilds, Archipelago rooms, APWorlds and OBS.

Back up your existing .env, archicord_data, deathlinks and tracker settings
before deploying; do not restore an archive onto a running bot.
