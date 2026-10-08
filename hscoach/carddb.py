"""Kartendatenbank. Quelle: HearthstoneJSON (Standard, ohne HDT) oder HDTs CardDefs (Fallback), mit Disk-Cache."""
import json
import logging
import os
import pickle
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

from . import config
from .effects import clean_text, parse_effect
from .extract import ensure_base_xml

log = logging.getLogger("hscoach.carddb")

SCHEMA = 4
HSJSON_URL = "https://api.hearthstonejson.com/v1/latest/{loc}/cards.json"
HSJSON_TTL_S = 3 * 24 * 3600          # Kartendaten hoechstens alle 3 Tage neu laden
USER_AGENT = "HSCoach/2 (+https://github.com/undelete83/hs-coach)"

CARDTYPE_NAMES = {3: "HERO", 4: "MINION", 5: "SPELL", 7: "WEAPON", 10: "HERO_POWER", 39: "LOCATION"}
RACE_NAMES = {
    11: "UNDEAD", 14: "MURLOC", 15: "DEMON", 17: "MECHANICAL", 18: "ELEMENTAL", 20: "BEAST",
    21: "TOTEM", 23: "PIRATE", 24: "DRAGON", 26: "ALL", 43: "QUILBOAR", 92: "NAGA",
}
_FLAG_TAGS = ("TAUNT", "FREEZE", "STEALTH", "WINDFURY", "POISONOUS", "LIFESTEAL", "REBORN",
              "DIVINE_SHIELD", "RUSH", "CHARGE", "IMMUNE", "ELUSIVE", "SECRET", "DEATHRATTLE",
              "BATTLECRY", "COMBO", "MEGA_WINDFURY")
_INT_TAGS = {"COST": "cost", "ATK": "atk", "HEALTH": "health", "SPELLPOWER": "spellpower", "OVERLOAD": "overload"}


def targeting_from_arrow_text(txt):
    if not txt:
        return None
    tl = txt.lower()
    if "befreundeten" in tl or "verbündeten" in tl:
        return "friendly"
    if "diener" in tl and "charakter" not in tl:
        return "minion"
    if "feind" in tl or "charakter" in tl:
        return "any"
    return None


# -- Quelle 1: HearthstoneJSON ---------------------------------------------------------------

def hsjson_cache_path(cfg):
    return os.path.join(config.APP_DIR, f"cards_{cfg.get('card_language', 'deDE')}.json")


