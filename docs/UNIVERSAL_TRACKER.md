# Universal Tracker und Doable Checks

Universal Tracker ist optional. Ohne erfolgreiche Logikabfrage zeigt ArchiCord keine erfundenen Doable-Zahlen an.

1. Lokale Archipelago-Installation und Universal Tracker mit passenden APWorld-Versionen und Spieler-YAMLs einrichten.
2. `ARCHICORD_UT_LAUNCHER` auf die lokale ausführbare Launcher-Datei setzen.
3. `ARCHICORD_UT_INTERVAL` und `ARCHICORD_CHECKS_FILE` nach Bedarf setzen.
4. In `http://127.0.0.1:8765/apworlds` die APWorlds auswählen.
5. Bot starten und `[UT]`-Logs prüfen.

Der Launcher wird ohne Shell aufgerufen: `<Launcher> "Universal Tracker" -- --nogui --list <archipelago-URI>`. Die neue Bridge ordnet ausschließlich exakte und eindeutige Namen aus dem AP-Location-Datenpaket IDs zu. Bei Fehlern oder einem nicht erkannten Format erfolgt **kein** Erfolgs-Snapshot. Pro Slot werden erfolgreich ermittelte IDs als `doable` gespeichert; bereits erledigte Checks werden im Bot herausgefiltert.

**Einschränkung:** Die Originalimplementierung der Bridge war nicht in GitHub vorhanden. Die rekonstruierte Variante wurde durch automatisierte Tests geprüft, aber noch **nicht** mit einer echten Windows-/Universal-Tracker-Installation. Der CLI-Verbindungsparameter enthält ein Passwort gegebenenfalls als Prozessargument; den Host deshalb nur vertrauenswürdigen lokalen Nutzern zugänglich machen. Wenn der Universal Tracker andere Ausgaben erzeugt, darf der Parser nicht einfach auf permissives Zählen umgestellt werden.

Die Auswahl in `tracker/settings/apworld_selection.json` steuert nur ArchiCords Abfragen, nicht das Laden der Worlds im externen Launcher. Keine Auswahl entspricht bisherigem Verhalten (alle Spiele), eine explizit leere Auswahl deaktiviert die Abfrage für alle Spiele.
