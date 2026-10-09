"""Paket 5: Entdecken und Zufall werden nicht simuliert, aber pauschal bewertet (und als geschaetzt gekennzeichnet)."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "ENTDECKEN": dict(name="Magische Eingebung", cardtype="SPELL", cost=2, text="Entdeckt einen Zauber."),
    "ZUFALL": dict(name="Zufallsgabe", cardtype="SPELL", cost=2, text="Erhaltet 2 zufällige Zauber."),
    "SCHADEN": dict(name="Feuerschlag", cardtype="SPELL", cost=2, text="Fügt einem Diener 3 Schaden zu."),
    "RAETSEL": dict(name="Rätselhaft", cardtype="SPELL", cost=2, text="Tauscht die Plätze aller Diener."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_discover_is_estimated(self):
        e = parse_effect("Entdeckt einen Zauber.", "SPELL")
        self.assertEqual((e.unknown, e.est_label, e.est_value > 0), (False, "Entdecken", True))

    def test_random_is_estimated(self):
        e = parse_effect("Erhaltet 2 zufällige Zauber.", "SPELL")
        self.assertEqual((e.unknown, e.est_label), (False, "Zufall"))

    def test_recognized_effects_are_not_estimated(self):
        e = parse_effect("Fügt einem Diener 3 Schaden zu.", "SPELL")
        self.assertEqual((e.est_value, e.dmg), (0.0, 3))
        # teilweise erkannte Karte: der erkannte Teil zaehlt, nichts wird zusaetzlich geschaetzt
        e = parse_effect("Zieht eine Karte. Entdeckt einen Zauber.", "SPELL")
        self.assertEqual((e.draw, e.est_value), (1, 0.0))

    def test_unrelated_unknown_stays_unknown(self):
        e = parse_effect("Tauscht die Plätze aller Diener.", "SPELL")
        self.assertEqual((e.unknown, e.est_value), (True, 0.0))

    def test_minion_battlecry_unaffected(self):
        e = parse_effect("Kampfschrei: Entdeckt einen Zauber.", "MINION")
        self.assertEqual((e.unknown, e.est_value), (False, 0.0))


class TestPlanning(unittest.TestCase):
    def test_estimated_card_is_marked_in_plan(self):
        s = gs(mana=2, hand=[card(1, "ENTDECKEN")])
        p = plan_for(s)
        t = texts(p)
        self.assertTrue(any("Magische Eingebung" in x and "Entdecken: Wert pauschal geschätzt" in x and "Entdeckt einen Zauber" in x for x in t), t)
        self.assertEqual(p.unknown_cards, [])

    def test_real_effect_beats_estimate(self):
        # Mana nur fuer eine Karte: der echte Schaden an einer gefaehrlichen Bedrohung schlaegt die Pauschale
        s = gs(mana=2, opp=[mm(10, "Bedrohung", 6, 3)], hand=[card(1, "ENTDECKEN"), card(2, "SCHADEN")])
        t = texts(plan_for(s))
        self.assertTrue(any("Feuerschlag" in x for x in t), t)

    def test_truly_unknown_card_still_reported(self):
        s = gs(mana=2, hand=[card(1, "RAETSEL")])
        p = plan_for(s)
        self.assertEqual(p.unknown_cards, ["Rätselhaft"])


if __name__ == "__main__":
    unittest.main()
