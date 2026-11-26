# WebUI und APWorld-Auswahl

Start über `START_WEBUI.bat` oder `start_webui.sh`. Lokal aufrufen: `http://127.0.0.1:8765/` und für die World-Auswahl `http://127.0.0.1:8765/apworlds`.

Die WebUI kann den Bot starten, stoppen, neu starten, Einstellungen speichern, Live-Logs anzeigen und installierte APWorld-Dateien auflisten. Die API akzeptiert schreibende Aktionen nur mit einem temporären CSRF-Token. Zusätzlich werden Host-Header auf `localhost` bzw. `127.0.0.1` für den lokalen Port beschränkt.

APWorlds werden über ihr `archipelago.json` in der `.apworld`-ZIP gelesen. Dabei wird **kein** World-Python-Code ausgeführt. Eine Auswahl kann für das aktuelle Seed-Spiel gesetzt, gespeichert und mit Bot-Neustart aktiviert werden. Gespeichert wird sie in `tracker/settings/apworld_selection.json`.

Die ursprüngliche HTML-/CSS-/JS-Seite bleibt bestehen. Externe Bildassets `webui_assets/archicord-logo.png` und `webui_assets/archicord-bg.png` fehlen jedoch in GitHub. Für originalgetreue Darstellung müssen die ursprünglichen Dateien aus einer Sicherung eingebracht werden. Nicht per Reverse Proxy oder Portweiterleitung öffentlich anbieten.
