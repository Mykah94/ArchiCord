# Configuration ⚙️

Create a local `.env` by copying `.env.example`. The core settings include `DISCORD_TOKEN`, `AP_URL`, `AP_SLOT`, `AP_GAME`, `ITEM_CHANNEL_ID`, `HINT_CHANNEL_ID` and `DEATHLINK_CHANNEL_ID`.

## Discord channels

Optional channel settings remain available:

- `STATUS_CHANNEL_ID`
- `HINT_BOARD_CHANNEL_ID`
- `DEATH_BOARD_CHANNEL_ID`
- `STATS_CHANNEL_ID`
- `GOAL_CHANNEL_ID`
- `FEATURES_CHANNEL_ID`

`DISCORD_GUILD_ID` can limit command synchronization to a particular Discord guild.

## Storage and polling

`ARCHICORD_DATA_DIR` selects the local seed-state directory. `AP_POLL_INTERVAL` controls Archipelago polling. `ARCHICORD_UT_INTERVAL`, `ARCHICORD_UT_LAUNCHER` and `ARCHICORD_CHECKS_FILE` configure optional Universal Tracker queries and exports.

`ARCHICORD_AP_INSTALL_DIR` and `ARCHICORD_APWORLD_DIRS` specify local directories for APWorld discovery. `ARCHICORD_FEATURES_ANNOUNCE` controls the once-per-seed feature announcement; `ARCHICORD_DEBUG` enables optional debug output; `USE_ANSI_ITEM_NAMES` enables ANSI item-name formatting.

## Credential handling

Leaving the Discord token or Archipelago password field blank in the Web UI **keeps the existing saved value**. To change a secret, provide the new value explicitly.

Do not add credentials, player YAMLs, seed files or private exports to Git. Keep the Web UI local.
