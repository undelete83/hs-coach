"""Sammlung: liest die auf HSReplay hinterlegte Kartensammlung (der Hearthstone Deck Tracker laedt sie dorthin hoch) und
beantwortet damit Fragen wie "Was besitze ich?" und "Was fehlt mir fuer dieses Deck?".

Abgerufen wird nur der oeffentliche Teil der Sammlung (derselbe wie auf der Seite hsreplay.net/collection/<Region>/<Konto>/);
dafuer ist kein Login und kein Schluessel noetig, der Konto-Link steht nur in der lokalen Config des Benutzers."""
import base64
import json
import logging
import os
import re
import time
import urllib.request

from . import carddb, config

log = logging.getLogger("hscoach.collection")

API = "https://hsreplay.net/api/v1/collection/?region={region}&account_lo={lo}&type=CONSTRUCTED"
CACHE_TTL_S = 6 * 3600
DUST_CRAFT = {"COMMON": 40, "RARE": 100, "EPIC": 400, "LEGENDARY": 1600}
FORMAT_NAMES = {1: "Wild", 2: "Standard", 3: "Klassisch", 4: "Zwielicht"}

CLASS_DE = {"DRUID": "Druide", "HUNTER": "Jäger", "MAGE": "Magier", "PALADIN": "Paladin", "PRIEST": "Priester", "ROGUE": "Schurke",
            "SHAMAN": "Schamane", "WARLOCK": "Hexenmeister", "WARRIOR": "Krieger", "DEMONHUNTER": "Dämonenjäger",
            "DEATHKNIGHT": "Todesritter", "NEUTRAL": "Neutral"}
RARITY_DE = {"COMMON": "Gewöhnlich", "RARE": "Selten", "EPIC": "Episch", "LEGENDARY": "Legendär", "FREE": "Basis"}
TYPE_DE = {"MINION": "Diener", "SPELL": "Zauber", "WEAPON": "Waffe", "LOCATION": "Ort", "HERO": "Held"}

_ACCOUNT_RX = re.compile(r"(?:collection/)?(\d+)\s*/\s*(\d+)")


class CollectionError(Exception):
    pass


def parse_account(text):
    """'https://hsreplay.net/collection/2/123/' oder '2/123' -> (region, konto) oder None."""
    m = _ACCOUNT_RX.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def cache_path():
    return os.path.join(config.APP_DIR, "collection.json")


def fetch(cfg, urlopen=urllib.request.urlopen):
    """Holt die Sammlung von HSReplay, legt sie im Cache ab und gibt das rohe JSON (dict) zurueck."""
    acc = parse_account(cfg.get("hsreplay_collection", ""))
    if not acc:
        raise CollectionError("Kein HSReplay-Sammlungslink eingetragen (Einstellungen > Sammlung).")
    url = API.format(region=acc[0], lo=acc[1])
    req = urllib.request.Request(url, headers={"User-Agent": carddb.USER_AGENT, "Accept": "application/json"})
    try:
        data = urlopen(req, timeout=30).read()
        raw = json.loads(data)
    except Exception as ex:
        raise CollectionError(f"Abruf bei HSReplay fehlgeschlagen: {ex}") from ex
    if not isinstance(raw, dict) or not isinstance(raw.get("collection"), dict):
        raise CollectionError("HSReplay hat keine Sammlung geliefert (Link falsch oder Sammlung nicht öffentlich?).")
    raw["_fetched_at"] = int(time.time())
    os.makedirs(config.APP_DIR, exist_ok=True)
    tmp = cache_path() + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raw, f)
    os.replace(tmp, cache_path())
    return raw


def load_cached():
    try:
        with open(cache_path(), encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) and isinstance(raw.get("collection"), dict) else None
    except (OSError, ValueError):
        return None


