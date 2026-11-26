# Universal Tracker and doable checks 🧩

Universal Tracker is optional. ArchiCord shows **no logic data** when it cannot obtain reliable tracker results; it does **not** estimate doable checks from a list of unvisited locations.

## Setup

1. Install a compatible local Archipelago distribution, Universal Tracker, player YAMLs and APWorld versions.
2. Set `ARCHICORD_UT_LAUNCHER` to the real local launcher executable.
3. Optionally adjust `ARCHICORD_UT_INTERVAL` and `ARCHICORD_CHECKS_FILE`.
4. Select games at `http://127.0.0.1:8765/apworlds`.
5. Start the bot and inspect log lines prefixed `[UT]`.

The launcher is invoked **without a shell**, using the expected arguments:

```text
<Launcher> "Universal Tracker" -- --nogui --list <archipelago-URI>
```

The reconstructed bridge maps only **exact, unique** CLI location names to IDs from the Archipelago location data package. An unknown, incompatible or failed response does not become a successful snapshot. The bot excludes already-completed checks from confirmed `doable` locations.

## Limits and security

The original bridge was unavailable in Git history. The reconstructed implementation has automated tests, **not** confirmed end-to-end compatibility with a real Windows Universal Tracker setup.

The connection URI may contain the Archipelago password as a process argument. Users with permission to inspect local processes might read it. Run ArchiCord on a trusted machine/account.

If Universal Tracker outputs a different format, investigate it instead of making the parser permissive or fabricating results.

The saved selection at `tracker/settings/apworld_selection.json` controls **ArchiCord's queries only**, not which worlds a separate launcher loads. No saved selection retains the default “all games” behavior; an explicitly empty selection disables queries for all games.
