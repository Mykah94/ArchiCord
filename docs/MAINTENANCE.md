# Wartung: automatische Backups und Health Monitor

Diese Erweiterung ist **zusätzlich** zur bisherigen WebUI eingebaut und verändert keine Discord- oder Archipelago-Ereignisverarbeitung.

## Wartung öffnen

1. ArchiCord wie bisher mit `START_WEBUI.bat` starten.
2. Lokal `http://127.0.0.1:8765/wartung` öffnen.
3. Dort Bot-/Discord-Status, AP-Status, pro-Instanz-Heartbeats, Alter des letzten Universal-Tracker-Exports und freien Speicher sehen.
4. Über **„Jetzt Sicherung erstellen“** jederzeit eine manuelle Sicherung auslösen.

Die WebUI selbst ist nur für lokale Nutzung gedacht; **nicht öffentlich ins Internet weiterleiten**.

## Backup-Verhalten

- **Automatisch beim WebUI-Start** (falls die letzte Sicherung älter als das eingestellte Intervall ist) und danach beim laufenden WebUI-Prozess etwa minütlich auf Fälligkeit prüfen.
- Standard: **alle 24 Stunden**, höchstens **14 Archive** behalten.
- Archive: `backups/archicord-YYYYMMDD-HHMMSS.zip`, nicht für GitHub bestimmt.
- Gesichert werden ausschließlich passende lesbare **JSON-Zustandsdateien** aus `archicord_data/`, `deathlinks/` und `tracker/settings/`. Dazu gehören, sofern vorhanden, Multiworld-Instanzen, Seed-Status, DeathLink-Zähler, Slot-Claims, Wishlist und Overlay-Profile.
- **Nicht enthalten:** `.env`, Tokens, Passwörter aus JSON-Feldern mit typischen Geheimnisnamen, APWorld-Dateien, YAMLs, Seed-ZIPs, Sounds, Python-Code und Logs.
- Credential-Felder in JSON-Kopien werden geleert; die Originaldateien bleiben unverändert. Backups **können trotzdem private Spielerdaten oder Raum-Metadaten enthalten**, deshalb nur lokal verwahren und nicht öffentlich hochladen.
- Bei fehlenden JSON-Daten wird kein leeres ZIP erzeugt; einzelne ungültige oder übergroße Dateien werden ausgelassen.
- Archive werden vor ihrer Freigabe geprüft. Der Manager entfernt im Rotationsschritt ausschließlich seine eigenen `archicord-*.zip`-Dateien.

### Einstellungen (optional)

Die Datei `config/maintenance.json` wird nur **lokal** gespeichert und ist in `.gitignore` ausgeschlossen:

```json
{
  "enabled": true,
  "interval_hours": 24,
  "keep": 14
}
```

- `enabled: false` deaktiviert die automatischen Backups, nicht den Button für manuelle Backups.
- `interval_hours`: 1 bis 168 Stunden.
- `keep`: 1 bis 100 Archive.
- Änderungen werden beim nächsten geplanten Check erkannt; kein Bot-Neustart erforderlich.

### Daten wiederherstellen (bewusst nur manuell)

1. **Bot und WebUI stoppen.**
2. Das aktuelle `archicord_data/`, `deathlinks/` und `tracker/settings/` separat sichern.
3. Das gewählte lokale Backup-ZIP überprüfen (es enthält `manifest.json`).
4. Die benötigten JSON-Dateien in die jeweils passenden Ordner kopieren. **Nicht blind alles überschreiben**, insbesondere wenn ein neuerer Seed inzwischen hinzugekommen ist.
5. Konfigurationen mit entfernten Passwortfeldern gegebenenfalls in der WebUI ergänzen.

Ein automatischer Restore ist aus Sicherheitsgründen nicht implementiert.

## Health Monitor

Die Seite basiert auf **lokalen Prozess- und Statusdaten**, nicht auf einer zweiten Archipelago-Verbindung:

- **Bot und Discord:** zuletzt beobachteter Status der laufenden WebUI-Bot-Sitzung.
- **Archipelago:** vom Bot übermittelte Statusinformation (bei älteren ArchiCord-Versionen ein zusammengefasster Status).
- **Instanzen:** `archicord_data/instances/<instanz>/status.json` (falls vorhanden); ein Heartbeat über 120 Sekunden alt gilt als **veraltet**, nicht als online.
- **Universal Tracker:** Frische der Datei `tracker/exports/live_checks.json` (unter 5 Minuten = kürzlich aktualisiert). Dies beweist **keine korrekte APWorld-Logik**.
- **Speicherplatz:** freier Platz auf dem lokalen Dateisystem; unter 500 MiB wird gewarnt.
- **Backupstatus:** letzter Sicherungszeitpunkt, Anzahl und generischer Fehlerhinweis.

Es werden keine Discord-Nachrichten versendet, keine AP-Verbindungen neu gestartet und keine DeathLink-Boards bearbeitet.

## Grenzen

- **Die Sicherungsplanung läuft nur während die WebUI läuft.** Wenn sie ausgeschaltet ist, werden keine Zeitpläne im Hintergrund ausgeführt; beim nächsten Start wird die Fälligkeit erneut geprüft.
- Der Health Monitor überwacht ohne gesonderte Autorisierung keine fremden Prozesse und kann bei einem abweichenden `ARCHICORD_DATA_DIR` nur auf den tatsächlich konfigurierten Ordner zugreifen.
- Ein aktueller Heartbeat bestätigt nicht, dass jeder einzelne Item- oder Universal-Tracker-Ablauf korrekt funktioniert.
- Die vollständige lokale ArchiCord-Version mit Overlay und Multi-Seed-Clients ist im GitHub-`main` momentan **noch nicht vollständig synchronisiert**. Dieser PR ist für den vorhandenen GitHub-Stand als additive Funktion umgesetzt; vor dem produktiven Wechsel unbedingt einen Gesamtvergleich vornehmen.
