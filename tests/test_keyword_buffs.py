"""Paket 2 der unverstandenen Zauber: Gottesschild/Lebensentzug-Staerkungen, '+X Angriff in diesem Zug', Spott-Staerkung."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "SCHUTZ": dict(name="Hand des Schutzes", cardtype="SPELL", cost=1, text="Verleiht einem Diener Gottesschild."),
    "RECHT": dict(name="Rechtschaffenheit", cardtype="SPELL", cost=5, text="Verleiht Euren Dienern Gottesschild."),
    "SIEGEL": dict(name="Siegel des Champions", cardtype="SPELL", cost=3,
                   text="Verleiht einem Diener +3 Angriff und Gottesschild."),
    "KAMPFRAUSCH": dict(name="Kampfrausch", cardtype="SPELL", cost=5, text="Verleiht Euren Dienern +3 Angriff in diesem Zug."),
    "BRUELLEN": dict(name="Wildes Brüllen", cardtype="SPELL", cost=3,
                     text="Verleiht Euren Charakteren +2 Angriff in diesem Zug."),
    "STAERKEN": dict(name="Stärken", cardtype="SPELL", cost=2, text="Verleiht Euren Dienern mit Spott +2/+2."),
    "JAGD": dict(name="Unerbittliche Jagd", cardtype="SPELL", cost=3,
                 text="Verleiht Eurem Helden in diesem Zug +4 Angriff und Immunität."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_divine_shield_only(self):
        e = parse_effect("Verleiht einem Diener Gottesschild.", "SPELL")
        self.assertEqual((e.buff, e.buff_kw, e.target_kind, e.unknown), ((0, 0, False), ("gottesschild",), "friendly_minion", False))

    def test_stats_and_keywords(self):
        e = parse_effect("Verleiht einem Diener +4/+4, Gottesschild und Spott.", "SPELL")
        self.assertEqual((e.buff, e.buff_kw), ((4, 4, True), ("gottesschild",)))
        e = parse_effect("Verleiht einem Diener +2/+3 und Lebensentzug.", "SPELL")
        self.assertEqual((e.buff, e.buff_kw), ((2, 3, False), ("lebensentzug",)))

    def test_team_keyword_and_taunt_filter(self):
        e = parse_effect("Verleiht Euren Dienern Gottesschild.", "SPELL")
        self.assertEqual((e.team_kw, e.team_taunt_only, e.unknown), (("gottesschild",), False, False))
        e = parse_effect("Verleiht Euren Dienern mit Spott +2/+2.", "SPELL")
        self.assertEqual((e.team_buff, e.team_taunt_only), ((2, 2, False), True))

    def test_temp_attack(self):
        e = parse_effect("Verleiht Euren Dienern +3 Angriff in diesem Zug.", "SPELL")
        self.assertEqual((e.temp_atk, e.temp_hero, e.unknown), (3, False, False))
        e = parse_effect("Verleiht Euren Charakteren +2 Angriff in diesem Zug.", "SPELL")
        self.assertEqual((e.temp_atk, e.temp_hero), (2, True))

    def test_hero_attack_with_immunity(self):
        e = parse_effect("Verleiht Eurem Helden in diesem Zug +4 Angriff und Immunität.", "SPELL")
        self.assertEqual((e.hero_atk_buff, e.unknown), (4, False))

    def test_incomplete_or_unknown_stays_unknown(self):
        # mehrere Saetze mit neuen Merkmalen und unbekannte Zusaetze duerfen nicht als verstanden gelten
        self.assertTrue(parse_effect("Verleiht einem Diener +2 Leben. Gleicht dann seinen Angriff an sein Leben an.", "SPELL").unknown)
        self.assertTrue(parse_effect("Verleiht einem Diener +2/+4 und Zauberschaden +1.", "SPELL").unknown)
        self.assertTrue(parse_effect("Verleiht einem Diener +3 Angriff und Ansturm.", "SPELL").unknown)
        self.assertTrue(parse_effect("Verleiht Euren Dienern +1/+1 und Flüchtig.", "SPELL").unknown)
        self.assertTrue(parse_effect("Verleiht Eurem Helden in diesem Zug +2 Angriff und Immunität. Greift dann jeden feindlichen Diener an.", "SPELL").unknown)

    def test_old_buffs_unchanged(self):
        e = parse_effect("Verleiht einem Diener Spott und +2/+3. (+2 Angriff/+3 Leben)", "SPELL")
        self.assertEqual((e.buff, e.buff_kw), ((2, 3, True), ()))
        self.assertEqual(parse_effect("Verleiht Euren Dienern +2/+2 und Spott.", "SPELL").team_buff, (2, 2, True))


class TestPlanning(unittest.TestCase):
    def test_divine_shield_goes_on_own_minion(self):
        s = gs(mana=1, mine=[mm(1, "Kämpfer", 3, 3)], opp=[mm(10, "Wächter", 2, 6, taunt=True)], hand=[card(1, "SCHUTZ")])
        t = texts(plan_for(s))
        self.assertTrue(any("Hand des Schutzes auf Kämpfer" in x for x in t), t)

    def test_divine_shield_not_wasted_on_shielded_minion(self):
        s = gs(mana=1, mine=[mm(1, "Kämpfer", 3, 3, divine_shield=True)], hand=[card(1, "SCHUTZ")])
        self.assertFalse(any("Hand des Schutzes" in x for x in texts(plan_for(s))))

    def test_team_divine_shield_needs_unshielded_minions(self):
        s = gs(mana=5, mine=[mm(1, "A", 3, 3, divine_shield=True)], hand=[card(1, "RECHT")])
        self.assertFalse(any("Rechtschaffenheit" in x for x in texts(plan_for(s))))

    def test_temp_attack_enables_lethal(self):
        s = gs(mana=5, opp_hp=7, mine=[mm(1, "A", 2, 2), mm(2, "B", 2, 2)], hand=[card(1, "KAMPFRAUSCH")])
        p = plan_for(s)
        self.assertTrue(p.lethal, texts(p))
        self.assertIn("Kampfrausch", p.steps[0].text)

    def test_temp_attack_not_played_without_attackers(self):
        s = gs(mana=5, opp_hp=30, mine=[mm(1, "A", 2, 2, exhausted=True)], hand=[card(1, "KAMPFRAUSCH")])
        self.assertFalse(any("Kampfrausch" in x for x in texts(plan_for(s))))

    def test_hero_and_minions_get_temp_attack(self):
        s = gs(mana=3, opp_hp=5, mine=[mm(1, "A", 1, 1)], hand=[card(1, "BRUELLEN")])   # Diener 1+2 und Held 0+2 = 5
        s.my_hero_atk, s.my_hero_attacks_left = 0, 1
        p = plan_for(s)
        self.assertTrue(p.lethal, texts(p))

    def test_taunt_buff_only_when_taunt_minion_present(self):
        s = gs(mana=2, mine=[mm(1, "Ohne", 2, 2)], hand=[card(1, "STAERKEN")])
        self.assertFalse(any("Stärken" in x for x in texts(plan_for(s))))
        s = gs(mana=2, mine=[mm(1, "Mauer", 1, 3, taunt=True)], hand=[card(1, "STAERKEN")])
        self.assertTrue(any("Stärken" in x for x in texts(plan_for(s))), texts(plan_for(s)))

    def test_relentless_hunt_gives_hero_attack(self):
        s = gs(mana=3, opp_hp=4, hand=[card(1, "JAGD")])
        s.my_hero_atk, s.my_hero_attacks_left = 0, 1
        self.assertTrue(plan_for(s).lethal)


if __name__ == "__main__":
    unittest.main()
