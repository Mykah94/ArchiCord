"""Optional Universal Tracker CLI bridge.

Only exact known location names are accepted as doable checks. Launcher output
with missing/ambiguous data fails closed rather than inventing progress.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit


def _connect_uri(ap_url: str, slot: str, password: str) -> str:
    url = urlsplit(ap_url)
    if url.scheme not in ("ws", "wss") or not url.hostname or not url.port:
        raise ValueError("Ungültige Archipelago-Verbindungsadresse")
    host = url.hostname
    if ":" in host:
        host = f"[{host}]"
    return ("archipelago://" + quote(slot, safe="") + ":" +
            quote(password if password else "None", safe="") + "@" +
            host + ":" + str(url.port))


def parse_locations(output: str, known: dict[int, str]) -> list[int]:
    """Map exact CLI lines to AP IDs, rejecting unclear or empty results."""
    by_name = {}
    for ident, name in known.items():
        if isinstance(name, str):
            by_name.setdefault(name.strip(), []).append(int(ident))
    if not by_name:
        raise ValueError("Kein Location-Datenpaket vorhanden")
    found = set()
    for raw in output.splitlines():
        name = raw.strip()
        # UT --list prints locations as plain lines; all other log lines
        # are discarded. An exact match is required.
        if name not in by_name:
            continue
        ids = by_name[name]
        if len(ids) != 1:
            raise ValueError("Mehrdeutiger Location-Name aus Universal Tracker")
        found.add(ids[0])
    if not found:
        raise ValueError("Universal Tracker lieferte keine eindeutig zuordenbaren Locations")
    return sorted(found)


async def fetch_slot(
    launcher: Path, ap_url: str, slot: str, password: str,
    known: dict[int, str], timeout: int = 90
) -> list[int]:
    """Run launcher without a shell, apply time/size limits, never echo secrets."""
    executable = Path(launcher).expanduser()
    if not executable.is_file():
        raise ValueError("Universal-Tracker-Launcher nicht gefunden")
    if not 5 <= timeout <= 300:
        raise ValueError("Ungültiges Timeout")
    uri = _connect_uri(ap_url, slot, password)
    proc = await asyncio.create_subprocess_exec(
        str(executable), "Universal Tracker", "--", "--nogui", "--list", uri,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        # Stream output bounded to 4 MiB and a total wall-clock timeout.
        async def collect():
            chunks = []
            total = 0
            while True:
                part = await proc.stdout.read(65536)
                if not part:
                    break
                total += len(part)
                if total > 4 * 1024 * 1024:
                    raise ValueError("Universal-Tracker-Ausgabe ist zu groß")
                chunks.append(part)
            await proc.wait()
            return b"".join(chunks)
        raw = await asyncio.wait_for(collect(), timeout=timeout)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    if proc.returncode != 0:
        raise ValueError("Universal Tracker ist fehlgeschlagen (Launcher, YAML und APWorld prüfen)")
    return parse_locations(raw.decode("utf-8", errors="replace"), known)


def write_snapshot(output: Path, seed: str, team: int, players: dict,
                   failures: dict, selection_revision: str = "legacy-all") -> None:
    """Persist atomically so the bot never reads partial JSON."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seed_name": seed, "team": team, "players": players,
               "failures": failures, "selection_revision": selection_revision}
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
