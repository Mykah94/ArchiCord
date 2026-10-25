# ArchiCord – GitHub-Komplettpaket

## Enthalten

- Vollständiger Discord-Bot (`archicord.py`) mit Hints, Items, Traps, Zielen, Status, DeathLinks und Fortschritt
- Universal-Tracker-Bridge mit Erreichbarkeitslogik-Export (`tracker/ut_bridge.py`)
- WebUI mit neuem ArchiCord-Design (`webui.py` + `webui_assets/`)
- APWorld-Verwaltung (`tracker/apworld_manager.py`)
- Automatische Feature-Nachricht einmal pro Seed (konfigurierbar mit `ARCHICORD_FEATURES_ANNOUNCE`) und `/archi funktionen`
- Tests und GitHub-Actions-Workflow
- Installations-, Sicherheits-, Konfigurations- und GitHub-Upload-Anleitungen

## Was absichtlich fehlt

- **Keine `.env` mit Token oder Passwörtern** (nur `.env.example`)
- Keine persönlichen YAMLs, APWorlds, Seed-ZIPs, Spoiler, DeathLink-Zähler oder Laufzeitdaten
- Keine mitgelieferte Discord- oder Archipelago-Installation
- Keine pauschale Kompatibilitätsgarantie für alle Archipelago-Welten
- Keine automatisch erteilte Open-Source-Lizenz (bitte bewusst selbst auswählen)

## Verifikation

Die automatisierte lokale Testsuite wurde unter Python 3.13 ausgeführt und umfasst 44 Tests.
Die HTML/JavaScript-Funktionen wurden auf JavaScript-Syntax geprüft.
Vollständige Live-Tests mit Discord, Windows und Universal Tracker sind damit nicht ersetzt.
