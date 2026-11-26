# ArchiCord installieren

## Voraussetzungen

- Python 3.11 oder 3.13
- Discord-Bot mit den im README angegebenen Berechtigungen
- Archipelago-Multiworld-Server und Slot für den Bot
- Optional Universal Tracker und kompatible APWorlds/YAMLs

```sh
python -m pip install -r requirements.txt
```

Unter Windows `.env.example` als `.env` kopieren und lokale Konfigurationsdaten eintragen. Die echte `.env` niemals veröffentlichen. Danach `START_WEBUI.bat` auf Windows oder `./start_webui.sh` auf Linux starten, die WebUI unter `http://127.0.0.1:8765/` aufrufen und den Bot starten.

Die WebUI lässt nur localhost/127.0.0.1 zu und ist nicht zur öffentlichen Bereitstellung gedacht. Bei Updates `.env`, `archicord_data/`, `deathlinks/` und den Tracker-Ordner vorher lokal sichern.

**Hinweis:** Die Bilddateien der ursprünglichen WebUI fehlen derzeit in diesem Repository. Die vorhandene HTML/CSS-Oberfläche bleibt unverändert, aber die Originalbilder müssen aus einer lokalen Sicherung wiederhergestellt werden.
