# ArchiCord 🎮

**ArchiCord** ist ein Discord-Bot für [Archipelago](https://archipelago.gg/)-Multiworlds mit lokalem Web-Control-Center, Live-Boards, DeathLinks und optionaler **Universal-Tracker-Anbindung für Doable Checks**.

![ArchiCord WebUI Hintergrund](webui_assets/archicord-bg.png)

> **Projektstatus:** Hobby-/Community-Projekt. Die vorhandenen automatisierten Tests prüfen Code, Parser und WebUI-Schnittstellen; ein vollständiger Live-Test mit deiner Discord- und Archipelago-Installation ist weiterhin erforderlich. Universal Tracker unterstützt nicht garantiert jedes Spiel oder jede APWorld-Version.

## Funktionen

| Funktion | Beschreibung |
| --- | --- |
| 🎯 **Live-Fortschritt** | Aktuell machbare, noch nicht erledigte Checks pro Spieler, sofern Universal Tracker gültige Logikdaten liefert |
| 🧩 **Universal Tracker** | Automatischer CLI-Aufruf je ausgewähltem Slot; Zuordnung der Location-Namen zu Archipelago-IDs |
| 🌍 **APWorld-Verwaltung** | Separate WebUI-Seite, um installierte APWorlds zu durchsuchen und Tracking-Spiele auszuwählen |
| 👥 **Spielerstatus** | Online-/Offline-Board und Spielzuordnung |
| 🔎 **Hints** | Hint-Meldungen sowie eine aktualisierte Übersicht offener/gefundener Hints |
| 🎁 **Items / Traps** | Farbige Discord-Embeds für beobachtete Progression-Items und Traps |
| ☠️ **DeathLinks** | Live-Rangliste, Speicherung pro Seed und humorvolle Meldungen bei jedem 25. Tod pro Spieler |
| 🏆 **Ziele** | Zielankündigungen und Zielzähler |
| 📣 **Feature-Embed** | Einmalige Übersicht der Bot-Funktionen pro Seed, plus `/archi funktionen` |
| 🌐 **WebUI** | Bot starten, stoppen, neu starten, `.env` bearbeiten, Verbindung und Konsole ansehen |
| 💾 **Seed-Speicherung** | JSON-Zustand je Server/Seed/Team/Slot für Boards, Hints und DeathLinks |

**Nicht Teil der Live-Fortschrittsübersicht:** Progression-Item-Zähler und Trap-Zähler (diese Events werden bei Bedarf weiterhin separat verarbeitet).

## Schnellstart (Windows)

1. **Python 3.11 oder 3.13** installieren. Python 3.15 wird von diesem Repository nicht durchgehend getestet.
2. Repository als ZIP herunterladen oder klonen und in einen eigenen Ordner entpacken.
3. Abhängigkeiten installieren:
   ```powershell
   py -3 -m pip install -r requirements.txt
   ```
4. Die Beispieldatei kopieren und **lokal** bearbeiten:
   ```powershell
   Copy-Item .env.example .env
   ```
   `DISCORD_TOKEN`, `AP_URL`, `AP_SLOT`, `AP_GAME` und die gewünschten Discord-Kanal-IDs eintragen.
5. `START_WEBUI.bat` ausführen und **http://127.0.0.1:8765** öffnen.
6. Über die WebUI den Bot starten. Discord- und Archipelago-Verbindung in der Konsole kontrollieren.

**Bestehende Installation aktualisieren:** Den alten ArchiCord-Ordner vorher sichern. Programmdateien ersetzen, aber **deine bestehende `.env`, `archicord_data/`, `deathlinks/` und Tracker-Dateien behalten**. Diesem öffentlichen Repository liegt absichtlich keine `.env` bei.

## Universal Tracker einrichten

Universal Tracker ist **optional**. Ohne Tracker bleibt der Discord-Bot lauffähig, zeigt aber bei Doable Checks „keine Logikdaten“.

1. Passende Archipelago-Installation und die **Universal Tracker**-Komponente lokal installieren.
2. Für deinen Seed die passenden Spieler-YAMLs und `.apworld`-Dateien lokal bereitstellen. Du kannst sie in `tracker/yamls/`, `tracker/apworlds/` und die Seed-ZIP in `tracker/seeds/` ablegen. Die für die CLI tatsächlich benötigten Dateien müssen außerdem in den von der lokalen Archipelago-Installation verwendeten Ordnern liegen.
3. In `.env` den installierten Launcher setzen, unter Windows beispielsweise:
   ```dotenv
   ARCHICORD_UT_LAUNCHER=C:\ProgramData\Archipelago\ArchipelagoLauncherDebug.exe
   ARCHICORD_UT_INTERVAL=120
   ARCHICORD_CHECKS_FILE=tracker/exports/live_checks.json
   ```
4. Im Browser **http://127.0.0.1:8765/apworlds** die gewünschten APWorlds auswählen.
5. Bot starten. In den Logs auf `[UT]` achten. Der erste Lauf wird nach dem Empfang des Archipelago-Datenpakets angestoßen; danach erfolgen regelmäßige Prüfungen.

Die **APWorld-Auswahl steuert nur ArchiCords Tracker-Abfragen**, nicht das Laden aller APWorlds durch den Archipelago-Launcher. Loader-Warnungen für andere installierte APWorlds können auftreten. Bei inkompatiblen YAML-/APWorld-Versionen werden Ergebnisse nicht als verlässlich ausgegeben.

[Ausführliche Anleitung zur Tracker-Integration](docs/UNIVERSAL_TRACKER.md)

## WebUI

![ArchiCord Logo](webui_assets/archicord-logo.png)

- Bot-Steuerung: <http://127.0.0.1:8765/>
- APWorld-Verwaltung: <http://127.0.0.1:8765/apworlds>
- WebUI ist absichtlich nur über `127.0.0.1` erreichbar. **Nicht ins öffentliche Internet weiterleiten.**
- `DISCORD_TOKEN` wird im Browser nicht angezeigt. Bereits gespeicherte Tokens bleiben bei leeren Tokenfeldern bestehen.

## Discord Slash-Commands

`/archi status`, `/archi hints`, `/archi deaths`, `/archi fortschritt`, `/archi statistik`, `/archi funktionen`.

Discord-Bot-Berechtigungen: **View Channels, Send Messages, Embed Links, Read Message History, Use Application Commands**. Einladen mit den Scopes **`bot`** und **`applications.commands`**. Es werden keine privilegierten Gateway-Intents benötigt.

## Dokumentation

- [Installation](docs/INSTALLATION.md)
- [Konfiguration](docs/KONFIGURATION.md)
- [Universal Tracker und Doable Checks](docs/UNIVERSAL_TRACKER.md)
- [WebUI und APWorld-Auswahl](docs/WEBUI.md)
- [Fehlersuche](docs/FEHLERSUCHE.md)
- [Sicherheit und GitHub-Veröffentlichung](SECURITY.md)
- [Mitwirken](CONTRIBUTING.md)

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Zusätzlich führt GitHub Actions die Tests bei Pushes und Pull Requests unter Python 3.11 und 3.13 aus.

## Lizenz

**Keine Lizenz automatisch vergeben.** Wenn du das Repository öffentlich machst und anderen die Nutzung/Weiterentwicklung erlauben möchtest, wähle ausdrücklich eine passende Lizenz in GitHub (beispielsweise MIT, sofern du dafür alle nötigen Rechte besitzt). Archipelago, Discord und fremde `.apworld`-Dateien unterliegen jeweils ihren eigenen Bedingungen und sind **nicht** Bestandteil dieses Repositories.
