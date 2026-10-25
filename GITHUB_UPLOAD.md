# ArchiCord bei GitHub hochladen

## Variante A: Ohne Git-Kommandozeile

1. Auf github.com über **New repository** ein neues Repository, z. B. `ArchiCord`, anlegen.
2. ZIP **zuerst entpacken**. GitHub erwartet die Projektdateien, nicht ein einziges ZIP im Repository.
3. Im neuen Repository **Add file → Upload files** öffnen und den Inhalt des Ordners `ArchiCord` hochladen. Auch die Ordner `.github` und `webui_assets` mitnehmen. Versteckte Dateien wie `.gitignore`, `.gitattributes` und `.env.example` gehören dazu.
4. Dateien committen. **Keine `.env` oder privaten Tracker-Daten** hochladen.
5. Unter **Actions** sollte der Test-Workflow sichtbar sein.

## Variante B: Mit Git

Im entpackten Projektordner:

```bash
git init
git add .
git status
git commit -m "Initial ArchiCord release"
git branch -M main
git remote add origin https://github.com/DEIN_NUTZERNAME/ArchiCord.git
git push -u origin main
```

`DEIN_NUTZERNAME` durch deinen GitHub-Nutzernamen ersetzen; das neue GitHub-Repository vorher anlegen.

**Vor dem Push prüfen:** Mit `git status --short` und `git ls-files` kontrollieren, dass **keine** `.env`, `AP_...zip`, private YAMLs, DeathLink-Dateien oder Secrets enthalten sind.

## Nach dem Upload

- Repo-Beschreibung und Topics wie `archipelago`, `discord-bot`, `python`, `universal-tracker` setzen.
- Die gewünschte Lizenz unter **Add file → Create new file → LICENSE** explizit wählen. Ohne Lizenz ist die Wiederverwendung durch Dritte rechtlich eingeschränkt.
- Optional ein erstes Release aus dem aktuellen Stand erstellen.
