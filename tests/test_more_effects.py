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
        e = parse_effect("Wählt aus: Verleiht einem Diener +4 Angriff; oder +4 Leben und Spott.", "SPELL")    # Waehlt aus: je Option ein Effekt
        self.assertEqual([o.buff for o in e.choices], [(4, 0, False), (0, 4, True)])

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


class TestLifestealPriority(unittest.TestCase):
    def test_lifesteal_windfury_minion_is_hit_first(self):
        """Zwei gleich gefaehrliche Ziele: der mit Lebensraub + Windzorn heilt den Gegner und muss zuerst fallen."""
        s = gs(mana=0, opp_hp=30, mine=[mm(1, "Angreifer", 4, 6)],
               opp=[mm(10, "Klotz", 9, 4), mm(11, "Brunnen", 3, 4, lifesteal=True, windfury=True)])
        p = plan_for(s)
        self.assertTrue(p.steps)
        self.assertIn("Brunnen", p.steps[0].text)

    def test_lifesteal_value_grows_with_attack_and_windfury(self):
        from hscoach.planner import M, _mval
        base = dict(uid=1, name="x", cid="", atk=4, hp=4, taunt=False, ds=False, poison=False, frozen=False, stealth=False,
                    immune=False, wf=1, att=0, face=True, lifesteal=False, sp=0, race="", mine=False, fzr=False, mhp=4)
        plain = _mval(M(**base))
        ls = _mval(M(**dict(base, lifesteal=True)))
        ls_wf = _mval(M(**dict(base, lifesteal=True, wf=2)))
        self.assertGreater(ls, plain + 1.0)
        self.assertGreater(ls_wf, ls + 2.0)

    def test_thrall_boss_knows_the_fountain(self):
        from hscoach import bosses
        b = bosses.find("Story_01_Thrall")
        self.assertEqual(b.name, "Thrall")
        self.assertGreaterEqual(b.bias.get("priority", {}).get("Wandelnder Brunnen", 1), 2)
        self.assertTrue(any("Brunnen" in d for d in b.dangers))



class TestAuras(unittest.TestCase):
    def test_summoning_aura_gets_an_estimated_value(self):
        from hscoach.effects import parse_effect
        e = parse_effect("Ruft am Ende Eures Zuges einen Drachen (3/5) mit Spott herbei. Hält 3 Züge lang an.", "SPELL")
        self.assertFalse(e.unknown)
        self.assertEqual(e.est_label, "Aura")
        self.assertGreater(e.est_value, 8)

    def test_generic_aura_is_not_unknown(self):
        from hscoach.effects import parse_effect
        e = parse_effect("Die Effekte am Ende des Zuges Eurer Diener werden zweimal ausgelöst. Hält 3 Züge lang an.", "SPELL")
        self.assertFalse(e.unknown)
        self.assertGreater(e.est_value, 0)


class TestManaCrystalLoss(unittest.TestCase):
    def test_parsed(self):
        from hscoach.effects import parse_effect
        e = parse_effect("Spott. Kampfschrei: Zerstört einen Eurer Manakristalle.", "MINION")
        self.assertEqual(e.lose_crystal, 1)

    def test_early_game_penalty_makes_hellguard_unattractive_vs_plain_play(self):
        from tests.helpers import CARDS
        CARDS["TEUFELSWACHE"] = dict(name="Teufelswache", cardtype="MINION", cost=3, text="Spott. Kampfschrei: Zerstört einen Eurer Manakristalle.")
        CARDS["GRUNT"] = dict(name="Grunzer", cardtype="MINION", cost=3, text="")
        try:
            hand = [card(1, "TEUFELSWACHE", atk=3, hp=5), card(2, "GRUNT", atk=3, hp=3)]
            plan = Planner(fake_db(), 1.0).plan(gs(mana=3, hand=hand), None)
            self.assertIn("Grunzer", plan.steps[0].text)
            late = Planner(fake_db(), 1.0).plan(gs(mana=10, hand=[card(1, "TEUFELSWACHE", atk=3, hp=5)]), None)
            self.assertIn("Teufelswache", late.steps[0].text)           # bei 10 Mana kostet der Kristall nichts mehr
        finally:
            del CARDS["TEUFELSWACHE"], CARDS["GRUNT"]


