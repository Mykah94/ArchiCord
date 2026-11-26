"""Small native desktop notification cards for ArchiCord Overlay Studio.

Only called on the Tk main thread. Popups are opt-in, use sanitized event text,
and never make requests to Discord or spawn subprocesses.
"""
from __future__ import annotations

import time

COLORS={"progression":"#a94cf7","item":"#ffdb54","trap":"#ff4b8e",
        "hint":"#318cf8","goal":"#50e282","deathlink":"#ff4b8e"}

def clip_text(value,limit=84)->str:
    return " ".join(str(value or "").split())[:limit]

def position(screen_w:int,screen_h:int,width:int=430,height:int=132,
             x_pct:float=.93,y_pct:float=.12)->tuple[int,int]:
    x=max(0,min(screen_w-width,int(screen_w*x_pct)-width))
    y=max(0,min(screen_h-height,int(screen_h*y_pct)))
    return x,y

class ScreenNotificationManager:
    def __init__(self,root):
        self.root=root
        self.visible=[]
    def show(self,category:str,item:str,actor:str="",duration_ms:int=4800):
        import tkinter as tk
        if category not in COLORS:return
        win=tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost",True)
        color=COLORS[category]
        width,height=435,137
        x,y=position(win.winfo_screenwidth(),win.winfo_screenheight(),width,height,
                     y_pct=.12+len(self.visible)*.17)
        win.geometry(f"{width}x{height}+{x}+{y}")
        shell=tk.Frame(win,bg="#11172d",highlightthickness=3,highlightbackground=color)
        shell.pack(fill="both",expand=True)
        tk.Label(shell,text="🌈 ARCHICORD · "+category.upper(),bg="#11172d",fg=color,
                 anchor="w",font=("Segoe UI",13,"bold")).pack(fill="x",padx=16,pady=(10,4))
        tk.Label(shell,text=clip_text(item),bg="#11172d",fg="#f4f3ff",
                 anchor="w",font=("Segoe UI",17,"bold"),wraplength=390).pack(fill="x",padx=16)
        tk.Label(shell,text=clip_text(actor),bg="#11172d",fg="#bbc4e0",
                 anchor="w",font=("Segoe UI",11)).pack(fill="x",padx=16)
        self.visible.append(win)
        def close():
            if win in self.visible:self.visible.remove(win)
            try:win.destroy()
            except tk.TclError:pass
        win.after(max(1000,min(duration_ms,15000)),close)
        return win
    def close_all(self):
        for win in list(self.visible):
            try:win.destroy()
            except Exception:pass
        self.visible.clear()
