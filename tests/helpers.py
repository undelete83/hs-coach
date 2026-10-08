"""Gemeinsame Test-Hilfen: Fixtures laden, Fake-DB, Zustands-Bausteine."""
import gzip
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from hscoach import config  # noqa: E402
from hscoach.carddb import CardDB  # noqa: E402
from hscoach.effects import parse_effect  # noqa: E402
from hscoach.logparser import Tracker  # noqa: E402
from hscoach.state import Card, GameState, HeroPower, Minion, Weapon, build_state  # noqa: E402


def fixture_lines(n):
    with gzip.open(os.path.join(HERE, "fixtures", f"game{n}.log.gz"), "rt", encoding="utf-8") as f:
        return f.read().split("\n")


def new_tracker():
    return Tracker(r"C:\nonexistent", "Spieler#1234")


def real_db():
    """Echte Card-DB, falls die HDT-Dateien vorhanden sind, sonst None."""
    cfg = config.load()
    if not (os.path.exists(cfg["carddefs_base"]) and os.path.exists(cfg["carddefs_de"])):
        return None
    db = CardDB(cfg)
    db.load()
    return db if db.cards else None


class FakeDB:
    """Minimale DB: cid -> {name, cardtype, text}. Effekte werden aus dem Text geparst."""

    def __init__(self, cards=None):
        self.cards = cards or {}
        self._fx = {}

    def info(self, cid):
        return self.cards.get(cid, {})

    def name(self, cid):
        return self.info(cid).get("name", "")

    def effect(self, cid):
        if cid not in self._fx:
            i = self.info(cid)
            self._fx[cid] = parse_effect(i.get("text", ""), i.get("cardtype", "SPELL"), secret=bool(i.get("secret")))
        return self._fx[cid]


# Echte Kartentexte (deDE), damit die Tests die Parser-Ergebnisse mitpruefen.
CARDS = {
    "FROSTBLITZ": dict(name="Frostblitz", cardtype="SPELL", cost=2, text="Fügt einem Charakter 3 Schaden zu und friert ihn ein."),
    "FROSTSTRAHL": dict(name="Froststrahl", cardtype="SPELL", cost=1,
                        text="Zwillingszauber. Friert einen Diener ein. Fügt ihm 2 Schaden zu, wenn er bereits eingefroren ist."),
    "ZERTRUEMMERN": dict(name="Zertrümmern", cardtype="SPELL", cost=2, text="Vernichtet einen eingefrorenen Diener."),
    "FEUERBALL": dict(name="Feuerball", cardtype="SPELL", cost=4, text="Verursacht 6 Schaden."),
    "BLIZZARD": dict(name="Blizzard", cardtype="SPELL", cost=6, text="Fügt allen feindlichen Dienern 2 Schaden zu und friert sie ein."),
    "FLAMMENSTOSS": dict(name="Flammenstoß", cardtype="SPELL", cost=7, text="Fügt allen feindlichen Dienern 5 Schaden zu."),
    "GLETSCHER": dict(name="Unaufhaltbarer Gletscher", cardtype="SPELL", cost=3,
                      text="Verursacht 4 Schaden. Euer nächster Zauber in diesem Zug kostet (2) weniger."),
    "ELEMBESCH": dict(name="Elementarbeschwörung", cardtype="SPELL", cost=0,
                      text="Der nächste Elementar, den Ihr in diesem Zug ausspielt, kostet (2) weniger."),
    "ARKANE": dict(name="Arkane Intelligenz", cardtype="SPELL", cost=3, text="Zieht 2 Karten."),
    "VERWANDLUNG": dict(name="Verwandlung", cardtype="SPELL", cost=4, text="Verwandelt einen Diener in ein Schaf (1/1)."),
    "EISBLOCK": dict(name="Eisblock", cardtype="SPELL", cost=3, secret=True,
                     text="Geheimnis: Wenn Euer Held tödlichen Schaden erleidet, wird dieser verhindert."),
    "MUENZE": dict(name="Die Münze", cardtype="SPELL", cost=0, text="Erhaltet 1 Manakristall nur für diesen Zug."),
    "HEROPOWER_SCHLAG": dict(name="Eisschlag", cardtype="HERO_POWER", cost=2, text="Verursacht 1 Schaden."),
    "ELEM": dict(name="Wasserelementar", cardtype="MINION", cost=4, text=""),
    "WEAPON": dict(name="Kriegsbeil", cardtype="WEAPON", cost=1, text=""),
    "SCHUPPENREITERIN": dict(name="Schuppenreiterin", cardtype="MINION", cost=3,
                             text="Kampfschrei: Verursacht 2 Schaden, wenn Ihr einen Drachen auf der Hand habt."),
    "BUECHERWYRM": dict(name="Bücherwyrm", cardtype="MINION", cost=6,
                        text="Kampfschrei: Vernichtet einen feindlichen Diener mit max. 3 Angriff, wenn Ihr einen Drachen auf der Hand habt."),
    "GESCHOSSE": dict(name="Arkane Geschosse", cardtype="SPELL", cost=1,
                      text="Verursacht $3 Schaden, der zufällig auf alle Feinde verteilt wird."),
    "SCHUPPENWURM": dict(name="Schuppenwurm", cardtype="MINION", cost=4,
                        text="Kampfschrei: Erhält +1 Angriff und Eifer, wenn Ihr einen Drachen auf der Hand habt."),
    "DRACHE": dict(name="Drachenjunges", cardtype="MINION", cost=5, text=""),
}


def fake_db():
    return FakeDB(CARDS)


def mm(eid, name, atk, hp, **kw):
    return Minion(eid=eid, name=name, cid=kw.pop("cid", ""), atk=atk, hp=hp, max_hp=kw.pop("max_hp", hp), **kw)


def card(eid, key, cost=None, **kw):
    c = CARDS[key]
    return Card(eid=eid, name=c["name"], cid=key, cost=c["cost"] if cost is None else cost, cardtype=c["cardtype"],
                text=c["text"], atk=kw.pop("atk", 0), hp=kw.pop("hp", 0), zpos=kw.pop("zpos", eid), **kw)


def gs(mana=5, my_hp=30, opp_hp=30, mine=(), opp=(), hand=(), **kw):
    s = GameState(turn=5, my_active=True, my_mana=mana, max_mana=mana, my_hp=my_hp, opp_hp=opp_hp,
                  my_minions=list(mine), opp_minions=list(opp), my_hand=list(hand), opp_name="Gegner")
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def replay(game_no, db, every=30):
    """Spielt eine Fixture-Partie ab und liefert (Zeilennummer, Tracker, State) alle `every` Zeilen."""
    lines = fixture_lines(game_no)
    tr = new_tracker()
    chunk = []
    for i, line in enumerate(lines):
        chunk.append(line)
        if i % every == 0 or i == len(lines) - 1:
            tr.feed_lines(chunk)
            chunk = []
            yield i, tr, build_state(tr, db)
