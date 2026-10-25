"""Lokale ArchiCord-Verwaltung: .env AP_URL bearbeiten und Bot-Prozess steuern.
Nur auf 127.0.0.1 verfügbar. Keine externen Abhängigkeiten.
"""
from __future__ import annotations

import argparse
import ast
import atexit
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from urllib.parse import unquote, urlsplit

from tracker.apworld_manager import scan_worlds, load_selection, save_selection

ROOT = Path(__file__).resolve().parent
ENV = ROOT / '.env'
# Bei Updates in Unterordnern die vorhandene Konfiguration weiterverwenden.
if not ENV.exists():
    for candidate in (ROOT.parent / '.env', ROOT.parent / 'ArchiCord' / '.env'):
        if candidate.is_file():
            ENV = candidate
            break
ENV_EXAMPLE = ROOT / '.env.example'
BOT = ROOT / 'archicord.py'
ASSETS_DIR = ROOT / 'webui_assets'
LOCK = threading.RLock()
CSRF = secrets.token_urlsafe(32)
PROCESS = None
LOG = deque(maxlen=250)
READER = None
BOT_STATUS = {"discord": "offline", "archipelago": "offline", "last_error": "", "exit_code": None}

FIELDS = (
    'AP_URL', 'AP_SLOT', 'AP_PASSWORD', 'AP_GAME', 'ITEM_CHANNEL_ID',
    'HINT_CHANNEL_ID', 'DEATHLINK_CHANNEL_ID', 'STATUS_CHANNEL_ID',
    'ARCHICORD_AP_INSTALL_DIR', 'ARCHICORD_APWORLD_DIRS'
)
DEFAULTS = {
    'AP_URL': 'wss://archipelago.gg:61664',
    'AP_SLOT': '',
    'AP_PASSWORD': '',
    'AP_GAME': '',
    'ITEM_CHANNEL_ID': '',
    'HINT_CHANNEL_ID': '',
    'DEATHLINK_CHANNEL_ID': '',
    'STATUS_CHANNEL_ID': '',
    'ARCHICORD_AP_INSTALL_DIR': r'C:\ProgramData\Archipelago',
    'ARCHICORD_APWORLD_DIRS': '',
}


def read_env_value(key):
    if not ENV.exists():
        return ''
    for line in ENV.read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^\s*([A-Z_]+)\s*=(.*)$', line)
        if match and match.group(1) == key:
            return match.group(2).strip().strip('"\'')
    return ''


def token_configured():
    token = read_env_value('DISCORD_TOKEN')
    return bool(token and not any(word in token.upper() for word in ('HIER_EINTRAGEN', 'YOUR_TOKEN', 'DEIN_TOKEN', 'PLACEHOLDER')))


def ensure_env():
    # Eine vorhandene .env niemals beim WebUI-Start ersetzen.
    if ENV.exists():
        return
    template = ENV_EXAMPLE.read_text(encoding='utf-8') if ENV_EXAMPLE.exists() else ''
    if not template:
        template = 'DISCORD_TOKEN=\n'
    with ENV.open('x', encoding='utf-8') as f:
        f.write(template)


def read_settings():
    result = dict(DEFAULTS)
    if ENV.exists():
        for line in ENV.read_text(encoding='utf-8-sig').splitlines():
            match = re.match(r'^\s*([A-Z_]+)\s*=(.*)$', line)
            if match and match.group(1) in FIELDS:
                result[match.group(1)] = match.group(2).strip().strip('"\'')
    return result


def env_url():
    return read_settings()['AP_URL']


def parse_address(value):
    value = str(value).strip()
    if not value or len(value) > 300 or any(c in value for c in '\r\n\x00'):
        raise ValueError('Ungültige Serveradresse.')
    if '://' not in value:
        value = 'wss://' + value
    url = urlsplit(value)
    if url.scheme not in ('ws', 'wss') or not url.hostname or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
        raise ValueError('Erlaubt sind ws:// oder wss:// mit Host und Port.')
    try:
        port = url.port
    except ValueError:
        raise ValueError('Ungültiger Port.') from None
    if port is None or not 1 <= port <= 65535:
        raise ValueError('Bitte einen Port von 1 bis 65535 angeben.')
    return f'{url.scheme}://{url.netloc}'


