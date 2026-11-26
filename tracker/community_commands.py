"""Discord run-thread, slot-claim and wishlist commands for parallel rooms.

Adapted from the user-provided package without replacing legacy /archi
commands. Every action is tied to the invoking Discord guild and one room.
"""
from __future__ import annotations

import discord
from discord import app_commands

from tracker.community_features import (
    claim, claimed, release, slot_claims, profile, wish_add, wish_remove,
    run_entry, run_begin, run_end,
)


def moderator(interaction: discord.Interaction) -> bool:
    member=interaction.user
    perms=getattr(member,"guild_permissions",None)
    return bool(perms and (perms.manage_threads or perms.manage_guild or perms.administrator))


async def choose(client, interaction, instance: str | None):
    if not interaction.guild_id:
        await interaction.response.send_message("Only available in Discord servers.",ephemeral=True)
        return None
    rooms=client.multi_seed.for_guild(interaction.guild_id)
    if instance:
        rooms=[r for r in rooms if r.id.casefold()==instance.casefold()]
    if len(rooms)!=1:
        labels=", ".join(r.id for r in rooms[:12]) or "none"
        await interaction.response.send_message(
            f"Choose a unique room with instanz. Available: {labels}",ephemeral=True)
        return None
    room=rooms[0]
    if not room.connected or not room.seed:
        await interaction.response.send_message("The selected Multiworld is not connected.",ephemeral=True)
        return None
    return room


async def answer(interaction,message):
    await interaction.response.send_message(message,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())


class RunCommands(app_commands.Group):
    def __init__(self,client):
        super().__init__(name="run",description="Manage per-seed Multiworld Discord threads")
        self.client=client

    @app_commands.command(name="starten",description="Create/reopen a thread for this seed")
    async def starten(self,interaction:discord.Interaction,instanz:str|None=None):
        if not moderator(interaction):
            return await answer(interaction,"Manage Threads permission required.")
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        cfg=room.config
        parent_id=cfg.get("thread_parent_channel_id") or cfg.get("status_channel_id")
        if not parent_id:
            return await answer(interaction,"Set a thread parent or status channel in the WebUI.")
        previous=run_entry(room.state,interaction.guild_id,room.seed,room.team)
        if previous and previous.get("status")=="active":
            return await answer(interaction,"Run already has an active thread.")
        try:
            channel=self.client.get_channel(int(parent_id)) or await self.client.fetch_channel(int(parent_id))
            if not isinstance(channel,discord.TextChannel) or channel.guild.id!=interaction.guild_id:
                return await answer(interaction,"Thread parent must be a text channel in this guild.")
            thread=await channel.create_thread(
                name=f"🌈 {room.config['name'][:30]} · {room.seed[:40]}",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,
                reason="ArchiCord Multiworld run")
            value=run_begin(room.state,interaction.guild_id,room.seed,room.team,parent_id,thread.id,
                            restart=bool(previous))
            room.save_state()
            embed=room.embed("🌈 Multiworld run started",
                             f"Seed: **{room.seed[:140]}**\nTeam: **{room.team}**\nInstance: **{room.id}**")
            await thread.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
            await answer(interaction,f"Run thread created: {thread.mention}")
        except (discord.Forbidden,discord.HTTPException,ValueError) as exc:
            await answer(interaction,f"Cannot create run thread: {type(exc).__name__}")

    @app_commands.command(name="beenden",description="Archive or delete the current seed thread")
    @app_commands.choices(aktion=[app_commands.Choice(name="Archive",value="archived"),
                                   app_commands.Choice(name="Delete",value="deleted")])
    async def beenden(self,interaction:discord.Interaction,
                      aktion:app_commands.Choice[str],instanz:str|None=None):
        if not moderator(interaction):
            return await answer(interaction,"Manage Threads permission required.")
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        entry=run_entry(room.state,interaction.guild_id,room.seed,room.team)
        if not entry or entry.get("status")!="active":
            return await answer(interaction,"No active run thread.")
        try:
            thread=self.client.get_channel(int(entry["thread_id"])) or await self.client.fetch_channel(int(entry["thread_id"]))
            if not isinstance(thread,discord.Thread) or thread.guild.id!=interaction.guild_id:
                return await answer(interaction,"Thread does not belong to this guild.")
            if aktion.value=="deleted":
                await thread.delete(reason=f"ArchiCord run ended by {interaction.user.id}")
            else:
                await thread.edit(archived=True,locked=True,reason="ArchiCord run archived")
            run_end(room.state,interaction.guild_id,room.seed,room.team,aktion.value)
            room.save_state()
            await answer(interaction,"Run thread "+aktion.value+".")
        except (discord.Forbidden,discord.HTTPException,ValueError) as exc:
            await answer(interaction,"Run could not be finished: "+type(exc).__name__)

    @app_commands.command(name="thread",description="Show the run thread for the current seed")
    async def thread(self,interaction:discord.Interaction,instanz:str|None=None):
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        entry=run_entry(room.state,interaction.guild_id,room.seed,room.team)
        await answer(interaction,f"Thread: <#{entry['thread_id']}> · {entry['status']}"
                     if entry else "No run thread for this seed.")


