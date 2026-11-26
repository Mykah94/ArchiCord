"""Local-only user-supplied WAV sounds for ArchiCord notifications."""
from __future__ import annotations

from pathlib import Path
import re
import sys

def sound_directory(root:Path)->Path:
    return Path(root)/"overlay_sounds"

def available_sounds(root:Path)->list[str]:
    path=sound_directory(root)
    if not path.is_dir() or path.is_symlink():return []
    return sorted(p.name for p in path.iterdir()
                  if p.is_file() and not p.is_symlink() and p.suffix.lower()==".wav"
                  and p.stat().st_size<=8*1024*1024)[:100]

def resolve_sound(root:Path,value:str)->Path|None:
    if not isinstance(value,str) or not re.fullmatch(r"[a-zA-Z0-9._ -]{1,120}\.wav",value,re.I):
        return None
    path=sound_directory(root)/value
    if path.is_file() and not path.is_symlink() and path.name in available_sounds(root):
        return path
    return None

def play_sound(root:Path,value:str)->bool:
    path=resolve_sound(root,value)
    if not path or sys.platform!="win32":return False
    import winsound
    winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
    return True
