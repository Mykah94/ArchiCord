# Installation 🛠️

## Requirements

- Python **3.11 or 3.13**.
- A Discord bot/application with the permissions listed in the [README](../README.md).
- An Archipelago Multiworld server and a slot for the bot.
- Optional: Universal Tracker with compatible APWorlds and player YAMLs.

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and enter your **local** credentials, server details and channel IDs. Never publish your real `.env`.

On Windows, run `START_WEBUI.bat`; on Linux/macOS run `sh start_webui.sh`. Then open `http://127.0.0.1:8765/` and start the bot from the control panel.

The Web UI is for localhost/127.0.0.1, **not for public hosting**.

## Updating an existing installation

Back up your entire ArchiCord folder before replacing files. In particular, preserve `.env`, `archicord_data/`, `deathlinks/` and local tracker/YAML data. Keep these private and do not overwrite them with example files.

## Artwork note

The previous Web UI artwork was not present in the available GitHub history. The repository now ships **new original SVG illustrations** instead of restoring those historical files.
