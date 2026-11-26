"""Native Windows ArchiCord Overlay Studio launcher and popup log.

Tk is imported lazily so headless CI and Linux bot installations do not
require a graphical display. The authoritative profile settings are shared
with the safe localhost browser Studio at port 8766.
"""
from __future__ import annotations

from pathlib import Path
import threading
import time
import webbrowser

from overlay_sounds import available_sounds,play_sound
from screen_notifications import ScreenNotificationManager

ROOT=Path(__file__).resolve().parent

class DesktopStudio:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        from overlay_studio import load_profiles,save_profiles,DATA_ROOT
        from tracker.multi_instances import read_instances,instance_directory
        from tracker.overlay_events import recent_events

        self.tk,self.ttk=tk,ttk
        self.load_profiles,self.save_profiles=load_profiles,save_profiles
        self.read_instances=read_instances
        self.instance_directory=instance_directory
        self.recent_events=recent_events
        self.data_root=DATA_ROOT
        self.root=tk.Tk()
        self.notifications=ScreenNotificationManager(self.root)
        self.popups_enabled=tk.BooleanVar(value=False)
        self.last_event_id=None
        self.root.title("ArchiCord · Overlay Studio")
        self.root.geometry("790x720")
        self.root.configure(bg="#10172c")
        self.root.minsize(630,550)
        self.message=tk.StringVar(value="Local desktop studio · no bot credentials required")
        self.profile_id=tk.StringVar()
        self.profile_name=tk.StringVar()
        self.instance=tk.StringVar()
        self.theme=tk.StringVar()
        self.effect=tk.StringVar()
        self.font_size=tk.StringVar()
        self.max_items=tk.StringVar()
        self.sound=tk.StringVar()
        self.data=self.load_profiles()
        self.ids={}
        self._ui()
        self.reload()
        self.root.after(2000,self.tick)

    def label(self,parent,text):
        return self.tk.Label(parent,text=text,fg="#d7d9fa",bg="#10172c",
                             font=("Segoe UI",10,"bold"),anchor="w")
    def button(self,parent,text,callback):
        return self.tk.Button(parent,text=text,command=callback,bg="#7657d8",
                              fg="white",relief="flat",padx=13,pady=8,
                              activebackground="#9e68e3")
    def _ui(self):
        tk=self.tk
        head=tk.Frame(self.root,bg="#10172c")
        head.pack(fill="x",padx=22,pady=15)
        tk.Label(head,text="🌈 ArchiCord Overlay Studio",fg="#efeaff",bg="#10172c",
                 font=("Segoe UI",21,"bold")).pack(anchor="w")
        tk.Label(head,text="Profile editor · OBS · Desktop live log",fg="#b3bce0",
                 bg="#10172c").pack(anchor="w")
        bar=tk.Frame(self.root,bg="#10172c");bar.pack(fill="x",padx=22,pady=8)
        self.button(bar,"Open Browser Studio",lambda:webbrowser.open("http://127.0.0.1:8766/")).pack(side="left",padx=3)
        self.button(bar,"Open OBS Source",self.open_obs).pack(side="left",padx=3)
        self.button(bar,"Show Log Window",self.popout).pack(side="left",padx=3)
        body=tk.Frame(self.root,bg="#10172c");body.pack(fill="both",expand=True,padx=22)
        self.controls={}
        specs=[("Profile","profile_id"),("Display name","profile_name"),
               ("Multiworld instance","instance"),("Theme","theme"),("Animation","effect"),
               ("Font size","font_size"),("Max events","max_items")]
        for number,(title,key) in enumerate(specs):
            self.label(body,title).grid(row=number,column=0,sticky="w",pady=8)
            row=tk.Frame(body,bg="#10172c");row.grid(row=number,column=1,sticky="ew",pady=5)
            if key in ("profile_id","instance","theme","effect"):
                ctrl=self.ttk.Combobox(row,textvariable=getattr(self,key),state="readonly")
                if key=='profile_id':
                    ctrl.bind("<<ComboboxSelected>>",lambda event:self.on_select())
            else:
                ctrl=tk.Entry(row,textvariable=getattr(self,key),fg="#20233a",font=("Segoe UI",11))
            ctrl.pack(fill="x")
            self.controls[key]=ctrl
        body.grid_columnconfigure(1,weight=1)
        actions=tk.Frame(self.root,bg="#10172c");actions.pack(fill="x",padx=22,pady=10)
        self.button(actions,"Save profile",self.save).pack(side="left",padx=3)
        self.button(actions,"Add profile",self.add).pack(side="left",padx=3)
        self.button(actions,"Delete profile",self.delete).pack(side="left",padx=3)
        sounds=tk.Frame(self.root,bg="#10172c");sounds.pack(fill="x",padx=22,pady=5)
        self.label(sounds,"Sound preview (WAV only)").pack(side="left")
        self.sounds=self.ttk.Combobox(sounds,textvariable=self.sound,state="readonly",width=30)
        self.sounds.pack(side="left",padx=8)
        self.button(sounds,"▶ Play",lambda:play_sound(ROOT,self.sound.get())).pack(side="left")
        tk.Checkbutton(sounds,text='Desktop pop-ups',variable=self.popups_enabled,
            bg='#10172c',fg='#ffffff',selectcolor='#222a45',activebackground='#10172c').pack(side='left')
        self.label(self.root,self.message.get()).pack_forget()
        tk.Label(self.root,textvariable=self.message,fg="#a6e4cc",bg="#10172c",
                 wraplength=680,anchor="w").pack(fill="x",padx=25,pady=15)
    def reload(self):
        self.data=self.load_profiles()
        self.controls["profile_id"]["values"]=[x["id"] for x in self.data["profiles"]]
        self.controls["theme"]["values"]=["archipelago","violet","cyan","gold","minimal"]
        self.controls["effect"]["values"]=["fade","slide","pop","none"]
        self.controls["instance"]["values"]=[""]+[x["id"] for x in self.read_instances(self.data_root)]
        self.sounds["values"]=available_sounds(ROOT)
        self.profile_id.set(self.data["selected"])
        self.on_select()
    def current(self):
        return next((p for p in self.data["profiles"] if p["id"]==self.profile_id.get()),None)
    def on_select(self):
        p=self.current()
        if p is None:return
        if self.data.get('selected')!=p['id']:
            self.last_event_id=None
        self.data["selected"]=p["id"]
        for key,control in [("profile_name","name"),("instance","instance"),("theme","theme"),
                            ("effect","effect"),("font_size","font_size"),("max_items","max_items")]:
            getattr(self,key).set(str(p[control]))
    def save(self):
        from tkinter import messagebox
        p=self.current()
        if p is None:return
        try:
            p.update(name=self.profile_name.get(),instance=self.instance.get(),
                     theme=self.theme.get(),effect=self.effect.get(),
                     font_size=int(self.font_size.get()),max_items=int(self.max_items.get()))
            self.save_profiles(self.data);self.message.set("Profile saved")
        except (ValueError,OSError) as exc:messagebox.showerror("ArchiCord",str(exc))
    def add(self):
        self.save()
        n=1
        while any(p["id"]=="profile"+str(n) for p in self.data["profiles"]):n+=1
        if len(self.data["profiles"])>=30:return
        self.data["profiles"].append({"id":"profile"+str(n),"name":"Profile "+str(n),
           "theme":"archipelago","effect":"fade","font_size":21,"max_items":8,
           "enabled":True,"instance":""})
        self.data["selected"]="profile"+str(n)
        self.save_profiles(self.data);self.reload()
    def delete(self):
        if len(self.data["profiles"])<=1:return
        self.data["profiles"]=[p for p in self.data["profiles"] if p["id"]!=self.profile_id.get()]
        self.data["selected"]=self.data["profiles"][0]["id"]
        self.save_profiles(self.data);self.reload()
    def open_obs(self):
        import urllib.parse
        webbrowser.open("http://127.0.0.1:8766/obs?profile="+
                        urllib.parse.quote(self.profile_id.get()))
    def popout(self):
        tk=self.tk
        if getattr(self,"pop",None) and self.pop.winfo_exists():
            self.pop.lift();return
        self.pop=tk.Toplevel(self.root)
        self.pop.title("ArchiCord · Live Log")
        self.pop.geometry("750x480")
        self.pop.configure(bg="#10172c")
        self.log=tk.Text(self.pop,bg="#161c33",fg="#eaeafb",font=("Consolas",13),
                         wrap="word",state="disabled")
        self.log.pack(fill="both",expand=True,padx=10,pady=10)
    def tick(self):
        if getattr(self,"pop",None) and self.pop.winfo_exists():
            p=self.current()
            if p and p.get("instance"):
                path=self.instance_directory(self.data_root,p["instance"])
                events=self.recent_events(path,limit=60)
                lines=["{timestamp}  {category:12} {item} · {player} → {recipient}".format(**ev)
                       for ev in events]
                self.log.configure(state="normal");self.log.delete("1.0","end")
                self.log.insert("end","\n".join(lines));self.log.configure(state="disabled")
        if self.popups_enabled.get():
            p=self.current()
            if p and p.get('instance'):
                events=self.recent_events(self.instance_directory(self.data_root,p['instance']),limit=20)
                newest=max((event['id'] for event in events),default=0)
                if self.last_event_id is not None:
                    for event in events:
                        if event['id']>self.last_event_id:
                            self.notifications.show(event['category'],event.get('item') or event['category'],
                                                    event.get('player',''))
                self.last_event_id=newest
        else:
            self.last_event_id=None
        self.root.after(2000,self.tick)
    def run(self):self.root.mainloop()

def main():
    import overlay_studio
    def server():
        try:overlay_studio.main(8766)
        except OSError as exc:print("Studio server unavailable:",type(exc).__name__)
    threading.Thread(target=server,daemon=True,name="ArchiCordOverlayStudio").start()
    DesktopStudio().run()

if __name__=="__main__":main()
