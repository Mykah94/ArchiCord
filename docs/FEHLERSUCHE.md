# Troubleshooting 🔍

**The bot will not start.** Check your Python version, install `requirements.txt`, and confirm that `.env` contains a valid Discord token, AP slot/game, connection URL and Discord channel IDs.

**Discord is online but Archipelago is offline.** Check `AP_URL`, port, slot name, `AP_GAME`, password and server availability. Review local error logs but do not post credentials publicly.

**No doable checks appear.** Confirm `ARCHICORD_UT_LAUNCHER`, Universal Tracker installation, YAMLs, APWorld versions and the selected games. Inspect `[UT]` messages. **Do not convert missing locations into guessed doable checks.**

**An APWorld is missing.** Search `tracker/apworlds/`, your configured Archipelago installation or `ARCHICORD_APWORLD_DIRS`. The scanner expects a readable, unique `archipelago.json` manifest.

**The Web UI has no images.** The updated repository includes new SVG branding. Make sure `webui_assets/archicord-logo.svg` and `webui_assets/archicord-bg.svg` are present and refresh the page.

**Old seed data seems missing after an upgrade.** Do not overwrite newly found state. Compare `.env`, `ARCHICORD_DATA_DIR`, server URL, seed, team and slot with your local backup.

**Running tests.**

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Passing CI checks does **not** replace live Discord, Windows or Archipelago integration tests.
