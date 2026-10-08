import unittest

from hscoach.effects import clean_text, parse_effect

from tests.helpers import CARDS


def fx(key):
    c = CARDS[key]
    return parse_effect(c["text"], c["cardtype"], secret=bool(c.get("secret")))


class TestCleanText(unittest.TestCase):
    def test_placeholders(self):
        self.assertEqual(clean_text("Fügt einem Charakter $3_Schaden zu und ___friert ihn ein."),
                         "Fügt einem Charakter 3 Schaden zu und friert ihn ein.")

    def test_plural_markup(self):
        self.assertEqual(clean_text("Zieht $1 |4(Karte,Karten) (wird verbessert)."), "Zieht 1 Karte (wird verbessert).")
        self.assertEqual(clean_text("Zieht $2 |4(Karte,Karten)."), "Zieht 2 Karten.")

    def test_tags_and_x(self):
        self.assertEqual(clean_text("[x]<b>Spott</b> und mehr"), "Spott und mehr")


class TestParse(unittest.TestCase):
    def test_frostblitz(self):
        e = fx("FROSTBLITZ")
        self.assertEqual((e.dmg, e.dmg_target, e.freeze, e.target_kind), (3, "any", "target", "any"))

    def test_froststrahl_minion_only(self):
        e = fx("FROSTSTRAHL")
        self.assertEqual(e.target_kind, "minion")
        self.assertEqual((e.freeze, e.cond_frozen_dmg, e.dmg), ("target", 2, 0))

    def test_zertruemmern(self):
        e = fx("ZERTRUEMMERN")
        self.assertTrue(e.needs_frozen)
        self.assertEqual((e.destroy, e.target_kind), ("target", "enemy_minion"))

    def test_feuerball_any(self):
        e = fx("FEUERBALL")
        self.assertEqual((e.dmg, e.target_kind), (6, "any"))

    def test_blizzard_aoe(self):
        e = fx("BLIZZARD")
        self.assertEqual((e.aoe_dmg, e.aoe_scope, e.freeze, e.target_kind), (2, "enemy_minions", "aoe", ""))

    def test_flammenstoss_scope_not_chars(self):
        self.assertEqual(fx("FLAMMENSTOSS").aoe_scope, "enemy_minions")

    def test_gletscher_discount(self):
        e = fx("GLETSCHER")
        self.assertEqual((e.dmg, e.discount), (4, ("spell", 2)))

    def test_elementar_discount(self):
        self.assertEqual(fx("ELEMBESCH").discount, ("ELEMENTAL", 2))

    def test_draw_and_coin(self):
        self.assertEqual(fx("ARKANE").draw, 2)
        self.assertEqual(fx("MUENZE").temp_mana, 1)

    def test_transform(self):
        self.assertEqual(fx("VERWANDLUNG").transform, (1, 1))

    def test_secret(self):
        e = fx("EISBLOCK")
        self.assertTrue(e.secret)
        self.assertFalse(e.unknown)

    def test_heulende_boe(self):
        e = parse_effect("Fügt einem Feind $3_Schaden zu und friert ihn ein. Fügt allen anderen Feinden $1 Schaden zu.", "SPELL")
        self.assertEqual((e.dmg, e.dmg_target, e.aoe_dmg, e.aoe_scope), (3, "enemy", 1, "enemy_chars"))

    def test_battlecry_only_for_minions(self):
        e = parse_effect("Kampfschrei: Fügt einem Charakter 2 Schaden zu.", "MINION")
        self.assertEqual((e.dmg, e.target_kind), (2, "any"))
        plain = parse_effect("Spott. Verursacht 2 Schaden am Zugende.", "MINION")
        self.assertEqual(plain.dmg, 0)

    def test_unknown_spell(self):
        self.assertTrue(parse_effect("Tut etwas Unerklärliches.", "SPELL").unknown)

    def test_conditional_not_simulated(self):
        e = parse_effect("Wenn Ihr einen Elementar gespielt habt, verursacht dies 5 Schaden.", "SPELL")
        self.assertEqual(e.dmg, 0)
        self.assertTrue(e.unknown)


class TestHoldRaceCondition(unittest.TestCase):
    def test_damage_battlecry_with_dragon_condition(self):
        e = parse_effect("Kampfschrei: Verursacht 2 Schaden, wenn Ihr einen Drachen auf der Hand habt.", "MINION")
        self.assertEqual(e.cond_hold, "DRAGON")
        self.assertEqual((e.cond_fx.dmg, e.cond_fx.target_kind), (2, "any"))
        self.assertEqual(e.dmg, 0)

    def test_destroy_with_max_attack(self):
        e = parse_effect("Kampfschrei: Vernichtet einen feindlichen Diener mit max. 3 Angriff, wenn Ihr einen Drachen auf der Hand habt.", "MINION")
        self.assertEqual((e.cond_hold, e.cond_fx.destroy, e.cond_fx.max_atk), ("DRAGON", "target", 3))

    def test_self_buff_with_keyword(self):
        for word, kw in (("Eifer", "eifer"), ("Spott", "spott"), ("Ansturm", "ansturm")):
            e = parse_effect(f"Kampfschrei: Erhält +1 Angriff und {word}, wenn Ihr einen Drachen auf der Hand habt.", "MINION")
            self.assertEqual((e.cond_hold, e.cond_fx.self_buff), ("DRAGON", (1, 0, kw)))

    def test_risky_variants_stay_ignored(self):
        for t in ("Kampfschrei: Fügt allen anderen Charakteren 3 Schaden zu, wenn Ihr einen Drachen auf der Hand habt.",
                  "Kampfschrei: Vernichtet einen zufälligen feindlichen Diener, wenn Ihr einen Drachen auf der Hand habt.",
                  "Kampfschrei: Vernichtet einen verletzten feindlichen Diener, wenn Ihr einen Drachen auf der Hand habt.",
                  "Spott. Kampfschrei: Erhält +1/+2, wenn Ihr einen Dämon auf der Hand habt, der mind. (5) kostet."):
            e = parse_effect(t, "MINION")
            self.assertEqual(e.cond_hold, "", t)
            self.assertEqual((e.dmg, e.destroy), (0, ""), t)


if __name__ == "__main__":
    unittest.main()


class TestSecretPayload(unittest.TestCase):
    def test_flammenfalle_payload(self):
        e = parse_effect("Geheimnis: Fügt allen feindlichen Dienern $3 Schaden zu, nachdem ein Diener Euren Helden angegriffen hat.", "SPELL")
        self.assertTrue(e.secret)
        self.assertEqual((e.payload.aoe_dmg, e.payload.aoe_scope), (3, "enemy_minions"))
        self.assertEqual(e.dmg, 0)          # nicht sofort wirksam

    def test_eisblock_has_no_payload(self):
        self.assertIsNone(fx("EISBLOCK").payload)
