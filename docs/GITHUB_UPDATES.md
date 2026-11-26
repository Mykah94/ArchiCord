# Updates über GitHub

ArchiCord wird in **Mykah94/ArchiCord** verwaltet. Neue Funktionen und Fehlerbehebungen werden vorzugsweise als **Pull Request (PR)** entwickelt und geprüft, bevor sie nach `main` gelangen.

## Ablauf

1. Ein Update auf Basis des aktuellen `main`-Branches vorbereiten (z. B. `feature/overlay-audio` oder `fix/deathlink-board`).
2. Nur die geänderten Projektdateien committen. **Keine** persönlichen Konfigurationsdateien, Zugangsdaten, APWorlds, Seed-Archive, Spieler-YAMLs oder Laufzeitdaten pushen.
3. In GitHub einen Pull Request von diesem Branch nach `main` eröffnen. Änderungen, Risikobereiche und Testergebnisse dokumentieren.
4. GitHub Actions prüft Python 3.11 und 3.13 auf Syntaxfehler, führt `pytest` aus und sucht nach bekannten unerwünschten lokalen Dateien.
5. Bei grünen Checks und nach Prüfung des Diffs kann der PR nach `main` übernommen werden. Der tatsächliche Discord-/Archipelago-/OBS-Livetest ist bei entsprechenden Änderungen weiterhin nötig.

## Lokal testen

```powershell
py -3 -m pip install -r requirements-dev.txt
py -3 -m pytest -q
```

Beim ersten Start auf einem neuen Rechner die `.env.example` lokal nach `.env` kopieren. Eine bestehende `.env` bei Updates **niemals ersetzen**. `.env`, `archicord_data/`, `deathlinks/`, `tracker/seeds/`, `tracker/yamls/`, `tracker/apworlds/` sowie benutzerspezifische Einstellungen bleiben lokal und gehören nicht in Git.

## Automatisierung – Umfang und Grenzen

Der Workflow wird automatisch bei Pushes auf `main`, bei PRs nach `main` und manuell über **Actions → ArchiCord CI → Run workflow** ausgeführt.

**GitHub lädt Änderungen nicht von deinem Windows-PC hoch** und kann keine Codeänderungen aus einem Chat selbständig nachholen. Bei einem neuen Auftrag kann ChatGPT über die verbundene GitHub-Integration Änderungen im Repository vorbereiten und einen PR erstellen. Das ist kein kontinuierlicher Hintergrunddienst.

Für eine zusätzliche Freigabesperre kann der Repository-Eigentümer in **Settings → Branches / Rules → Rulesets** eine Regel für `main` einrichten, die Pull Requests und erfolgreiche Statuschecks verlangt. Ob diese Funktion für dein Repository verfügbar ist, hängt von GitHub-Plan und Sichtbarkeit ab.

## Sicherheit

Die CI-Kontrolle erkennt einige bekannte Dateinamen und private Pfade, aber **keine beliebigen in Quelltext eingefügten Geheimnisse**. Prüfe jeden PR auf Token, Passwörter, API-Schlüssel und private Slot-/Spielerdaten. Ein versehentlich öffentlich gemachter Discord-Token muss beim Anbieter rotiert werden; reines Löschen aus einem Commit genügt nicht.
