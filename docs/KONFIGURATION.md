# ArchiCord konfigurieren

Die `.env` wird aus `.env.example` erzeugt. Pflichtwerte für den Bot sind `DISCORD_TOKEN`, `AP_SLOT`, `ITEM_CHANNEL_ID`, `HINT_CHANNEL_ID` und `DEATHLINK_CHANNEL_ID`; für den üblichen Archipelago-Betrieb zusätzlich `AP_URL` und `AP_GAME`.

Die optionalen Discord-Kanäle `STATUS_CHANNEL_ID`, `HINT_BOARD_CHANNEL_ID`, `DEATH_BOARD_CHANNEL_ID`, `STATS_CHANNEL_ID`, `GOAL_CHANNEL_ID` und `FEATURES_CHANNEL_ID` bleiben verfügbar. `DISCORD_GUILD_ID` beschränkt die Slash-Command-Synchronisierung auf einen Server.

`ARCHICORD_DATA_DIR` legt den Speicherort der Seed-Zustände fest. `AP_POLL_INTERVAL`, `ARCHICORD_UT_INTERVAL`, `ARCHICORD_UT_LAUNCHER`, `ARCHICORD_CHECKS_FILE`, `ARCHICORD_AP_INSTALL_DIR` und `ARCHICORD_APWORLD_DIRS` steuern Polling, Tracker und APWorld-Suche. `ARCHICORD_FEATURES_ANNOUNCE` steuert die einmalige Feature-Ankündigung, `ARCHICORD_DEBUG` die optionalen Debug-Logs, `USE_ANSI_ITEM_NAMES` die ANSI-Darstellung.

Ein leeres Passwort-/Token-Feld in der WebUI lässt einen bereits gespeicherten Wert unverändert. Zum Wechsel von Zugangsdaten den neuen Wert ausdrücklich eingeben.

**Sicherheit:** Token, AP-Passwort, YAMLs und Seeds gehören nicht ins Git-Repository. Die WebUI nur lokal betreiben.
