"""Local Universal Tracker configuration and non-executing path diagnostics.

Adapts the uploaded package's tracker-settings subsystem without importing its
older file layout or launching any executable during validation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from tracker.multi_instances import atomic_json,safe_read

KEYS=("launcher_path","install_dir","yaml_dir","seed_dir","apworld_dir")

def defaults(root:Path,env=None):
    e=os.environ if env is None else env
    return {
        "launcher_path":e.get("ARCHICORD_UT_LAUNCHER",""),
        "install_dir":e.get("ARCHICORD_AP_INSTALL_DIR",r"C:\ProgramData\Archipelago"),
        "yaml_dir":str(root/"tracker"/"yamls"),
        "seed_dir":str(root/"tracker"/"seeds"),
        "apworld_dir":str(root/"tracker"/"apworlds"),
    }

def path_file(root:Path):
    return root/"tracker"/"settings"/"ut_paths.json"

def load_settings(root:Path,env=None):
    values=defaults(root,env)
    raw=safe_read(path_file(root),{})
    if isinstance(raw,dict):
        values.update({k:raw[k] for k in KEYS if isinstance(raw.get(k),str)})
    return values

def validate_settings(raw:Any):
    if not isinstance(raw,dict) or any(k not in KEYS for k in raw):
        raise ValueError("Invalid tracker settings")
    result={}
    for key in KEYS:
        value=raw.get(key,"")
        if not isinstance(value,str) or len(value)>1024 or any(c in value for c in "\r\n\x00"):
            raise ValueError("Invalid tracker path")
        value=value.strip().strip('"')
        if key=="launcher_path" and value and Path(value).suffix.lower()!=".exe":
            raise ValueError("Tracker launcher must be a .exe file")
        result[key]=value
    return result

def save_settings(root:Path,raw:Any):
    current=load_settings(root)
    current.update(validate_settings(raw))
    atomic_json(path_file(root),{"version":1,**current})
    return current

def diagnose(settings:dict):
    result=[]
    for key in KEYS:
        raw=str(settings.get(key,"")).strip()
        if not raw:
            status="warning"; message="Not configured"
        else:
            p=Path(raw)
            found=p.is_file() if key=="launcher_path" else p.is_dir()
            status="ok" if found else "error"
            message="Found" if found else "Not found"
        result.append({"key":key,"status":status,"message":message})
    return result