class Collection:
    """Besitz pro Karte (dbfId). Ein Eintrag ist [normal, golden, ...]; fuer den Deckbau zaehlen beide Varianten."""

    def __init__(self, raw):
        self.raw = raw
        self.counts = {}
        for k, v in (raw.get("collection") or {}).items():
            try:
                n = int(v[0]) + int(v[1]) if isinstance(v, (list, tuple)) and len(v) > 1 else int(v[0])
                self.counts[int(k)] = n
            except (ValueError, TypeError, IndexError):
                continue
        self.dust = raw.get("dust")
        self.fetched_at = raw.get("_fetched_at", 0)

    def owned(self, dbf, rarity="COMMON"):
        """Besessene Exemplare, begrenzt auf die Deckgrenze (2, Legendaere 1)."""
        return min(self.counts.get(dbf, 0), 1 if rarity == "LEGENDARY" else 2)


def card_rows(cfg, cards=None):
    """Alle sammelbaren Karten aus den HearthstoneJSON-Daten (Cache der Kartendatenbank) als schlanke Dicts."""
    if cards is None:
        try:
            path = carddb.download_hsjson(cfg)
            with open(path, encoding="utf-8") as f:
                cards = json.load(f)
        except Exception as ex:
            raise CollectionError(f"Kartendaten nicht verfügbar: {ex}") from ex
    std = set(cfg.get("standard_sets") or ())
    rows = []
    for c in cards:
        if not c.get("collectible") or not c.get("dbfId") or c.get("type") == "HERO":
            continue
        rows.append({
            "dbf": c["dbfId"], "id": c.get("id", ""), "name": c.get("name", "?"), "cost": c.get("cost", 0) or 0,
            "type": c.get("type", ""), "cls": c.get("cardClass", "NEUTRAL"), "rarity": c.get("rarity", "COMMON"),
            "set": c.get("set", ""), "text": re.sub(r"<[^>]+>", "", (c.get("text") or "")).replace("\n", " ").replace("[x]", "").strip(),
            "atk": c.get("attack"), "hp": c.get("health", c.get("durability")), "standard": c.get("set") in std,
        })
    return rows


def filter_rows(rows, coll, text="", cls="", fmt="", rarity="", cost="", own="", ctype=""):
    """Filter fuer die Anzeige. own: '' | 'have' (mind. 1) | 'full' (vollstaendig) | 'missing' (fehlt etwas)."""
    t = text.strip().lower()
    out = []
    for r in rows:
        if t and t not in r["name"].lower() and t not in r["text"].lower():
            continue
        if cls and r["cls"] != cls:
            continue
        if fmt == "standard" and not r["standard"]:
            continue
        if rarity and r["rarity"] != rarity:
            continue
        if ctype and r["type"] != ctype:
            continue
        if cost != "":
            c = int(cost)
            if (c >= 7 and r["cost"] < 7) or (c < 7 and r["cost"] != c):
                continue
        have = coll.owned(r["dbf"], r["rarity"])
        cap = 1 if r["rarity"] == "LEGENDARY" else 2
        if own == "have" and have == 0:
            continue
        if own == "full" and have < cap:
            continue
        if own == "missing" and have >= cap:
            continue
        out.append(r)
    out.sort(key=lambda r: (r["cost"], r["name"]))
    return out


# -- Deckcodes ---------------------------------------------------------------------------------------

def _varint(data, i):
    r = sh = 0
    while True:
        b = data[i]
        i += 1
        r |= (b & 0x7F) << sh
        sh += 7
        if b < 0x80:
            return r, i


def _enc_varint(n):
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def decode_deck(code):
    """Deckcode -> (format, [Helden-dbfId], [(dbfId, Anzahl)]). Ausnahme CollectionError bei ungueltigem Code."""
    code = "".join((code or "").split())
    m = re.search(r"[A-Za-z0-9+/=]{8,}", code)
    if not m:
        raise CollectionError("Das sieht nicht wie ein Deckcode aus.")
    code = m.group(0)
    try:
        data = base64.b64decode(code + "=" * (-len(code) % 4))
        if not data or data[0] != 0:
            raise ValueError("Kopfbyte")
        i = 1
        _version, i = _varint(data, i)
        fmt, i = _varint(data, i)
        n, i = _varint(data, i)
        heroes = []
        for _ in range(n):
            h, i = _varint(data, i)
            heroes.append(h)
        cards = []
        for count in (1, 2):
            n, i = _varint(data, i)
            for _ in range(n):
                d, i = _varint(data, i)
                cards.append((d, count))
        n, i = _varint(data, i)
        for _ in range(n):
            d, i = _varint(data, i)
            c, i = _varint(data, i)
            cards.append((d, c))
    except (ValueError, IndexError) as ex:
        raise CollectionError("Der Deckcode ist ungültig oder abgeschnitten.") from ex
    return fmt, heroes, cards


