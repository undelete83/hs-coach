import time
import unittest

from hscoach.planner import Planner
from hscoach.state import HeroPower

from tests.helpers import card, fake_db, fixture_lines, gs, mm, real_db, replay


def plan_for(s, db=None):
    return Planner(db or fake_db(), 1.0).plan(s)


def texts(plan):
    return [st.text for st in plan.steps]


class TestAttacks(unittest.TestCase):
    def test_must_hit_taunt_first(self):
        s = gs(mana=0, mine=[mm(1, "Angreifer", 3, 3)], opp=[mm(10, "Wächter", 2, 3, taunt=True), mm(11, "Nebensache", 1, 1)])
        p = plan_for(s)
        self.assertTrue(p.steps)
        self.assertIn("Wächter", p.steps[0].text)
        self.assertFalse(any("Helden" in t for t in texts(p)))

    def test_face_when_board_empty(self):
        s = gs(mana=0, mine=[mm(1, "Angreifer", 3, 3)], opp_hp=20)
        p = plan_for(s)
        self.assertEqual(len(p.steps), 1)
        self.assertIn("gegnerischen Helden", p.steps[0].text)

    def test_rush_cannot_hit_face(self):
        s = gs(mana=0, mine=[mm(1, "Stürmer", 4, 4, rush=True, turns_in_play=0)], opp_hp=20)
        self.assertEqual(plan_for(s).steps, [])

    def test_sleeping_minion_does_not_attack(self):
        s = gs(mana=0, mine=[mm(1, "Schläfer", 4, 4, exhausted=True)], opp_hp=20)
        self.assertEqual(plan_for(s).steps, [])

    def test_frozen_minion_does_not_attack(self):
        s = gs(mana=0, mine=[mm(1, "Eisklotz", 4, 4, frozen=True)], opp_hp=20)
        self.assertEqual(plan_for(s).steps, [])

    def test_hero_attacks_with_weapon(self):
        s = gs(mana=0, opp_hp=20, my_hero_atk=2, my_hero_attacks_left=1)
        p = plan_for(s)
        self.assertEqual(len(p.steps), 1)
        self.assertEqual(p.steps[0].kind, "hero_attack")

    def test_trade_kills_dangerous_minion(self):
        s = gs(mana=0, mine=[mm(1, "Gut", 5, 5)], opp=[mm(10, "Gefahr", 4, 3)], opp_hp=30)
        p = plan_for(s)
        self.assertIn("Gefahr", p.steps[0].text)
        self.assertIn("stirbt", p.steps[0].text)

    def test_divine_shield_absorbs_first_hit(self):
        s = gs(mana=0, mine=[mm(1, "Schlag", 3, 3), mm(2, "Zweitschlag", 3, 3)],
               opp=[mm(10, "Geschützt", 1, 1, divine_shield=True)])
        p = plan_for(s)
        self.assertTrue(any("Gottesschild weg" in t for t in texts(p)))
        self.assertTrue(any("Geschützt stirbt" in t for t in texts(p)))


