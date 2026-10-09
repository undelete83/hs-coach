"""Paket 8: Kopie eines befreundeten Dieners (Verschmelzung)."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({"VERSCHM": dict(name="Verschmelzung", cardtype="SPELL", cost=4,
                              text="Ruft eine Kopie eines befreundeten Dieners herbei. Verleiht der Kopie Spott.")})


class T(unittest.TestCase):
    def test_parse(self):
        e = parse_effect("Ruft eine Kopie eines befreundeten Dieners herbei. Verleiht der Kopie Spott.", "SPELL")
        self.assertEqual((e.copy_friendly, e.copy_taunt, e.target_kind, e.unknown), (True, True, "friendly_minion", False))
        e = parse_effect("Ruft eine Kopie eines befreundeten Dieners herbei.", "SPELL")
        self.assertEqual((e.copy_friendly, e.copy_taunt, e.unknown), (True, False, False))

    def test_other_copies_stay_unknown(self):
        self.assertTrue(parse_effect("Ruft eine Kopie eines feindlichen Dieners herbei, die das Original angreift.", "SPELL").unknown)
        self.assertTrue(parse_effect("Ruft eine Kopie eines befreundeten Protoss-Dieners herbei. Er erleidet doppelten Schaden.", "SPELL").unknown)

    def test_plan_copies_best_minion(self):
        s = gs(mana=4, mine=[mm(1, "Klein", 1, 1), mm(2, "Gross", 6, 6)], hand=[card(1, "VERSCHM")])
        t = [x.text for x in Planner(fake_db(), 1.0).plan(s).steps]
        self.assertTrue(any("Verschmelzung auf Gross" in x for x in t), t)

    def test_not_played_without_minion_or_room(self):
        s = gs(mana=4, mine=[], hand=[card(1, "VERSCHM")])
        self.assertFalse(any("Verschmelzung" in x.text for x in Planner(fake_db(), 1.0).plan(s).steps))
        s = gs(mana=4, mine=[mm(i, f"M{i}", 2, 2) for i in range(1, 8)], hand=[card(1, "VERSCHM")])
        self.assertFalse(any("Verschmelzung" in x.text for x in Planner(fake_db(), 1.0).plan(s).steps))


if __name__ == "__main__":
    unittest.main()