def save_settings(values):
    if not isinstance(values, dict):
        raise ValueError('Ungültige Einstellungen.')
    clean = {}
    new_token = values.get('DISCORD_TOKEN', '')
    if new_token is not None and not isinstance(new_token, str):
        raise ValueError('Ungültiger Discord-Token.')
    new_token = (new_token or '').strip()
    if new_token:
        if any(c in new_token for c in '\r\n\x00') or len(new_token) > 300 or any(c.isspace() for c in new_token):
            raise ValueError('Ungültiger Discord-Token.')
        clean['DISCORD_TOKEN'] = new_token
    for key in FIELDS:
        if key not in values:
            continue
        value = str(values[key]).strip()
        if any(c in value for c in '\r\n\x00') or len(value) > 300:
            raise ValueError(f'Ungültiger Wert für {key}.')
        if key == 'AP_URL':
            value = parse_address(value)
        if key.endswith('_CHANNEL_ID') and value and not re.fullmatch(r'\d{15,22}', value):
            raise ValueError(f'{key} muss eine Discord-Kanal-ID sein.')
        if key == 'AP_SLOT' and not value:
            raise ValueError(f'{key} darf nicht leer sein.')
        if key == 'AP_PASSWORD' and not value:
            # Ein leeres Passwortfeld im Browser darf ein bereits gespeichertes
            # Archipelago-Passwort niemals unbeabsichtigt entfernen.
            continue
        clean[key] = value
    with LOCK:
        ensure_env()
        lines = ENV.read_text(encoding='utf-8-sig').splitlines(keepends=True)
        seen = set()
        output = []
        for line in lines:
            match = re.match(r'^\s*([A-Z_]+)\s*=', line)
            if match and match.group(1) in clean:
                key = match.group(1)
                if key not in seen:
                    output.append(f'{key}={json.dumps(clean[key], ensure_ascii=False) if key in ("AP_GAME", "AP_PASSWORD", "AP_SLOT") else clean[key]}\n')
                    seen.add(key)
            else:
                output.append(line if line.endswith('\n') else line + '\n')
        for key, value in clean.items():
            if key not in seen:
                output.append(f'{key}={json.dumps(value, ensure_ascii=False) if key in ("AP_GAME", "AP_PASSWORD", "AP_SLOT") else value}\n')
        temp = ENV.with_name('.env.tmp')
        try:
            with temp.open('w', encoding='utf-8') as f:
                f.writelines(output)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, ENV)
        finally:
            temp.unlink(missing_ok=True)
    return read_settings()


def safe_logs():
    lines = list(LOG)
    for name in ('DISCORD_TOKEN', 'AP_PASSWORD'):
        secret = read_env_value(name)
        if secret:
            lines = [line.replace(secret, '[' + name + '_VERBORGEN]') for line in lines]
    return lines


def update_status_from_log(line, proc):
    with LOCK:
        if PROCESS is not proc:
            return
        if 'ArchiCord 2.0 eingeloggt als ' in line:
            BOT_STATUS['discord'] = 'online'
        elif '[AP] Als ' in line and ' verbunden, Seed ' in line:
            BOT_STATUS['archipelago'] = 'online'
        elif '[AP] Verbinde mit ' in line:
            BOT_STATUS['archipelago'] = 'connecting'
        elif '[AP] Verbindung abgelehnt:' in line:
            BOT_STATUS['archipelago'] = 'error'
            BOT_STATUS['last_error'] = line[:300]
        elif '[AP] Verbindungsfehler:' in line:
            BOT_STATUS['archipelago'] = 'error'
            BOT_STATUS['last_error'] = line[:300]
        elif 'LoginFailure:' in line or 'Improper token' in line:
            BOT_STATUS['discord'] = 'error'
            BOT_STATUS['last_error'] = 'Discord-Anmeldung fehlgeschlagen. Bot-Token prüfen.'
        elif 'Traceback (most recent call last)' in line:
            BOT_STATUS['last_error'] = 'Python-Fehler im Bot. Details in der Konsole.'


def log_reader(proc):
    try:
        for line in proc.stdout:
            update_status_from_log(line, proc)
            with LOCK:
                LOG.append(line.rstrip()[:500])
    except (OSError, ValueError):
        pass
    finally:
        with LOCK:
            LOG.append(f'[WebUI] Bot-Prozess beendet (Exitcode {proc.poll()}).')
            if PROCESS is proc:
                BOT_STATUS['exit_code'] = proc.poll()
                BOT_STATUS['discord'] = 'offline'
                BOT_STATUS['archipelago'] = 'offline'


def is_running():
    return PROCESS is not None and PROCESS.poll() is None


def start_bot():
    global PROCESS, READER
    with LOCK:
        if is_running():
            raise ValueError('Bot läuft bereits.')
        if not ENV.exists():
            raise ValueError('Die .env fehlt. Erstelle sie zuerst aus .env.example.')
        if not BOT.exists():
            raise ValueError('archicord.py fehlt.')
        parse_address(env_url())
        if not token_configured():
            raise ValueError('Discord-Token fehlt. Bitte im geschützten Token-Feld einmalig speichern.')
        LOG.append('[WebUI] Starte ArchiCord: ' + str(BOT))
        LOG.append('[WebUI] Konfiguration: ' + str(ENV))
        BOT_STATUS.update(discord='starting', archipelago='offline', last_error='', exit_code=None)
        child_env = os.environ.copy()
        child_env['ARCHICORD_ENV_FILE'] = str(ENV.resolve())
        PROCESS = subprocess.Popen(
            [sys.executable, '-u', str(BOT)], cwd=ROOT, env=child_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1,
        )
        READER = threading.Thread(target=log_reader, args=(PROCESS,), daemon=True)
        READER.start()
        return 'Bot-Prozess gestartet. Discord-/AP-Verbindung bitte im Live-Log prüfen.'