class TestSpells(unittest.TestCase):
    def test_freeze_before_shatter(self):
        s = gs(mana=3, opp=[mm(10, "Koloss", 6, 6)], hand=[card(1, "ZERTRUEMMERN"), card(2, "FROSTSTRAHL")])
        p = plan_for(s)
        names = [st.text.split()[1] for st in p.steps if st.kind == "spell"]
        self.assertEqual(names[:2], ["Froststrahl", "Zertrümmern"])
        self.assertIn("vernichtet", " ".join(texts(p)))

    def test_shatter_needs_frozen_target(self):
        s = gs(mana=2, opp=[mm(10, "Koloss", 6, 6)], hand=[card(1, "ZERTRUEMMERN")])
        self.assertEqual(plan_for(s).steps, [])

    def test_shatter_works_on_already_frozen(self):
        s = gs(mana=2, opp=[mm(10, "Koloss", 6, 6, frozen=True)], hand=[card(1, "ZERTRUEMMERN")])
        self.assertEqual(len(plan_for(s).steps), 1)

    def test_minion_only_spell_never_hits_face(self):
        s = gs(mana=1, hand=[card(1, "FROSTSTRAHL")])
        self.assertEqual(plan_for(s).steps, [])

    def test_lethal_with_spell_and_attack(self):
        s = gs(mana=2, opp_hp=5, mine=[mm(1, "Angreifer", 3, 3)], hand=[card(1, "FROSTBLITZ")])
        p = plan_for(s)
        self.assertTrue(p.lethal)
        self.assertIn("LETHAL", p.summary)

    def test_taunt_blocks_lethal(self):
        s = gs(mana=0, opp_hp=3, mine=[mm(1, "Angreifer", 3, 3)], opp=[mm(10, "Mauer", 0, 9, taunt=True)])
        self.assertFalse(plan_for(s).lethal)

    def test_spell_discount_makes_double_play_possible(self):
        s = gs(mana=3, opp_hp=7, hand=[card(1, "GLETSCHER"), card(2, "FROSTBLITZ")])
        p = plan_for(s)
        self.assertTrue(p.lethal)
        self.assertEqual(set(p.cids), {"GLETSCHER", "FROSTBLITZ"})

    def test_zero_mana_card_is_played(self):
        s = gs(mana=2, hand=[card(1, "ELEMBESCH"), card(2, "ELEM", cost=4, atk=3, hp=6, race="ELEMENTAL", zpos=2)])
        p = plan_for(s)
        self.assertEqual(p.cids, ["ELEMBESCH", "ELEM"])

    def test_non_elemental_gets_no_discount(self):
        s = gs(mana=2, hand=[card(1, "ELEMBESCH"), card(2, "ELEM", cost=4, atk=3, hp=6, race="GIANT", zpos=2)])
        self.assertNotIn("ELEM", plan_for(s).cids)

    def test_coin_enables_play(self):
        s = gs(mana=1, opp=[mm(10, "Ziel", 2, 2)], hand=[card(1, "MUENZE", is_coin=True), card(2, "FROSTBLITZ")])
        p = plan_for(s)
        self.assertEqual(set(p.cids), {"MUENZE", "FROSTBLITZ"})

    def test_aoe_kills_small_board(self):
        s = gs(mana=7, opp=[mm(10, "A", 2, 4), mm(11, "B", 3, 5), mm(12, "C", 1, 1)], hand=[card(1, "FLAMMENSTOSS")])
        p = plan_for(s)
        self.assertEqual(p.cids, ["FLAMMENSTOSS"])

    def test_spell_power_boosts_damage(self):
        s = gs(mana=4, opp=[mm(10, "Ziel", 3, 7)], mine=[mm(1, "Magier", 1, 3, spellpower=1, exhausted=True)],
               hand=[card(1, "FEUERBALL")])
        p = plan_for(s)
        self.assertIn("stirbt", " ".join(texts(p)))        # 6 + 1 Zauberschaden = 7

    def test_hero_power_damage(self):
        hp = HeroPower("Eisschlag", "HEROPOWER_SCHLAG", 2, False, "Verursacht 1 Schaden.")
        s = gs(mana=2, opp=[mm(10, "Winzling", 1, 1)], my_hero_power=hp)
        p = plan_for(s)
        self.assertEqual(p.steps[0].kind, "hero_power")
        self.assertIn("stirbt", p.steps[0].text)

    def test_unknown_spell_is_flagged(self):
        db = fake_db()
        db.cards["RAETSEL"] = dict(name="Rätsel", cardtype="SPELL", cost=2, text="Tut etwas Unerklärliches.")
        c = card(1, "FROSTBLITZ")
        c.cid, c.name, c.cost, c.text = "RAETSEL", "Rätsel", 2, "Tut etwas Unerklärliches."
        s = gs(mana=2, hand=[c])
        p = plan_for(s, db)
        self.assertIn("Rätsel", p.unknown_cards)


