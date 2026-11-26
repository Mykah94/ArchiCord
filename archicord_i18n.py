"""Optional English/German translations of user-facing Discord embeds.

Default German content remains completely unchanged. Translations act only on
known ArchiCord strings, never on unknown game/player text.
"""
from __future__ import annotations

TEXTS = {
    "✨ Progression-Item ✨": "✨ Progression Item ✨",
    "🪤 Trap-Item": "🪤 Trap Item",
    "🔎 Progression-Hint": "🔎 Progression Hint",
    "🎉 Progression-Item gefunden!": "🎉 Progression item found!",
    "🏆 Spielziel erreicht!": "🏆 Goal reached!",
    "👥 Spieler-Status": "👥 Player status",
    "☠️ Live-DeathLink-Rangliste": "☠️ Live DeathLink leaderboard",
    "📈 Archipelago – Live-Fortschritt": "📈 Archipelago – Live progress",
    "🔎 Archipelago – Hintboard": "🔎 Archipelago – Hint board",
    "🏆 Ziele erreicht": "🏆 Goals completed",
    "🔎 Hints offen / gefunden": "🔎 Hints open / found",
    "Gesamte DeathLinks": "Total DeathLinks",
    "🎮 Spieler online": "🎮 Players online",
    "📡 Archipelago": "📡 Archipelago",
    "📍 Fundort": "📍 Location",
    "🌍 Von": "🌍 From",
    "🌍 Welt": "🌍 World",
    "🎯 Für": "🎯 For",
    "📌 Status": "📌 Status",
    "✅ Bereits gefunden": "✅ Already found",
    "✅ Jetzt gefunden": "✅ Found now",
    "❓ Noch nicht gefunden": "❓ Not found yet",
    "Noch keine DeathLinks in diesem Seed.": "No DeathLinks for this seed yet.",
    "Noch keine passenden Progression-Hints vorhanden.": "No matching progression hints.",
    "Noch keine Daten.": "No data yet.",
}
FRAGMENTS = {
    " hat das Ziel in ": " completed the goal in ",
    " erreicht.": ".",
    " · 🎯 Doable: keine Logikdaten": " · 🎯 Doable: no logic data",
    " · 🎯 Nicht ausgewählt": " · 🎯 Not selected",
    " aktuell machbar": " currently reachable",
    " · weitere Einträge:": " · more entries:",
    " · Check-Zahlen im Live-Fortschritt": " · check counts in live progress",
    "🔴 Getrennt": "🔴 Disconnected",
    "🟢 Verbunden": "🟢 Connected",
    "Noch kein": "No",
    "Unbekannt": "Unknown",
}


def localize_embed(embed, language: str):
    """Translate known static strings, preserving embeds and markup.

    The caller supplies a discord.Embed; returns a copy only for English.
    """
    if language != "en":
        return embed
    translated = embed.copy()
    if translated.title:
        title = translated.title
        for old, new in TEXTS.items():
            title = title.replace(old, new)
        if "TODE! EIN NEUER TIEFPUNKT!" in title:
            title = title.replace("TODE! EIN NEUER TIEFPUNKT!", "DEATHS! A NEW LOW!")
        translated.title = title
    if translated.description:
        desc = translated.description
        for old, new in TEXTS.items():
            desc = desc.replace(old, new)
        for old, new in FRAGMENTS.items():
            desc = desc.replace(old, new)
        # Preserve player names and counts without repeating German taunts.
        if " gestorben!" in desc and "\n\n" in desc:
            head = desc.split("\n\n", 1)[0]
            head = head.replace(" ist jetzt **", " has died **").replace("** gestorben!", "** times!")
            desc = head + "\n\nEven the respawn screen knows your name by now."
        translated.description = desc
    for index, field in enumerate(translated.fields):
        name, value = field.name, field.value
        for old, new in TEXTS.items():
            name = name.replace(old, new)
            value = value.replace(old, new)
        for old, new in FRAGMENTS.items():
            value = value.replace(old, new)
        translated.set_field_at(index, name=name, value=value, inline=field.inline)
    if translated.footer.text:
        footer = translated.footer.text
        for old, new in FRAGMENTS.items():
            footer = footer.replace(old, new)
        translated.set_footer(text=footer)
    return translated
