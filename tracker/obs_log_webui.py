"""Sharp local OBS browser-source log, inspired by supplied ArchiCord package.

For OBS on the same machine, add http://127.0.0.1:8765/obs-log?instance=<id>
as a Browser Source. No third-party fonts, blurry filters or public sockets.
"""
from __future__ import annotations

import json

OBS_HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>ArchiCord OBS Live Log</title><style>
:root{color-scheme:dark;--size:20px;--panel-width:1080px}
*,*::before,*::after{box-sizing:border-box}
html,body{background:transparent!important;margin:0;padding:0;width:100%;height:100%;overflow:hidden}
body{font-family:Inter,Poppins,"Segoe UI",Arial,sans-serif;color:#f5f2ff;text-rendering:optimizeLegibility;-webkit-font-smoothing:auto}
#container{position:fixed;inset:0;display:flex;align-items:flex-end;justify-content:flex-end;padding:22px;pointer-events:none}
#panel{width:min(100%,var(--panel-width));max-height:calc(100vh - 44px);display:flex;flex-direction:column;border:2px solid #8271dc;border-radius:20px;background:#10172b;overflow:hidden;box-shadow:0 10px 24px #060817aa}
#rainbow{height:6px;flex-shrink:0;background:linear-gradient(90deg,#a94cf7,#ff4b8e,#ffdb54,#50e282,#22d3ef,#318cf8)}
header{display:flex;align-items:center;padding:18px 22px;gap:15px;border-bottom:1px solid #838acc33}
header img{width:62px;height:62px;flex:none;border-radius:14px}
h1{font-size:30px;font-weight:850;margin:0}header p{font-size:15px;color:#c5c8e8;margin:4px 0 0}
#signal{margin-left:auto;color:#50e282;font-size:15px;font-weight:850}
#entries{display:flex;flex-direction:column;gap:11px;padding:15px 20px;overflow:hidden}
.entry{background:#1b2440;border:1px solid #666d9a77;border-left:5px solid #a94cf7;border-radius:12px;padding:13px 15px;display:grid;grid-template-columns:110px 1fr;gap:15px;overflow-wrap:anywhere}
.entry[data-kind=trap]{border-left-color:#ff4b8e}.entry[data-kind=item]{border-left-color:#ffdb54}
.entry[data-kind=hint]{border-left-color:#318cf8}.entry[data-kind=goal]{border-left-color:#50e282}
.time{color:#c6cbed;font-variant-numeric:tabular-nums;font-weight:650;font-size:16px}
.label{color:#b6baff;font-size:14px;font-weight:800;text-transform:uppercase}
.detail{font-size:var(--size);font-weight:650;line-height:1.35}
@media(max-width:720px){#container{padding:8px}#panel{max-height:calc(100vh - 16px)}header img{width:42px;height:42px}h1{font-size:23px}.entry{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body><main id="container"><section id="panel"><div id="rainbow"></div><header><img src="/assets/archicord-logo.svg" alt=""><div><h1>ArchiCord Live Log</h1><p id="subtitle">Multiworld events · OBS Browser Source</p></div><div id="signal">● LIVE</div></header><div id="entries"></div></section></main>
<script>
const INSTANCE=__INSTANCE__,entries=document.getElementById('entries');
const types={item:'Item',progression:'Progression Item',trap:'Trap',hint:'Hint',goal:'Goal',deathlink:'DeathLink'};
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n}
async function refresh(){try{const result=await fetch('/api/obs-log?instance='+encodeURIComponent(INSTANCE),{cache:'no-store'});if(!result.ok)throw Error('offline');const data=await result.json();document.getElementById('subtitle').textContent=(data.name||INSTANCE)+' · '+(data.seed||'No seed');entries.replaceChildren();for(const ev of (data.events||[]).slice(-8).reverse()){const row=node('div');row.className='entry';row.dataset.kind=ev.category;row.append(node('span',ev.timestamp||'',));const box=node('div'),label=node('div',types[ev.category]||'Event'),line=node('div',(ev.item||'')+(ev.player?' · '+ev.player:'')+(ev.recipient?' → '+ev.recipient:'')+(ev.location?' · '+ev.location:''));label.className='label';line.className='detail';box.append(label,line);row.append(box);entries.append(row)}}catch(e){document.getElementById('signal').textContent='○ OFFLINE'}}
refresh();setInterval(refresh,2000);
</script></body></html>'''


def render_obs_log(instance: str) -> str:
    return OBS_HTML.replace("__INSTANCE__", json.dumps(instance))
