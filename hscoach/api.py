"""Lese-API: Zugplan und Spielstand als JSON, Text und kleine Webseite (fuer Zweitbildschirme, Handy, Tablet, USB-Displays).

Nur lesen, nichts steuern. Standardmaessig nur auf diesem PC (127.0.0.1) erreichbar. Im Heimnetz (LAN) nur mit Zugangscode
(Token) und nur von privaten Adressen. Es werden keine Namen von Mitspielern, kein BattleTag und kein API-Key ausgegeben.

Endpunkte (GET):
  /                 Webseite mit dem aktuellen Plan (aktualisiert sich selbst)
  /api/state        alles als JSON; mit ?since=<version> wartet die Antwort bis zu 20 s auf eine Aenderung (Long-Poll)
  /api/plan         nur Phase, Zugplan, Warnungen (kleiner, fuer Mini-Displays)
  /api/plan.txt     Plan als reiner Text
  /api/health       {"ok": true, "version": ...}
Zugangscode: ?token=... oder Kopfzeile "X-Token: ..." oder "Authorization: Bearer ...".
"""
import ipaddress
import json
import logging
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__

log = logging.getLogger("hscoach.api")
LONG_POLL_S = 20.0


# -- Momentaufnahme -------------------------------------------------------------------------------------------------
def _mini(m):
    d = {"name": m.name, "atk": m.atk, "hp": m.hp}
    for k in ("can_attack", "taunt", "divine_shield", "frozen", "stealth", "lifesteal", "poisonous"):
        if getattr(m, k, False):
            d[k] = True
    if (getattr(m, "windfury", 1) or 1) > 1:
        d["windfury"] = True
    return d


def _step(i, st):
    title, _, detail = st.text.partition("  →  ")
    d = {"n": i, "kind": st.kind, "title": title.strip(), "text": st.text}
    if detail:
        d["detail"] = detail.strip()
    return d


def phase_of(s, plan, waiting=False):
    if s is None:
        return "idle"
    if s.result:
        return "result"
    if s.mulligan:
        return "mulligan"
    if getattr(s, "choice", None):
        return "choice"
    if not s.my_active:
        return "opponent"
    if waiting:
        return "waiting"
    if plan is None:
        return "thinking"
    return "plan"


def build_snapshot(s, plan=None, boss=None, text="", waiting=False, db=None):
    """Baut die Momentaufnahme (reine Funktion, ohne Netzwerk). `text` ist der fertige Anzeigetext der Oberflaeche."""
    snap = {"app": "HS Coach", "version": __version__, "phase": phase_of(s, plan, waiting), "updated": time.time(),
            "text": text or ""}
    if s is None:
        return snap
    hero = ""
    try:
        hero = (db.info(s.opp_hero_cid).get("name") or "") if (db and s.opp_hero_cid) else ""
    except Exception:
        hero = ""
    snap["game"] = {"turn": s.turn, "my_active": bool(s.my_active), "step": s.step, "result": s.result or "",
                    "mulligan": bool(s.mulligan)}
    snap["me"] = {"hp": s.my_hp, "armor": s.my_armor, "mana": s.my_mana, "max_mana": s.max_mana,
                  "hand": len(s.my_hand), "deck": s.my_deck_count, "secrets": list(s.my_secrets),
                  "weapon": ({"name": s.my_weapon.name, "atk": s.my_weapon.atk, "durability": s.my_weapon.durability}
                             if s.my_weapon else None),
                  "hero_power": ({"name": s.my_hero_power.name, "cost": s.my_hero_power.cost, "used": bool(s.my_hero_power.used)}
                                 if s.my_hero_power else None)}
    snap["opp"] = {"hero": boss.name if boss else hero, "hp": s.opp_hp, "armor": s.opp_armor, "hand": s.opp_hand_count,
                   "deck": s.opp_deck_count, "secrets": s.opp_secret_count}
    snap["board"] = {"mine": [_mini(m) for m in s.my_minions], "opp": [_mini(m) for m in s.opp_minions]}
    snap["hand"] = [{"name": c.name, "cost": c.cost, "type": c.cardtype} for c in sorted(s.my_hand, key=lambda c: c.zpos)]
    if boss:
        snap["boss"] = {"name": boss.name, "goal": boss.goal, "power": boss.boss_power, "tips": list(boss.tips),
                        "dangers": list(boss.dangers), "win_hp": boss.win_hp or None}
    if getattr(s, "choice", None):
        snap["choice"] = {"source": s.choice.source, "options": [o.name for o in s.choice.options]}
    if plan is not None and snap["phase"] in ("plan", "waiting"):
        snap["plan"] = {"steps": [_step(i, st) for i, st in enumerate(plan.steps, 1)], "warnings": list(plan.warnings),
                        "summary": plan.summary, "lethal": bool(plan.lethal), "mana_used": plan.mana_used,
                        "unknown_cards": sorted(set(plan.unknown_cards)),
                        "alternatives": [" → ".join(x.text.split("  →")[0] for x in a.steps[:4]) for a in plan.alternatives if a.steps]}
    return snap