def download_hsjson(cfg, force=False):
    """Laedt cards.json (oeffentlich, ohne Token). Gibt den Pfad zurueck; bei Fehler den alten Cache, sonst Ausnahme."""
    path = hsjson_cache_path(cfg)
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < HSJSON_TTL_S
    if fresh and not force:
        return path
    url = HSJSON_URL.format(loc=cfg.get("card_language", "deDE"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        data = urllib.request.urlopen(req, timeout=60).read()
        if not data.lstrip().startswith(b"["):
            raise ValueError("unerwartete Antwort der Kartendaten-Quelle")
        os.makedirs(config.APP_DIR, exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        log.info("Kartendaten geladen: %s (%d KB)", url, len(data) // 1024)
    except Exception as ex:
        if os.path.exists(path):
            log.warning("Kartendaten-Download fehlgeschlagen (%s) - nutze Cache", ex)
        else:
            raise
    return path


def parse_hsjson(cards):
    """HearthstoneJSON-Liste -> internes Format (identisch zur HDT-Quelle)."""
    db = {}
    for c in cards:
        cid = c.get("id")
        if not cid:
            continue
        info = {}
        if "name" in c:
            info["name"] = c["name"]
        if c.get("text"):
            info["text"] = clean_text(c["text"])
        if "cost" in c:
            info["cost"] = c["cost"]
        if "attack" in c:
            info["atk"] = c["attack"]
        if "health" in c:
            info["health"] = c["health"]
        elif "durability" in c:
            info["health"] = c["durability"]
        if c.get("type"):
            info["cardtype"] = c["type"]
        race = c.get("race") or (c.get("races") or [None])[0]
        if race:
            info["race"] = race
        for m in c.get("mechanics", ()):
            if m in _FLAG_TAGS:
                info[m.lower()] = True
        if c.get("spellDamage"):
            info["spellpower"] = c["spellDamage"]
        if c.get("overload"):
            info["overload"] = c["overload"]
        if c.get("elite") or c.get("rarity") == "LEGENDARY":
            info["elite"] = True
        if c.get("targetingArrowText"):
            t = targeting_from_arrow_text(re.sub(r"<[^>]+>", "", c["targetingArrowText"]).strip())
            if t:
                info["targeting"] = t
        db[cid] = info
    return db


# -- Quelle 2: HDT CardDefs (Fallback) ---------------------------------------------------------

def parse_hdt(cfg):
    ensure_base_xml(cfg)
    db = {}
    try:
        for entity in ET.parse(cfg["carddefs_base"]).getroot():
            cid = entity.get("CardID")
            if not cid:
                continue
            info = {}
            for tag in entity:
                n, v = tag.get("name", ""), tag.get("value", "")
                if not v:
                    continue
                if n in _INT_TAGS:
                    try:
                        info[_INT_TAGS[n]] = int(v)
                    except ValueError:
                        pass
                elif n == "CARDTYPE":
                    info["cardtype"] = CARDTYPE_NAMES.get(int(v), f"TYPE_{v}")
                elif n == "CARDRACE":
                    info["race"] = RACE_NAMES.get(int(v), f"RACE_{v}")
                elif n == "ELITE" and v == "1":
                    info["elite"] = True
                elif n in _FLAG_TAGS and v == "1":
                    info[n.lower()] = True
            if info:
                db[cid] = info
    except Exception:
        log.exception("base.xml Fehler")
    try:
        for entity in ET.parse(cfg["carddefs_de"]).getroot():
            cid = entity.get("CardID")
            if not cid:
                continue
            info = db.setdefault(cid, {})
            for tag in entity:
                name = tag.get("name", "")
                val = tag.get("value", "")
                de = tag.find("deDE")
                if name == "COST" and val and "cost" not in info:
                    try:
                        info["cost"] = int(val)
                    except ValueError:
                        pass
                if de is not None and de.text:
                    if name == "CARDNAME":
                        info["name"] = de.text.strip()
                    elif name == "CARDTEXT":
                        info["text"] = clean_text(de.text)
                    elif name == "TARGETING_ARROW_TEXT":
                        info["targeting"] = targeting_from_arrow_text(re.sub(r"<[^>]+>", "", de.text).strip())
    except Exception:
        log.exception("deDE.xml Fehler")
    return db


class CardDB:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cards = {}
        self.ready = threading.Event()
        self.source = ""
        self.error = ""
        self._fx = {}

    # -- Laden ---------------------------------------------------------------
    def _sources(self):
        s = self.cfg.get("card_source", "auto")
        return ["hearthstonejson", "hdt"] if s == "auto" else [s]

    @staticmethod
    def _stat(path):
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _load_source(self, name):
        """Gibt (karten, signatur, parse_funktion) zurueck; `karten` None -> Cache pruefen."""
        if name == "hearthstonejson":
            path = download_hsjson(self.cfg)
            sig = [SCHEMA, name, self._stat(path)]

            def parse():
                with open(path, encoding="utf-8") as f:
                    return parse_hsjson(json.load(f))
            return sig, parse
        if name == "hdt":
            sig = [SCHEMA, name, self._stat(self.cfg["carddefs_base"]), self._stat(self.cfg["carddefs_de"])]
            if sig[2] is None and sig[3] is None:
                raise FileNotFoundError("HDT-CardDefs nicht gefunden")
            return sig, lambda: parse_hdt(self.cfg)
        raise ValueError(f"Unbekannte Kartenquelle: {name}")

    def load(self):
        errors = []
        try:
            for name in self._sources():
                try:
                    sig, parse = self._load_source(name)
                    cp = os.path.join(config.APP_DIR, f"carddb_{name}.pkl")
                    cards = None
                    try:
                        with open(cp, "rb") as f:
                            data = pickle.load(f)
                        if data.get("sig") == sig:
                            cards = data["cards"]
                    except Exception:
                        pass
                    if cards is None:
                        cards = parse()
                        try:
                            os.makedirs(config.APP_DIR, exist_ok=True)
                            with open(cp, "wb") as f:
                                pickle.dump({"sig": sig, "cards": cards}, f, protocol=pickle.HIGHEST_PROTOCOL)
                        except Exception as ex:
                            log.warning("Card-DB Cache nicht schreibbar: %s", ex)
                    if cards:
                        self.cards, self.source = cards, name
                        log.info("Card-DB (%s): %d Karten", name, len(cards))
                        return
                    errors.append(f"{name}: keine Karten")
                except Exception as ex:
                    log.warning("Kartenquelle %s nicht nutzbar: %s", name, ex)
                    errors.append(f"{name}: {ex}")
            self.error = "; ".join(errors) or "keine Quelle"
            log.error("Card-DB konnte nicht geladen werden: %s", self.error)
        except Exception:
            log.exception("Card-DB konnte nicht geladen werden")
            self.error = "unerwarteter Fehler (siehe Log)"
        finally:
            self.ready.set()

    def load_async(self):
        threading.Thread(target=self.load, daemon=True, name="carddb").start()

    # -- Zugriff -------------------------------------------------------------
    def info(self, cid):
        return self.cards.get(cid) or {}

    def name(self, cid):
        return self.info(cid).get("name", "")

    def text(self, cid):
        return self.info(cid).get("text", "")

    def effect(self, cid):
        """Geparster Effekt (gecacht). Fuer unbekannte Karten: leerer unknown-Effekt."""
        fx = self._fx.get(cid)
        if fx is None:
            i = self.info(cid)
            fx = parse_effect(i.get("text", ""), i.get("cardtype", "SPELL"), secret=bool(i.get("secret")))
            self._fx[cid] = fx
        return fx
