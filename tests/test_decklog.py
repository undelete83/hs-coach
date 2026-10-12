"""Deckliste aus der Decks.log, Rest im Deck und Eichenranken-Bewertung mit dem echten Deckinhalt."""
import os
import tempfile
import unittest

from hscoach import collection, decklog, detect
from hscoach.planner import Planner

from tests.helpers import CARDS, FakeDB, card, gs, mm

CARDS.update({
    "EICHENRANKEN": dict(name="Eichenranken", cardtype="SPELL", cost=3, text="Ruft einen Diener aus Eurem Deck herbei."),
    "OGER": dict(name="Großer Oger", cardtype="MINION", cost=6, atk=6, health=7, text="", dbf=101),
    "RIESE": dict(name="Riese", cardtype="MINION", cost=8, atk=8, health=8, taunt=True, text="", dbf=102),
    "WELPE": dict(name="Welpe", cardtype="MINION", cost=1, atk=1, health=1, text="", dbf=103),
    "ZAUBER": dict(name="Arkane Geschosse", cardtype="SPELL", cost=1, text="Verursacht 3 Schaden.", dbf=104),
})
DECK_CARDS = CARDS


class DeckDB(FakeDB):
    def cid_by_dbf(self, dbf):
        return next((cid for cid, i in self.cards.items() if i.get("dbf") == dbf), "")


SAMPLE = """I 21:20:00.1000000 Deck Contents Received:
I 21:20:00.1000000 ### Altes Deck
I 21:20:00.1000000 # Deck ID: 1
I 21:20:00.1000000 AAECAQcAAAA=
I 21:31:02.1234567 Finding Game With Deck:
I 21:31:02.1234567 ### Erstes Deck
I 21:31:02.1234567 # Deck ID: 11
I 21:31:02.1234567 AAECAZICAAAAAA==
I 21:40:02.1234567 Finding Game With Deck:
I 21:40:02.1234567 ### Druide
I 21:40:02.1234567 # Deck ID: 12
I 21:40:02.1234567 AAECAZICAv/TBLifBw6m
"""


class FakeTracker:
    def __init__(self, entities):
        self.entities = entities


def ent(cid, zone, zone0="DECK", ctrl=1, creator=False):
    tags = {"CONTROLLER": ctrl, "ZONE": zone}
    if creator:
        tags["CREATOR"] = 99
    return {"cardId": cid, "tags": tags, "zone0": zone0}


class TestDecksLog(unittest.TestCase):
    def test_last_finding_game_block_wins(self):
        self.assertEqual(decklog.parse_decks_log(SAMPLE), ("Druide", "AAECAZICAv/TBLifBw6m"))

    def test_no_block(self):
        self.assertEqual(decklog.parse_decks_log("I 21:20:00.1 Deck Contents Received:\n"), ("", ""))

    def test_reads_file_next_to_power_log(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Decks.log"), "w", encoding="utf-8") as f:
                f.write(SAMPLE)
            self.assertEqual(decklog.deck_for_power_log(os.path.join(d, "Power.log"))[0], "Druide")
            self.assertEqual(decklog.deck_for_power_log(os.path.join(d, "fehlt", "Power.log")), ("", ""))

    def test_deck_code_to_card_ids(self):
        code = collection.encode_deck(2, 274, [(101, 2), (103, 1), (104, 2)])
        self.assertEqual(sorted(decklog.deck_cids(code, DeckDB(DECK_CARDS))),
                         ["OGER", "OGER", "WELPE", "ZAUBER", "ZAUBER"])
        self.assertEqual(decklog.deck_cids("kein code", DeckDB(DECK_CARDS)), [])

    def test_remaining_subtracts_cards_that_left_the_deck(self):
        deck = ["OGER", "OGER", "WELPE", "ZAUBER"]
        tr = FakeTracker({
            1: ent("OGER", "HAND"),                       # gezogen
            2: ent("WELPE", "GRAVEYARD"),                 # gespielt und gestorben
            3: ent("", "DECK"),                           # noch verdeckt im Deck
            4: ent("OGER", "DECK"),                       # nach dem Mulligan zurueck ins Deck: bleibt drin
            5: ent("OGER", "HAND", creator=True),         # erzeugte Kopie: zaehlt nicht
            6: ent("ZAUBER", "HAND", ctrl=2),             # Karte des Gegners
            7: ent("ZAUBER", "PLAY", zone0="HAND"),       # Muenze o. Ae.: lag nie im Deck
        })
        self.assertEqual(sorted(decklog.remaining(deck, tr, 1)), ["OGER", "ZAUBER"])


class TestOakenSummonsPlanning(unittest.TestCase):
    def plan(self, deck_left, **kw):
        s = gs(mana=3, hand=[card(1, "EICHENRANKEN")], **kw)
        s.my_deck_left = deck_left
        return Planner(DeckDB(DECK_CARDS), 1.0).plan(s)

    def test_value_from_real_deck(self):
        big = self.plan(["OGER", "RIESE", "ZAUBER"])
        small = self.plan(["WELPE", "ZAUBER"])
        self.assertTrue(big.steps and "Eichenranken" in big.steps[0].text)
        self.assertGreater(big.score, small.score)
        self.assertIn("2 Diener noch im Deck", " ".join(st.text for st in big.steps))

    def test_no_minions_left_is_not_played(self):
        p = self.plan(["ZAUBER", "ZAUBER"])
        self.assertFalse(any("Eichenranken" in st.text for st in p.steps), [st.text for st in p.steps])

    def test_unknown_deck_keeps_flat_estimate(self):
        p = self.plan(None)
        self.assertTrue(any("Eichenranken" in st.text for st in p.steps))
        self.assertEqual(p.unknown_cards, [])

    def test_full_board_gives_no_value(self):
        full = [mm(i, f"D{i}", 1, 1) for i in range(1, 8)]
        p = self.plan(["RIESE"], mine=full, opp_hp=30)
        self.assertFalse(any("Eichenranken" in st.text for st in p.steps), [st.text for st in p.steps])


class TestLethalWarning(unittest.TestCase):
    def test_no_unused_mana_warning_when_winning(self):
        s = gs(mana=9, opp_hp=4, mine=[mm(1, "Brocken", 5, 5)], hand=[card(1, "OGER", atk=6, hp=7), card(2, "WELPE", atk=1, hp=1)])
        p = Planner(DeckDB(DECK_CARDS), 1.0).plan(s)
        self.assertTrue(p.lethal)
        self.assertFalse([w for w in p.warnings if "Mana im Plan" in w], p.warnings)


class TestLogConfigDecks(unittest.TestCase):
    def test_write_adds_decks_and_keeps_other_sections(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.config")
            with open(p, "w", encoding="utf-8") as f:
                f.write("[Achievements]\nLogLevel=1\n\n[Power]\nFilePrinting=False\n")
            self.assertFalse(detect.decks_logged(p))
            detect.write_log_config(p)
            text = open(p, encoding="utf-8").read()
            self.assertEqual(detect.check_log_config(p), "ok")
            self.assertTrue(detect.decks_logged(p))
            self.assertIn("[Achievements]", text)
            self.assertEqual(text.count("[Power]"), 1)
            self.assertEqual(text.count("[Decks]"), 1)
            detect.write_log_config(p)                       # zweimal schreiben: keine doppelten Abschnitte
            self.assertEqual(open(p, encoding="utf-8").read().count("[Decks]"), 1)


if __name__ == "__main__":
    unittest.main()
