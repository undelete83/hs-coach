"""Paket 1 der unverstandenen Zauber: Schaden nach Wert (Angriff, Heldenangriff, Ruestung) und Strangulieren."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "LICHT": dict(name="Das Licht! Es brennt!", cardtype="SPELL", cost=1,
                  text="Fügt einem Diener Schaden zu, der seinem Angriff entspricht."),
    "BOMBE": dict(name="Lichtbombe", cardtype="SPELL", cost=6,
                  text="Fügt jedem Diener Schaden zu, der seinem Angriff entspricht."),
    "UNBAENDIG": dict(name="Unbändigkeit", cardtype="SPELL", cost=1,
                      text="Fügt einem Diener Schaden zu, der dem Angriff Eures Helden entspricht."),
    "RUNDUM": dict(name="Rundumschlag", cardtype="SPELL", cost=3,
                   text="Verbraucht Eure gesamte Rüstung. Fügt allen Dienern ebenso viel Schaden zu."),
    "STRANGULIEREN": dict(name="Strangulieren", cardtype="SPELL", cost=3,
                          text="Vernichtet den feindlichen Diener mit dem höchsten Angriff."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_target_attack_damage(self):
        e = parse_effect("Fügt einem Diener Schaden zu, der seinem Angriff entspricht.", "SPELL")
        self.assertEqual((e.dmg_scale, e.target_kind, e.unknown), ("target_atk", "minion", False))

    def test_hero_attack_damage(self):
        e = parse_effect("Fügt einem Diener Schaden zu, der dem Angriff Eures Helden entspricht.", "SPELL")
        self.assertEqual((e.dmg_scale, e.target_kind, e.unknown), ("hero_atk", "minion", False))

    def test_all_minions_own_attack(self):
        e = parse_effect("Fügt jedem Diener Schaden zu, der seinem Angriff entspricht.", "SPELL")
        self.assertEqual((e.dmg_scale, e.target_kind, e.unknown), ("own_atk", "", False))

    def test_armor_damage(self):
        e = parse_effect("Verbraucht Eure gesamte Rüstung. Fügt allen Dienern ebenso viel Schaden zu.", "SPELL")
        self.assertEqual((e.dmg_scale, e.unknown), ("armor", False))

    def test_destroy_highest_attack(self):
        e = parse_effect("Vernichtet den feindlichen Diener mit dem höchsten Angriff.", "SPELL")
        self.assertEqual((e.destroy_highest, e.unknown), (True, False))

    def test_similar_texts_stay_unknown(self):
        # abweichender Wortlaut (verletzter Diener, Handkarten ...) darf nicht faelschlich erkannt werden
        self.assertTrue(parse_effect("Fügt einem Diener Schaden zu, der der Anzahl Eurer Leichen entspricht.", "SPELL").unknown)
        self.assertTrue(parse_effect("Fügt allen Dienern ihren Schaden zu.", "SPELL").unknown)


class TestPlanning(unittest.TestCase):
    def test_target_attack_kills_big_minion(self):
        s = gs(mana=1, opp=[mm(10, "Brocken", 5, 5), mm(11, "Wicht", 1, 1)], hand=[card(1, "LICHT")])
        p = plan_for(s)
        self.assertTrue(any("Das Licht! Es brennt! auf Brocken" in t for t in texts(p)), texts(p))
        self.assertEqual(p.unknown_cards, [])

    def test_target_attack_not_played_on_zero_attack(self):
        s = gs(mana=1, opp_hp=30, opp=[mm(10, "Totem", 0, 3)], hand=[card(1, "LICHT")])
        self.assertFalse(any("Das Licht" in t for t in texts(plan_for(s))))

    def test_light_bomb_hits_both_sides(self):
        s = gs(mana=6, mine=[mm(1, "Eigener", 2, 2)], opp=[mm(10, "A", 3, 3), mm(11, "B", 4, 4)], hand=[card(1, "BOMBE")])
        p = plan_for(s)
        self.assertTrue(any("Lichtbombe" in t for t in texts(p)), texts(p))

    def test_hero_attack_damage_needs_hero_attack(self):
        s = gs(mana=1, opp=[mm(10, "Brocken", 2, 4)], hand=[card(1, "UNBAENDIG")])
        s.my_hero_atk = 0
        self.assertFalse(any("Unbändigkeit" in t for t in texts(plan_for(s))))
        s = gs(mana=1, opp=[mm(10, "Brocken", 2, 4)], hand=[card(1, "UNBAENDIG")])
        s.my_hero_atk, s.my_hero_attacks_left = 4, 1
        self.assertTrue(any("Unbändigkeit auf Brocken" in t for t in texts(plan_for(s))), texts(plan_for(s)))

    def test_armor_damage_needs_armor(self):
        s = gs(mana=3, opp=[mm(10, "A", 2, 2)], hand=[card(1, "RUNDUM")])
        self.assertFalse(any("Rundumschlag" in t for t in texts(plan_for(s))))
        s = gs(mana=3, opp=[mm(10, "A", 2, 2)], hand=[card(1, "RUNDUM")])
        s.my_armor = 5
        self.assertTrue(any("Rundumschlag" in t for t in texts(plan_for(s))), texts(plan_for(s)))

    def test_strangle_removes_highest_attack(self):
        s = gs(mana=3, opp=[mm(10, "Klein", 2, 9), mm(11, "Groß", 7, 2)], hand=[card(1, "STRANGULIEREN")])
        p = plan_for(s)
        self.assertTrue(any("Groß wird vernichtet" in t or "Strangulieren" in t for t in texts(p)), texts(p))
        self.assertEqual(p.unknown_cards, [])

    def test_strangle_not_played_into_empty_board(self):
        s = gs(mana=3, opp=[], hand=[card(1, "STRANGULIEREN")])
        self.assertFalse(any("Strangulieren" in t for t in texts(plan_for(s))))


if __name__ == "__main__":
    unittest.main()
