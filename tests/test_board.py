import unittest

from hscoach import board
from hscoach.planner import Plan, Step

from tests.helpers import card, gs, mm


class TestModel(unittest.TestCase):
    def test_tiles_flags_and_ready(self):
        s = gs(mine=[mm(1, "Wache", 3, 4, taunt=True, divine_shield=True), mm(2, "Müder", 2, 2, exhausted=True)],
               opp=[mm(10, "Wolf", 2, 3, frozen=True)])
        m = board.build_model(s)
        a, b = m.my_tiles
        self.assertTrue(a.ready and a.taunt and a.ds)
        self.assertIn("Spott", a.badges)
        self.assertFalse(b.ready)
        self.assertTrue(m.opp_tiles[0].frozen)
        self.assertNotIn("Frost", m.opp_tiles[0].badges)          # Frost wird als Eisschicht gezeichnet, nicht als Chip

    def test_hurt_minion_keeps_max_hp(self):
        s = gs(mine=[mm(1, "Alt", 3, 2, max_hp=6)])
        t = board.build_model(s).my_tiles[0]
        self.assertEqual((t.hp, t.max_hp), (2, 6))

    def test_plan_creates_arrows_and_marks(self):
        s = gs(mine=[mm(1, "A", 3, 3), mm(2, "B", 2, 2)], opp=[mm(10, "Wolf", 2, 3)])
        plan = Plan(steps=[Step("attack", "A greift Wolf", src=1, dst=("m", 10)),
                           Step("attack", "B greift Gesicht", src=2, dst=("face",)),
                           Step("hero_attack", "Held greift Wolf", src=0, dst=("m", 10)),
                           Step("spell", "Zauber auf Wolf", dst=("m", 10))])
        m = board.build_model(s, plan)
        self.assertEqual([(a.n, a.src, a.dst) for a in m.arrows], [(1, 1, 10), (2, 2, "face"), (3, "hero", 10)])
        self.assertEqual(m.my_tiles[0].marks, ((1, "att"),))
        self.assertEqual(m.opp_tiles[0].marks, ((1, "tgt"), (3, "tgt"), (4, "tgt")))
        self.assertEqual(m.opp.marks, (2,))

    def test_steps_for_unknown_minions_are_ignored(self):
        s = gs(mine=[mm(1, "A", 3, 3)], opp=[mm(10, "Wolf", 2, 3)])
        plan = Plan(steps=[Step("attack", "?", src=99, dst=("m", 10)), Step("attack", "?", src=1, dst=("m", 77))])
        self.assertEqual(board.build_model(s, plan).arrows, ())

    def test_heroes_and_goal(self):
        s = gs(my_hp=14, opp_hp=30)
        s.my_armor, s.opp_hand_count, s.opp_deck_count = 3, 4, 20
        m = board.build_model(s, None, "Ziel: ≤ 10 Leben")
        self.assertEqual((m.me.hp, m.me.armor), (14, 3))
        self.assertEqual((m.opp.hand, m.opp.deck, m.opp.goal), (4, 20, "Ziel: ≤ 10 Leben"))

    def test_model_equality_allows_redraw_skip(self):
        s = gs(mine=[mm(1, "A", 3, 3)])
        self.assertEqual(board.build_model(s), board.build_model(s))


class TestLayout(unittest.TestCase):
    def test_tiles_stay_inside_the_canvas(self):
        for width in (900, 1200, 1700):
            for n in (0, 1, 5, 7):
                lay = board.layout(n, n, width, 380)
                for (x, y) in lay["opp"] + lay["me"]:
                    self.assertGreaterEqual(x, board.LEFT)
                    self.assertLessEqual(x + lay["tw"], width - 8, (width, n))
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(y + lay["th"], 380)

    def test_rows_do_not_overlap(self):
        lay = board.layout(7, 7, 1000, 380)
        self.assertLess(lay["opp"][0][1] + lay["th"], lay["me"][0][1])

    def test_seven_tiles_fit_in_a_narrow_window(self):
        lay = board.layout(7, 7, 960, 300)
        self.assertGreaterEqual(lay["tw"], 50)
        last = lay["me"][-1]
        self.assertLessEqual(last[0] + lay["tw"], 960 - 8)

    def test_compact_height_shrinks_tiles(self):
        big = board.layout(5, 5, 1400, 380)
        small = board.layout(5, 5, 1400, 300)
        self.assertLess(small["th"], big["th"])
        self.assertLessEqual(small["me"][0][1] + small["th"], 300)

    def test_height_for_window(self):
        self.assertEqual(board.height_for(2000), board.HEIGHT)
        self.assertEqual(board.height_for(900), 300)
        self.assertEqual(board.height_for(1100), 330)