def stop_bot():
    with LOCK:
        proc = PROCESS
        if proc is None or proc.poll() is not None:
            return 'Bot ist bereits gestoppt.'
        LOG.append('[WebUI] Stoppe ArchiCord ...')
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    with LOCK:
        BOT_STATUS['discord'] = 'offline'
        BOT_STATUS['archipelago'] = 'offline'
    return 'Bot gestoppt.'


def shutdown():
    try:
        stop_bot()
    except Exception:
        pass


atexit.register(shutdown)

BASE_STYLE = r'''
:root{
  color-scheme:dark;
  --bg:#07101d;
  --bg-soft:#0b1425;
  --card:rgba(10,17,31,.78);
  --card-border:rgba(120,146,255,.18);
  --text:#f7f8ff;
  --muted:#b2bfd9;
  --line:rgba(141,160,255,.14);
  --accent:#7480ff;
  --accent-2:#ef6fae;
  --accent-3:#82e1a0;
  --accent-4:#f3df7d;
  --shadow:0 18px 60px rgba(0,0,0,.36);
  --radius:22px;
  --radius-sm:14px;
  font-family:Inter, Poppins, "Avenir Next", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}
*{box-sizing:border-box}
html,body{min-height:100%}
body{
  margin:0;
  color:var(--text);
  background:
    linear-gradient(rgba(6,10,20,.86), rgba(6,10,20,.92)),
    url('/assets/archicord-bg.png') center/cover fixed no-repeat,
    radial-gradient(circle at top right, rgba(239,111,174,.18), transparent 32%),
    radial-gradient(circle at bottom left, rgba(103,126,255,.20), transparent 30%),
    var(--bg);
}
a{color:#cad1ff;text-decoration:none}
a:hover{text-decoration:underline}
main{max-width:1180px;margin:0 auto;padding:32px 18px 48px}
.hero{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:24px}
.brand{display:flex;align-items:center;gap:18px}
.brand img{width:88px;height:88px;object-fit:contain;filter:drop-shadow(0 10px 24px rgba(0,0,0,.35))}
.hero-copy h1{font-size:clamp(2rem,4.2vw,3.5rem);line-height:1.03;margin:0 0 8px;font-weight:900;letter-spacing:-.04em}
.hero-copy p{margin:0;color:var(--muted);max-width:760px;line-height:1.65}
.title-gradient{background:linear-gradient(90deg,#ffffff 0 42%, #8b93ff 60%, #95b7ff 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.navbar{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 24px}
.nav-pill{display:inline-flex;align-items:center;gap:10px;padding:12px 16px;border-radius:999px;background:rgba(9,15,27,.68);border:1px solid var(--line);backdrop-filter:blur(12px);box-shadow:var(--shadow);font-weight:700;color:#ecf1ff}
.nav-pill.active{background:linear-gradient(135deg, rgba(116,128,255,.32), rgba(239,111,174,.18));border-color:rgba(184,190,255,.28)}
.icon-badge{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,.12), rgba(255,255,255,.03));border:1px solid rgba(255,255,255,.08);box-shadow:inset 0 1px 0 rgba(255,255,255,.1)}
.icon-badge.pink{box-shadow:0 0 0 1px rgba(239,111,174,.18) inset;background:linear-gradient(180deg, rgba(239,111,174,.30), rgba(239,111,174,.08))}
.icon-badge.green{box-shadow:0 0 0 1px rgba(130,225,160,.18) inset;background:linear-gradient(180deg, rgba(130,225,160,.26), rgba(130,225,160,.08))}
.icon-badge.blue{box-shadow:0 0 0 1px rgba(116,128,255,.18) inset;background:linear-gradient(180deg, rgba(116,128,255,.30), rgba(116,128,255,.08))}
.icon-badge.gold{box-shadow:0 0 0 1px rgba(243,223,125,.18) inset;background:linear-gradient(180deg, rgba(243,223,125,.26), rgba(243,223,125,.08))}
.grid{display:grid;gap:20px}
.grid.two{grid-template-columns:1.15fr .85fr}
@media (max-width:980px){.grid.two{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--card-border);border-radius:var(--radius);padding:22px;box-shadow:var(--shadow);backdrop-filter:blur(18px);position:relative;overflow:hidden}
.card::before{content:"";position:absolute;inset:0 auto auto 0;width:100%;height:1px;background:linear-gradient(90deg, rgba(255,255,255,.16), transparent 70%)}
.card h2,.card h3{margin:0 0 10px;font-size:1.16rem;letter-spacing:-.02em}
.section-sub{color:var(--muted);line-height:1.6;margin:0 0 12px}
.status-stack{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:14px}
.mini-panel{padding:14px 16px;border-radius:18px;background:rgba(8,13,24,.62);border:1px solid rgba(255,255,255,.06)}
.mini-panel strong{display:block;font-size:.84rem;color:#d2daf2;margin-bottom:8px}
.mini-panel span{display:flex;align-items:center;gap:10px;font-size:1rem;font-weight:700}
.pill{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:7px 12px;font-size:.94rem;font-weight:800;background:rgba(44,58,79,.68);border:1px solid rgba(255,255,255,.06)}
.pill.on{background:rgba(31,92,68,.88);color:#b9ffd5}.pill.off{background:rgba(115,45,59,.88);color:#ffe0e6}
.pill.wait{background:rgba(112,100,32,.8);color:#fff4bf}
label{display:block;font-weight:750;margin:14px 0 8px;color:#f5f8ff}
input,pre{font:inherit}
input[type=text],input[type=password],input[type=search]{width:100%;background:rgba(6,12,22,.82);border:1px solid rgba(147,163,214,.20);color:#fff;border-radius:15px;padding:14px 15px;outline:none;transition:.15s border-color,.15s box-shadow}
input[type=text]:focus,input[type=password]:focus,input[type=search]:focus{border-color:rgba(144,154,255,.56);box-shadow:0 0 0 4px rgba(116,128,255,.16)}
input[type=checkbox]{width:20px;height:20px;vertical-align:middle;accent-color:#7480ff}
button{border:0;border-radius:16px;padding:13px 18px;color:#fff;background:linear-gradient(135deg,#6d78ff,#8d66ff);font-weight:850;letter-spacing:.01em;cursor:pointer;margin:8px 10px 0 0;box-shadow:0 12px 24px rgba(73,80,209,.28);transition:.16s transform,.16s filter}
button:hover{transform:translateY(-1px);filter:brightness(1.08)}
button.secondary{background:linear-gradient(135deg, rgba(92,109,151,.95), rgba(52,73,107,.95));box-shadow:none}
button.stop,button.danger{background:linear-gradient(135deg,#b8466b,#913551)}
button.restart{background:linear-gradient(135deg,#2d87d5,#506bff)}
.notice{min-height:24px;color:#a7ecff;line-height:1.5}
.hint,.meta,small,p{color:var(--muted)}
pre{height:320px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:rgba(5,10,20,.82);padding:18px;border-radius:18px;border:1px solid rgba(255,255,255,.06);font-size:.86rem;line-height:1.58}
.list-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:16px}
.world{background:rgba(6,12,22,.72);border:1px solid rgba(255,255,255,.08);padding:16px;border-radius:18px;min-width:0;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.world.invalid{opacity:.7}
.world strong,.world .meta{overflow-wrap:anywhere}
.world strong{display:block;font-size:1rem}
.ok{color:#9df2bb}.warn{color:#ffd789}
.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.toolbar input{flex:1;min-width:210px}
.number{font-variant-numeric:tabular-nums;color:#eaf0ff;font-weight:800}
.footer-note{margin-top:16px;font-size:.85rem;color:var(--muted)}
code{color:#cad1ff}
.banner{display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:18px;background:linear-gradient(135deg, rgba(15,25,48,.9), rgba(10,17,31,.66));border:1px solid rgba(255,255,255,.08);margin-bottom:18px}
.banner strong{display:block;font-size:1rem;margin-bottom:4px}
hr.soft{border:0;height:1px;background:linear-gradient(90deg, rgba(255,255,255,.14), transparent);margin:18px 0}
'''