class TestGenericEstimate(unittest.TestCase):
    def est(self, text):
        from hscoach.effects import parse_effect_estimated
        return parse_effect_estimated(text, "SPELL")

    def test_useful_cards_get_an_estimate(self):
        for t in ("Zieht 3 Diener. Verleiht Dienern auf Eurer Hand +2/+2.",
                  "Verleiht einem befreundeten Diener +3/+3 und Eifer.",
                  "Verdoppelt den Angriff eines Dieners.",
                  "Belebt 2 verschiedene befreundete Diener wieder."):
            e = self.est(t)
            self.assertFalse(e.unknown, t)
            self.assertGreater(e.est_value, 0, t)
            self.assertLessEqual(e.est_value, 6.0)

    def test_short_lived_buff_is_worth_less(self):
        full = self.est("Verleiht einem befreundeten Diener +3/+3 und Eifer.").est_value
        temp = self.est("Verleiht einem befreundeten Diener +3/+3 und Eifer. Er stirbt am Ende des Zuges.").est_value
        self.assertLess(temp, full)

    def test_drawbacks_and_quests_stay_unknown(self):
        for t in ("Setzt Eure Manakristalle auf 0. Setzt die Kosten aller Karten auf Eurer Hand auf (1).",
                  "Quest: Ruft 20 Diener herbei. Belohnung: Kriegsmaske des Pharaos.",
                  "Zerstört einen Eurer Manakristalle. Erhaltet in 2 Zügen 2 Manakristalle.",
                  "Vernichtet Eure Untoten. Ruft sie erneut herbei."):
            self.assertTrue(self.est(t).unknown, t)


class TestShuffleBack(unittest.TestCase):
    """Geschuetzter Ueberlebender: der Plan nennt die Karte, die ins Deck gemischt werden soll."""

    def setUp(self):
        from tests.helpers import CARDS
        CARDS["SURVIVOR"] = dict(name="Geschützter Überlebender", cardtype="MINION", cost=2,
                                 text="Kampfschrei: Wählt eine Karte auf Eurer Hand und mischt sie in Euer Deck. Zieht eine Karte.")
        self.CARDS = CARDS

    def tearDown(self):
        del self.CARDS["SURVIVOR"]

    def test_parsed(self):
        from hscoach.effects import parse_effect
        self.assertTrue(parse_effect(self.CARDS["SURVIVOR"]["text"], "MINION").shuffle_back)

    def test_names_the_card_to_shuffle(self):
        hand = [card(1, "SURVIVOR", atk=2, hp=3), card(2, "FEUERBALL"), card(3, "ELEM"), card(4, "VERWANDLUNG")]
        # 2 Mana: nur der Ueberlebende ist spielbar; Wasserelementar (4) ist noch zu teuer, Verwandlung kostet 4 -> ebenfalls
        p = Planner(fake_db(), 1.0).plan(gs(mana=2, hand=hand), None)
        text = p.steps[0].text
        self.assertIn("mische", text)
        self.assertNotIn("mische Geschützter Überlebender", text)

    def test_never_shuffles_a_card_the_plan_plays(self):
        hand = [card(1, "SURVIVOR", atk=2, hp=3), card(2, "MUENZE")]
        p = Planner(fake_db(), 1.0).plan(gs(mana=2, hand=hand), None)
        for st in p.steps:
            if "Überlebender" in st.text and "mische" in st.text:
                played_other = [x.text for x in p.steps if x is not st]
                name = st.text.split("mische ")[1].split(" zurück")[0]
                self.assertFalse(any(name in t for t in played_other), (name, played_other))


class TestSilenceBattlecryHint(unittest.TestCase):
    """Bibliothekar des Koenigs: das Schweigen braucht ein Ziel - der Plan nennt eines, auch wenn es nichts bringt."""

    def setUp(self):
        from tests.helpers import CARDS
        CARDS["BIBLIO"] = dict(name="Bibliothekar des Königs", cardtype="MINION", cost=4, text="Handelbar Kampfschrei: Bringt einen Diener zum Schweigen.")
        self.CARDS = CARDS

    def tearDown(self):
        del self.CARDS["BIBLIO"]

    def test_names_a_target_when_nothing_useful_to_silence(self):
        p = Planner(fake_db(), 1.0).plan(gs(mana=4, hand=[card(1, "BIBLIO", atk=4, hp=4)], opp=[mm(10, "Drilly", 4, 3)], mine=[mm(20, "Welpling", 2, 1)]), None)
        txt = " ".join(st.text for st in p.steps)
        self.assertIn("Bibliothekar", txt)
        self.assertTrue("Drilly" in txt and "Pflichtziel" in txt, txt)

    def test_own_minion_only_when_no_enemy(self):
        p = Planner(fake_db(), 1.0).plan(gs(mana=4, hand=[card(1, "BIBLIO", atk=4, hp=4)], mine=[mm(20, "Welpling", 2, 1)]), None)
        txt = " ".join(st.text for st in p.steps)
        self.assertIn("Welpling", txt)
        self.assertIn("einer deiner Diener", txt)


