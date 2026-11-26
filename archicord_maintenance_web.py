"""Self-contained local maintenance page used by the classic ArchiCord WebUI."""
import json


def maintenance_html(csrf_token: str) -> str:
    template = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ArchiCord · Wartung / Maintenance</title>
<style>
:root {color-scheme:dark;font-family:"Lexend Deca","Segoe UI",system-ui,sans-serif;--bg:#07101d;--card:#10192af2;--line:#354366;--text:#f8f9ff;--sub:#afbed7;--blue:#7787ff;--pink:#ec6cae;--mint:#83e7b3;--gold:#f6df87}
* {box-sizing:border-box}
html {scroll-behavior:smooth}
body {margin:0;min-height:100vh;color:var(--text);background:radial-gradient(ellipse at 15% 0%,#2930646b,transparent 42%),radial-gradient(ellipse at 96% 40%,#491f4a66,transparent 39%),var(--bg)}
a {color:#c8d0ff;text-decoration:none} a:hover {text-decoration:underline}
nav {position:sticky;top:0;z-index:10;display:flex;flex-wrap:wrap;align-items:center;gap:14px;background:#0a1120ee;border-bottom:1px solid #49537b;backdrop-filter:blur(15px);padding:13px max(18px,calc((100% - 1160px)/2))}
nav .logo {font-size:22px;font-weight:900;background:linear-gradient(110deg,#fff,#9aa5ff);background-clip:text;color:transparent;margin-right:auto}
nav a:not(.logo) {padding:9px 12px;border-radius:12px;color:var(--sub);font-size:14px}
nav a.active {background:#6978ed3d;color:white}
nav select {border:1px solid var(--line);background:#121e36;color:white;padding:9px;border-radius:10px}
main {max-width:1160px;padding:36px 18px 65px;margin:auto}
.hero {position:relative;overflow:hidden;padding:30px;border:1px solid #56649a88;background:linear-gradient(110deg,#101a35ed,#111b2ce8);border-radius:25px;margin-bottom:24px}
.hero::after {content:"";position:absolute;right:7%;top:-50px;width:200px;height:200px;background:radial-gradient(circle,#eb6aa837,transparent 68%);animation:float 8s ease-in-out infinite;pointer-events:none}
h1 {font-size:clamp(28px,4vw,44px);margin:0 0 10px}h2{font-size:20px;margin:0 0 14px}.muted{color:var(--sub)}p{line-height:1.6}
.eyebrow{color:var(--mint);font-size:12px;letter-spacing:.19em;font-weight:bold;margin-bottom:8px}
.grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}
.card{background:var(--card);border:1px solid #3f4e70;border-radius:20px;padding:23px;box-shadow:0 12px 30px #0005;transition:transform .24s,border-color .24s}
.card:hover {transform:translateY(-3px);border-color:#8996ee}
.card.pink{border-top:3px solid var(--pink)}.card.mint{border-top:3px solid var(--mint)}.card.gold{border-top:3px solid var(--gold)}
.big{font-weight:800;font-size:25px;margin:6px 0 8px}.chip{display:inline-block;padding:5px 12px;border:1px solid #576484;border-radius:20px;background:#1d2b46;color:#dfe8ff;font-size:12px;font-weight:700}
.good {color:var(--mint)}.warn{color:var(--gold)}.bad{color:#ff92ad}
button {font:inherit;border:1px solid #98a3ff;background:linear-gradient(115deg,#6c77eb,#a06dd7);border-radius:14px;color:white;font-weight:700;padding:13px 19px;cursor:pointer;transition:filter .2s,transform .2s}
button:hover{filter:brightness(1.15);transform:translateY(-2px)}button:disabled{opacity:.5;cursor:wait;transform:none}
.list{display:grid;gap:10px;margin-top:14px}
.item{display:flex;align-items:center;justify-content:space-between;gap:14px;background:#0b1728;border-radius:12px;border:1px solid #364767;padding:12px 14px}
.note{font-size:13px;color:var(--sub)}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(27px)}}
@media (prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
</style></head><body>
<nav><a class="logo" href="/">ArchiCord</a><a href="/" data-de="Startseite" data-en="Home">Startseite</a><a href="/instanzen" data-de="Instanzen" data-en="Instances">Instanzen</a><a href="/tracker">Universal Tracker</a><a href="/wartung" class="active" data-de="Wartung" data-en="Maintenance">Wartung</a><select id="language" aria-label="Language"><option value="de">Deutsch</option><option value="en">English</option></select></nav>
<main>
<section class="hero"><div class="eyebrow">ARCHICORD · SYSTEM HEALTH</div><h1 data-de="Wartung & Gesundheit" data-en="Maintenance & Health">Wartung & Gesundheit</h1><p class="muted" data-de="Status deiner Discord- und Archipelago-Verbindungen sowie automatische lokale Sicherungen. Keine bestehenden Bot-Funktionen werden verändert." data-en="Discord and Archipelago connection status plus automatic local backups. Existing bot features remain untouched.">Status deiner Discord- und Archipelago-Verbindungen sowie automatische lokale Sicherungen. Keine bestehenden Bot-Funktionen werden verändert.</p></section>
<section class="grid">
<div class="card mint"><h2>Discord</h2><div id="discord" class="big">…</div><div class="note" data-de="Aus den Statusmeldungen des lokalen Bot-Prozesses" data-en="Based on local bot process status messages">Aus den Statusmeldungen des lokalen Bot-Prozesses</div></div>
<div class="card"><h2>Archipelago</h2><div id="ap" class="big">…</div><div id="instancesSummary" class="note"></div></div>
<div class="card pink"><h2>Universal Tracker</h2><div id="tracker" class="big">…</div><div class="note" data-de="Alter der letzten Exportdaten; kein vollständiger Logik-Selbsttest" data-en="Age of last exported data, not a complete logic health check">Alter der letzten Exportdaten; kein vollständiger Logik-Selbsttest</div></div>
</section>
<section class="grid" style="margin-top:16px">
<div class="card gold"><h2 data-de="Automatische Backups" data-en="Automatic backups">Automatische Backups</h2>
<div id="backupSummary" class="big">…</div>
<p class="muted" id="backupDetails"></p>
<button id="create" data-de="Jetzt Sicherung erstellen" data-en="Create backup now">Jetzt Sicherung erstellen</button>
<p id="notice" class="note" role="status" aria-live="polite"></p>
<p class="note" data-de="Speicherung nur lokal im Ordner backups/. Passwörter werden aus JSON-Kopien entfernt; .env und rohe Seeds werden nicht gespeichert." data-en="Stored locally in backups/. Credential fields are redacted from JSON copies; .env and raw seed packages are excluded.">Speicherung nur lokal im Ordner backups/. Passwörter werden aus JSON-Kopien entfernt; .env und rohe Seeds werden nicht gespeichert.</p></div>
<div class="card"><h2 data-de="Instanzdiagnose" data-en="Instance diagnostics">Instanzdiagnose</h2>
<div id="roomList" class="list"></div><p class="note" data-de="Ein veralteter Status wird nicht als online angezeigt." data-en="Stale heartbeat data is never shown as online.">Ein veralteter Status wird nicht als online angezeigt.</p></div>
<div class="card"><h2 data-de="Speicherplatz" data-en="Disk space">Speicherplatz</h2><div class="big" id="disk">…</div><p class="muted" id="diskNote"></p><p class="note" data-de="Diese Seite zeigt den Zustand an; sie startet, stoppt oder verbindet keine Instanzen." data-en="This dashboard is read-only; it never starts, stops or connects instances.">Diese Seite zeigt den Zustand an; sie startet, stoppt oder verbindet keine Instanzen.</p></div>
</section>
</main><script>
"use strict";
const csrf=__CSRF__;
let language=localStorage.getItem("archicord-language")==="en"?"en":"de";
const tr=(de,en)=>language==="en"?en:de;
const $=id=>document.getElementById(id);
function translate(){document.documentElement.lang=language;$("language").value=language;document.querySelectorAll("[data-de][data-en]").forEach(el=>el.textContent=el.dataset[language]);}
$("language").addEventListener("change",event=>{language=event.target.value;localStorage.setItem("archicord-language",language);translate();refresh()});
function statusText(value){const key=String(value||"unknown");const de={online:"Online",offline:"Offline",starting:"Startet",error:"Fehler",running:"Läuft",stopped:"Gestoppt",stale:"Veraltet",recent_data:"Aktuelle Daten",stale_data:"Veraltete Daten",no_export:"Keine Exportdaten",unknown:"Unbekannt"};const en={online:"Online",offline:"Offline",starting:"Starting",error:"Error",running:"Running",stopped:"Stopped",stale:"Stale",recent_data:"Recent data",stale_data:"Stale data",no_export:"No export data",unknown:"Unknown"};return (language==="en"?en:de)[key]||key;}
async function refresh(){
try {
 const response=await fetch("/api/maintenance",{cache:"no-store"});if(!response.ok)throw Error("HTTP "+response.status);
 const data=await response.json();const h=data.health,b=data.backups;
 $("discord").textContent=statusText(h.discord);$("ap").textContent=statusText(h.archipelago_reported);
 $("instancesSummary").textContent=tr("Verbundene Instanzen: ","Connected instances: ")+h.online_instances;
 $("tracker").textContent=statusText(h.universal_tracker?.status);
 $("backupSummary").textContent=b.count+" "+tr("Sicherungen","backups");
 const last=b.last_backup?new Date(b.last_backup).toLocaleString(language==="en"?"en-GB":"de-DE"):tr("Noch keine","None yet");
 $("backupDetails").textContent=tr("Letzte Sicherung: ","Last backup: ")+last+" · "+tr("Intervall: ","Interval: ")+b.interval_hours+"h · "+tr("Behalten: ","Keep: ")+b.keep+
 (b.enabled?"":tr(" · Automatik aus"," · scheduling disabled"));
 if(b.last_error)$("notice").textContent=b.last_error;
 $("disk").textContent=h.free_disk_bytes===null?"—":(h.free_disk_bytes/1073741824).toFixed(1)+" GiB";
 $("diskNote").textContent=h.disk_status==="low"?tr("Wenig freier Speicherplatz","Low free disk space"):tr("Freier lokaler Speicherplatz","Free local disk space");
 const list=$("roomList");list.replaceChildren();
 if(!h.instances.length){list.textContent=tr("Keine aktuellen Instanz-Statusdateien vorhanden.","No instance status files available.");}
 for(const room of h.instances){const row=document.createElement("div");row.className="item";const name=document.createElement("span");name.textContent=room.name;const state=document.createElement("span");state.textContent=statusText(room.status);state.className=room.status==="online"?"good":"warn";row.append(name,state);list.appendChild(row);}
} catch(error){$("notice").textContent=tr("Status kann nicht geladen werden: ","Could not load status: ")+error.message;}
}
$("create").addEventListener("click",async()=>{
const button=$("create");button.disabled=true;$("notice").textContent=tr("Sichere lokale Daten …","Backing up local data …");
try{
const r=await fetch("/api/maintenance/backup",{method:"POST",headers:{"Content-Type":"application/json","X-ArchiCord-Token":csrf},body:"{}"});
const data=await r.json();if(!r.ok||!data.ok)throw Error(data.message||"HTTP "+r.status);
$("notice").textContent=data.backup.created?tr("Sicherung erstellt: ","Backup created: ")+data.backup.name:tr("Keine sicherbaren Daten gefunden.","No eligible data found.");
await refresh();
}catch(e){$("notice").textContent=tr("Sicherung fehlgeschlagen: ","Backup failed: ")+e.message;}
finally{button.disabled=false;}
});
translate();refresh();setInterval(refresh,6500);
</script></body></html>"""
    return template.replace("__CSRF__", json.dumps(csrf_token))