def plan_view(snap):
    """Kleine Sicht fuer Mini-Displays: Phase, Text, Plan-Schritte."""
    out = {"version": snap.get("version"), "rev": snap.get("rev", 0), "phase": snap.get("phase"), "text": snap.get("text", "")}
    for k in ("game", "me", "opp", "plan", "choice", "boss"):
        if k in snap:
            out[k] = snap[k]
    return out


class Hub:
    """Haelt die neueste Momentaufnahme; Leser koennen auf Aenderungen warten."""

    def __init__(self):
        self._cond = threading.Condition()
        self._snap = {"app": "HS Coach", "version": __version__, "phase": "idle", "text": "", "rev": 0, "updated": time.time()}

    def publish(self, snap):
        with self._cond:
            body = {k: v for k, v in snap.items() if k not in ("updated", "rev")}
            old = {k: v for k, v in self._snap.items() if k not in ("updated", "rev")}
            if body == old:
                return False
            snap = dict(snap)
            snap["rev"] = self._snap.get("rev", 0) + 1
            self._snap = snap
            self._cond.notify_all()
            return True

    def get(self):
        with self._cond:
            return dict(self._snap)

    def wait(self, since, timeout=LONG_POLL_S):
        end = time.time() + timeout
        with self._cond:
            while self._snap.get("rev", 0) <= since:
                left = end - time.time()
                if left <= 0:
                    break
                self._cond.wait(left)
            return dict(self._snap)


# -- Zugangsregeln ---------------------------------------------------------------------------------------------------
def new_token():
    return secrets.token_urlsafe(9)


def client_allowed(ip, lan):
    """Ohne LAN-Freigabe nur dieser PC; mit LAN nur private/lokale Adressen (nie Adressen aus dem Internet)."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.is_loopback:
        return True
    return bool(lan and (a.is_private or a.is_link_local))


def lan_ip():
    """Aktuelle private IPv4-Adresse dieses Rechners im Heimnetz (z. B. 192.168.1.127), sonst "".
    Der UDP-"connect" schickt nichts ab, er fragt nur das Betriebssystem, ueber welche Adresse es raus ginge."""
    candidates = []
    for probe in ("192.168.0.1", "10.0.0.1", "172.16.0.1", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 9))
                candidates.append(s.getsockname()[0])
        except OSError:
            continue
    try:
        candidates += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    for ip in candidates:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.version == 4 and a.is_private and not a.is_loopback and not a.is_link_local:
            return ip
    return ""


def phone_url(ip, port, token=""):
    """Adresse der Plan-Webseite fuer andere Geraete im Heimnetz."""
    url = f"http://{ip}:{int(port)}/"
    return url + (f"?token={token}" if token else "")


def token_ok(expected, given):
    return (not expected) or (bool(given) and secrets.compare_digest(str(expected), str(given)))


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HS Coach</title><style>
:root{--bg:#14110d;--fg:#f3e9d2;--dim:#a99c80;--gold:#ffd24d;--ok:#7be07b;--bad:#ff7a6b;--card:#241d14}
@media (prefers-color-scheme: light){:root{--bg:#f5efe0;--fg:#2a2218;--dim:#7a6c52;--gold:#8a5a00;--ok:#1d7a1d;--bad:#b3261e;--card:#fffaf0}}
html,body{margin:0;background:var(--bg);color:var(--fg);font-family:Segoe UI,system-ui,sans-serif}
main{max-width:900px;margin:0 auto;padding:12px 16px}
h1{font-size:15px;margin:0 0 8px;color:var(--dim);font-weight:600;letter-spacing:.04em}
.bar{display:flex;gap:14px;flex-wrap:wrap;font-size:18px;margin-bottom:10px}.bar b{color:var(--gold)}
.phase{font-size:22px;font-weight:700;margin:4px 0 10px}
ol{list-style:none;padding:0;margin:0;counter-reset:s}
li{counter-increment:s;background:var(--card);border-radius:10px;padding:10px 12px;margin:8px 0;font-size:20px;line-height:1.3}
li::before{content:counter(s);display:inline-block;min-width:1.6em;color:var(--gold);font-weight:700}
.detail{display:block;color:var(--dim);font-size:15px;margin-left:1.6em;margin-top:2px}
.warn{color:var(--bad);font-size:17px;margin:6px 0}.lethal{color:var(--ok);font-weight:700;font-size:20px}
pre{white-space:pre-wrap;font:inherit;font-size:18px;line-height:1.35}
.sum{color:var(--dim);margin-top:8px}
</style></head><body><main>
<h1>HS COACH</h1>
<div id="bar" class="bar"></div><div id="phase" class="phase">verbinde ...</div><div id="body"></div>
</main><script>
const q=new URLSearchParams(location.search);const tok=q.get('token')||'';let rev=0;
const $=id=>document.getElementById(id);
function esc(t){return String(t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
const PH={idle:'Warte auf ein Spiel ...',mulligan:'Mulligan',opponent:'Gegner ist am Zug',thinking:'Berechne Plan ...',
waiting:'Gleich bist du dran ...',plan:'Dein Zug',choice:'Auswahl',result:'Spiel vorbei'};
function draw(s){
  $('phase').textContent=(s.game&&s.game.turn?('Runde '+s.game.turn+' · '):'')+(PH[s.phase]||s.phase);
  let bar='';
  if(s.me)bar+='<span>❤ <b>'+s.me.hp+(s.me.armor?'+'+s.me.armor:'')+'</b></span><span>💎 <b>'+s.me.mana+'/'+s.me.max_mana+'</b></span>';
  if(s.opp)bar+='<span>Gegner ❤ <b>'+s.opp.hp+(s.opp.armor?'+'+s.opp.armor:'')+'</b></span>';
  $('bar').innerHTML=bar;
  let h='';
  if(s.plan){
    if(s.plan.lethal)h+='<div class="lethal">★ LETHAL</div>';
    h+='<ol>'+s.plan.steps.map(x=>'<li>'+esc(x.title)+(x.detail?'<span class="detail">'+esc(x.detail)+'</span>':'')+'</li>').join('')+'</ol>';
    if(!s.plan.steps.length)h+='<div class="sum">Keine sinnvolle Aktion – Zug beenden.</div>';
    h+=s.plan.warnings.map(w=>'<div class="warn">⚠ '+esc(w)+'</div>').join('');
    if(s.plan.summary)h+='<div class="sum">→ '+esc(s.plan.summary)+'</div>';
  } else if(s.text){h+='<pre>'+esc(s.text)+'</pre>';}
  if(s.boss)h+='<div class="sum">Boss: '+esc(s.boss.name)+(s.boss.goal?' – '+esc(s.boss.goal):'')+'</div>';
  $('body').innerHTML=h;
}
async function loop(){
  for(;;){
    try{
      const r=await fetch('api/state?since='+rev+(tok?'&token='+encodeURIComponent(tok):''),{cache:'no-store'});
      if(r.status===401){$('phase').textContent='Zugangscode fehlt oder falsch (?token=...)';await new Promise(t=>setTimeout(t,5000));continue}
      const s=await r.json();rev=s.rev||0;draw(s);
    }catch(e){$('phase').textContent='keine Verbindung ...';await new Promise(t=>setTimeout(t,2000))}
  }
}
loop();
</script></body></html>
"""