HTML = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ArchiCord Control Center</title><style>'''+BASE_STYLE+'''</style></head><body><main>
<nav class="navbar"><a class="nav-pill active" href="/"><span class="icon-badge blue">🎮</span>Bot-Steuerung</a><a class="nav-pill" href="/apworlds"><span class="icon-badge pink">🧩</span>APWorld-Verwaltung</a></nav>
<section class="hero"><div class="brand"><img src="/assets/archicord-logo.png" alt="ArchiCord Logo"><div class="hero-copy"><h1><span class="title-gradient">ArchiCord</span> Control Center</h1><p>Verwalte deinen Archipelago-Bot mit dem neuen ArchiCord-WebUI-Look: Serververbindung, Live-Status, Konfiguration und Bot-Konsole an einem Ort.</p></div></div></section>
<div class="grid two">
  <section class="card">
    <div class="banner"><span class="icon-badge green">●</span><div><strong>Bot-Status</strong><span class="meta">Starten, stoppen und überwachen – direkt aus der WebUI.</span></div></div>
    <div><strong>Prozess:</strong> <span id="state" class="pill">Lade …</span></div>
    <div class="status-stack">
      <div class="mini-panel"><strong>Discord</strong><span><span class="icon-badge blue">💬</span><span id="discordState">Prüfe …</span></span></div>
      <div class="mini-panel"><strong>Archipelago</strong><span><span class="icon-badge pink">🌐</span><span id="apState">Prüfe …</span></span></div>
    </div>
    <p id="lastError" class="section-sub"></p>
    <p id="notice" class="notice"></p>
    <button onclick="action('start')">▶ Starten</button><button class="restart" onclick="action('restart')">↻ Neustarten</button><button class="stop" onclick="action('stop')">■ Stoppen</button>
  </section>
  <section class="card">
    <div class="banner"><span class="icon-badge gold">🔒</span><div><strong>Sicherheit & Hinweise</strong><span class="meta">Die WebUI läuft nur lokal auf 127.0.0.1.</span></div></div>
    <p class="section-sub">Dein Discord-Token wird <strong>niemals angezeigt</strong> und beim normalen Speichern auch nicht überschrieben. Änderungen an der Konfiguration werden dauerhaft in derselben <code>.env</code> gesichert.</p>
    <p class="section-sub">Die WebUI startet und steuert den <strong>ArchiCord-Bot</strong>, nicht den Archipelago-Server selbst.</p>
    <p class="footer-note">Schließen der WebUI: <strong>Strg+C</strong> im Terminal.</p>
  </section>
