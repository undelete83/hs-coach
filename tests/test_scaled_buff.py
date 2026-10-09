"""Paket 7: Staerkung je eigenem Diener (Geschenk des Waldes)."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({"WALD": dict(name="Geschenk des Waldes", cardtype="SPELL", cost=3,
                           text="Verleiht einem befreundeten Diener +1/+1 für jeden Diener, den Ihr kontrolliert.")})


class T(unittest.TestCase):
    def test_parse(self):
        e = parse_effect("Verleiht einem befreundeten Diener +1/+1 für jeden Diener, den Ihr kontrolliert.", "SPELL")
        self.assertEqual((e.buff, e.buff_scale_minions, e.target_kind, e.unknown), ((1, 1, False), True, "friendly_minion", False))

    def test_extra_sentence_stays_unknown(self):
        self.assertTrue(parse_effect("Verleiht einem befreundeten Diener +1/+1 für jeden Diener, den Ihr kontrolliert. Mischt eine Kopie in Euer Deck.", "SPELL").unknown)

    def test_plan_uses_board_size(self):
        # 3 eigene Diener -> +3/+3: Der 2/2 kann den 5/3 des Gegners danach toeten und ueberleben
        s = gs(mana=3, mine=[mm(1, "A", 2, 2), mm(2, "B", 1, 1), mm(3, "C", 1, 1)], opp=[mm(10, "Brocken", 4, 5)], hand=[card(1, "WALD")])
        t = [x.text for x in Planner(fake_db(), 1.0).plan(s).steps]
        self.assertTrue(any("Geschenk des Waldes" in x for x in t), t)


if __name__ == "__main__":
    unittest.main()
