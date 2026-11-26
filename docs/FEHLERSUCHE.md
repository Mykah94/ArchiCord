# Fehlersuche

**Bot startet nicht:** Python-Version und `requirements.txt` prüfen. Bei fehlenden Konfigurationen zuerst `.env` mit gültigem Discord-Token, AP-Slot, Spiel und Discord-Kanal-IDs prüfen.

**Discord online, Archipelago offline:** `AP_URL`, Port, Slot-Name, `AP_GAME`, Passwort und Serververfügbarkeit prüfen. Bei Verbindungsfehlern vollständige lokale Logs ansehen, ohne Geheimnisse öffentlich zu kopieren.

**Keine Doable Checks:** `ARCHICORD_UT_LAUNCHER`, installierte Universal-Tracker-Komponente, YAML und World-Versionen prüfen. `[UT]`-Logs ansehen, APWorld-Auswahl kontrollieren. Nicht aus `missing`-Locations automatisch `doable` berechnen.

**APWorld nicht gefunden:** In `tracker/apworlds/`, dem konfigurierten Archipelago-Installationsordner oder `ARCHICORD_APWORLD_DIRS` nach `.apworld` suchen. Ein lesbares, eindeutiges `archipelago.json` ist Voraussetzung.

**WebUI zeigt keine Bilder:** Die originalen `webui_assets` sind im derzeitigen GitHub-Stand nicht enthalten und müssen aus der lokalen Sicherung ergänzt werden.

**Nach einem Update fehlen alte Daten:** Nicht sofort neue Zustandsdateien überschreiben. Verwendete `.env`, `ARCHICORD_DATA_DIR`, AP-Server/Seed/Team/Slot und deine lokale Sicherung vergleichen.

**Tests ausführen:** `python -m pip install -r requirements-dev.txt`, danach `python -m pytest -q`. CI-Erfolg ersetzt keinen Discord-/Windows-/Archipelago-Live-Test.