</div>
<section class="card"><div class="banner"><span class="icon-badge pink">⚙</span><div><strong>Gespeicherte .env-Einstellungen</strong><span class="meta">Alle Änderungen bleiben dauerhaft erhalten. Der Discord-Token bleibt verborgen.</span></div></div>
<div id="fields"></div><label for="discordToken">Discord-Token (optional neu setzen)</label><input id="discordToken" type="password" autocomplete="new-password" placeholder="Leer lassen = gespeicherten Token behalten"><p class="hint" id="tokenStatus"></p><button onclick="action('save')">💾 Speichern</button><button class="restart" onclick="action('save_restart')">💾 Speichern & Neustarten</button></section>
<section class="card"><div class="banner"><span class="icon-badge blue">📝</span><div><strong>Bot-Konsole</strong><span class="meta">Die letzten 250 Logzeilen. Keine Token oder Passwörter hier eingeben.</span></div></div><pre id="log"></pre></section>
<script>
const token=__TOKEN__;let edited=false;
const names={AP_URL:'Archipelago-Adresse / Port',AP_SLOT:'Slot-Name',AP_PASSWORD:'Archipelago-Passwort',AP_GAME:'Spiel',ITEM_CHANNEL_ID:'Item-Kanal',HINT_CHANNEL_ID:'Hint-Kanal',DEATHLINK_CHANNEL_ID:'DeathLink-Kanal',STATUS_CHANNEL_ID:'Status-Kanal',ARCHICORD_AP_INSTALL_DIR:'Archipelago-Installationsordner',ARCHICORD_APWORLD_DIRS:'Zusätzliche APWorld-Ordner (mit ; getrennt)'};
const fields=document.getElementById('fields');
for(const [key,name] of Object.entries(names)){
  const label=document.createElement('label');label.htmlFor=key;label.textContent=name+' ('+key+')';
  const inp=document.createElement('input');inp.id=key;inp.autocomplete='off';inp.type=key==='AP_PASSWORD'?'password':'text';if(key==='AP_PASSWORD')inp.placeholder='Leer lassen = gespeichertes Passwort behalten';inp.addEventListener('input',()=>edited=true);fields.append(label,inp)
}
function uiStatusText(value){return value==='online'?'Online':value==='starting'?'Startet …':value==='connecting'?'Verbinde …':value==='error'?'Fehler':'Offline'}
function decoratePill(elem, running){elem.className='pill '+(running?'on':'off')}
async function refresh(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json();
    document.getElementById('tokenStatus').textContent=d.token_configured?'✓ Discord-Token ist lokal gespeichert (Wert verborgen).':'⚠ Noch kein Discord-Token gespeichert.';
    const s=document.getElementById('state');s.textContent=d.running?'● Läuft (PID '+d.pid+')':'● Gestoppt';decoratePill(s,d.running);
    document.getElementById('discordState').textContent=uiStatusText(d.discord_status);
    document.getElementById('apState').textContent=uiStatusText(d.archipelago_status);
    document.getElementById('lastError').textContent=d.last_error||(!d.running&&d.exit_code!==null?'Bot beendet (Exitcode '+d.exit_code+').':'');
    if(!edited)for(const key of Object.keys(names))document.getElementById(key).value=d.settings[key]??'';
    document.getElementById('log').textContent=d.logs.join('\\n');
  }catch(e){document.getElementById('notice').textContent='Verbindung zur WebUI verloren.'}
}
async function action(op){
  const notice=document.getElementById('notice');notice.textContent='Bitte warten …';
  const settings={};for(const key of Object.keys(names))settings[key]=document.getElementById(key).value;
  const newToken=document.getElementById('discordToken').value;if(newToken)settings.DISCORD_TOKEN=newToken;
  try{
    const r=await fetch('/api/'+op,{method:'POST',headers:{'Content-Type':'application/json','X-ArchiCord-Token':token},body:JSON.stringify({settings})});
    const d=await r.json();notice.textContent=d.message;if(d.ok){document.getElementById('discordToken').value='';edited=false;await refresh()}
  }catch(e){notice.textContent='Fehler: '+e.message}
}
refresh();setInterval(refresh,2500);
</script></main></body></html>'''

APWORLD_HTML = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ArchiCord · APWorld-Verwaltung</title><style>'''+BASE_STYLE+'''</style></head><body><main>
<nav class="navbar"><a class="nav-pill" href="/"><span class="icon-badge blue">🎮</span>Bot-Steuerung</a><a class="nav-pill active" href="/apworlds"><span class="icon-badge pink">🧩</span>APWorld-Verwaltung</a></nav>
<section class="hero"><div class="brand"><img src="/assets/archicord-logo.png" alt="ArchiCord Logo"><div class="hero-copy"><h1><span class="title-gradient">APWorld-Verwaltung</span></h1><p>Durchsuche installierte <code>.apworld</code>-Dateien und lege fest, welche Spiele ArchiCord per Universal Tracker live abfragen soll.</p></div></div></section>
<section class="card"><div class="toolbar"><button class="secondary" id="rescan">↻ APWorlds neu einlesen</button><button class="secondary" id="seedOnly">🎮 Aktuelle Seed-Spiele auswählen</button><button class="secondary" id="selectAll">Alle gültigen</button><button class="secondary" id="selectNone">Keine</button></div>
<p id="summary" class="section-sub">Lese installierte APWorlds …</p><p id="seedInfo" class="section-sub"></p><p class="warn" id="warnings"></p><div class="toolbar"><input id="search" type="search" placeholder="Spielname oder APWorld-Datei suchen …"><span id="counter" class="number"></span></div></section>
<div id="list" class="list-grid"></div>
<section class="card"><div class="banner"><span class="icon-badge green">💾</span><div><strong>Auswahl speichern</strong><span class="meta">Die Auswahl wird in <code>tracker/settings/apworld_selection.json</code> gespeichert – unabhängig von der <code>.env</code>.</span></div></div>
<p class="section-sub">Nicht ausgewählte Spiele werden bei der nächsten Universal-Tracker-Abfrage übersprungen. Für eine sofortige Neuberechnung kannst du „Speichern & Bot neu starten“ nutzen.</p>
<div><button id="save">💾 Auswahl speichern</button><button id="saveRestart" class="restart">💾 Speichern & Bot neu starten</button></div>
<p class="notice" id="notice"></p>
<p class="footer-note">Die Auswahl steuert die ArchiCord-Tracker-Abfragen, <strong>nicht</strong> das Laden der APWorlds durch den Archipelago-Launcher. Es werden keine Dateien verschoben oder gelöscht.</p></section>
<script>
const csrf=__TOKEN__;
let catalog=[],selected=new Map(),seedGames=[],filterText='',configured=false;
const $=id=>document.getElementById(id);
function note(msg){$('notice').textContent=msg||''}
function updateSummary(){
  const valid=catalog.filter(x=>x.valid).length;
  const invalid=catalog.length-valid;
  $('summary').textContent=`${catalog.length} APWorld(s) gefunden · ${valid} mit lesbarem Manifest · ${invalid} auffällig`;
  $('seedInfo').textContent=seedGames.length?('Aktuelle Seed-Spiele: '+seedGames.join(', ')):'Noch keine Seed-Spiele im Bot-Log erkannt.';
}
async function readCatalog(){
  try{
    note('APWorlds werden eingelesen …');
    const r=await fetch('/api/apworlds',{cache:'no-store'});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.message||'Fehler beim Laden');
    catalog=d.worlds||[];configured=!!d.configured;seedGames=d.seed_games||[];selected=new Map();
    for(const row of (d.selection||[]))selected.set(row.id,row.game_override||'');
    updateSummary();draw();
    note(configured?'Gespeicherte Auswahl geladen.':'Noch keine gespeicherte APWorld-Auswahl vorhanden.');
  }catch(e){note('Fehler: '+e.message)}
}
function draw(){
  updateSummary();
  const duplicates=[];
  const validShown=catalog.filter(row=>(row.game+' '+row.file+' '+row.source).toLowerCase().includes(filterText));
  const counts=new Map();for(const row of catalog.filter(x=>x.valid)){counts.set(row.game,(counts.get(row.game)||0)+1)}
  for(const [game,count] of counts.entries())if(count>1)duplicates.push(game);
  $('warnings').textContent=duplicates.length?('Hinweis · Mehrfach gefundene Spiele (Versionen prüfen): '+duplicates.join(', ')):' ';
  $('counter').textContent=selected.size+' ausgewählt';
  const list=$('list');list.replaceChildren();
  for(const row of validShown){
    const card=document.createElement('div');card.className='world'+(row.valid?'':' invalid');
    const line=document.createElement('label');
    const cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(row.id);cb.disabled=!row.valid;
    const heading=document.createElement('strong');heading.textContent=' '+(row.game||row.file);
    line.append(cb,heading);card.append(line);
    const meta=document.createElement('div');meta.className='meta';meta.textContent=row.file+' · '+row.source;card.append(meta);
    const state=document.createElement('div');state.className=row.valid?'ok':'warn';state.textContent=row.valid?'✓ Manifest gelesen'+(row.world_version?' · Version '+row.world_version:''):'⚠ '+row.detail;card.append(state);
    if(row.valid){
      const hint=document.createElement('p');hint.className='meta';hint.textContent='Spielname für AP-Zuordnung (nur bei abweichender Spielbezeichnung ändern):';card.append(hint);
      const inp=document.createElement('input');inp.type='text';inp.value=selected.get(row.id)||row.game;inp.maxLength=160;inp.setAttribute('aria-label','Archipelago-Spielname für '+row.file);card.append(inp);
      cb.addEventListener('change',()=>{if(cb.checked)selected.set(row.id,inp.value.trim()||row.game);else selected.delete(row.id);draw()});
      inp.addEventListener('input',()=>{if(selected.has(row.id)){selected.set(row.id,inp.value);$('counter').textContent=selected.size+' ausgewählt';}});
    }
    list.append(card);
  }
}
function changeSelection(kind){
 if(kind==='all')selected=new Map(catalog.filter(x=>x.valid).map(x=>[x.id,x.game]));
 if(kind==='none')selected=new Map();
 if(kind==='seed'){
   if(!seedGames.length){note('Aktuell sind keine Seed-Spiele im Bot-Log zu finden. Verbinde den Bot oder wähle manuell.');return}
   const pool=catalog.filter(x=>x.valid&&seedGames.some(g=>g.trim().toLowerCase()===x.game.trim().toLowerCase()));
   pool.sort((a,b)=>(a.source==='Archipelago/custom_worlds'?-1:1)-(b.source==='Archipelago/custom_worlds'?-1:1));
   selected=new Map();const used=new Set();for(const row of pool){const name=row.game.trim().toLowerCase();if(!used.has(name)){selected.set(row.id,row.game);used.add(name)}}
   const selectedNames=new Set([...selected.values()].map(g=>g.trim().toLowerCase()));
   const missing=seedGames.filter(g=>!selectedNames.has(g.trim().toLowerCase()));
   note(missing.length?'Für diese Spiele wurde kein passendes gültiges Manifest gefunden: '+missing.join(', '):'Passende Seed-Spiele ausgewählt. Jetzt speichern.');
 }
 draw();
}
async function save(restart){
 const worlds=Array.from(selected.entries()).map(([id,game])=>({id,game_override:game}));
 try{
  note('Auswahl wird gespeichert …');
  const r=await fetch(restart?'/api/apworlds/save_restart':'/api/apworlds/save',{method:'POST',headers:{'Content-Type':'application/json','X-ArchiCord-Token':csrf},body:JSON.stringify({worlds})});
  const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.message||'Speichern fehlgeschlagen');
  await readCatalog();note(d.message);
 }catch(e){note('Fehler: '+e.message)}
}
$('rescan').addEventListener('click',readCatalog);
$('search').addEventListener('input',e=>{filterText=e.target.value.toLowerCase();draw()});
$('seedOnly').addEventListener('click',()=>changeSelection('seed'));
$('selectAll').addEventListener('click',()=>changeSelection('all'));
$('selectNone').addEventListener('click',()=>changeSelection('none'));
$('save').addEventListener('click',()=>save(false));
$('saveRestart').addEventListener('click',()=>save(true));
readCatalog();
</script></main></body></html>'''


