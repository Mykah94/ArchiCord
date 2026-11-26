"""Additional multiworld community features adapted from the user-provided package.

Only applies to a single room's persisted state. Every operation requires a
Discord guild context; no cross-guild slot claims or wishlist leakage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time

MAX_WISHES=30
MAX_SEEN=15000
MAX_RUNS=300
def _key(guild): return str(int(guild))
def _owners(state,guild): return state.setdefault("slot_claims",{}).setdefault(_key(guild),{})
def claimed(state,guild,user):
    for slot, owner in _owners(state,guild).items():
        if str(owner)==str(user): return int(slot)
    return None

def claim(state,guild,user,slot,available):
    slot=int(slot)
    if slot not in available: return False,"Slot not present in this seed"
    owners=_owners(state,guild)
    if claimed(state,guild,user) is not None: return False,"You already claimed a slot"
    if str(slot) in owners: return False,"Already claimed"
    owners[str(slot)]=str(int(user))
    return True,"Slot claimed"

def release(state,guild,user,slot=None,admin=False):
    owners=_owners(state,guild)
    slot=claimed(state,guild,user) if slot is None else int(slot)
    if slot is None or str(slot) not in owners: return False,"Slot not claimed"
    if not admin and owners[str(slot)]!=str(user): return False,"Not your slot"
    del owners[str(slot)]
    return True,"Slot released"

def slot_claims(state,guild):
    return {int(slot):int(user) for slot,user in _owners(state,guild).items()}

def profile(state,guild,user):
    p=state.setdefault("wishlists",{}).setdefault(_key(guild),{}).setdefault(
        str(int(user)),{"notify":False,"items":[]})
    p.setdefault("notify",False);p.setdefault("items",[])
    return p

def _item(value): return re.sub(r"\s+"," ",str(value).strip()).casefold()

def wish_add(state,guild,user,slot,name):
    if not isinstance(name,str) or not name.strip() or len(name)>120 or any(ord(c)<32 for c in name):
        return False,"Invalid item name"
    p=profile(state,guild,user)
    if len(p["items"])>=MAX_WISHES: return False,"Wishlist full"
    if any(w["slot"]==int(slot) and _item(w["name"])==_item(name) for w in p["items"]):
        return False,"Already wished"
    p["items"].append({"slot":int(slot),"name":name.strip(),"found":False,
                       "finder":"","location":"","found_at":None})
    return True,"Added to wishlist"

def wish_remove(state,guild,user,name,slot=None):
    p=profile(state,guild,user)
    matches=[w for w in p["items"] if _item(w["name"])==_item(name) and
             (slot is None or w["slot"]==int(slot))]
    if len(matches)!=1: return False,"Wish not uniquely found"
    p["items"].remove(matches[0])
    return True,"Removed"

def wish_match(state,receiver,item_name,finder,location,event_key):
    """Mark new delivered items, notify opt-in users only once per event."""
    seen=state.setdefault("wishlist_seen_events",[])
    if not event_key or event_key in seen:return []
    seen.append(event_key);del seen[:-MAX_SEEN]
    notifications=[]
    for guild,users in state.get("wishlists",{}).items():
        for user,p in users.items():
            for wish in p.get("items",[]):
                if (wish.get("found") or wish.get("slot")!=int(receiver)
                    or _item(wish.get("name",""))!=_item(item_name)): continue
                wish.update(found=True,found_at=time.time(),
                            finder=str(finder)[:120],location=str(location)[:120])
                if p.get("notify"): notifications.append((int(guild),int(user),dict(wish)))
    return notifications

def _run_id(guild,seed,team):
    raw=json.dumps([str(guild),str(seed),int(team)],separators=(",",":"),ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def run_entry(state,guild,seed,team):
    value=state.setdefault("run_threads",{}).get(_run_id(guild,seed,team))
    return dict(value) if isinstance(value,dict) else None

def run_begin(state,guild,seed,team,parent,thread,*,restart=False):
    key=_run_id(guild,seed,team)
    if not seed or not all(str(value).isdigit() for value in (guild,parent,thread)):
        raise ValueError("Invalid run identity")
    runs=state.setdefault("run_threads",{})
    old=runs.get(key)
    if old and (old.get("status")=="active" or not restart):
        raise ValueError("Run already exists; explicitly restart a closed run")
    value={"guild_id":str(guild),"seed":str(seed),"team":int(team),"parent_id":str(parent),
           "thread_id":str(thread),"status":"active","created_at":int(time.time()),
           "closed_at":None,"message_id":""}
    runs[key]=value
    if len(runs)>MAX_RUNS:
        for older in list(runs):
            if older!=key and runs[older].get("status")!="active":
                del runs[older]
                if len(runs)<=MAX_RUNS:break
    return dict(value)

def run_end(state,guild,seed,team,status):
    if status not in ("archived","deleted"):raise ValueError("Invalid run end")
    key=_run_id(guild,seed,team)
    item=state.setdefault("run_threads",{}).get(key)
    if not isinstance(item,dict) or item.get("status")!="active":
        raise ValueError("No active run")
    item.update(status=status,closed_at=int(time.time()))
    return dict(item)
