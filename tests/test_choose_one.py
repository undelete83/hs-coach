"""Paket 4 der unverstandenen Zauber: 'Waehlt aus' - der Planer spielt jede bekannte Option durch und waehlt die bessere."""
import unittest

from hscoach.effects import parse_effect
from hscoach.planner import Planner

from tests.helpers import CARDS, card, fake_db, gs, mm

CARDS.update({
    "MAL_NATUR": dict(name="Mal der Natur", cardtype="SPELL", cost=3,
                      text="Wählt aus: Verleiht einem Diener +4 Angriff; oder +4 Leben und Spott."),
    "EINFLUESTERUNG": dict(name="Dunkle Einflüsterung", cardtype="SPELL", cost=6,
                           text="Wählt aus: Ruft 5 Irrwische herbei; oder verleiht einem Diener +5/+5 und Spott."),
    "AUFFORSTUNG": dict(name="Aufforstung", cardtype="SPELL", cost=2,
                        text="Wählt aus: Zieht einen Zauber; oder zieht einen Diener. (Behaltet diesen Zauber @ Zug, um beides zu tun!)"),
    "RABENGOETZE": dict(name="Rabengötze", cardtype="SPELL", cost=1,
                        text="Wählt aus: Entdeckt einen Diener; oder entdeckt einen Zauber."),
})


def plan_for(s):
    return Planner(fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestParsing(unittest.TestCase):
    def test_both_options_known(self):
        e = parse_effect("Wählt aus: Verleiht einem Diener +4 Angriff; oder +4 Leben und Spott.", "SPELL")
        self.assertEqual((e.unknown, len(e.choices), e.choice_labels), (False, 2, ("Verleiht einem Diener +4 Angriff", "+4 Leben und Spott")))

    def test_only_known_options_are_kept(self):
        e = parse_effect("Wählt aus: Ruft 5 Irrwische herbei; oder verleiht einem Diener +5/+5 und Spott.", "SPELL")
        self.assertEqual([o.buff for o in e.choices], [(5, 5, True)])

    def test_draw_options_and_trailing_hint(self):
        e = parse_effect("Wählt aus: Zieht einen Zauber; oder zieht einen Diener. (Behaltet diesen Zauber @ Zug, um beides zu tun!)", "SPELL")
        self.assertEqual([o.draw for o in e.choices], [1, 1])

    def test_discover_options_are_estimated(self):
        e = parse_effect("Wählt aus: Entdeckt einen Diener; oder entdeckt einen Zauber.", "SPELL")
        self.assertEqual((e.unknown, [o.est_label for o in e.choices]), (False, ["Entdecken", "Entdecken"]))

    def test_unrecognizable_options_stay_unknown(self):
        self.assertTrue(parse_effect("Wählt aus: Tauscht etwas Merkwürdiges; oder tut etwas Unbekanntes.", "SPELL").unknown)

    def test_typed_draw_only_for_single_sentence_cards(self):
        self.assertEqual(parse_effect("Zieht einen Zauber.", "SPELL").draw, 1)
        # Mehrsatz-Karten (Zusatzeffekte) duerfen nicht halb verstanden werden
        self.assertTrue(parse_effect("Zieht 2 Diener. Verleiht ihnen +2/+2, wenn Ihr mind. 10 Mana habt.", "SPELL").unknown)
        self.assertTrue(parse_effect("Zieht einen Diener. Tauscht ihr Leben.", "SPELL").unknown)

    def test_without_semicolon_stays_unknown(self):
        self.assertTrue(parse_effect("Wählt aus: Erhaltet 2 Naturzauber auf Eure Hand oder verringert die Kosten von Zaubern auf Eurer Hand um (1).", "SPELL").unknown)


class TestPlanning(unittest.TestCase):
    def test_planner_picks_attack_option_for_lethal_pressure(self):
        # Gegner-Held 4 Leben, mein Diener 1/1: +4 Angriff ist letal, +4 Leben nicht
        s = gs(mana=3, opp_hp=5, mine=[mm(1, "Kämpfer", 1, 1)], hand=[card(1, "MAL_NATUR")])
        p = plan_for(s)
        self.assertTrue(p.lethal, texts(p))
        self.assertIn("Wahl: Verleiht einem Diener +4 Angriff", texts(p)[0])

    def test_planner_picks_taunt_option_when_defending(self):
        # Ich stehe kurz vor dem Tod und der Gegner hat viel Angriff: Spott/Leben ist die bessere Wahl
        s = gs(mana=3, my_hp=3, opp_hp=30, mine=[mm(1, "Kämpfer", 1, 1)], opp=[mm(10, "Brocken", 6, 6), mm(11, "Zweiter", 4, 4)],
               hand=[card(1, "MAL_NATUR")])
        p = plan_for(s)
        self.assertTrue(any("+4 Leben und Spott" in t for t in texts(p)), texts(p))

    def test_only_known_option_is_played(self):
        s = gs(mana=6, mine=[mm(1, "Kämpfer", 2, 2)], opp=[mm(10, "Wächter", 3, 6, taunt=True)], hand=[card(1, "EINFLUESTERUNG")])
        t = texts(plan_for(s))
        self.assertTrue(any("Dunkle Einflüsterung" in x and "+5/+5 und Spott" in x for x in t), t)
        self.assertFalse(any("Irrwisch" in x for x in t))

    def test_discover_choose_one_is_estimated_not_unknown(self):
        s = gs(mana=1, hand=[card(1, "RABENGOETZE")])
        p = plan_for(s)
        t = texts(p)
        self.assertTrue(any("Rabengötze" in x and "pauschal geschätzt" in x for x in t), t)
        self.assertEqual(p.unknown_cards, [])


if __name__ == "__main__":
    unittest.main()