class TestHand(unittest.TestCase):
    def test_cards_sorted_by_cost_and_playable(self):
        s = gs(mana=3, hand=[card(1, "FEUERBALL"), card(2, "FROSTBLITZ"), card(3, "ARKANE")])
        h = board.build_hand(s)
        self.assertEqual([c.cost for c in h.cards], [2, 3, 4])
        self.assertEqual([c.playable for c in h.cards], [True, True, False])      # 4 Mana sind zu teuer
        self.assertEqual((h.mana, h.max_mana), (3, 3))

    def test_not_my_turn_nothing_playable(self):
        s = gs(mana=5, hand=[card(1, "FROSTBLITZ")])
        s.my_active = False
        self.assertFalse(board.build_hand(s).cards[0].playable)

    def test_plan_steps_mark_the_cards_in_order(self):
        s = gs(mana=9, hand=[card(1, "FROSTBLITZ"), card(2, "FROSTBLITZ"), card(3, "FEUERBALL")])
        plan = Plan(steps=[Step("spell", "a", cid="FEUERBALL"), Step("attack", "b", src=1, dst=("face",)),
                           Step("spell", "c", cid="FROSTBLITZ")])
        h = board.build_hand(s, plan)
        by_cid = {}
        for c in h.cards:
            by_cid.setdefault(c.cid, []).append(c.marks)
        self.assertEqual(by_cid["FEUERBALL"], [(1,)])
        self.assertEqual(by_cid["FROSTBLITZ"], [(3,), ()])        # nur eine der zwei Kopien wird gespielt

    def test_hand_layout_fits(self):
        for n in (0, 1, 5, 10):
            for width in (900, 1700):
                lay = board.hand_layout(n, width, 150)
                for (x, y) in lay["xs"]:
                    self.assertGreaterEqual(x, board.LEFT)
                    self.assertLessEqual(x + lay["cw"], width - 8)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(y + lay["ch"], 150)


class TestTooltips(unittest.TestCase):
    def test_tile_tip_explains_keywords(self):
        s = gs(opp=[mm(10, "Wache", 2, 3, taunt=True, divine_shield=True)])
        t = board.build_model(s, None, "", lambda cid: "Kampfschrei: Zieht eine Karte.").opp_tiles[0]
        title, body = board.tile_tip(t)
        self.assertIn("Wache", title)
        self.assertIn("2/3", title)
        self.assertIn("Spott:", body)
        self.assertIn("Gottesschild:", body)

    def test_hurt_minion_shows_max_hp(self):
        s = gs(mine=[mm(1, "Alt", 3, 2, max_hp=6)])
        title, _ = board.tile_tip(board.build_model(s).my_tiles[0])
        self.assertIn("max. 6", title)

    def test_card_tip_with_text_and_plan_step(self):
        c = board.HCard("X", "Frostblitz", 2, 0, 0, "SPELL", "Fügt einem Charakter 3 Schaden zu und friert ihn ein.", marks=(2,))
        title, body = board.card_tip(c)
        self.assertIn("[2 Mana]", title)
        self.assertIn("Zauber", title)
        self.assertIn("Im Plan: Schritt 2", body)
        self.assertNotIn("Einfrieren", body)               # reine Wortformen wie 'einfrieren' werden nicht doppelt erklaert

    def test_hero_tip(self):
        s = gs(my_hp=14)
        s.my_armor = 3
        title, body = board.hero_tip(board.build_model(s).me)
        self.assertIn("14 Leben", title)
        self.assertIn("3 Rüstung", title)
        self.assertIn("Handkarten", body)

    def test_gloss_lines_limit_and_unknown(self):
        self.assertEqual(board.gloss_lines("nichts Besonderes"), [])
        self.assertLessEqual(len(board.gloss_lines("Spott Gottesschild Windzorn Gift Lebensraub Tarnung Kampfschrei")), 4)


if __name__ == "__main__":
    unittest.main()
