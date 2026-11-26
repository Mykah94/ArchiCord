# ArchiCord – Release and maintenance notes 📝

## Current repository

- Full Discord bot source (`archicord.py`): player status, hints, item/trap notifications, goals, DeathLinks and progress displays.
- Optional Universal Tracker CLI bridge (`tracker/ut_bridge.py`) with bounded output, timeout and exact location-name mapping.
- APWorld manifest discovery and game selection (`tracker/apworld_manager.py`).
- Local web control panel (`webui.py`) and **new replacement SVG artwork** (`webui_assets/`).
- Per-seed feature announcement, controlled by `ARCHICORD_FEATURES_ANNOUNCE`, and `/archi funktionen`.
- Regression tests and GitHub Actions on Python 3.11 and 3.13.
- English setup, configuration, troubleshooting, security and contribution documentation.

## Restoration notes

Earlier source archives documented additional assets that were missing from the available GitHub history. The tracker bridge and APWorld manager were **reconstructed**, not recovered byte-for-byte. New original vector artwork replaces the missing Web UI images. The original images are **not** claimed to have been restored.

## What is intentionally not included

- No `.env` credentials (only the safe `.env.example`).
- No personal player YAMLs, APWorld files, seed archives, spoilers, DeathLink counts or runtime data.
- No bundled Discord/Archipelago installation.
- No guarantee that all Universal Tracker/APWorld versions work together.
- No automatic open-source license grant; the maintainer must choose one explicitly.

## Verification status

GitHub Actions runs automated Python checks. Those checks cover key contracts, parser behavior, local Web UI security and data snapshot handling; they **do not** replace full end-to-end Discord, Windows or Archipelago tests. Local installations, especially Universal Tracker, must be validated with their own world/YAML versions.

See [restoration review](docs/RESTORATION_REVIEW.md).