def encode_deck(fmt, hero, cards):
    """(Format, Helden-dbfId, [(dbfId, Anzahl)]) -> Deckcode."""
    ones = sorted(d for d, c in cards if c == 1)
    twos = sorted(d for d, c in cards if c == 2)
    more = sorted((d, c) for d, c in cards if c > 2)
    b = bytearray([0, 1]) + _enc_varint(fmt) + _enc_varint(1) + _enc_varint(hero)
    b += _enc_varint(len(ones)) + b"".join(_enc_varint(d) for d in ones)
    b += _enc_varint(len(twos)) + b"".join(_enc_varint(d) for d in twos)
    b += _enc_varint(len(more)) + b"".join(_enc_varint(d) + _enc_varint(c) for d, c in more)
    return base64.b64encode(bytes(b)).decode("ascii")


def check_deck(code, rows, coll):
    """Prueft ein Deck gegen die Sammlung. Ergebnis: dict mit Karten, Fehlendem, Staub und Hinweisen."""
    fmt, heroes, cards = decode_deck(code)
    by_dbf = {r["dbf"]: r for r in rows}
    entries, missing, notes, dust, size = [], [], [], 0, 0
    for dbf, count in cards:
        r = by_dbf.get(dbf)
        size += count
        if r is None:
            entries.append({"row": None, "dbf": dbf, "need": count, "have": 0})
            notes.append(f"Unbekannte Karte (dbfId {dbf}) - Kartendaten evtl. veraltet.")
            continue
        have = coll.owned(dbf, r["rarity"])
        entries.append({"row": r, "dbf": dbf, "need": count, "have": have})
        if have < count:
            lack = count - have
            missing.append({"row": r, "lack": lack})
            dust += DUST_CRAFT.get(r["rarity"], 0) * lack
        if fmt == 2 and not r["standard"]:
            notes.append(f"{r['name']} ist nicht Standard-zugelassen.")
    entries.sort(key=lambda e: ((e["row"] or {}).get("cost", 99), (e["row"] or {}).get("name", "")))
    hero = by_dbf.get(heroes[0]) if heroes else None
    if size != 30:
        notes.append(f"Das Deck hat {size} statt 30 Karten.")
    return {"format": fmt, "format_name": FORMAT_NAMES.get(fmt, f"Format {fmt}"), "hero": hero, "size": size, "entries": entries,
            "missing": missing, "dust": dust, "notes": notes}


def render_check(res):
    lines = [f"Deck: {res['size']} Karten, Format {res['format_name']}"]
    if res["missing"]:
        lines.append(f"Es fehlen {sum(m['lack'] for m in res['missing'])} Karte(n), Herstellung ca. {res['dust']} Staub:")
        for m in sorted(res["missing"], key=lambda m: m["row"]["cost"]):
            r = m["row"]
            lines.append(f"  {m['lack']}x [{r['cost']}] {r['name']}  ({RARITY_DE.get(r['rarity'], r['rarity'])})")
    else:
        lines.append("✓ Du besitzt alle Karten dieses Decks.")
    for n in res["notes"]:
        lines.append("⚠ " + n)
    return "\n".join(lines)


def age_text(coll):
    if not coll or not coll.fetched_at:
        return "unbekannt"
    d = int(time.time()) - coll.fetched_at
    if d < 90:
        return "gerade eben"
    if d < 5400:
        return f"vor {d // 60} Min."
    if d < 2 * 86400:
        return f"vor {d // 3600} Std."
    return f"vor {d // 86400} Tagen"
