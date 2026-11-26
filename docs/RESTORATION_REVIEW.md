# ArchiCord – Review und Wiederherstellung (26. November 2026)

Dieser Branch stellt fehlende Python-Bausteine **neu** bereit. Ihre Originaldateien waren weder in `main` noch in der überprüften Repository-Historie verfügbar. Es wird **keine** 1:1-Wiederherstellung behauptet.

## Bewahrte Verhaltensweisen

- Bestehende Discord-Slash-Commands und Kanal-Konfiguration
- Item-, Trap-, Hint-, Ziel- und DeathLink-Ereignisse einschließlich jeder 25. Todesmeldung
- Seed-, Server-, Team- und Slot-getrennte Datenspeicherung; keine Migration und keine Löschung
- Bestehender HTML/CSS/JS-Code der lokalen WebUI
- Bestehende .env-Schlüssel und der Schutz, leere Passwort-/Token-Felder nicht zum Überschreiben zu verwenden
- Tracker-Zahlen nur aus nachgewiesenen Logik-Checks, niemals bloß aus Missing-Location-IDs

## Wiederhergestellte Schnittstellen

`tracker/apworld_manager.py` liefert `scan_worlds`, `load_selection`, `save_selection`, `selection_fingerprint`, `selected_games`.
Die Auswahl bleibt in `tracker/settings/apworld_selection.json`. Für die Spielauswahl werden APWorld-ZIP-Manifeste gelesen, fremder Python-Code wird nicht ausgeführt. Eine fehlende Auswahl bedeutet weiterhin „alle“, eine leere Auswahl „keines“.

`tracker/ut_bridge.py` liefert `fetch_slot` und `write_snapshot`. Der lokale Launcher wird im erwarteten Format `Universal Tracker -- --nogui --list` gestartet; Anmeldedaten werden nicht in Fehlermeldungen wiedergegeben. Ausgegeben werden ausschließlich exakte, eindeutige Namen aus dem Archipelago-Location-Datenpaket. Scheitert die Abfrage, erscheinen keine erdachten Doable-Zahlen.

**Einschränkungen:** Der CLI-Aufruf enthält AP-Zugangsdaten in Prozessargumenten, wie vom UT-CLI-Format vorgegeben. Lokale Betriebssystemnutzer mit Prozessinspektionsrechten könnten diese sehen. Geeignete Host-Sicherheit ist deshalb weiterhin wichtig. Ein echter Windows-Launcher-/APWorld-/YAML-Test ist Pflicht, bevor diese Bridge als vollständig kompatibel gelten kann.

## Sicherheitskorrekturen

- WebUI lässt Host-Header nur für localhost bzw. 127.0.0.1 und den eigenen Port zu (DNS-Rebinding-Schutz)
- Zusätzliche HTTP-Header und Maskierung von gespeicherten Zugangsdaten in Status-/Logausgaben
- Begrenzung eingehender WebSocket-Nachrichten auf 32 MiB statt unbeschränkter Aufnahme
- Bot-Debug-Ausgaben sind standardmäßig deaktiviert, können aber explizit konfiguriert werden

## Teststatus / Release-Gates

CI testet Python 3.11 und 3.13, Syntax, die vorhandenen Smoke-Tests und neue Tests für APWorld-Auswahl, Seed-Snapshot, CLI-Parsing und lokale Host-Validierung. Dies ersetzt **nicht** die vollständigen Live-/Integrationstests.

Vor einem Merge sind mindestens folgende manuelle Prüfungen nötig:

1. Windows und Python 3.11/3.13: WebUI öffnet sich mit der unveränderten Oberfläche und kann den Bot starten/stoppen.
2. Bestehende lokale `.env` und `archicord_data/` sichern, dann Wiederanlauf desselben Seeds ohne Zählerverlust bestätigen.
3. Discord: alle sechs Slash-Befehle, Boards, Hints, Trap-/Item-Embeds, Ziele, DeathLink-Deduplizierung und 25er-Meldungen testen.
4. Archipelago: Verbindungswechsel, Seed-Wechsel, Team-Trennung und große DataPackages testen.
5. Universal Tracker: echte lokal kompatible APWorld/YAML-Installation, `--list` Ausgabe, pro Spieler sichere ID-Zuordnung und Fehler-/Inkompatibilitätsfall prüfen.
6. Bilder `webui_assets/archicord-bg.png` und `webui_assets/archicord-logo.png` aus der ursprünglichen lokalen Projektversion wieder hinzufügen. Sie fehlen weiterhin; ein Ersatzdesign wäre keine unveränderte Wiederherstellung.

**Kein Release-Status:** Solange die Originalgrafiken und realen Integrationsprüfungen fehlen, ist die Arbeit nur ein abgesicherter Draft, nicht die endgültig verifizierte Fassung.
