# ArchiCord 3.0 — Multiworld Control Center

**Status:** Feature integration branch. Existing Discord commands, old WebUI URLs, seed states, DeathLink milestone rules, and APWorld settings remain in place. Python CI does not substitute for a live Discord / Archipelago / Windows / Universal Tracker test.

## Feature pages

| Path | Feature | Behavior |
| --- | --- | --- |
| /dashboard | Live Multiworld Dashboard | Current seed, players, goals, deaths, progression items, confirmed doable checks; refreshes every 15 seconds |
| /players | Players | Game, online status, goals and confirmed doable checks per player |
| /checks | Interactive Checks | Filter by player, location name and status. Other players show only confirmed tracker results |
| /history | Multiworld History | Read-only summaries of saved seeds and teams |
| /item-routes | Item Routes | Sender, receiver, item, location and time for newly accepted items/traps |
| /health | Connection Monitor | Bot, Discord, Archipelago, tracker and snapshot age |
| /backups | Backup & Restore | Create, list, verify and restore local archives; restore requires stopped bot and a safety backup |
| /compatibility | APWorld Diagnostics | Duplicates, invalid manifests, unknown versions; does not certify game runtime compatibility |
| /notifications | Notification Rules | Category switches, channel overrides, cooldowns and language choices |
| /achievements | Achievements | Per-seed goals, checks, items and DeathLink milestones, read-only and no automatic spam |

Old routes /, /apworlds and /resources remain. All APIs are local-only and writing requires the existing CSRF token.

## Configuration

Notification preferences are stored in ARCHICORD_DATA_DIR/notifications_v3.json and are optional. Without configuration, existing Discord channels and messages behave as before.

Web UI and Discord message language are selected separately. German stays the default. English localization covers recognized built-in embeds; arbitrary APWorld text and some legacy slash command descriptions remain untranslated.

Set ARCHICORD_BACKUP_INTERVAL_HOURS to control automatic backups; default 24 hours, 0 disables, supported range 0–168. The running local WebUI periodically creates an archive and retains the ten most recent backups. Archives are stored under backups/ and ignored by Git.

## Backup scope and warning

Backups include files under the project root only: .env, archicord_data/, deathlinks/, and tracker/settings/. They contain potentially sensitive credentials and seed data. Never upload, publish, or serve them publicly. Files stored at external custom data paths, or an .env living outside the project directory, are not included; those require separate backups.

Backups use bounded archive sizes, SHA-256 verification and path-safety checks. Restore requires a stopped bot and confirmation and creates a safety archive before changes. Test restore on a COPY of the installation before using it with a live seed. Do not edit files externally during the process.

## Data compatibility

ArchiCord 3 adds the optional activity_v3 field to existing seed JSON; older keys and formats remain. The local live snapshot is written under ARCHICORD_DATA_DIR/live_v3.json and must never contain credentials. The original seed state remains authoritative.

Historical item routes cannot be reconstructed from old versions if those events were never persisted. Achievements are derived from known state. Doable checks are NEVER guessed from missing-location IDs.

## Manual release gates

1. Test the WebUI, all original control/settings/APWorlds/Resources pages, and the new pages on Windows.
2. Confirm all existing slash commands, live boards, hints, items/traps, goals and every-25th-DeathLink behavior.
3. Reconnect the same stored seed without losing data or mixing server/team/slot boundaries.
4. Test Universal Tracker with real APWorld/YAML combinations and failure cases.
5. Run backup and restore on a throwaway copy and compare all files.
6. Exercise notification settings, cooldowns, channel permissions, and DE/EN messages.
7. Check that APIs and logs never expose credentials and that the WebUI remains bound to localhost.

## Automated tests

Install requirements-dev.txt and run: python -m pytest -q

CI covers Python 3.11 and 3.13. It does not certify live third-party integration.
