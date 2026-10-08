"""Weitere Kartenmuster: Heilen, Schweigen, Zurueck auf die Hand, Manakristalle, Aufstocken, Staerkungen, Eckdiener."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "STILLE": dict(name="Stille", cardtype="SPELL", cost=0, text="Bringt einen Diener zum Schweigen."),
    "IRIS": dict(name="Fokussierungsiris", cardtype="MINION", cost=8,
                 text="Zauberschaden +1. Kampfschrei: Füllt Eure Seite des Schlachtfelds mit Wasser[d]elementaren (3/6)."),
    "KRIEGSFUERST": dict(name="Frostwolfkriegsfürst", cardtype="MINION", cost=5,
                         text="Kampfschrei: Erhält +1/+1 für jeden anderen befreundeten Diener auf dem Schlachtfeld."),
    "ZWIELICHT": dict(name="Zwielichtdrache", cardtype="MINION", cost=4,
                      text="Kampfschrei: Erhält +1 Leben für jede Karte auf Eurer Hand."),
    "SHANDRIS": dict(name="Shandris Mondfeder", cardtype="MINION", cost=7,
                     text="Verstohlenheit. Kampfschrei: Vernichtet die feindlichen Diener, die sich ganz links und ganz rechts befinden."),
    "MAL": dict(name="Mal der Wildnis", cardtype="SPELL", cost=2, text="Verleiht einem Diener Spott und +2/+3. (+2 Angriff/+3 Leben)"),
    "KLAUE": dict(name="Klaue", cardtype="SPELL", cost=1, text="Verleiht Eurem Helden +2 Angriff in diesem Zug und 2 Rüstung."),
    "HEILUNG": dict(name="Heiliges Licht", cardtype="SPELL", cost=2, text="Stellt bei Eurem Helden 8 Leben wieder her."),
    "WILDWUCHS": dict(name="Wildwuchs", cardtype="SPELL", cost=2, text="Erhaltet einen leeren Manakristall."),
    "FREMD": dict(name="Fremder", cardtype="MINION", cost=1, text=""),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_hero_heal(self):
        self.assertEqual(parse_effect("Stellt bei Eurem Helden 8 Leben wieder her.", "SPELL").heal, 8)

    def test_silence_and_bounce(self):
        e = parse_effect("Bringt einen Diener zum Schweigen.", "SPELL")
        self.assertEqual((e.silence, e.target_kind), ("target", "enemy_minion"))
        self.assertEqual(parse_effect("Bringt alle feindlichen Diener zum Schweigen.", "SPELL").silence, "aoe")
        self.assertEqual(parse_effect("Bringt alle Diener zum Schweigen und vernichtet sie.", "SPELL").silence, "")
        e = parse_effect("Lasst einen feindlichen Diener auf seine Hand zurückkehren.", "SPELL")
        self.assertEqual((e.bounce, e.target_kind), ("target", "enemy_minion"))

    def test_ramp_and_remove(self):
        self.assertEqual(parse_effect("Erhaltet einen leeren Manakristall.", "SPELL").ramp, 1)
        self.assertEqual(parse_effect("Erhaltet 2 leere Manakristalle.", "SPELL").ramp, 2)
        e = parse_effect("Entfernt einen Diener aus dem Spiel.", "SPELL")
        self.assertEqual((e.destroy, e.target_kind), ("target", "enemy_minion"))

    def test_fill_board(self):
        e = parse_effect("Zauberschaden +1. Kampfschrei: Füllt Eure Seite des Schlachtfelds mit Wasser[d]elementaren (3/6).", "MINION")
        self.assertEqual((e.summon, e.fill_summon, e.summon_freezer), ((3, 6, 0), True, True))

    def test_buff_per(self):
        e = parse_effect("Kampfschrei: Erhält +1/+1 für jeden anderen befreundeten Diener auf dem Schlachtfeld.", "MINION")
        self.assertEqual(e.buff_per, ("minions", 1, 1))
        e = parse_effect("Kampfschrei: Erhält +1 Leben für jede Karte auf Eurer Hand.", "MINION")
        self.assertEqual(e.buff_per, ("hand", 0, 1))

    def test_destroy_ends(self):
        e = parse_effect("Verstohlenheit. Kampfschrei: Vernichtet die feindlichen Diener, die sich ganz links und ganz rechts befinden.", "MINION")
        self.assertTrue(e.destroy_ends)

    def test_cost_zero_discount_with_dragon(self):
        e = parse_effect("Kampfschrei: Euer nächster Zauber in diesem Zug kostet (0), wenn Ihr einen Drachen auf der Hand habt.", "MINION")
        self.assertEqual((e.cond_hold, e.cond_fx.discount), ("DRAGON", ("spell", 99)))

    def test_buffs(self):
        e = parse_effect("Verleiht einem Diener Spott und +2/+3. (+2 Angriff/+3 Leben)", "SPELL")
        self.assertEqual((e.buff, e.target_kind), ((2, 3, True), "friendly_minion"))
        self.assertEqual(parse_effect("Verleiht Euren Dienern +2/+2 und Spott.", "SPELL").team_buff, (2, 2, True))
        e = parse_effect("Verleiht Eurem Helden +2 Angriff in diesem Zug und 2 Rüstung.", "SPELL")
        self.assertEqual((e.hero_atk_buff, e.armor), (2, 2))
        self.assertTrue(parse_effect("Wählt aus: Verleiht einem Diener +4 Angriff; oder +4 Leben und Spott.", "SPELL").unknown)

    def test_newer_missile_wording(self):
        e = parse_effect("Verursacht 3 Schaden, der zufällig auf alle feindlichen Charaktere verteilt wird.", "SPELL")
        self.assertEqual(e.missiles, (3, 1))


class TestPlanning(unittest.TestCase):
    def test_silence_removes_taunt_and_enables_lethal(self):
        s = gs(mana=0, opp_hp=3, mine=[mm(1, "Angreifer", 4, 4)], opp=[mm(10, "Wächter", 2, 5, taunt=True)])
        self.assertFalse(plan_for(s).lethal)
        s = gs(mana=0, opp_hp=3, mine=[mm(1, "Angreifer", 4, 4)], opp=[mm(10, "Wächter", 2, 5, taunt=True)],
               hand=[card(1, "STILLE")])
        p = plan_for(s)
        self.assertTrue(p.lethal, texts(p))
        self.assertIn("Stille", p.steps[0].text)

    def test_silence_not_wasted_on_plain_minion(self):
        s = gs(mana=0, opp_hp=30, opp=[mm(10, "Wolf", 2, 2)], hand=[card(1, "STILLE")])
        self.assertFalse(any("Stille" in t for t in texts(plan_for(s))))

    def test_iris_fills_board(self):
        s = gs(mana=8, opp_hp=30, hand=[card(1, "IRIS", atk=4, hp=4)])
        p = plan_for(s)
        self.assertIn("Fokussierungsiris", p.steps[0].text)
        self.assertIn("7 Diener", p.summary)

    def test_buff_per_other_minions_and_hand(self):
        s = gs(mana=5, mine=[mm(1, "A", 1, 1), mm(2, "B", 1, 1)], hand=[card(1, "KRIEGSFUERST", atk=4, hp=4)])
        self.assertIn("Frostwolfkriegsfürst (6/6)", texts(plan_for(s))[0])
        s = gs(mana=4, hand=[card(1, "ZWIELICHT", atk=4, hp=1), card(2, "FREMD", atk=1, hp=1), card(3, "FREMD", atk=1, hp=1)])
        self.assertIn("Zwielichtdrache (4/3)", texts(plan_for(s))[0])

    def test_shandris_kills_both_ends(self):
        s = gs(mana=7, opp=[mm(10, "L", 2, 2), mm(11, "M", 2, 2), mm(12, "R", 2, 2)], hand=[card(1, "SHANDRIS", atk=4, hp=4)])
        p = plan_for(s)
        self.assertIn("vernichtet L und R", p.steps[0].text)

    def test_friendly_buff_spell_has_target(self):
        s = gs(mana=2, mine=[mm(1, "Kämpfer", 2, 2)], opp=[mm(10, "Wächter", 2, 5, taunt=True)], hand=[card(1, "MAL")])
        t = texts(plan_for(s))
        self.assertTrue(any("Mal der Wildnis auf Kämpfer" in x for x in t), t)

    def test_hero_attack_buff_enables_hero_attack(self):
        s = gs(mana=1, opp_hp=2, hand=[card(1, "KLAUE")])
        s.my_hero_atk, s.my_hero_attacks_left = 0, 1
        p = plan_for(s)
        self.assertTrue(p.lethal, texts(p))

    def test_heal_and_ramp_are_not_unknown(self):
        s = gs(mana=2, my_hp=20, hand=[card(1, "HEILUNG")])
        self.assertEqual(plan_for(s).unknown_cards, [])
        s = gs(mana=2, hand=[card(1, "WILDWUCHS")])
        self.assertEqual(plan_for(s).unknown_cards, [])


if __name__ == "__main__":
    unittest.main()
