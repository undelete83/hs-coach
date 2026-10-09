"""Unbekannte gegnerische Geheimnisse: erster Zauber als Koeder, Warnungen, Aethas-Boss."""
import unittest

from hscoach import bosses
from hscoach.planner import Plan, Planner, Step

from tests.helpers import card, fake_db, gs, mm


def plan_for(s, boss=None):
    return Planner(fake_db(), 1.0).plan(s, boss)


def spells(plan):
    return [st.text for st in plan.steps if st.kind == "spell"]


def board():
    return [mm(10 + i, f"Diener{i}", 3, 4) for i in range(3)]


class TestBait(unittest.TestCase):
    def hand(self):
        return [card(1, "FLAMMENSTOSS"), card(2, "FROSTBLITZ")]

    def test_cheap_spell_goes_first_when_opponent_has_a_secret(self):
        s = gs(mana=9, opp=board(), hand=self.hand(), opp_secret_count=1)
        sp = spells(plan_for(s))
        self.assertEqual(len(sp), 2, sp)
        self.assertIn("Frostblitz", sp[0])
        self.assertIn("Flammenstoß", sp[1])

    def test_without_secret_both_spells_are_still_played(self):
        s = gs(mana=9, opp=board(), hand=self.hand(), opp_secret_count=0)
        self.assertEqual(len(spells(plan_for(s))), 2)

    def test_lethal_is_not_held_back_by_secret_risk(self):
        s = gs(mana=7, opp_hp=5, hand=[card(1, "FEUERBALL")], opp_secret_count=2)
        self.assertTrue(plan_for(s).lethal)

    def test_aethas_assumes_higher_counterspell_risk(self):
        b = bosses.find("Story_01_Aethas")
        self.assertIsNotNone(b)
        self.assertEqual(b.bias.get("secret_p"), 0.5)
        self.assertTrue(any("Köder" in t for t in b.tips))


class TestWarnings(unittest.TestCase):
    def test_expensive_first_spell_with_secret_gets_warning(self):
        s = gs(mana=7, opp=board(), hand=[card(1, "FLAMMENSTOSS")], opp_secret_count=1)
        w = " ".join(plan_for(s).warnings)
        self.assertIn("Gegenzauber", w)
        self.assertIn("Flammenstoß", w)

    def test_no_warning_without_secret(self):
        s = gs(mana=7, opp=board(), hand=[card(1, "FLAMMENSTOSS")], opp_secret_count=0)
        self.assertNotIn("Gegenzauber", " ".join(plan_for(s).warnings))

    def test_cheap_bait_is_named_in_the_hint(self):
        pl = Planner(fake_db(), 1.0)
        s = gs(mana=9, opp=board(), hand=[card(1, "FLAMMENSTOSS"), card(2, "FROSTBLITZ")], opp_secret_count=1)
        cards = pl._cards(s)
        flam = next(c for c in cards if c.cid == "FLAMMENSTOSS")
        plan = Plan(steps=[Step("spell", "Spiele Flammenstoß", cid=flam.cid)], mana_used=7)
        w = " ".join(pl._extra_warnings(s, plan, cards))
        self.assertIn("Frostblitz", w)

    def test_unused_mana_warning_lists_playable_cards(self):
        pl = Planner(fake_db(), 1.0)
        s = gs(mana=8, hand=[card(1, "FEUERBALL"), card(2, "FROSTBLITZ")])
        cards = pl._cards(s)
        w = " ".join(pl._extra_warnings(s, Plan(steps=[], mana_used=0), cards))
        self.assertIn("Nur 0 von 8 Mana", w)
        self.assertIn("Feuerball", w)

    def test_enough_mana_used_no_warning(self):
        pl = Planner(fake_db(), 1.0)
        s = gs(mana=8, hand=[card(1, "FEUERBALL")])
        cards = pl._cards(s)
        self.assertEqual(pl._extra_warnings(s, Plan(steps=[], mana_used=6), cards), [])


if __name__ == "__main__":
    unittest.main()


class TestSecretZoneCap(unittest.TestCase):
    """Auren und Geheimnisse teilen sich 5 Plaetze: bei voller Zone sind weitere nicht spielbar (REQ_SECRET_ZONE_CAP)."""

    def test_aura_not_played_when_zone_is_full(self):
        from tests.helpers import CARDS
        CARDS["AURA"] = dict(name="Chronologische Aura", cardtype="SPELL", cost=5,
                             text="Ruft am Ende Eures Zuges einen Drachen (3/5) mit Spott herbei. Hält 3 Züge lang an.")
        try:
            hand = [card(1, "AURA")]
            full = plan_for(gs(mana=8, hand=hand, my_secrets=["a", "b", "c", "d", "e"]))
            self.assertFalse(full.steps, [st.text for st in full.steps])
            self.assertTrue(any("nicht spielbar" in w for w in full.warnings), full.warnings)
            free = plan_for(gs(mana=8, hand=hand, my_secrets=["a"]))
            self.assertEqual(len(free.steps), 1)
        finally:
            del CARDS["AURA"]

    def test_same_secret_cannot_be_played_twice(self):
        s = gs(mana=8, hand=[card(1, "EISBLOCK")], my_secrets=["Eisblock"])
        self.assertFalse(plan_for(s).steps)
