"""Paket 10: Karten/Kopien auf die Hand."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "APFEL": dict(name="Hexenwaldapfel", cardtype="SPELL", cost=1, text="Erhaltet 2 Treants (2/2) auf die Hand."),
    "GEIST": dict(name="Geisterbeschwörung", cardtype="SPELL", cost=2, text="Wählt einen Diener. Erhaltet eine Kopie davon auf die Hand."),
    "ECHO": dict(name="Echo von Medivh", cardtype="SPELL", cost=4, text="Erhaltet eine Kopie jedes befreundeten Dieners auf die Hand."),
})


def texts(s):
    return [x.text for x in Planner(fake_db(), 1.0).plan(s).steps]


class T(unittest.TestCase):
    def test_parse(self):
        e = parse_effect("Erhaltet 2 Treants (2/2) auf die Hand.", "SPELL")
        self.assertEqual((e.hand_gain, e.unknown), (2, False))
        e = parse_effect("Wählt einen Diener. Erhaltet eine Kopie davon auf die Hand.", "SPELL")
        self.assertEqual((e.hand_copy, e.target_kind, e.unknown), ("any", "any_minion", False))
        e = parse_effect("Erhaltet eine Kopie jedes befreundeten Dieners auf die Hand.", "SPELL")
        self.assertEqual((e.hand_copy, e.unknown), ("friendly_all", False))

    def test_extras_stay_unknown(self):
        self.assertTrue(parse_effect("Wählt einen Diener. Erhaltet eine Kopie davon auf die Hand. Finale: Verleiht beiden +1/+2.", "SPELL").unknown)
        self.assertTrue(parse_effect("Wählt einen feindlichen Diener aus und erhaltet eine Kopie davon auf die Hand. Sie kostet (1).", "SPELL").unknown)

    def test_plan(self):
        self.assertTrue(any("Hexenwaldapfel" in x for x in texts(gs(mana=1, hand=[card(1, "APFEL")]))))
        s = gs(mana=2, mine=[mm(1, "A", 2, 2)], opp=[mm(10, "Brocken", 6, 6)], hand=[card(1, "GEIST")])
        self.assertTrue(any("Geisterbeschwörung" in x for x in texts(s)), texts(s))
        self.assertFalse(any("Echo" in x for x in texts(gs(mana=4, mine=[], hand=[card(1, "ECHO")]))))


if __name__ == "__main__":
    unittest.main()
