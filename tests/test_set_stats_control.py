"""Paket 6: Werte setzen, Kontrolle uebernehmen und Zielbedingungen (verletzt / Volk) bei Staerkungen."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "DINO": dict(name="Dinogröße", cardtype="SPELL", cost=7, text="Setzt die Werte eines Dieners auf 7/14."),
    "UNTERDRUECKUNG": dict(name="Unterdrückung", cardtype="SPELL", cost=2, text="Setzt Angriff und Leben eines Dieners auf 1."),
    "DEMUT": dict(name="Demut", cardtype="SPELL", cost=1, text="Setzt den Angriff eines Dieners auf 1."),
    "JAEGER": dict(name="Mal des Jägers", cardtype="SPELL", cost=1, text="Setzt das Leben eines Dieners auf 1."),
    "GLEICHHEIT": dict(name="Gleichheit", cardtype="SPELL", cost=2, text="Setzt das Leben ALLER Diener auf 1."),
    "SCHRUMPF": dict(name="Schrumpfstrahl", cardtype="SPELL", cost=5, text="Setzt Angriff und Leben aller Diener auf 1."),
    "KONTROLLE": dict(name="Gedankenkontrolle", cardtype="SPELL", cost=10, text="Übernehmt die Kontrolle über einen feindlichen Diener."),
    "TOBEN": dict(name="Toben", cardtype="SPELL", cost=2, text="Verleiht einem verletzten Diener +3/+3."),
    "FUSION": dict(name="Dämonische Fusion", cardtype="SPELL", cost=2, text="Verleiht einem Dämon +3/+3."),
    "TOTEMKRAFT": dict(name="Kraft der Totems", cardtype="SPELL", cost=2, text="Verleiht Euren Totems +2 Angriff."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_set_stats_variants(self):
        e = parse_effect("Setzt das Leben eines Dieners auf 1.", "SPELL")
        self.assertEqual((e.set_stats, e.set_scope, e.target_kind), ((None, 1), "target", "any_minion"))
        self.assertEqual(parse_effect("Setzt den Angriff eines Dieners auf 1.", "SPELL").set_stats, (1, None))
        self.assertEqual(parse_effect("Setzt die Werte eines Dieners auf 7/14.", "SPELL").set_stats, (7, 14))
        self.assertEqual(parse_effect("Setzt Angriff und Leben eines Dieners auf 3.", "SPELL").set_stats, (3, 3))

    def test_set_stats_all_minions(self):
        e = parse_effect("Setzt Angriff und Leben aller Diener auf 1.", "SPELL")
        self.assertEqual((e.set_stats, e.set_scope, e.target_kind), ((1, 1), "all", ""))
        self.assertEqual(parse_effect("Setzt das Leben ALLER Diener auf 1.", "SPELL").set_stats, (None, 1))

    def test_steal(self):
        e = parse_effect("Übernehmt die Kontrolle über einen feindlichen Diener.", "SPELL")
        self.assertEqual((e.steal, e.target_kind, e.unknown), (True, "enemy_minion", False))

    def test_target_conditions(self):
        e = parse_effect("Verleiht einem verletzten Diener +3/+3.", "SPELL")
        self.assertEqual((e.buff, e.buff_hurt_only, e.target_kind), ((3, 3, False), True, "friendly_minion"))
        e = parse_effect("Verleiht einem Dämon +3/+3.", "SPELL")
        self.assertEqual((e.buff, e.buff_race), ((3, 3, False), "DEMON"))
        e = parse_effect("Verleiht Euren Totems +2 Angriff.", "SPELL")
        self.assertEqual((e.team_buff, e.team_race), ((2, 0, False), "TOTEM"))

    def test_incomplete_texts_stay_unknown(self):
        for t in ("Setzt das Leben eines feindlichen Dieners auf 1. Wählt ein zweites Ziel, wenn Ihr einen Drachen auf der Hand habt.",
                  "Setzt die Werte eines feindlichen Dieners auf 1/1; oder setzt die Werte eines befreundeten Dieners auf 3/3.",
                  "Übernehmt bis zum Ende des Zuges die Kontrolle über einen feindlichen Diener mit max. 3 Angriff.",
                  "Verleiht einem Wildtier +3/+3. Mischt 3 Kopien mit +3/+3 in Euer Deck."):
            self.assertTrue(parse_effect(t, "SPELL").unknown, t)

    def test_unknown_word_is_no_race_or_temp_buff(self):
        self.assertTrue(parse_effect("Verleiht Euren Gebäuden +3 Angriff in diesem Zug.", "SPELL").unknown)
        self.assertTrue(parse_effect("Verleiht einem Gebäude +3/+3.", "SPELL").unknown)


class TestPlanning(unittest.TestCase):
    def test_big_stats_go_on_my_own_minion(self):
        s = gs(mana=7, opp_hp=14, mine=[mm(1, "Kämpfer", 2, 2)], hand=[card(1, "DINO")])
        t = texts(plan_for(s))
        self.assertTrue(any("Dinogröße auf Kämpfer" in x for x in t), t)

    def test_shrink_ray_hits_the_enemy_threat(self):
        s = gs(mana=2, my_hp=5, opp=[mm(10, "Brocken", 9, 9)], hand=[card(1, "UNTERDRUECKUNG")])
        t = texts(plan_for(s))
        self.assertTrue(any("Unterdrückung auf Brocken" in x for x in t), t)

    def test_hp_set_to_one_enables_trade(self):
        s = gs(mana=1, mine=[mm(1, "Kämpfer", 2, 4)], opp=[mm(10, "Dicker", 3, 9, taunt=True)], hand=[card(1, "JAEGER")])
        t = texts(plan_for(s))
        self.assertTrue(any("Mal des Jägers auf Dicker" in x for x in t), t)

    def test_set_to_same_values_is_not_played(self):
        s = gs(mana=1, opp=[mm(10, "Winzig", 1, 1)], hand=[card(1, "UNTERDRUECKUNG")])
        self.assertFalse(any("Unterdrückung" in x for x in texts(plan_for(s))))

    def test_equality_hurts_my_own_board_too(self):
        # nur mein grosser Diener auf dem Board: Gleichheit waere ein Eigentor und wird nicht gespielt
        s = gs(mana=2, mine=[mm(1, "Mein Riese", 5, 8)], opp=[], hand=[card(1, "GLEICHHEIT")])
        self.assertFalse(any("Gleichheit" in x for x in texts(plan_for(s))))
        s = gs(mana=5, my_hp=6, mine=[mm(1, "Winzling", 1, 1)], opp=[mm(10, "A", 6, 9), mm(11, "B", 6, 9)], hand=[card(1, "SCHRUMPF")])
        self.assertTrue(any("Schrumpfstrahl" in x for x in texts(plan_for(s))))

    def test_mind_control_moves_minion_to_my_side(self):
        s = gs(mana=10, opp=[mm(10, "Wächter", 4, 4)], hand=[card(1, "KONTROLLE")])
        p = plan_for(s)
        self.assertTrue(any("Gedankenkontrolle auf Wächter" in x and "wechselt auf deine Seite" in x for x in texts(p)), texts(p))
        self.assertIn("1 Diener", p.summary.split("Du:")[1])

    def test_hurt_and_race_targets(self):
        s = gs(mana=2, mine=[mm(1, "Heil", 2, 4), mm(2, "Verletzt", 3, 1, max_hp=4)], hand=[card(1, "TOBEN")])
        t = texts(plan_for(s))
        self.assertTrue(any("Toben auf Verletzt" in x for x in t), t)
        s = gs(mana=2, mine=[mm(1, "Heil", 2, 4)], hand=[card(1, "TOBEN")])
        self.assertFalse(any("Toben" in x for x in texts(plan_for(s))))
        s = gs(mana=2, mine=[mm(1, "Kobold", 2, 2), mm(2, "Imp", 1, 1, race="DEMON")], hand=[card(1, "FUSION")])
        t = texts(plan_for(s))
        self.assertTrue(any("Dämonische Fusion auf Imp" in x for x in t), t)

    def test_team_race_buff_needs_matching_minion(self):
        s = gs(mana=2, mine=[mm(1, "Kobold", 2, 2)], hand=[card(1, "TOTEMKRAFT")])
        self.assertFalse(any("Kraft der Totems" in x for x in texts(plan_for(s))))
        s = gs(mana=2, mine=[mm(1, "Totem", 0, 2, race="TOTEM"), mm(2, "Kobold", 2, 2)], hand=[card(1, "TOTEMKRAFT")])
        self.assertTrue(any("Kraft der Totems" in x for x in texts(plan_for(s))), texts(plan_for(s)))


if __name__ == "__main__":
    unittest.main()
