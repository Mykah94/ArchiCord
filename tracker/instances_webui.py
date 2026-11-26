"""Local Web UI for parallel Archipelago Multiworld instances.

Existing page routes, typography and color palette remain unchanged.
"""
from __future__ import annotations

import json

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchiCord · Multiworld Instances</title><style>__STYLE__
.instance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,390px),1fr));gap:18px;margin-top:18px}
.instance-grid .card{min-width:0}.instance-grid input{width:100%;margin:5px 0 12px}
.instance-grid label{display:block;color:#b9bfdf;font-size:.9rem}
.instance-grid .row-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.instance-grid .instance-actions{display:flex;justify-content:space-between;gap:12px;align-items:center}
.instance-status{font-size:.87rem;color:#74e9c0;overflow-wrap:anywhere}
.instance-note{color:#b9bfdf;line-height:1.55}.instance-grid select{padding:10px;background:#151a31;color:white}
@media(max-width:520px){.instance-grid .row-fields{grid-template-columns:1fr}}
</style></head><body><main>
<nav class="navbar"><a class="nav-pill" href="/">🎮 Bot Control</a><a class="nav-pill" href="/dashboard">📊 Dashboard</a><a class="nav-pill active" href="/instanzen">🌍 Multiworlds</a><a class="nav-pill" href="/apworlds">🧩 APWorlds</a><a class="nav-pill" href="/resources">📚 Resources</a></nav>
<section class="hero"><div class="brand"><img src="/assets/archicord-logo.svg" alt="ArchiCord logo"><div class="hero-copy"><h1><span class="title-gradient">Multiworld Instances</span></h1><p>Connect multiple Archipelago seeds simultaneously through a single Discord bot login. Every room has its own seed data and Discord destinations.</p></div></div></section>
<section class="card"><div class="banner"><span class="icon-badge blue">🌍</span><div><strong>Independent Multiworld rooms</strong><span class="meta">Add up to twelve extra rooms. The original Bot Control room remains available.</span></div></div>
<p class="instance-note">Each room requires its own Archipelago server URL and a Discord server (Guild) ID. Leave a saved room's password blank to keep it. Room changes take effect automatically while the bot is running. Room data is never deleted by removing a configuration.</p>
<div class="toolbar"><button id="addRoom">＋ Add Multiworld</button><button class="secondary" id="reload">↻ Refresh</button></div><p id="message" class="notice" role="status"></p></section>
<div id="rooms" class="instance-grid"></div>
<section class="card"><div class="banner"><span class="icon-badge green">💾</span><div><strong>Save all room settings</strong><span class="meta">Credentials are kept in a local private JSON file under archicord_data.</span></div></div><button id="saveRooms">💾 Save & apply rooms</button></section>
<script>
const CSRF=__TOKEN__,keys=['id','name','ap_url','slot','game','guild_id','item_channel_id','hint_channel_id','death_channel_id','status_channel_id'];
const labels={id:'Instance ID (permanent)',name:'Display name',ap_url:'Archipelago WebSocket URL (ws/wss)',slot:'Bot slot name',game:'Game',guild_id:'Discord Guild ID',item_channel_id:'Progression item channel ID',hint_channel_id:'Hint channel ID',death_channel_id:'DeathLink channel ID',status_channel_id:'Status channel ID'};
const el=id=>document.getElementById(id);let records=[],statuses=[];
const input=(label,value,type='text')=>{const box=document.createElement('label');box.textContent=label;const node=document.createElement('input');node.type=type;node.value=value??'';node.autocomplete='off';box.append(node);return [box,node]};
function note(t){el('message').textContent=t}
function newRoom(){let n=1;while(records.some(x=>x.id==='room'+n))n++;return {id:'room'+n,name:'Multiworld '+n,ap_url:'wss://archipelago.gg:61664',slot:'',game:'',guild_id:'',item_channel_id:'',hint_channel_id:'',death_channel_id:'',status_channel_id:'',enabled:true,password:''}}
function paint(){const root=el('rooms');root.replaceChildren();for(const record of records){const card=document.createElement('section');card.className='card';const top=document.createElement('div');top.className='instance-actions';const title=document.createElement('strong');title.textContent=record.name||record.id;const status=document.createElement('span');status.className='instance-status';const found=statuses.find(x=>x.id===record.id);const data=found?.status||{};status.textContent=data.connected?'🟢 '+(data.seed||'Connected')+' · '+(data.players||0)+' players':(data.error?'⚠ '+data.error:'⚪ Disconnected');top.append(title,status);card.append(top);const grid=document.createElement('div');grid.className='row-fields';for(const key of keys){const [label,field]=input(labels[key],record[key]);field.maxLength=key==='ap_url'?300:90;if(key==='id'&&record.persisted)field.readOnly=true;field.addEventListener('input',()=>{record[key]=field.value;if(key==='name')title.textContent=field.value});grid.append(label)}const [passLabel,pass]=input('Archipelago password (blank keeps saved password)','','password');pass.addEventListener('input',()=>record.password=pass.value);grid.append(passLabel);card.append(grid);const row=document.createElement('div');row.className='instance-actions';const enabledLabel=document.createElement('label');enabledLabel.textContent='Enabled ';const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=record.enabled!==false;enabled.addEventListener('change',()=>record.enabled=enabled.checked);enabledLabel.append(enabled);const remove=document.createElement('button');remove.className='stop';remove.textContent='Remove room';remove.addEventListener('click',()=>{if(confirm('Remove '+record.id+' from the configuration? Existing saved seeds will remain.')){records=records.filter(x=>x!==record);paint()}});row.append(enabledLabel,remove);card.append(row);root.append(card)}if(!records.length){const p=document.createElement('p');p.className='instance-note';p.textContent='No extra rooms yet. Choose Add Multiworld to configure one.';root.append(p)}}
async function load(){try{const r=await fetch('/api/instances',{cache:'no-store'});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.message||'Read failed');records=d.instances.map(x=>({...x,persisted:true,password:''}));statuses=d.statuses||[];paint();note('')}catch(e){note('Unable to load instances: '+e.message)}}
async function refresh(){try{const r=await fetch('/api/instances/status',{cache:'no-store'}),d=await r.json();if(r.ok&&d.ok){statuses=d.statuses||[];for(const entry of document.querySelectorAll('.instance-status')){const card=entry.closest('.card'),idx=[...el('rooms').children].indexOf(card);const room=records[idx],data=statuses.find(x=>x.id===room?.id)?.status||{};entry.textContent=data.connected?'🟢 '+(data.seed||'Connected')+' · '+(data.players||0)+' players':(data.error?'⚠ '+data.error:'⚪ Disconnected')}}}catch(e){}}
async function save(){try{const rows=records.map(({persisted,password_configured,...x})=>x);const r=await fetch('/api/instances/save',{method:'POST',headers:{'Content-Type':'application/json','X-ArchiCord-Token':CSRF},body:JSON.stringify({instances:rows})});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.message||'Save failed');note('Rooms saved. The running bot will apply changes shortly.');await load()}catch(e){note('Save failed: '+e.message)}}
el('addRoom').addEventListener('click',()=>{if(records.length>=12){note('Maximum 12 extra rooms.');return}records.push(newRoom());paint()});el('reload').addEventListener('click',load);el('saveRooms').addEventListener('click',save);load();setInterval(refresh,7000);
</script></main></body></html>'''


def render_instances(style: str, csrf: str) -> str:
    return PAGE.replace("__STYLE__", style).replace("__TOKEN__", json.dumps(csrf))
