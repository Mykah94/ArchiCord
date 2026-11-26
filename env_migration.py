"""Non-destructive ArchiCord .env upgrade helper.

Keeps existing values and comments; only appends newly introduced keys from
.env.example. Before any mutation, saves an independent private backup.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import stat

KEY=re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")

def locate_env(root:Path)->Path:
    root=Path(root).resolve()
    for path in (root/".env",root.parent/".env",root.parent/"ArchiCord"/".env"):
        if path.is_file():return path
    return root/".env"

def merge_env(env_file:Path,template_file:Path,*,dry_run=False)->dict:
    env_file=Path(env_file);template_file=Path(template_file)
    template=template_file.read_text(encoding="utf-8-sig")
    entries={}
    for line in template.splitlines():
        match=KEY.match(line)
        if match and match.group(1) not in entries:entries[match.group(1)]=line
    existing=env_file.read_bytes() if env_file.exists() else b""
    text=existing.decode("utf-8-sig") if existing else ""
    known={m.group(1) for line in text.splitlines() if (m:=KEY.match(line))}
    added={k:line for k,line in entries.items() if k not in known}
    if not added:return {"added":[],"created":False,"backup":None}
    if dry_run:return {"added":list(added),"created":not env_file.exists(),"backup":None}
    env_file.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    if existing:
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        backup=env_file.with_name(env_file.name+".backup-"+stamp)
        n=1
        while backup.exists():
            backup=env_file.with_name(env_file.name+f".backup-{stamp}-{n}")
            n+=1
        with backup.open("xb") as fp:
            os.chmod(backup,0o600)
            fp.write(existing);fp.flush();os.fsync(fp.fileno())
    newline="\r\n" if b"\r\n" in existing else "\n"
    if text and not text.endswith(("\r","\n")):text+=newline
    text+=newline+"# New ArchiCord settings"+newline
    text+=newline.join(added.values())+newline
    tmp=env_file.with_name("."+env_file.name+"."+str(os.getpid())+".tmp")
    try:
        with tmp.open("xb") as fp:
            os.chmod(tmp,stat.S_IMODE(env_file.stat().st_mode) if env_file.exists() else 0o600)
            fp.write((("\ufeff" if existing.startswith(b"\xef\xbb\xbf") else "")+
                      text).encode("utf-8"))
            fp.flush();os.fsync(fp.fileno())
        os.replace(tmp,env_file)
    finally:tmp.unlink(missing_ok=True)
    return {"added":list(added),"created":not bool(existing),"backup":str(backup) if backup else None}

def main():
    parser=argparse.ArgumentParser(description="Safely merge new ArchiCord .env keys")
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    result=merge_env(locate_env(root),root/".env.example",dry_run=args.dry_run)
    print("New configuration keys: "+(", ".join(result["added"]) or "none"))
    print("Existing values and secrets are never printed.")
    return 0

if __name__=="__main__":raise SystemExit(main())
