"""Inkrementeller Parser fuer Hearthstones Power.log.

Es werden ausschliesslich `GameState.*`-Zeilen ausgewertet: `PowerTaskList` ist dieselbe Information
nochmal (mit Animations-Verzoegerung) und wuerde Ereignisse doppeln. Namen werden nicht aus den
Klammern der Log-Zeilen uebernommen (dort steht oft UNKNOWN ENTITY), sondern spaeter ueber die
cardId aus der Card-DB aufgeloest.
"""
import glob
import logging
import os
import re

log = logging.getLogger("hscoach.parser")

_BRACKET = re.compile(r"\[entityName=(.*?) id=(\d+) zone=(\w+) zonePos=(\d+) cardId=(\S*) player=(\d+)\]")
_TAGLINE = re.compile(r"tag=(\w+) value=(\S*)")
_TAGCHANGE = re.compile(r"TAG_CHANGE Entity=(.+?) tag=(\w+) value=(\S*)")
_FULL_CREATE = re.compile(r"FULL_ENTITY - Creating ID=(\d+) CardID=(\S*)")
_ENTITY_UPD = re.compile(r"(SHOW_ENTITY|CHANGE_ENTITY|FULL_ENTITY) - Updating (?:Entity=)?(\[.*?\]|\d+) CardID=(\S*)")
_HIDE = re.compile(r"HIDE_ENTITY - Entity=(\[.*?\]|\d+) tag=(\w+) value=(\S*)")
_BLOCK = re.compile(r"BLOCK_START BlockType=(\w+) Entity=(\[.*?\]|\S+?) EffectCardId=.*? Target=(\[.*\]|\S+)")
_PLAYER = re.compile(r"Player EntityID=(\d+) PlayerID=(\d+) GameAccountId=\[hi=(\d+) lo=(\d+)\]")
_PLAYERNAME = re.compile(r"PlayerID=(\d+), PlayerName=(.*)")

_CHOICE = re.compile(r"id=(\d+) Player=(.*?) TaskList=(\d+) ChoiceType=(\w+) CountMin=(\d+) CountMax=(\d+)")
_CHOICE_SRC = re.compile(r"Source=\[entityName=(.*?) id=(\d+) .*?cardId=(\S*) player=(\d+)\]")
_CHOICE_ENT = re.compile(r"Entities\[(\d+)\]=\[entityName=(.*?) id=(\d+) zone=\w+ zonePos=\d+ cardId=(\S*) player=(\d+)\]")
_CHOSEN = re.compile(r"id=(\d+) Player=.*? EntitiesCount=")

CREATE_MARK = b"GameState.DebugPrintPower() - CREATE_GAME"
EVENT_CAP = 600


def latest_log(log_dir):
    dirs = sorted(glob.glob(os.path.join(log_dir, "Hearthstone_*")), reverse=True)
    for d in dirs:
        p = os.path.join(d, "Power.log")
        if os.path.exists(p):
            return p
    return None


def _val(v):
    if v.lstrip("-").isdigit():
        try:
            return int(v)
        except ValueError:
            return v
    return v