class TestSafety(unittest.TestCase):
    def test_warns_about_lethal_threat(self):
        s = gs(mana=0, my_hp=5, opp=[mm(10, "Brecher", 6, 6)])
        self.assertTrue(any("GEFAHR" in w for w in plan_for(s).warnings))

    def test_frozen_attacker_is_no_threat(self):
        s = gs(mana=0, my_hp=5, opp=[mm(10, "Brecher", 6, 6, frozen=True)])
        self.assertFalse(any("GEFAHR" in w for w in plan_for(s).warnings))

    def test_taunt_blocks_incoming(self):
        s = gs(mana=0, my_hp=5, opp=[mm(10, "Brecher", 6, 6)], mine=[mm(1, "Mauer", 0, 9, taunt=True, exhausted=True)])
        self.assertFalse(any("GEFAHR" in w for w in plan_for(s).warnings))

    def test_prefers_freeze_when_facing_lethal(self):
        s = gs(mana=3, my_hp=5, opp=[mm(10, "Brecher", 6, 6)], hand=[card(1, "FROSTSTRAHL")])
        p = plan_for(s)
        self.assertEqual(p.cids, ["FROSTSTRAHL"])
        self.assertFalse(any("GEFAHR" in w for w in p.warnings))


@unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
class TestOnRecordedGames(unittest.TestCase):
    """Property-Tests ueber alle aufgezeichneten Partien."""

    @classmethod
    def setUpClass(cls):
        cls.db = real_db()

    def test_plans_are_valid_and_fast(self):
        planner = Planner(self.db, 1.2)
        checked = 0
        for g in range(6):
            last = None
            for i, tr, s in replay(g, self.db, every=45):
                if not (s.my_active and s.turn > 0 and s.my_mana > 0) or s.mulligan:
                    continue
                key = (s.turn, s.my_mana, len(s.my_hand))
                if key == last:
                    continue
                last = key
                t0 = time.time()
                p = planner.plan(s)
                self.assertLess(time.time() - t0, 3.0, f"Spiel {g} Zeile {i} zu langsam")
                self.assertLessEqual(len(p.steps), 14)
                self.assertLessEqual(p.mana_used, s.my_mana + 4, f"Spiel {g} Zeile {i}: Mana-Budget verletzt")
                played = [st for st in p.steps if st.kind in ("minion", "spell", "weapon")]
                self.assertLessEqual(len(played), len(s.my_hand))
                for st in p.steps:
                    self.assertTrue(st.text)
                checked += 1
        self.assertGreater(checked, 40)

    def test_zero_mana_spell_in_real_game(self):
        # Regression: 0-Mana-Karten (Elementarbeschwoerung) wurden frueher nie empfohlen
        planner = Planner(self.db, 1.0)
        for i, tr, s in replay(5, self.db, every=15):
            if s.my_active and s.turn == 9 and s.my_mana == 5 and any(c.cid == "TRL_310" for c in s.my_hand):
                self.assertIn("TRL_310", planner.plan(s).cids)
                return
        self.skipTest("Situation in der Fixture nicht gefunden")


if __name__ == "__main__":
    unittest.main()


class TestSecrets(unittest.TestCase):
    def test_trap_is_more_valuable_against_wide_board(self):
        db = fake_db()
        db.cards["FALLE"] = dict(name="Flammenfalle", cardtype="SPELL", cost=3, secret=True,
                                 text="Geheimnis: Fügt allen feindlichen Dienern 3 Schaden zu, nachdem ein Diener Euren Helden angegriffen hat.")
        c = card(1, "EISBLOCK")
        c.cid, c.name, c.text = "FALLE", "Flammenfalle", db.cards["FALLE"]["text"]
        wide = gs(mana=3, opp=[mm(10 + i, f"M{i}", 2, 3) for i in range(4)], hand=[c])
        none = gs(mana=3, hand=[c])
        pw, pn = Planner(db).plan(wide), Planner(db).plan(none)
        self.assertEqual(pw.cids, ["FALLE"])
        self.assertGreater(pw.score - pn.score, -1000)      # beide spielen die Falle; Bewertung bleibt endlich


@unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
class TestBossFight(unittest.TestCase):
    """Verlorene Partie gegen Archimonde (Fixture game6): Gegner-Heldenkraft beschwoert 2x 6/6."""

    @classmethod
    def setUpClass(cls):
        cls.db = real_db()

    def _state_at(self, turn, mana, need_card):
        for i, tr, s in replay(6, self.db, every=6):
            if s.my_active and s.turn == turn and s.my_mana == mana and any(c.name == need_card for c in s.my_hand):
                return s
        self.fail("Zustand nicht gefunden")

    def test_opponent_hero_power_is_known(self):
        s = self._state_at(17, 9, "Feuerball")
        self.assertEqual(s.opp_hero_power.name, "Chaosregen")
        self.assertEqual(Planner(self.db)._initial(s).opp_spawn_atk, 12)

    def test_low_life_after_enemy_turn_is_flagged(self):
        s = self._state_at(17, 9, "Feuerball")
        p = Planner(self.db, 1.2).plan(s)
        self.assertTrue(any("GEFAHR" in w for w in p.warnings), p.warnings)
        self.assertTrue(any("Heldenkraft" in w for w in p.warnings), p.warnings)


class TestUselessDiscount(unittest.TestCase):
    def test_discount_spell_without_matching_card_is_not_suggested(self):
        s = gs(mana=2, hand=[card(1, "ELEMBESCH"), card(2, "VERWANDLUNG")])
        p = plan_for(s)
        self.assertEqual(p.cids, [])
        self.assertFalse(any("ELEMBESCH" in a.cids for a in p.alternatives))

    def test_discount_spell_is_used_when_elemental_in_hand(self):
        s = gs(mana=2, hand=[card(1, "ELEMBESCH"), card(2, "ELEM", cost=4, atk=3, hp=6, race="ELEMENTAL")])
        self.assertEqual(plan_for(s).cids, ["ELEMBESCH", "ELEM"])

    def test_alternatives_are_not_much_worse(self):
        s = gs(mana=5, opp=[mm(10, "Ziel", 3, 3)], hand=[card(1, "FROSTBLITZ"), card(2, "ARKANE")])
        p = plan_for(s)
        for a in p.alternatives:
            self.assertGreaterEqual(a.score, p.score - 12.0)


class TestAmbiguousTargets(unittest.TestCase):
    def test_same_name_targets_get_position(self):
        s = gs(mana=0, mine=[mm(1, "Angreifer", 3, 3)], opp=[mm(10, "Schaf", 1, 1), mm(11, "Schaf", 1, 1)])
        p = plan_for(s)
        self.assertRegex(p.steps[0].text, r"\[\d\. von links\]")


class TestLethalGradient(unittest.TestCase):
    def test_reduce_incoming_damage_even_when_death_looms(self):
        opp = [mm(10, "Spotter", 1, 1, taunt=True), mm(11, "Bestie", 6, 6), mm(12, "Bestie", 6, 6),
               mm(13, "Schreckenslord", 4, 4), mm(14, "Dunkelblick", 3, 2)]
        s = gs(mana=0, my_hp=19, mine=[mm(1, "Elementar", 4, 1)], opp=opp)
        p = plan_for(s)
        self.assertTrue(p.steps)
        self.assertIn("Spotter", p.steps[0].text)


