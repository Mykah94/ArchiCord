"""Local-only ArchiCord Overlay Studio.

A safe, independently launchable browser studio inspired by the uploaded
Windows OBS package. It does not expose credentials or start the Discord bot.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qs,urlsplit

from tracker.multi_instances import atomic_json,read_instances,instance_directory,safe_read
from tracker.overlay_events import recent_events

ROOT=Path(__file__).resolve().parent
DATA_ROOT=ROOT/"archicord_data"
TOKEN=secrets.token_urlsafe(32)
THEMES=("archipelago","violet","cyan","gold","minimal")
EFFECTS=("fade","slide","pop","none")
KINDS=("item","progression","trap","hint","goal","deathlink")
COLORS={"archipelago":"#a94cf7","violet":"#8971f7","cyan":"#22d3ef","gold":"#ffdb54","minimal":"#ffffff"}

def profile_path()->Path:
    return DATA_ROOT/"overlay_profiles.json"

def default_profiles()->dict:
    return {"version":1,"profiles":[{"id":"default","name":"Default Rainbow",
             "theme":"archipelago","font_size":21,"effect":"slide",
             "max_items":8,"enabled":True,"instance":""}],
             "selected":"default"}

def valid_profiles(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get("profiles"),list):
        raise ValueError("Invalid overlay profile set")
    if len(raw["profiles"])>30:raise ValueError("At most 30 profiles")
    ids=set(); result=[]
    for row in raw["profiles"]:
        if not isinstance(row,dict):raise ValueError("Invalid profile")
        ident=row.get("id","")
        if not isinstance(ident,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,39}",ident) or ident in ids:
            raise ValueError("Profile IDs must be unique")
        ids.add(ident)
        name=row.get("name","")
        if not isinstance(name,str) or not 1<=len(name)<=90 or any(ord(c)<32 for c in name):
            raise ValueError("Invalid profile name")
        theme=row.get("theme","archipelago");effect=row.get("effect","slide")
        font=row.get("font_size",21);max_items=row.get("max_items",8)
        if theme not in THEMES or effect not in EFFECTS:
            raise ValueError("Unsupported profile style")
        if type(font) is not int or not 12<=font<=52 or type(max_items) is not int or not 1<=max_items<=25:
            raise ValueError("Font or item count out of range")
        instance=row.get("instance","")
        if not isinstance(instance,str) or (instance and
             not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}",instance)):
            raise ValueError("Invalid instance ID")
        result.append({"id":ident,"name":name,"theme":theme,"effect":effect,
                       "font_size":font,"max_items":max_items,
                       "enabled":row.get("enabled",True) is not False,"instance":instance})
    selected=raw.get("selected","default")
    if selected not in ids:raise ValueError("Selected overlay profile missing")
    return {"version":1,"profiles":result,"selected":selected}

def load_profiles():
    return valid_profiles(safe_read(profile_path(),default_profiles()))

def save_profiles(data):
    valid=valid_profiles(data)
    atomic_json(profile_path(),valid)
    return valid

def events(instance:str,limit=25):
    rooms=read_instances(DATA_ROOT)
    match=next((x for x in rooms if x["id"]==instance),None)
    if not match:return []
    path=instance_directory(DATA_ROOT,instance)
    status=safe_read(path/"status.json",{})
    seed=status.get("seed") if status.get("connected") else None
    return recent_events(path,limit=limit,seed=seed) if seed else []

CSS="""
*{box-sizing:border-box}body{margin:0;background:#0b1021;color:#f5f2ff;font-family:Inter,Poppins,"Segoe UI",sans-serif}
a{color:#7cd8ff}.wrap{max-width:1280px;margin:26px auto;padding:16px}
h1{font-size:35px;margin:6px 0 10px}.muted{color:#abb8dd}header{border-bottom:5px solid transparent;
border-image:linear-gradient(90deg,#a94cf7,#ff4b8e,#ffdb54,#50e282,#22d3ef,#318cf8) 1}
.layout{display:grid;grid-template-columns:380px minmax(0,1fr);gap:20px;margin-top:24px}
.panel{padding:21px;border-radius:20px;border:1px solid #6f6aab88;background:#171d36}
label{display:block;color:#aab8e1;font-size:14px;margin:14px 0}
input,select{display:block;width:100%;margin-top:5px;padding:12px;background:#0d142a;color:white;border:1px solid #676da3;border-radius:9px}
button{border:none;border-radius:10px;padding:12px 17px;color:white;font-weight:750;background:linear-gradient(125deg,#674ee3,#9e53c9);cursor:pointer;margin:8px 7px 8px 0}
#preview{border-radius:16px;background:#10172b;border:2px solid #a94cf7;padding:20px;min-height:180px}
#feed{display:flex;flex-direction:column;gap:12px}.event{padding:13px;border-left:5px solid #a94cf7;background:#1e2645;border-radius:10px}
.event strong{display:block}.event small{color:#bfc9ea}
@media(max-width:850px){.layout{grid-template-columns:1fr}}
"""
STUDIO='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchiCord Overlay Studio</title><style>__CSS__</style></head>
<body><header><div class="wrap"><h1>🌈 ArchiCord Overlay Studio</h1><p class="muted">Local design editor · Multiworld profiles · OBS Browser Sources</p></div></header>
<main class="wrap"><p><a href="http://127.0.0.1:8765/instanzen">Multiworld Manager</a></p><div class="layout"><section class="panel">
<h2>Overlay profile</h2><label>Profile<select id="choose"></select></label><button id="new">＋ New profile</button><button id="delete">Remove selected</button>
<label>Profile name<input id="name" maxlength="90"></label><label>Archipelago instance<select id="instance"></select></label>
<label>Theme<select id="theme"></select></label><label>Animation<select id="effect"></select></label>
<label>Font size<input id="size" type="number" min="12" max="52"></label>
<label>Events visible<input id="max" type="number" min="1" max="25"></label>
<label>Enabled<input id="enabled" type="checkbox"></label>
<button id="save">💾 Save studio profiles</button><p id="message" role="status" class="muted"></p>
</section><section class="panel"><h2>Live preview</h2><p class="muted">Profile settings apply to the OBS Browser Source once saved.</p><div id="preview"><h2>ArchiCord Live Log</h2><div id="feed"></div></div><p><a id="url" href="#" target="_blank" rel="noopener noreferrer">Open OBS Browser Source</a></p><p id="copy" class="muted"></p></section></div></main>
<script>
const KEY=__TOKEN__,themes=['archipelago','violet','cyan','gold','minimal'],effects=['fade','slide','pop','none'];let data={profiles:[],selected:'default'},rooms=[];
const el=id=>document.getElementById(id);
function opt(sel,value,label){const o=document.createElement('option');o.value=value;o.textContent=label||value;sel.append(o)}
function current(){return data.profiles.find(p=>p.id===data.selected)||data.profiles[0]}
async function api(url,body){const options={cache:'no-store'};if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-ArchiCord-Token':KEY};options.body=JSON.stringify(body)}const r=await fetch(url,options),v=await r.json();if(!r.ok||v.ok===false)throw Error(v.message||'Request failed');return v}
function form(){const p=current();if(!p)return;el('choose').replaceChildren();data.profiles.forEach(x=>opt(el('choose'),x.id,x.name));el('choose').value=p.id;el('instance').replaceChildren();opt(el('instance'),'','Select room');rooms.forEach(r=>opt(el('instance'),r.id,r.name));el('theme').replaceChildren();themes.forEach(v=>opt(el('theme'),v));el('effect').replaceChildren();effects.forEach(v=>opt(el('effect'),v));
for(const [id,key] of [['name','name'],['instance','instance'],['theme','theme'],['effect','effect'],['size','font_size'],['max','max_items']])el(id).value=p[key];el('enabled').checked=p.enabled!==false;preview()}
function collect(){const p=current();if(!p)return;Object.assign(p,{name:el('name').value,instance:el('instance').value,theme:el('theme').value,effect:el('effect').value,font_size:Number(el('size').value),max_items:Number(el('max').value),enabled:el('enabled').checked})}
function preview(){const p=current();if(!p)return;const color={archipelago:'#a94cf7',violet:'#8971f7',cyan:'#22d3ef',gold:'#ffdb54',minimal:'#fff'}[p.theme]||'#a94cf7';el('preview').style.borderColor=color;el('preview').style.fontSize=p.font_size+'px';const url='http://127.0.0.1:8766/obs?profile='+encodeURIComponent(p.id);el('url').href=url;el('copy').textContent=url}
async function refresh(){try{const p=current();if(!p)return;const r=await api('/api/events?instance='+encodeURIComponent(p.instance));const feed=el('feed');feed.replaceChildren();for(const ev of r.events.slice(-p.max_items).reverse()){const row=document.createElement('div');row.className='event';const title=document.createElement('strong');title.textContent=(ev.category||'event').toUpperCase()+': '+(ev.item||ev.player||'');const details=document.createElement('small');details.textContent=(ev.timestamp||'')+' · '+(ev.player||'')+' → '+(ev.recipient||'');row.append(title,details);feed.append(row)}}catch(e){}}
async function start(){try{data=(await api('/api/profiles')).profiles;rooms=(await api('/api/rooms')).rooms;form();refresh()}catch(e){el('message').textContent=e.message}}
el('choose').addEventListener('change',()=>{collect();data.selected=el('choose').value;form();refresh()});
el('new').addEventListener('click',()=>{collect();if(data.profiles.length>=30)return;let n=1;while(data.profiles.some(p=>p.id==='profile'+n))n++;const p={id:'profile'+n,name:'New profile '+n,theme:'archipelago',effect:'fade',font_size:21,max_items:8,enabled:true,instance:''};data.profiles.push(p);data.selected=p.id;form()});
el('delete').addEventListener('click',()=>{if(data.profiles.length<=1)return;data.profiles=data.profiles.filter(p=>p.id!==data.selected);data.selected=data.profiles[0].id;form()});
el('save').addEventListener('click',async()=>{collect();try{data=(await api('/api/profiles/save',data)).profiles;el('message').textContent='Saved locally';form()}catch(e){el('message').textContent=e.message}});
['name','theme','effect','size','max','enabled','instance'].forEach(id=>el(id).addEventListener('change',()=>{collect();preview();refresh()}));start();setInterval(refresh,2000);
</script></body></html>'''
OBS='''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ArchiCord OBS Overlay</title><style>
html,body{margin:0;background:transparent;color:#fff;font-family:Inter,Poppins,"Segoe UI",sans-serif}
#panel{position:absolute;bottom:15px;right:15px;max-width:min(95vw,900px);min-width:380px;border:2px solid var(--accent,#a94cf7);border-radius:18px;background:#10172bef;padding:20px}
h2{margin:0 0 12px}.event{margin:8px 0;padding:12px;background:#26314fee;border-left:5px solid var(--accent,#a94cf7);border-radius:10px;overflow-wrap:anywhere}
</style></head><body><div id="panel"><h2>🌈 ArchiCord Live Log</h2><div id="feed"></div></div><script>
const ID=__PROFILE__;let settings=null;
async function update(){try{const q=await fetch('/api/overlay?profile='+encodeURIComponent(ID),{cache:'no-store'}),d=await q.json();if(!q.ok)throw Error('offline');const p=d.profile;if(!p||!p.enabled){document.getElementById('panel').hidden=true;return}const root=document.getElementById('panel');root.hidden=false;root.style.setProperty('--accent',d.color);root.style.fontSize=p.font_size+'px';const feed=document.getElementById('feed');feed.replaceChildren();for(const ev of d.events.slice(-p.max_items).reverse()){const row=document.createElement('div');row.className='event';row.textContent=(ev.category||'event').toUpperCase()+' · '+(ev.item||'')+' · '+(ev.player||'')+(ev.recipient?' → '+ev.recipient:'');feed.append(row)}}catch(e){document.getElementById('panel').hidden=true}}
update();setInterval(update,2000);
</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def host_ok(self):
        host=self.headers.get("Host","").split(":")[0].lower()
        return host in ("127.0.0.1","localhost","[::1]")
    def reply(self,status,data):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def page(self,source):
        raw=source.encode("utf-8")
        self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Security-Policy","default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if not self.host_ok():return self.reply(403,{"ok":False,"message":"Local access only"})
        path=urlsplit(self.path);query=parse_qs(path.query)
        try:
            if path.path=="/":return self.page(STUDIO.replace("__CSS__",CSS).replace("__TOKEN__",json.dumps(TOKEN)))
            if path.path=="/obs":
                ident=query.get("profile",["default"])[0]
                return self.page(OBS.replace("__PROFILE__",json.dumps(ident)))
            if path.path=="/api/profiles":return self.reply(200,{"ok":True,"profiles":load_profiles()})
            if path.path=="/api/rooms":
                return self.reply(200,{"ok":True,"rooms":[{"id":r["id"],"name":r["name"]} for r in read_instances(DATA_ROOT)]})
            if path.path=="/api/events":
                ident=query.get("instance",[""])[0]
                return self.reply(200,{"ok":True,"events":events(ident)})
            if path.path=="/api/overlay":
                ident=query.get("profile",["default"])[0]
                p=next((x for x in load_profiles()["profiles"] if x["id"]==ident),None)
                if p is None:return self.reply(404,{"ok":False,"message":"Unknown profile"})
                return self.reply(200,{"ok":True,"profile":p,"color":COLORS[p["theme"]],
                                       "events":events(p["instance"],p["max_items"])})
            return self.reply(404,{"ok":False,"message":"Not found"})
        except (OSError,ValueError,TypeError):
            return self.reply(400,{"ok":False,"message":"Invalid local configuration"})
    def do_POST(self):
        if not self.host_ok():return self.reply(403,{"ok":False,"message":"Local access only"})
        host=self.headers.get("Host","")
        origin=self.headers.get("Origin")
        if (origin and origin!="http://"+host) or not secrets.compare_digest(
            self.headers.get("X-ArchiCord-Token",""),TOKEN):
            return self.reply(403,{"ok":False,"message":"CSRF validation failed"})
        if self.path!="/api/profiles/save":
            return self.reply(404,{"ok":False,"message":"Not found"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=128000:raise ValueError("Request too large")
            data=json.loads(self.rfile.read(length))
            return self.reply(200,{"ok":True,"profiles":save_profiles(data)})
        except (OSError,ValueError,TypeError):
            return self.reply(400,{"ok":False,"message":"Invalid profiles"})

def main(port:int=8766):
    if not 1<=port<=65535:raise ValueError("Invalid port")
    http=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"ArchiCord Overlay Studio: http://127.0.0.1:{port}/")
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:http.server_close()

if __name__=="__main__":
    main()