class TestHeroAttack(unittest.TestCase):
    """Mit Waffe und ohne Gegner-Diener soll der Held ins Gesicht schlagen (frueher blieb der Plan leer)."""

    def test_hero_swings_at_face(self):
        s = gs(mana=1, my_weapon=None, opp=[])
        from hscoach.state import Weapon
        s.my_weapon = Weapon(name="Hammer", cid="", atk=2, durability=2)
        s.my_hero_atk = 2
        s.my_hero_can_attack = True
        s.my_hero_attacks_left = 1
        p = Planner(fake_db(), 1.0).plan(s, None)
        self.assertTrue(any("Held" in st.text and "Gesicht" in st.text for st in p.steps), [st.text for st in p.steps])

    def test_equip_then_swing(self):
        from tests.helpers import CARDS
        CARDS["HAMMER"] = dict(name="Inspirierender Hammer", cardtype="WEAPON", cost=2, text="Todesröcheln: Löst den Effekt am Ende des Zuges eines zufälligen befreundeten Dieners aus.")
        try:
            p = Planner(fake_db(), 1.0).plan(gs(mana=3, hand=[card(1, "HAMMER", atk=2, hp=2)], my_hero_attacks_left=1), None)
            texts = [st.text for st in p.steps]
            self.assertTrue(any("Lege" in t for t in texts), texts)
            self.assertTrue(any("Held" in t and "Gesicht" in t for t in texts), texts)
        finally:
            del CARDS["HAMMER"]


class TestRafaamClock(unittest.TestCase):
    def test_warns_after_many_rafaams(self):
        names = ["Winziger Rafaam", "Entdecker Rafaam", "Murloc-Rafaam", "Riesiger Rafaam", "Verhängnisvoller Rafaam", "Gedankenschinder R’faam"]
        p = Planner(fake_db(), 1.0).plan(gs(mana=3, hand=[], opp_played=names), None)
        self.assertTrue(any("RAFAAM-UHR" in w for w in p.warnings), p.warnings)

    def test_no_warning_for_a_few(self):
        p = Planner(fake_db(), 1.0).plan(gs(mana=3, hand=[], opp_played=["Grüner Rafaam", "Feuerball"]), None)
        self.assertFalse(any("RAFAAM" in w for w in p.warnings), p.warnings)


class TestSilenceResetsBuffs(unittest.TestCase):
    """Schweigen setzt gestaerkte Diener auf ihre Grundwerte zurueck (Speerherzwaechter 7/5 -> 3/4)."""

    def setUp(self):
        from tests.helpers import CARDS
        CARDS["BIBLIO"] = dict(name="Bibliothekar des Königs", cardtype="MINION", cost=4, text="Handelbar Kampfschrei: Bringt einen Diener zum Schweigen.")
        CARDS["BUFFED"] = dict(name="Wächter", cardtype="MINION", cost=4, atk=3, health=4, text="")
        self.CARDS = CARDS

    def tearDown(self):
        del self.CARDS["BIBLIO"], self.CARDS["BUFFED"]

    def test_silence_target_is_the_buffed_minion(self):
        foes = [mm(10, "Wächter", 7, 5, cid="BUFFED"), mm(11, "Plain", 2, 2)]
        p = Planner(fake_db(), 1.0).plan(gs(mana=4, hand=[card(1, "BIBLIO", atk=4, hp=4)], opp=foes), None)
        txt = " ".join(st.text for st in p.steps)
        self.assertIn("auf Wächter", txt)

    def test_base_stats_applied(self):
        from hscoach import planner
        planner.BASE_STATS["BUFFED"] = (3, 4)
        m = planner.M(10, "Wächter", "BUFFED", 7, 5, True, False, False, False, False, False, 1, 0, True, False, 0, "", False, False, 5)
        r = planner._silenced(m)
        self.assertEqual((r.atk, r.hp), (3, 4))
        planner.BASE_STATS.clear()
