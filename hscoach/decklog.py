"""Deckliste der laufenden Partie aus der Decks.log und daraus der Rest im Deck.

Die Power.log zeigt die eigenen Deckkarten verdeckt (CardID leer), bis sie gezogen werden. Hearthstone schreibt aber mit
einem [Decks]-Abschnitt in der log.config beim Spielstart den Deckcode in die Decks.log:

    I 21:31:02.1234567 Finding Game With Deck:
    I 21:31:02.1234567 ### Druide
    I 21:31:02.1234567 # Deck ID: 1234567
    I 21:31:02.1234567 AAECAZICAv/TBLifBw6m...

Rest im Deck = Deckliste minus alle Karten, die erkennbar aus dem Startdeck gekommen sind (gezogen, gespielt, abgelegt).
"""
import logging
import os
import re
from collections import Counter

from .collection import CollectionError, decode_deck

log = logging.getLogger("hscoach.decklog")

_LINE = re.compile(r"^[DIWE] \d\d:\d\d:\d\d(?:\.\d+)? (.*)$")
_CODE = re.compile(r"^[A-Za-z0-9+/]{12,}={0,2}$")
_cache = {}


def parse_decks_log(text):
    """Letzter Eintrag "Finding Game With Deck:" -> (Deckname, Deckcode) oder ("", "")."""
    found, cur = ("", ""), None
    for raw in text.splitlines():
        m = _LINE.match(raw.strip())
        body = (m.group(1) if m else raw).strip()
        if body.startswith("Finding Game With Deck"):
            cur = {"name": "", "code": ""}
            continue
        if cur is None:
            continue
        if body.startswith("### "):
            cur["name"] = body[4:].strip()
        elif body.startswith("#"):
            continue
        elif _CODE.match(body):
            cur["code"] = body
            found, cur = (cur["name"], body), None
        else:
            cur = None                     # Block ohne Deckcode zu Ende
    return found


def deck_for_power_log(power_path):
    """(Deckname, Deckcode) der aktuellen Sitzung (Decks.log neben der Power.log); gecacht nach Dateistand."""
    if not power_path:
        return "", ""
    path = os.path.join(os.path.dirname(power_path), "Decks.log")
    try:
        st = os.stat(path)
    except OSError:
        return "", ""
    key = (path, st.st_size, st.st_mtime)
    if key not in _cache:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                _cache.clear()
                _cache[key] = parse_decks_log(f.read())
        except OSError:
            return "", ""
    return _cache[key]


def deck_cids(code, db):
    """Deckcode -> Liste der Karten-IDs (mit Mehrfachen). Leer, wenn der Code nicht lesbar ist."""
    try:
        _fmt, _heroes, cards = decode_deck(code)
    except CollectionError:
        return []
    out = []
    for dbf, count in cards:
        cid = db.cid_by_dbf(dbf)
        if cid:
            out += [cid] * count
    return out


def remaining(deck, tr, my_pid):
    """Karten-IDs, die noch im Deck liegen: Deckliste minus erkennbar aus dem Startdeck gekommene Karten.
    Gezaehlt werden eigene Entitaeten, die zu Spielbeginn im Deck lagen (keine erzeugten Karten) und deren ID bekannt ist."""
    left = Counter(deck)
    for e in tr.entities.values():
        tags = e.get("tags", {})
        cid = e.get("cardId")
        if not cid or tags.get("CONTROLLER") != my_pid or e.get("zone0") != "DECK" or "CREATOR" in tags:
            continue
        if tags.get("ZONE") == "DECK":
            continue
        if left[cid] > 0:
            left[cid] -= 1
    return list(left.elements())
