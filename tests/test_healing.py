"""Paket 3 der unverstandenen Zauber: Diener heilen (Kreis der Heilung, Verbindende Heilung, Heilung der Ahnen)."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "KREIS": dict(name="Kreis der Heilung", cardtype="SPELL", cost=0, text="Stellt bei ALLEN Dienern 4 Leben wieder her."),
    "VERBINDEND": dict(name="Verbindende Heilung", cardtype="SPELL", cost=1,
                       text="Stellt bei einem Diener und Eurem Helden 5 Leben wieder her."),
    "AHNEN": dict(name="Heilung der Ahnen", cardtype="SPELL", cost=0,
                  text="Stellt das volle Leben eines Dieners wieder her und verleiht ihm Spott."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_heal_all_minions(self):
        e = parse_effect("Stellt bei ALLEN Dienern 4 Leben wieder her.", "SPELL")
        self.assertEqual((e.heal_all_minions, e.target_kind, e.unknown), (4, "", False))

    def test_heal_minion_and_hero(self):
        e = parse_effect("Stellt bei einem Diener und Eurem Helden 5 Leben wieder her.", "SPELL")
        self.assertEqual((e.heal_minion, e.heal, e.target_kind, e.unknown), (5, 5, "friendly_minion", False))

    def test_heal_full_and_taunt(self):
        e = parse_effect("Stellt das volle Leben eines Dieners wieder her und verleiht ihm Spott.", "SPELL")
        self.assertEqual((e.heal_minion, e.buff, e.target_kind), (999, (0, 0, True), "friendly_minion"))

    def test_other_heals_unchanged(self):
        self.assertEqual(parse_effect("Stellt bei Eurem Helden 8 Leben wieder her.", "SPELL").heal, 8)
        # Zusatzbedingungen: bleibt unbekannt
        self.assertTrue(parse_effect("Stellt bei einem Diener und seinen Nachbarn 3 Leben wieder her. Füllt für jeden überheilten Diener einen Manakristall wieder auf.", "SPELL").unknown)
        self.assertTrue(parse_effect("Stellt das volle Leben aller Charaktere wieder her.", "SPELL").unknown)


class TestPlanning(unittest.TestCase):
    def test_circle_heals_my_damaged_minion(self):
        s = gs(mana=0, mine=[mm(1, "Verletzt", 4, 2, max_hp=6)], opp=[mm(10, "Gegner", 3, 3)], hand=[card(1, "KREIS")])
        p = plan_for(s)
        self.assertTrue(any("Kreis der Heilung" in t for t in texts(p)), texts(p))
        self.assertEqual(p.unknown_cards, [])

    def test_circle_not_played_when_everyone_is_healthy(self):
        s = gs(mana=0, mine=[mm(1, "Heil", 4, 4, exhausted=True)], opp=[], hand=[card(1, "KREIS")])
        self.assertFalse(any("Kreis der Heilung" in t for t in texts(plan_for(s))))

    def test_circle_after_trade_heals_the_survivor(self):
        # Planer darf erst angreifen (Schaden nehmen) und danach heilen
        s = gs(mana=0, mine=[mm(1, "Heil", 4, 4)], opp=[mm(10, "Gegner", 3, 3)], hand=[card(1, "KREIS")])
        t = texts(plan_for(s))
        self.assertTrue(any("greift" in x for x in t) and any("Kreis der Heilung" in x for x in t), t)

    def test_circle_does_not_heal_above_max(self):
        from hscoach.planner import _healed, M
        m = M(1, "A", "", 1, 5, False, False, False, False, False, False, 1, 0, False, False, 0, "", True, False, 6)
        self.assertEqual(_healed(m, 4).hp, 6)

    def test_linked_heal_targets_damaged_minion_or_hurt_hero(self):
        s = gs(mana=1, my_hp=20, mine=[mm(1, "Unverletzt", 3, 3)], hand=[card(1, "VERBINDEND")])
        self.assertTrue(any("Verbindende Heilung" in t for t in texts(plan_for(s))), texts(plan_for(s)))    # Held ist verletzt
        s = gs(mana=1, my_hp=30, mine=[mm(1, "Unverletzt", 3, 3)], hand=[card(1, "VERBINDEND")])
        self.assertFalse(any("Verbindende Heilung" in t for t in texts(plan_for(s))))                        # nichts zu heilen

    def test_ancestral_healing_gives_taunt(self):
        s = gs(mana=0, mine=[mm(1, "Verletzt", 3, 1, max_hp=5)], opp=[mm(10, "Stark", 5, 5)], hand=[card(1, "AHNEN")])
        p = plan_for(s)
        t = texts(p)
        self.assertTrue(any("Heilung der Ahnen auf Verletzt" in x for x in t), t)

    def test_buffed_minion_keeps_correct_max_hp(self):
        from hscoach.planner import _buffed, _healed, M
        m = M(1, "A", "", 2, 3, False, False, False, False, False, False, 1, 0, False, False, 0, "", True, False, 5)
        m = _buffed(m, (0, 2, ""))            # +2 Leben: Maximum steigt von 5 auf 7
        self.assertEqual((m.hp, m.mhp), (5, 7))
        self.assertEqual(_healed(m, 10).hp, 7)


if __name__ == "__main__":
    unittest.main()
