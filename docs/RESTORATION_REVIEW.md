# ArchiCord – Restoration and compatibility review

**Review date:** November 26, 2026

The repository previously referred to components that had not actually been committed. The missing Python modules were **reimplemented** because their original sources were not available in the inspected Git history. These are not claimed to be byte-for-byte restorations.

## Behavior kept in place

- Existing Discord slash commands and configurable channel IDs.
- Item, trap, hint, goal and DeathLink events, including special announcements at every 25 deaths.
- Seed, server, team and bot-slot-specific persistence, without automatic deletion or migration.
- Existing Web UI HTML/CSS/JavaScript controls and existing `.env` configuration keys.
- Doable-check counts only from confirmed tracker logic, never guessed from missing locations.

## Reconstructed modules

**`tracker/apworld_manager.py`** provides `scan_worlds`, `load_selection`, `save_selection`, `selection_fingerprint` and `selected_games`. Game selection is stored in `tracker/settings/apworld_selection.json`. It reads manifests from APWorld ZIP archives **without executing world code**. Missing selection means all games; an explicitly empty selection means none.

**`tracker/ut_bridge.py`** provides `fetch_slot` and `write_snapshot`. It invokes the local launcher as `Universal Tracker -- --nogui --list` and accepts only uniquely matched, exact location names present in the Archipelago data package. Failed or incompatible outputs must not produce fabricated progress results.

The CLI can pass Archipelago credentials in a process argument as required by its connection URI. Operating-system users with sufficient process inspection permissions could see it; use a trusted host.

## Security improvements

- Local-only Web UI Host-header restrictions, to reduce DNS-rebinding risk.
- Response hardening headers and masking of configured secrets in logs and status messages.
- A 32 MiB limit on inbound WebSocket messages instead of unbounded reads.
- Debug output disabled unless explicitly enabled in configuration.

## Artwork and visual design

The original PNG logo and background could not be retrieved from the available GitHub history. **New ArchiCord vector illustrations** now replace them:

- `webui_assets/archicord-logo.svg`
- `webui_assets/archicord-bg.svg`
- `docs/assets/archicord-banner.svg`

They are new artwork, **not restored historical image files**. Existing dashboard layouts and controls have otherwise been retained.

## Automated verification

CI runs on Python 3.11 and 3.13 and covers syntax checks, core helper behavior, APWorld selection, tracking snapshots, CLI location mapping, localhost Host-header checks, DeathLink milestones and the six existing slash-command definitions. Any new tests added later are reflected by the GitHub Actions results.

**Automated checks alone do not demonstrate full production compatibility.** In particular:

1. On Windows, start and stop the real bot using the Web UI with Python 3.11/3.13.
2. Preserve private `.env` and seed state, then reconnect to the same seed and verify that counters and boards remain consistent.
3. Test the six Discord slash commands, items, traps, hints, goals, DeathLinks, deduplication and 25-death milestones with a real Discord server.
4. Exercise Archipelago reconnects, seed changes, team separation and sufficiently large data packages.
5. Test a real Universal Tracker launcher against matching APWorld/YAML installations and verify exact location-ID mapping and fail-closed behavior.
6. Review the newly created SVG assets on the target Web UI installation.

**Release claim:** This repository has automated verification and replacement artwork. Complete Windows/Discord/Archipelago/Universal Tracker end-to-end validation has **not** been demonstrated in this environment.