def catalog_worlds():
    settings = read_settings()
    return scan_worlds(ROOT, install_dir=settings.get('ARCHICORD_AP_INSTALL_DIR'),
                       extra_dirs=settings.get('ARCHICORD_APWORLD_DIRS'))


def detected_seed_games():
    with LOCK:
        current = list(LOG)
    for line in reversed(current):
        if '[AP] Als ' not in line or ' Spiele: ' not in line:
            continue
        try:
            value = ast.literal_eval(line.split(' Spiele: ', 1)[1].strip())
            if isinstance(value, list):
                return [game for game in value if isinstance(game, str)][:100]
        except (SyntaxError, ValueError, TypeError):
            pass
    return []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def reply(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def serve_asset(self, relative):
        relative = unquote(relative).lstrip('/').replace('..', '')
        path = (ASSETS_DIR / relative).resolve()
        if not path.is_relative_to(ASSETS_DIR.resolve()) or not path.is_file():
            return self.reply(404, {'ok': False, 'message': 'Datei nicht gefunden.'})
        content_type = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith('/assets/'):
            return self.serve_asset(self.path[len('/assets/'):])
        if self.path == '/':
            raw = HTML.replace('__TOKEN__', json.dumps(CSRF)).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == '/apworlds':
            raw = APWORLD_HTML.replace('__TOKEN__', json.dumps(CSRF)).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == '/api/apworlds':
            try:
                catalog = catalog_worlds()
                selection = load_selection(ROOT)
                current_ids = {item['id'] for item in catalog}
                saved = selection['worlds'] if selection else []
                self.reply(200, {'ok': True, 'worlds': catalog,
                                 'selection': saved, 'configured': selection is not None,
                                 'stale_count': sum(row['id'] not in current_ids for row in saved),
                                 'seed_games': detected_seed_games()})
            except (OSError, ValueError) as exc:
                self.reply(400, {'ok': False, 'message': str(exc)})
        elif self.path == '/api/status':
            with LOCK:
                self.reply(200, {'running': is_running(), 'pid': PROCESS.pid if is_running() else None,
                    'settings': {k: v for k, v in read_settings().items() if k != 'AP_PASSWORD'},
                    'ap_password_configured': bool(read_env_value('AP_PASSWORD')),
                    'token_configured': token_configured(), 'logs': safe_logs(),
                    'discord_status': BOT_STATUS['discord'] if is_running() else 'offline',
                    'archipelago_status': BOT_STATUS['archipelago'] if is_running() else 'offline',
                    'last_error': BOT_STATUS['last_error'], 'exit_code': BOT_STATUS['exit_code']})
        else:
            self.reply(404, {'ok': False, 'message': 'Nicht gefunden.'})

    def do_POST(self):
        origin = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        if (origin and origin not in ('http://' + host,)) or not secrets.compare_digest(self.headers.get('X-ArchiCord-Token', ''), CSRF):
            return self.reply(403, {'ok': False, 'message': 'Zugriff verweigert.'})
        if self.path not in ('/api/start', '/api/stop', '/api/restart', '/api/save', '/api/save_restart',
                             '/api/apworlds/save', '/api/apworlds/save_restart'):
            return self.reply(404, {'ok': False, 'message': 'Unbekannte Aktion.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= (131072 if self.path.startswith('/api/apworlds/') else 2048):
                raise ValueError('Anfrage zu groß.')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('Ungültige Anfrage.')
            if self.path.startswith('/api/apworlds/'):
                save_selection(ROOT, data.get('worlds'), catalog_worlds())
                msg = 'APWorld-Auswahl dauerhaft gespeichert. '
                if self.path.endswith('/save_restart'):
                    msg += stop_bot() + ' ' + start_bot()
                else:
                    msg += 'Die Änderung greift bei der nächsten Tracker-Abfrage; alternativ Bot neu starten.'
                return self.reply(200, {'ok': True, 'message': msg})
            if self.path in ('/api/save', '/api/save_restart'):
                save_settings(data.get('settings', {}))
                msg = 'Einstellungen dauerhaft in .env gespeichert. '
            else:
                msg = ''
            if self.path in ('/api/stop', '/api/restart', '/api/save_restart'):
                msg += stop_bot() + ' '
            if self.path in ('/api/start', '/api/restart', '/api/save_restart'):
                msg += start_bot()
            return self.reply(200, {'ok': True, 'message': msg.strip() or 'Gespeichert.'})
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return self.reply(400, {'ok': False, 'message': str(exc)})


def main():
    parser = argparse.ArgumentParser(description='Lokale ArchiCord WebUI')
    parser.add_argument('--port', type=int, default=8765, help='Lokaler WebUI-Port (Standard 8765)')
    args = parser.parse_args()
    ensure_env()
    if not 1 <= args.port <= 65535:
        parser.error('Port muss zwischen 1 und 65535 liegen.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'ArchiCord WebUI: http://127.0.0.1:{args.port}', flush=True)
    print('Nur lokal erreichbar. Strg+C zum Beenden. Bot über die WebUI starten.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shutdown()


if __name__ == '__main__':
    main()
