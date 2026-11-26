"""Local Tracker settings page. Text-only DOM updates: no innerHTML inputs."""
from __future__ import annotations
import json

PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchiCord Tracker Settings</title><style>__STYLE__
.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px}
.settings-grid label{display:block;color:#bbc7e6}.settings-grid input{width:100%;margin:7px 0}
#checks{line-height:2}.ok{color:#50e282}.error{color:#ff709b}.warning{color:#ffdb54}
</style></head><body><main>
<nav class="navbar"><a class="nav-pill" href="/">🎮 Bot Control</a><a class="nav-pill" href="/dashboard">📊 Dashboard</a><a class="nav-pill" href="/instanzen">🌍 Multiworlds</a><a class="nav-pill active" href="/tracker-settings">🧭 Tracker Settings</a><a class="nav-pill" href="/resources">📚 Resources</a></nav>
<section class="hero"><h1 class="title-gradient">🧭 Universal Tracker Settings</h1><p>Set the local Archipelago launcher and YAML/APWorld folders. Diagnostics never execute APWorlds or the launcher.</p></section>
<section class="card"><div class="settings-grid" id="settings"></div><p><button id="save">Save paths</button><button class="secondary" id="test">Check paths</button></p><p id="message" role="status"></p></section>
<section class="card"><h2>Path diagnostics</h2><div id="checks"></div><p>Per-room checks are generated only when a running Universal Tracker returns confirmed, unambiguous location IDs. Restart the bot after changing the launcher path.</p></section>
<script>
const CSRF=__TOKEN__,keys=['launcher_path','install_dir','yaml_dir','seed_dir','apworld_dir'],labels={launcher_path:'Archipelago Launcher (.exe)',install_dir:'Archipelago installation folder',yaml_dir:'Player YAML folder',seed_dir:'Generated seed folder',apworld_dir:'Custom APWorld folder'},inputs={};const node=(tag,t)=>{const e=document.createElement(tag);if(t!==undefined)e.textContent=String(t);return e};
async function request(path,data){const options={cache:'no-store'};if(data!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-ArchiCord-Token':CSRF};options.body=JSON.stringify(data)}const res=await fetch(path,options),obj=await res.json();if(!res.ok||obj.ok===false)throw Error(obj.message||'Request failed');return obj}
async function load(){try{const result=await request('/api/tracker/settings');const grid=document.getElementById('settings');grid.replaceChildren();for(const key of keys){const l=node('label',labels[key]),i=node('input');i.value=result.settings[key]||'';i.maxLength=1024;i.autocomplete='off';l.append(i);grid.append(l);inputs[key]=i}paint(result.diagnostics)}catch(e){document.getElementById('message').textContent=e.message}}
function paint(results){const list=document.getElementById('checks');list.replaceChildren();for(const row of results){const p=node('p',row.key+' · '+row.message);p.className=row.status;list.append(p)}}
document.getElementById('save').addEventListener('click',async()=>{try{const settings={};for(const k of keys)settings[k]=inputs[k].value;const d=await request('/api/tracker/settings/save',{settings});document.getElementById('message').textContent='Saved locally';paint(d.diagnostics)}catch(e){document.getElementById('message').textContent=e.message}});
document.getElementById('test').addEventListener('click',load);load();
</script></main></body></html>'''

def render(style:str,csrf:str)->str:
    return PAGE.replace("__STYLE__",style).replace("__TOKEN__",json.dumps(csrf))