class Tracker:
    def __init__(self, log_dir, player_name):
        self.log_dir = log_dir
        self.player_name = player_name
        self.path = None
        self.offset = 0
        self._tail = b""
        self.game_no = 0
        self.version = 0          # zaehlt mit, sobald neue Daten verarbeitet wurden
        self._reset_game()

    # -- Zustand -----------------------------------------------------------
    def _reset_game(self):
        self.entities = {}
        self.events = []
        self.pid_eid = {}
        self.pid_name = {}
        self.pid_acct = {}
        self.name_eid = {}
        self._pending = {}
        self.my_pid = None
        self.me_fixed = False        # True, wenn der Spielername aus der Config im Log gefunden wurde
        self.game_type = ""
        self.cur = None
        self.choice = None           # offene Auswahl (Entdecken / "Waehlt aus"): dict oder None
        self.ui_step = ""            # Schritt laut PowerTaskList = was auf dem Bildschirm schon abgespielt wurde
        self.ui_current_pid = None

    def _ent(self, eid):
        e = self.entities.get(eid)
        if e is None:
            e = self.entities[eid] = {"name": "", "cardId": "", "tags": {}}
        return e

    # -- Datei lesen ---------------------------------------------------------
    def update(self):
        """Liest neue Bytes ein. Gibt True zurueck, wenn sich etwas geaendert hat."""
        path = latest_log(self.log_dir)
        if not path:
            return False
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        initial = path != self.path or size < self.offset
        if initial:
            self.path = path
            self.offset = 0
            self._tail = b""
            self._reset_game()
        if size == self.offset and not initial:
            return False
        try:
            with open(path, "rb") as f:
                if initial:
                    data = f.read()
                    i = data.rfind(CREATE_MARK)
                    if i >= 0:
                        data = data[data.rfind(b"\n", 0, i) + 1:]
                else:
                    f.seek(self.offset)
                    data = f.read(size - self.offset)
        except OSError:
            return False
        self.offset = size
        data = self._tail + data
        cut = data.rfind(b"\n")
        if cut < 0:
            self._tail = data
            return False
        self._tail = data[cut + 1:]
        text = data[:cut].decode("utf-8", errors="replace")
        for line in text.split("\n"):
            self._feed(line)
        self.version += 1
        return True

    def feed_lines(self, lines):
        """Fuer Tests/Replays: Zeilen direkt einspeisen."""
        for line in lines:
            self._feed(line.rstrip("\r\n"))
        self.version += 1

    # -- Zeilen ----------------------------------------------------------------
    def _feed(self, line):
        game_state = "GameState.Debug" in line
        if not game_state:
            # PowerTaskList hinkt der Spiellogik (GameState) hinterher: nur die Zugmarker daraus nutzen
            if "PowerTaskList.DebugPrintPower()" not in line or ("tag=STEP" not in line and "tag=CURRENT_PLAYER" not in line):
                return
        i = line.find(" - ")
        if i < 0:
            return
        src = line[:i].rsplit(" ", 1)[-1]
        rest = line[i + 3:].rstrip("\r")
        if src == "PowerTaskList.DebugPrintPower()":
            self._ui(rest)
        elif src == "GameState.DebugPrintPower()":
            self._power(rest)
        elif src == "GameState.DebugPrintGame()":
            self._game(rest)
        elif src == "GameState.DebugPrintEntityChoices()":
            self._choice(rest)
        elif src == "GameState.DebugPrintEntitiesChosen()":
            m = _CHOSEN.match(rest.strip())
            if m and self.choice and self.choice["id"] == int(m.group(1)):
                self.choice = None                     # die Auswahl wurde getroffen

    def _choice(self, rest):
        """Offene Kartenauswahl (Entdecken, 'Waehlt aus'): Quelle und angebotene Karten merken. Mulligan wird ignoriert."""
        s = rest.strip()
        m = _CHOICE.match(s)
        if m:
            cid_, player, _task, ctype, mn, mx = m.groups()
            self.choice = None if ctype == "MULLIGAN" else dict(
                id=int(cid_), player=player, type=ctype, count_min=int(mn), count_max=int(mx), source=None, options=[])
            return
        if not self.choice:
            return
        m = _CHOICE_SRC.match(s)
        if m:
            self.choice["source"] = dict(name=m.group(1), eid=int(m.group(2)), cid=m.group(3))
            return
        m = _CHOICE_ENT.match(s)
        if m:
            self.choice["options"].append(dict(name=m.group(2), eid=int(m.group(3)), cid=m.group(4)))

    def _ui(self, rest):
        m = _TAGCHANGE.match(rest.lstrip())
        if not m:
            return
        tok, k, v = m.groups()
        if k == "STEP" and tok == "GameEntity":
            self.ui_step = v
        elif k == "CURRENT_PLAYER" and v == "1":
            eid = self._resolve(tok)
            if eid is not None:
                self.ui_current_pid = self.entities.get(eid, {}).get("tags", {}).get("PLAYER_ID")

    def _resolve(self, tok):
        """Entity-Token (Klammer, Zahl, GameEntity oder Name) -> Entity-ID oder None."""
        tok = tok.strip()
        if tok.startswith("["):
            m = _BRACKET.match(tok)
            if m:
                name, eid, _z, _zp, cid, _pl = m.groups()
                eid = int(eid)
                e = self._ent(eid)
                if cid and not e["cardId"]:
                    e["cardId"] = cid
                if name and "UNKNOWN" not in name and not e["name"]:
                    e["name"] = name
                return eid
            m = re.search(r"\bid=(\d+)", tok)
            return int(m.group(1)) if m else None
        if tok.isdigit():
            return int(tok)
        if tok == "GameEntity":
            return 1
        eid = self.name_eid.get(tok)
        if eid is None and self.my_pid is not None and tok not in self.pid_name.values():
            # Der Gegner heisst in TAG_CHANGE-Zeilen oft wie sein Held ("Archimonde"), in DebugPrintGame aber "Gastwirt".
            eid = self.pid_eid.get(self.opp_pid)
            if eid is not None:
                self.name_eid[tok] = eid
        return eid

    def _set_tag(self, eid, k, v):
        self._ent(eid)["tags"][k] = _val(v)

    def _power(self, rest):
        s = rest.lstrip()
        if s.startswith("tag="):
            if self.cur is not None:
                m = _TAGLINE.match(s)
                if m:
                    self._set_tag(self.cur, m.group(1), m.group(2))
            return
        self.cur = None
        if s.startswith("TAG_CHANGE"):
            m = _TAGCHANGE.match(s)
            if not m:
                return
            tok, k, v = m.groups()
            eid = self._resolve(tok)
            if eid is None:
                self._pending.setdefault(tok.strip(), []).append((k, v))
                return
            self._set_tag(eid, k, v)
            return
        if s.startswith("BLOCK_START"):
            m = _BLOCK.match(s)
            if m and m.group(1) in ("ATTACK", "PLAY"):
                actor = self._resolve(m.group(2))
                tgt_tok = m.group(3)
                target = self._resolve(tgt_tok) if tgt_tok.startswith("[") else None
                if actor is not None:
                    ev = {"turn": self.entities.get(1, {}).get("tags", {}).get("TURN", 0),
                          "type": m.group(1), "actor": actor, "target": target,
                          "pid": self.entities[actor]["tags"].get("CONTROLLER")}
                    self.events.append(ev)
                    if len(self.events) > EVENT_CAP:
                        del self.events[:100]
            return
        if s.startswith("FULL_ENTITY - Creating"):
            m = _FULL_CREATE.match(s)
            if m:
                eid = int(m.group(1))
                e = self._ent(eid)
                if m.group(2):
                    e["cardId"] = m.group(2)
                self.cur = eid
            return
        if s.startswith(("SHOW_ENTITY", "CHANGE_ENTITY", "FULL_ENTITY")):
            m = _ENTITY_UPD.match(s)
            if m:
                eid = self._resolve(m.group(2))
                if eid is not None:
                    e = self._ent(eid)
                    if m.group(3):
                        e["cardId"] = m.group(3)
                    self.cur = eid
            return
        if s.startswith("HIDE_ENTITY"):
            m = _HIDE.match(s)
            if m:
                eid = self._resolve(m.group(1))
                if eid is not None:
                    self._set_tag(eid, m.group(2), m.group(3))
            return
        if s.startswith("Player EntityID="):
            m = _PLAYER.match(s)
            if m:
                eid, pid, hi, lo = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                self.pid_eid[pid] = eid
                self.pid_acct[pid] = (hi, lo)
                self._ent(eid)["tags"]["PLAYER_ID"] = pid
                self.cur = eid
            return
        if s.startswith("GameEntity EntityID="):
            self._ent(1)["name"] = "GameEntity"
            self.cur = 1
            return
        if s == "CREATE_GAME":
            self.game_no += 1
            self._reset_game()
            self.cur = None

    def _game(self, rest):
        if rest.startswith("GameType="):
            self.game_type = rest.split("=", 1)[1].strip()
            return
        m = _PLAYERNAME.match(rest)
        if not m:
            return
        pid, name = int(m.group(1)), m.group(2).strip()
        self.pid_name[pid] = name
        eid = self.pid_eid.get(pid)
        if eid is not None:
            self.name_eid[name] = eid
            self._ent(eid)["name"] = name
            for k, v in self._pending.pop(name, []):
                self._set_tag(eid, k, v)
        if self.player_name and name == self.player_name:
            self.my_pid = pid
            self.me_fixed = True
        self._guess_me()
        self._me_from_hidden_name()

    def _me_from_hidden_name(self):
        """Gegen echte Spieler zeigt das Log den Gegner als 'UNKNOWN HUMAN PLAYER', nur der eigene Name steht da: damit ist klar,
        wer man selbst ist (zuverlaessiger als die Zahl aufgedeckter Handkarten)."""
        if self.me_fixed or len(self.pid_name) < 2:
            return
        hidden = [p for p, n in self.pid_name.items() if "UNKNOWN" in (n or "").upper()]
        if len(hidden) == 1:
            others = [p for p in self.pid_name if p != hidden[0]]
            if len(others) == 1:
                self.my_pid = others[0]
                self.me_fixed = True

    def _guess_me(self):
        """Fallback, wenn der konfigurierte Spielername nicht vorkommt."""
        if self.my_pid is not None or len(self.pid_name) < 2:
            return
        humans = [p for p, (hi, lo) in self.pid_acct.items() if hi or lo]
        self.my_pid = humans[0] if len(humans) == 1 else 1

    def refresh_me(self):
        """Ohne passenden Spielernamen: der Spieler mit den (aufgedeckten) Handkarten ist man selbst."""
        if self.me_fixed or len(self.pid_eid) < 2:
            return
        counts = {}
        for e in self.entities.values():
            if isinstance(e, dict) and e.get("cardId"):
                t = e["tags"]
                pid = t.get("CONTROLLER")
                if t.get("ZONE") == "HAND" and pid in self.pid_eid:
                    counts[pid] = counts.get(pid, 0) + 1
        if counts:
            best = max(counts, key=counts.get)
            others = [v for k, v in counts.items() if k != best]
            if not others or counts[best] > max(others):
                self.my_pid = best

    # -- Hilfsfunktionen fuer den Snapshot ------------------------------------------
    @property
    def opp_pid(self):
        me = self.my_pid or 1
        return 2 if me == 1 else 1

    def player_tags(self, pid):
        eid = self.pid_eid.get(pid)
        return self.entities.get(eid, {}).get("tags", {}) if eid else {}