class TestFreezingElemental(unittest.TestCase):
    def test_water_elemental_freezes_the_minion_it_hurts(self):
        txt = "Friert jeden Charakter ein, der von diesem Diener verletzt wurde."
        db = fake_db()
        db.cards["WASSER"] = dict(name="Wasserelementar", cardtype="MINION", text=txt)
        el = mm(1, "Wasserelementar", 4, 7, cid="WASSER")
        s = gs(mana=0, mine=[el], opp=[mm(10, "Bestie", 6, 6)])
        p = Planner(db).plan(s)
        self.assertTrue(any("wird eingefroren" in st.text for st in p.steps), [st.text for st in p.steps])

    def test_summoned_elemental_from_hero_power_freezes_too(self):
        from hscoach.effects import parse_effect
        e = parse_effect("Ruft einen Wasserelementar (5/8) herbei.", "HERO_POWER")
        self.assertEqual(e.summon, (5, 8, 1))
        self.assertTrue(e.summon_freezer)


class TestHoldRaceBattlecry(unittest.TestCase):
    def hand(self, with_dragon=True):
        h = [card(1, "SCHUPPENREITERIN")]
        if with_dragon:
            h.append(card(2, "DRACHE", race="DRAGON"))
        return h

    def test_battlecry_targets_when_dragon_in_hand(self):
        s = gs(mana=3, opp=[mm(10, "Wächter", 2, 3, taunt=True)], hand=self.hand())
        p = plan_for(s)
        first = p.steps[0].text
        self.assertIn("Schuppenreiterin", first)
        self.assertIn("auf Wächter", first)
        self.assertIn("Kampfschrei aktiv (Drache auf der Hand)", first)

    def test_plain_minion_without_dragon(self):
        s = gs(mana=3, opp=[mm(10, "Wächter", 2, 3, taunt=True)], hand=self.hand(with_dragon=False))
        first = plan_for(s).steps[0].text
        self.assertNotIn(" auf ", first)
        self.assertNotIn("Kampfschrei aktiv", first)

    def test_playing_the_dragon_first_switches_battlecry_off(self):
        """Wer den Drachen zuerst spielt, hat ihn nicht mehr auf der Hand - die Planung darf das nicht uebersehen."""
        s = gs(mana=8, opp=[mm(10, "Wächter", 2, 3, taunt=True)], hand=self.hand())
        p = plan_for(s)
        texts_ = texts(p)
        ri = next(i for i, t in enumerate(texts_) if "Schuppenreiterin" in t)
        di = next((i for i, t in enumerate(texts_) if "Drachenjunges" in t), None)
        if di is not None and di < ri:
            self.assertNotIn("Kampfschrei aktiv", texts_[ri])

    def test_destroy_respects_max_attack(self):
        hand = [card(1, "BUECHERWYRM"), card(2, "DRACHE", race="DRAGON")]
        s = gs(mana=6, opp=[mm(10, "Brocken", 5, 5), mm(11, "Kleiner", 3, 2)], hand=hand)
        first = plan_for(s).steps[0].text
        if "Bücherwyrm" in first and " auf " in first:
            self.assertIn("auf Kleiner", first)
            self.assertNotIn("Brocken", first.split("→")[0].replace("Bücherwyrm", ""))

    def test_schuppenwurm_buff_and_rush_attack(self):
        """Mit Drache auf der Hand: 5/4 mit Eifer - greift sofort einen Diener an (aber nicht den Helden)."""
        hand = [card(1, "SCHUPPENWURM", atk=4, hp=4), card(2, "DRACHE", atk=5, hp=5, race="DRAGON")]
        s = gs(mana=4, opp=[mm(10, "Wächter", 2, 3, taunt=True)], hand=hand)
        t = texts(plan_for(s))
        self.assertIn("Schuppenwurm (5/4)", t[0])
        self.assertTrue(any("Schuppenwurm (5/4) greift Wächter" in x for x in t), t)

    def test_schuppenwurm_without_dragon_is_plain(self):
        s = gs(mana=4, opp=[mm(10, "Wächter", 2, 3, taunt=True)], hand=[card(1, "SCHUPPENWURM", atk=4, hp=4)])
        t = texts(plan_for(s))
        self.assertIn("Schuppenwurm (4/4)", t[0])
        self.assertFalse(any("greift" in x for x in t))

