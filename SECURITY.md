# Sicherheit und private Daten

**Niemals committen oder öffentlich hochladen:**

- `.env` oder andere Dateien mit Discord-Token und Archipelago-Passwort
- `archicord_data/`, `deathlinks/`, private Spieler-YAMLs und Seed-/Spoiler-Dateien
- lokale Universal-Tracker-Exports und APWorlds ohne ausdrückliche Berechtigung

Diese Dateien sind in `.gitignore` berücksichtigt. Prüfe vor jedem Push trotzdem `git status` und `git diff --cached`.

## Discord-Token kompromittiert?

Token im Discord Developer Portal unter **Bot → Reset Token** erneuern und nur den neuen Wert lokal in `.env` speichern. Ein bereits veröffentlichter Token gilt als kompromittiert.

## WebUI

Die WebUI ist nur für lokalen Betrieb auf `127.0.0.1` gedacht. Sie bietet keine öffentliche Benutzeranmeldung. **Nicht öffentlich hosten oder per Reverse Proxy bereitstellen.** Die lokale `.env` wird nicht mit ausgeliefert, der Discord-Token bleibt über die Status-API verborgen. Das AP-Passwort ebenfalls.

## Externe `.apworld`-Archive

APWorlds können ausführbaren Python-Code enthalten, sobald Archipelago sie lädt. Installiere nur Worlds aus vertrauenswürdigen Quellen und in einer kompatiblen Version. Der reine Manifest-Scan in der WebUI führt ihren Python-Code nicht aus.

## Schwachstellen melden

Sicherheitsprobleme möglichst privat an die Repository-Verantwortlichen melden und keine Tokens in öffentliche GitHub-Issues schreiben.
