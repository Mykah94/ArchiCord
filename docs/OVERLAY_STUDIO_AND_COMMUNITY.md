# ArchiCord: Overlay Studio, Community Commands and Per-Room Tracker

This feature set was selectively adapted from the user-supplied
ArchiCord OBS Log package and integrated into the newer ArchiCord main code.
It **does not overwrite** existing seed state, WebUI assets, Discord
commands, or Archipelago release monitoring.

## Windows Studio and OBS setup

1. Start the existing ArchiCord WebUI and bot as usual.
2. Run `START_OVERLAY_STUDIO.bat` for the local browser editor on
   **http://127.0.0.1:8766/**. This is a separate localhost service.
3. Alternatively run `START_OVERLAY_DESKTOP.bat` for the native desktop
   editor and popout log. Debug startup:
   `START_OVERLAY_DESKTOP_DEBUG.bat`. The desktop window also starts the
   localhost editor if the port is free.
4. Configure a profile, choose its Multiworld instance, adjust theme,
   font size, animation and event count, then save.
5. In OBS, add a **Browser Source** pointing to the displayed profile URL,
   e.g. `http://127.0.0.1:8766/obs?profile=default`.
6. The existing per-room log also remains available at
   `http://127.0.0.1:8765/obs-log?instance=room1`.

Studio profiles are stored locally under
`archicord_data/overlay_profiles.json`. Their validation limits profiles,
allowed themes, names, effects and displayed event counts. The Studio only
reads private local ArchiCord event logs; it does not request, store or
expose Discord/Archipelago credentials. Studio port 8766 is **localhost
only**. Do not expose it on your router or to the public Internet.

For optional native Windows sound previews, put your own small `.wav`
files under `overlay_sounds/`. Sounds and popups are optional and off by
default. The repository does **not** distribute copyrighted audio samples.
The build script `BUILD_OVERLAY_DESKTOP_EXE.bat` requires a separately
installed PyInstaller; the provided scripts do not silently install software.

## New Discord commands

All commands are scoped to one configured Discord guild and one selected
Multiworld seed. For multiple rooms, pass `instanz` to identify the room.

- `/slot claim` – claim a player slot
- `/slot freigeben` – release your slot; moderators may release another
  player's slot
- `/slot liste` – see slot claims
- `/wishlist add`, `entfernen`, `liste`,
  `benachrichtigung` – exact item names and opt-in private notices
- `/run starten`, `beenden`, `thread` – moderator-controlled
  per-seed run thread lifecycle

Optional **automatic run threads** can be enabled by setting
`thread_enabled=true` and an appropriate
`thread_parent_channel_id` for a Multiworld instance. They are keyed by
Discord guild, seed and team and do not duplicate on reconnect. A finished
run is not silently reopened. For manual delete/archive operations Discord
**Manage Threads** permission is required.

Wishlists receive opt-in Discord DMs only when the exact wished item
arrives for the claimed slot. Progression-only **channel embeds** are
unchanged: normal, useful and trap items do not generate item embeds.
Private wishlist notifications are a separate optional feature.

## Separate Universal Tracker checks

Open `http://127.0.0.1:8765/tracker-settings` to choose the
Archipelago launcher, installation, YAML, seed and APWorld paths.
Path validation never executes uploaded APWorld files or the launcher.

Each parallel room starts an optional Universal Tracker poll, using the
existing ArchiCord fail-closed bridge. Exact DataPackage names are required.
When successful, it exports only verified doable locations to the room's
private `ut_checks.json`; results carry the seed, team, slot and timestamp.
On failure, stale results are removed. A room's check page is available via
the **Confirmed Checks** link in the Multiworld editor.

Doable checks for untracked rooms are **unknown**, not guessed. A real UT
launcher, compatible APWorlds, matching YAMLs and successful Archipelago
connection are still required; an error or missing launcher is not a
successful logic check.

## Safe configuration migration

To append newly introduced .env keys while preserving existing values,
comments and credentials, run:

```powershell
py -3 env_migration.py --dry-run
py -3 env_migration.py
```

A private backup is made before changes. Never share .env files or their
backups publicly.

## Verification and limitations

CI runs on Python 3.11 and 3.13, tests the local APIs/CSRF, per-guild
isolation, profile validation, tracker path validation, state persistence and
overlay JavaScript syntax. A live test using your real Windows installation,
Discord permissions, APWorlds, Universal Tracker and OBS is still required.

This integration implements a native desktop editor, popup live log,
user-supplied WAV preview and profile-aware OBS browser sources. It does
**not** claim pixel-identical reproduction of every original ZIP theme,
custom effects, installer binary, sound asset or legacy interface. The old
ZIP includes substantially different source files; replacing the newer
main code wholesale would break existing features.