def _make_handler(hub, token, lan):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HSCoach"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):                 # kein Konsolen-/Dateirauschen pro Anfrage
            pass

        def _send(self, code, body, ctype):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

        def do_GET(self):
            try:
                if not client_allowed(self.client_address[0], lan):
                    return self._json(403, {"error": "nur lokal bzw. aus dem Heimnetz"})
                u = urlparse(self.path)
                qs = parse_qs(u.query)
                given = (qs.get("token") or [""])[0] or self.headers.get("X-Token", "")
                auth = self.headers.get("Authorization", "")
                if not given and auth.lower().startswith("bearer "):
                    given = auth[7:].strip()
                if not token_ok(token, given):
                    return self._json(401, {"error": "Zugangscode fehlt oder falsch"})
                path = u.path.rstrip("/") or "/"
                if path == "/":
                    return self._send(200, PAGE, "text/html; charset=utf-8")
                if path == "/api/health":
                    return self._json(200, {"ok": True, "version": __version__})
                if path in ("/api/state", "/api/plan", "/api/plan.txt"):
                    since = qs.get("since")
                    snap = hub.wait(int(since[0]), LONG_POLL_S) if since and since[0].lstrip("-").isdigit() else hub.get()
                    if path == "/api/state":
                        return self._json(200, snap)
                    if path == "/api/plan":
                        return self._json(200, plan_view(snap))
                    return self._send(200, snap.get("text", ""), "text/plain; charset=utf-8")
                return self._json(404, {"error": "unbekannter Pfad"})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                log.exception("API-Fehler")
                try:
                    self._json(500, {"error": "Fehler"})
                except Exception:
                    pass

    return Handler


class _Server(ThreadingHTTPServer):
    # Windows: SO_REUSEADDR erlaubt dort ein doppeltes Binden desselben Ports (auch durch fremde Programme) - ausschalten
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


class ApiServer:
    def __init__(self, hub, port=8765, lan=False, token=""):
        self.hub, self.port, self.lan, self.token = hub, int(port), bool(lan), token or ""
        self._srv = None
        self._thread = None
        self.error = ""

    @property
    def running(self):
        return self._srv is not None

    def start(self):
        if self._srv is not None:
            return True
        host = "0.0.0.0" if self.lan else "127.0.0.1"
        try:
            srv = _Server((host, self.port), _make_handler(self.hub, self.token, self.lan))
        except OSError as ex:
            self.error = f"Port {self.port} ist nicht verfügbar ({ex.strerror or ex})"
            log.warning("API nicht gestartet: %s", self.error)
            return False
        srv.daemon_threads = True
        self._srv = srv
        self._thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.3}, daemon=True, name="hs-api")
        self._thread.start()
        self.error = ""
        log.info("API laeuft auf %s:%s (LAN=%s)", host, self.port, self.lan)
        return True

    def stop(self):
        srv, self._srv = self._srv, None
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
