"""Accessible local-only ArchiCord 3.0 dashboard pages.

The browser reads sanitized same-origin JSON and uses textContent exclusively
for dynamic data. Existing control-center pages remain available unchanged.
"""
from __future__ import annotations

import html
import json

PAGES = {
    "dashboard": ("📊", "Dashboard"), "players": ("👥", "Players"),
    "checks": ("🎯", "Checks"), "history": ("🕘", "History"),
    "item-routes": ("🎁", "Item Routes"), "health": ("💚", "Health"),
    "backups": ("💾", "Backups"), "compatibility": ("🧩", "Compatibility"),
    "notifications": ("🔔", "Notifications"), "achievements": ("🏆", "Achievements"),
}

STYLES = """
.dashboard-shell{max-width:1360px;margin:auto;padding:22px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:26px}
.sidebar{background:rgba(15,19,40,.94);border:1px solid rgba(150,128,244,.22);border-radius:22px;padding:20px;align-self:start;position:sticky;top:18px}
.sidebar-brand{display:flex;align-items:center;gap:10px;font-weight:900;font-size:1.22rem;margin-bottom:26px}
.sidebar-brand img{width:55px;height:55px}
.sidebar a{display:flex;align-items:center;gap:10px;padding:12px;color:#cbd2ee;border-radius:12px;margin:3px 0;text-decoration:none;font-weight:650}
.sidebar a:hover,.sidebar a.active{background:rgba(135,102,242,.19);color:#fff;text-decoration:none}
.dashboard-main{min-width:0}.dashboard-main h1{margin:8px 0 8px}
.dashboard-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:18px 0}
.dashboard-kpi{background:rgba(22,26,52,.92);border:1px solid rgba(150,128,244,.22);border-top:3px solid #a94cf7;padding:18px;border-radius:17px}
.dashboard-kpi:nth-child(2){border-top-color:#50e282}.dashboard-kpi:nth-child(3){border-top-color:#22d3ef}.dashboard-kpi:nth-child(4){border-top-color:#ffdb54}
.dashboard-kpi strong{font-size:1.7rem;display:block}.dashboard-kpi small{font-size:.85rem}
.dashboard-panel{background:rgba(17,21,43,.89);border:1px solid rgba(150,128,244,.24);border-radius:20px;padding:22px;margin:16px 0;overflow:auto}
.dashboard-panel h2{margin-top:0}.dashboard-table{border-collapse:collapse;width:100%;font-size:.94rem}
.dashboard-table td,.dashboard-table th{text-align:left;padding:12px 9px;border-bottom:1px solid rgba(155,148,215,.16)}
.dashboard-table th{color:#b9bfdf}.dashboard-table td{overflow-wrap:anywhere}
.dashboard-toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}
.dashboard-toolbar input,.dashboard-toolbar select{max-width:330px;padding:10px;border:1px solid #595b96;border-radius:10px;background:#131a35;color:#fff}
.dashboard-toolbar button{margin:0;padding:10px 14px}
.dashboard-note{color:#b9bfdf;line-height:1.6}
.dashboard-warning{color:#ffdb9a}
.dashboard-accent{color:#58d8f2}
@media(max-width:850px){.dashboard-shell{grid-template-columns:1fr;padding:12px}.sidebar{position:static}.sidebar nav{display:flex;gap:6px;flex-wrap:wrap}.sidebar a{font-size:.86rem;padding:9px}.dashboard-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchiCord · __TITLE__</title><style>__CSS__</style></head><body>
<div class="dashboard-shell"><aside class="sidebar"><div class="sidebar-brand"><img src="/assets/archicord-logo.svg" alt="ArchiCord icon"><span>ArchiCord</span></div><nav>__NAV__</nav></aside>
<main class="dashboard-main"><div class="dashboard-toolbar"><span class="pill">🌈 Multiworld Center</span><a href="/">Bot Control</a><a href="/apworlds">APWorld Manager</a><a href="/resources">Resources</a></div>
<h1 id="heading">__TITLE__</h1><p id="description" class="dashboard-note">Live data appears when the ArchiCord bot is running. No simulated progress.</p>
<div id="kpis" class="dashboard-kpis"></div>
<section class="dashboard-panel" id="primary"><p id="message" class="dashboard-note">Loading…</p></section>
<section class="dashboard-panel" id="secondary" hidden></section>
</main></div>
<script>
const VIEW=__VIEW__,TOKEN=__TOKEN__,KIND_LIST=['item','trap','hint','goal','deathlink','status','release'];
const $=id=>document.getElementById(id);
let lastConfig=null;
function e(tag,text,klass){const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=String(text);if(klass)node.className=klass;return node;}
function empty(el){el.replaceChildren()}
function paragraph(parent,text){parent.append(e('p',text,'dashboard-note'))}
function table(parent,columns,items){const t=e('table',null,'dashboard-table'),head=e('thead'),tr=e('tr');columns.forEach(c=>tr.append(e('th',c[0])));head.append(tr);t.append(head);const body=e('tbody');items.forEach(row=>{const tr=e('tr');columns.forEach(([label,key])=>tr.append(e('td',row[key]===undefined||row[key]===null?'—':row[key])));body.append(tr)});t.append(body);parent.append(t)}
function kpi(label,value){const node=e('div',null,'dashboard-kpi');node.append(e('strong',value===null||value===undefined?'—':value),e('small',label));$('kpis').append(node);}
function reset(){empty($('kpis'));empty($('primary'));empty($('secondary'));$('secondary').hidden=true;}
async function api(path,body){const opts={cache:'no-store'};if(body!==undefined){opts.method='POST';opts.headers={'Content-Type':'application/json','X-ArchiCord-Token':TOKEN};opts.body=JSON.stringify(body);}const resp=await fetch('/api/v3/'+path,opts);const result=await resp.json();if(!resp.ok||result.ok===false)throw Error(result.message||'Request failed');return result}
function showError(ex){reset();paragraph($('primary'),'Unavailable: '+ex.message)}
function formatOnline(v){return v?'🟢 Online':'⚪ Offline'}
function addButton(parent,label,action){const b=e('button',label);b.addEventListener('click',action);parent.append(b);return b}
function setHeading(page,locale){const titles={de:{dashboard:'Übersicht',players:'Spieler',checks:'Checks',history:'Seed-Verlauf','item-routes':'Item-Routen',health:'Verbindungen',backups:'Sicherungen',notifications:'Benachrichtigungen',achievements:'Erfolge',compatibility:'APWorld-Kompatibilität'}};$('heading').textContent=locale==='de'?(titles.de[page]||page):({dashboard:'Dashboard',players:'Players',checks:'Checks',history:'History','item-routes':'Item Routes',health:'Health',backups:'Backups',notifications:'Notifications',achievements:'Achievements',compatibility:'APWorld Compatibility'}[page]||page)}
async function draw(){
 try{
 const config=await api('notifications');lastConfig=config.config;setHeading(VIEW,config.config.language||'en');
 if(VIEW==='notifications'){return drawNotifications(config.config)}
 if(VIEW==='backups'){return await drawBackups()}
 if(VIEW==='compatibility'){return await drawCompatibility()}
 if(VIEW==='history'){return await drawHistory()}
 const result=await api('dashboard');reset();
 const snap=result.snapshot;if(!snap){paragraph($('primary'),'No live snapshot yet. Start the bot or check the connection.');return}
 const meta=snap.summary||{};
 if(VIEW==='dashboard'){kpi('Players',snap.players.length);kpi('Online',snap.players.filter(p=>p.online).length);kpi('Goals',meta.goals);kpi('DeathLinks',meta.deaths);kpi('Checked locations',meta.checks?.checked);kpi('Progression items',meta.progression);paragraph($('primary'),'Seed: '+snap.seed+' · Team: '+snap.team);paragraph($('primary'),snap.ap_connected?'Archipelago connected':'Archipelago disconnected / data may be stale');table($('primary'),[['Player','name'],['Game','game'],['Status','status'],['Goal','goal'],['Doable','doable_label']],snap.players.map(p=>({...p,status:formatOnline(p.online),goal:p.goal?'🏆 Yes':'—'})));return}
 if(VIEW==='players'){table($('primary'),[['Player','name'],['Game','game'],['Status','status'],['Goal','goal'],['Doable checks','doable_label']],snap.players.map(p=>({...p,status:formatOnline(p.online),goal:p.goal?'Yes':'No'})));return}
 if(VIEW==='checks'){paragraph($('primary'),'Only confirmed tracker logic is marked doable. Unknown logic is never guessed. Other players show only their confirmed reachable checks.');const bar=e('div',null,'dashboard-toolbar'),inp=e('input'),sel=e('select'),player=e('select');inp.placeholder='Search locations';(snap.players||[]).forEach(p=>{const o=e('option',p.name+' · '+p.game);o.value=String(p.slot);player.append(o)});player.value=String(snap.own_slot||'');[['all','All'],['checked','Checked'],['doable','Doable'],['missing','Other missing']].forEach(([v,t])=>{const o=e('option',t);o.value=v;sel.append(o)});bar.append(player,inp,sel);$('primary').append(bar);const place=e('div');$('primary').append(place);const render=()=>{empty(place);const q=inp.value.toLowerCase();const all=(snap.player_checks&&snap.player_checks[player.value])||[];const rows=all.filter(x=>(sel.value==='all'||x.status===sel.value)&&String(x.name).toLowerCase().includes(q));table(place,[['Location','name'],['ID','id'],['State','status']],rows.slice(0,300));paragraph(place,rows.length+' results'+(rows.length>300?' (first 300 shown)':''))};inp.addEventListener('input',render);sel.addEventListener('change',render);player.addEventListener('change',render);render();return}
 if(VIEW==='item-routes'){table($('primary'),[['Time','at'],['From','player'],['To','recipient'],['Item','item'],['Location','location'],['Type','type']],(snap.item_routes||[]));return}
 if(VIEW==='health'){const health=await api('health');kpi('Health',health.status.status);kpi('Discord',health.status.components?.discord);kpi('Archipelago',health.status.components?.archipelago);kpi('Tracker',health.status.components?.universal_tracker);paragraph($('primary'),'Last update: '+(health.status.updated_at||'unknown'));paragraph($('primary'),'The bot must be running and exporting snapshots to refresh these values.');return}
 if(VIEW==='achievements'){const items=meta.achievements||[];if(!items.length){paragraph($('primary'),'No achievements yet for this seed.')}else table($('primary'),[['Achievement','title'],['ID','id']],items);paragraph($('primary'),'Achievements are computed from stored progression, goals, checks and DeathLinks. They do not send messages automatically.');}
 }catch(ex){showError(ex)}
}
async function drawHistory(){reset();const result=await api('history');kpi('Stored seeds',result.history.length);table($('primary'),[['Seed','seed'],['Team','team'],['Goals','goals'],['Deaths','deaths'],['Checks','checkcount'],['Last updated','updated']],result.history.map(x=>({...x,checkcount:x.checks?.checked??'—'})))}
async function drawCompatibility(){reset();const result=await api('compatibility');kpi('APWorld files',result.worlds.length);kpi('Warnings',result.worlds.filter(w=>w.issues.length).length);paragraph($('primary'),'Manifest checks only. Valid manifests do not guarantee that the world is compatible with your installed Archipelago or Universal Tracker.');table($('primary'),[['Game','game'],['Version','world_version'],['File','file'],['Issues','issue_text'],['Compatibility','compatibility']],result.worlds.map(w=>({...w,issue_text:w.issues.join(', ')||'None'})))}
async function drawBackups(){reset();const result=await api('backups');kpi('Local backups',result.backups.length);paragraph($('primary'),'Backups contain sensitive .env and seed data. They remain local and are never downloadable from this Web UI. Stop the bot before restoring.');const tools=e('div',null,'dashboard-toolbar');addButton(tools,'Create backup',async()=>{try{const x=await api('backup/create',{});alert('Backup created: '+x.backup.name);await drawBackups()}catch(ex){alert(ex.message)}});$('primary').append(tools);const rows=result.backups;table($('primary'),[['Filename','name'],['Bytes','bytes']],rows);const select=e('select'),actions=e('div',null,'dashboard-toolbar');rows.forEach(row=>{const opt=e('option',row.name);opt.value=row.name;select.append(opt)});actions.append(select);addButton(actions,'Verify selected',async()=>{try{const r=await api('backup/verify',{name:select.value});alert('Verified '+r.backup.files+' files')}catch(ex){alert(ex.message)}});addButton(actions,'Restore selected',async()=>{if(!confirm('Restore selected backup? Bot must be stopped. Current data will be backed up first.'))return;try{const r=await api('backup/restore',{name:select.value,confirm:'RESTORE'});alert('Restored '+r.result.restored+' files. Safety copy: '+r.result.safety_backup)}catch(ex){alert(ex.message)}});if(rows.length)$('primary').append(actions)}
function drawNotifications(cfg){reset();paragraph($('primary'),'Existing event behavior remains unchanged unless you explicitly edit these settings. Channel overrides and cool-downs apply to future events, not past messages.');const select=e('select');[['de','Deutsch'],['en','English']].forEach(([v,t])=>{const opt=e('option',t);opt.value=v;select.append(opt)});select.value=cfg.language||'de';const form=e('div');form.append(e('label','Interface language'),select);const controls=[];for(const kind of KIND_LIST){const box=e('div',null,'dashboard-toolbar');const label=e('label',kind);label.style.minWidth='110px';const enabled=e('input');enabled.type='checkbox';enabled.checked=cfg.enabled?.[kind]!==false;const channel=e('input');channel.placeholder='Channel override (optional)';channel.value=cfg.channels?.[kind]||'';channel.maxLength=22;const cooldown=e('input');cooldown.type='number';cooldown.min='0';cooldown.max='3600';cooldown.value=cfg.cooldown_seconds?.[kind]||0;cooldown.style.maxWidth='120px';box.append(label,enabled,channel,e('span','Cooldown (s)'),cooldown);form.append(box);controls.push({kind,enabled,channel,cooldown})}$('primary').append(form);addButton($('primary'),'Save settings',async()=>{const payload={language:select.value,enabled:{},channels:{},cooldown_seconds:{}};for(const c of controls){payload.enabled[c.kind]=c.enabled.checked;payload.channels[c.kind]=c.channel.value.trim();payload.cooldown_seconds[c.kind]=Number(c.cooldown.value)}try{await api('notifications/save',{config:payload});alert('Saved. Restart the bot to apply new notification rules.');await draw()}catch(ex){alert(ex.message)}})}
draw();if(VIEW==='dashboard'||VIEW==='players'||VIEW==='checks'||VIEW==='health')setInterval(draw,15000);
</script></body></html>"""


def render_dashboard(view: str, base_style: str, csrf: str) -> str:
    if view not in PAGES:
        raise ValueError("Unknown dashboard view")
    nav = "".join(
        '<a class="' + ("active" if key == view else "") + '" href="/' + key + '">'
        + html.escape(icon + " " + title) + "</a>"
        for key, (icon, title) in PAGES.items()
    )
    return (PAGE.replace("__TITLE__", html.escape(PAGES[view][1]))
            .replace("__CSS__", base_style + STYLES)
            .replace("__NAV__", nav)
            .replace("__VIEW__", json.dumps(view))
            .replace("__TOKEN__", json.dumps(csrf)))