class SlotCommands(app_commands.Group):
    def __init__(self,client):
        super().__init__(name="slot",description="Claim a Multiworld player slot")
        self.client=client

    @app_commands.command(name="claim",description="Claim a player slot for your Discord user")
    async def claim_cmd(self,interaction:discord.Interaction,spieler:str,instanz:str|None=None):
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        matches=[ident for ident,name in room.players.items()
                 if str(ident)==spieler or name.casefold()==spieler.casefold()]
        if len(matches)!=1:return await answer(interaction,"Player name or slot ID is not unique.")
        ok,msg=claim(room.state,interaction.guild_id,interaction.user.id,matches[0],set(room.players))
        if ok:room.save_state()
        await answer(interaction,msg)

    @app_commands.command(name="freigeben",description="Release your slot (moderators may specify a slot)")
    async def freigeben(self,interaction:discord.Interaction,spieler:int|None=None,instanz:str|None=None):
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        ok,msg=release(room.state,interaction.guild_id,interaction.user.id,spieler,moderator(interaction))
        if ok:room.save_state()
        await answer(interaction,msg)

    @app_commands.command(name="liste",description="Show claimed slots in this Multiworld")
    async def liste(self,interaction:discord.Interaction,instanz:str|None=None):
        room=await choose(self.client,interaction,instanz)
        if room is None:return
        claims=slot_claims(room.state,interaction.guild_id)
        lines=[f"{room.player(slot)} (#{slot}) → <@{user}>"
               for slot,user in sorted(claims.items())[:40]]
        await answer(interaction,"\n".join(lines) or "No claimed slots.")


class WishlistCommands(app_commands.Group):
    def __init__(self,client):
        super().__init__(name="wishlist",description="Manage your item wishlists per seed")
        self.client=client

    async def _owned(self,interaction,instanz):
        room=await choose(self.client,interaction,instanz)
        if room is None:return None,None
        slot=claimed(room.state,interaction.guild_id,interaction.user.id)
        if slot is None:
            await answer(interaction,"Claim your player slot using /slot claim first.")
            return None,None
        return room,slot

    @app_commands.command(name="add",description="Add an item to your claimed slot's wishlist")
    async def add(self,interaction:discord.Interaction,item:str,instanz:str|None=None):
        room,slot=await self._owned(interaction,instanz)
        if room is None:return
        ok,msg=wish_add(room.state,interaction.guild_id,interaction.user.id,slot,item)
        if ok:room.save_state()
        await answer(interaction,msg)

    @app_commands.command(name="entfernen",description="Remove a wishlist item")
    async def entfernen(self,interaction:discord.Interaction,item:str,instanz:str|None=None):
        room,slot=await self._owned(interaction,instanz)
        if room is None:return
        ok,msg=wish_remove(room.state,interaction.guild_id,interaction.user.id,item,slot)
        if ok:room.save_state()
        await answer(interaction,msg)

    @app_commands.command(name="liste",description="Show your wishlist")
    async def liste(self,interaction:discord.Interaction,instanz:str|None=None):
        room,slot=await self._owned(interaction,instanz)
        if room is None:return
        rows=profile(room.state,interaction.guild_id,interaction.user.id)["items"]
        await answer(interaction,"\n".join(
            ("✅ " if w["found"] else "❔ ")+w["name"] for w in rows[:30])
            or "Wishlist is empty.")

    @app_commands.command(name="benachrichtigung",description="Enable/disable private wishlist notifications")
    async def benachrichtigung(self,interaction:discord.Interaction,aktiv:bool,instanz:str|None=None):
        room,slot=await self._owned(interaction,instanz)
        if room is None:return
        profile(room.state,interaction.guild_id,interaction.user.id)["notify"]=aktiv
        room.save_state()
        await answer(interaction,"Wishlist notifications "+("enabled" if aktiv else "disabled")+".")
