"""Paket 9: 'Zieht N Diener. Verleiht ihnen +X/+X.'"""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({"LUEFTE": dict(name="Auf in die Lüfte", cardtype="SPELL", cost=3, text="Zieht 2 Drachen. Verleiht ihnen +1/+1.")})


class T(unittest.TestCase):
    def test_parse(self):
        e = parse_effect("Zieht 2 Drachen. Verleiht ihnen +1/+1.", "SPELL")
        self.assertEqual((e.draw, e.draw_buff, e.unknown), (2, (1, 1, 2), False))
        e = parse_effect("Zieht einen Diener mit Spott. Verleiht ihm +2/+2.", "SPELL")
        self.assertEqual((e.draw, e.draw_buff, e.unknown), (1, (2, 2, 1), False))

    def test_conditions_stay_unknown(self):
        self.assertTrue(parse_effect("Zieht 2 Diener. Verleiht ihnen +3/+3, wenn Ihr mind. 10 Mana habt.", "SPELL").unknown)
        self.assertTrue(parse_effect("Zieht einen Diener. Verleiht ihm +3/+3. Finale: Spielt Euer letztes Riff.", "SPELL").unknown)

    def test_plan_plays_it(self):
        s = gs(mana=3, hand=[card(1, "LUEFTE")])
        t = [x.text for x in Planner(fake_db(), 1.0).plan(s).steps]
        self.assertTrue(any("Auf in die Lüfte" in x for x in t), t)


if __name__ == "__main__":
    unittest.main()
