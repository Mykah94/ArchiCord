"""Read-only, fail-closed per-room Universal Tracker check overview."""
from __future__ import annotations
import json

PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchiCord Multiworld Checks</title><style>__STYLE__
#checks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.check{padding:12px;border:1px solid #655e9988;border-left:3px solid #50e282;border-radius:12px;background:#1a2340}
</style></head><body><main>
<nav class="navbar"><a class="nav-pill" href="/instanzen">🌍 Multiworlds</a><a class="nav-pill" href="/dashboard">📊 Dashboard</a><a class="nav-pill" href="/tracker-settings">🧭 Tracker settings</a></nav>
<section class="hero"><h1 class="title-gradient">🎯 Multiworld Doable Checks</h1><p id="subtitle">Only verified Universal Tracker results are displayed. Unknown logic never produces guessed checks.</p></section>
<section class="card"><label>Search locations <input type="search" id="search" placeholder="Filter by location name"></label><p id="notice"></p><div id="checks"></div></section>
<script>
const INSTANCE=__INSTANCE__,list=document.getElementById('checks');let rows=[];const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=String(value);return n};
function render(){const q=document.getElementById('search').value.toLowerCase();list.replaceChildren();let visible=rows.filter(v=>v.name.toLowerCase().includes(q));for(const row of visible.slice(0,500)){const el=text('div',row.name+' (#'+row.id+')');el.className='check';list.append(el)}document.getElementById('notice').textContent=visible.length+' confirmed reachable locations'+(visible.length>500?' (first 500 shown)':'')}
async function load(){try{const response=await fetch('/api/instances/checks?instance='+encodeURIComponent(INSTANCE),{cache:'no-store'}),data=await response.json();if(!response.ok||!data.ok)throw Error(data.message||'Unavailable');rows=data.known?data.checks:[];document.getElementById('subtitle').textContent=data.known?'Seed '+data.seed+' · Team '+data.team:'No confirmed Universal Tracker data for this room';render()}catch(error){rows=[];document.getElementById('notice').textContent=error.message;list.replaceChildren()}}
document.getElementById('search').addEventListener('input',render);load();setInterval(load,30000);
</script></main></body></html>'''

def render(style:str,instance:str)->str:
    return PAGE.replace("__STYLE__",style).replace("__INSTANCE__",json.dumps(instance))
