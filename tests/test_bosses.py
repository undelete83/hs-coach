import unittest

from hscoach import bosses
from hscoach.bosses import Boss
from hscoach.bosses_data import BOSSES
from hscoach.planner import Planner

from tests.helpers import card, fake_db, fixture_lines, gs, mm, new_tracker, real_db
from hscoach.state import build_state


class TestBossData(unittest.TestCase):
    def test_required_fields_and_unique_ids(self):
        ids, cids = set(), set()
        for d in BOSSES:
            for k in ("id", "match", "name", "chapter", "goal", "tips", "source"):
                self.assertIn(k, d, d.get("id"))
            self.assertTrue(d["match"] and d["tips"], d["id"])
            self.assertNotIn(d["id"], ids)
            ids.add(d["id"])
            for c in d["match"]:
                self.assertNotIn(c, cids, c)
                cids.add(c)

    def test_lookup(self):
        b = bosses.find("Story_01_Archimonde")
        self.assertEqual((b.name, b.win_hp, b.win_verified, b.start_hp), ("Archimonde", 10, True, 40))
        self.assertIsNone(bosses.find("Story_99_Nobody"))
        self.assertIsNone(bosses.find(""))

    def test_lines_and_prompt(self):
        b = bosses.find("Story_01_Archimonde")
        text = "\n".join(b.lines())
        self.assertIn("≤ 10", text)
        self.assertIn("Chaosregen", text)
        self.assertIn("10 Leben", b.prompt())

    @unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
    def test_cards_exist_and_hp_matches_card_db(self):
        db = real_db()
        for d in BOSSES:
            for c in d["match"]:
                info = db.info(c)
                self.assertEqual(info.get("cardtype"), "HERO", f"{c} ist keine Hero-Karte")
                if len(d["match"]) == 1 and d.get("start_hp"):
                    self.assertEqual(info.get("health"), d["start_hp"], f"{d['id']}: Start-Leben stimmt nicht")


@unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
class TestBossesInRecordedGames(unittest.TestCase):
    def test_fixture_opponents_are_recognized(self):
        db = real_db()
        expected = {0: "Prinz Kael'thas", 1: "Prinz Kael'thas", 2: "Prinz Arthas", 3: "Grommash Höllschrei",
                    4: "Archimonde", 5: "Archimonde", 6: "Archimonde"}
        for g, name in expected.items():
            tr = new_tracker()
            tr.feed_lines(fixture_lines(g))
            s = build_state(tr, db)
            b = bosses.find(s.opp_hero_cid)
            self.assertIsNotNone(b, f"Spiel {g}: {s.opp_hero_cid}")
            self.assertEqual(b.name, name)


def custom_boss(**kw):
    d = dict(id="t", match=["x"], name="Testboss", chapter="Test", goal="g", tips=["t"], source="s", bias={})
    d.update(kw)
    return Boss(d)


class TestBossBiasInPlanner(unittest.TestCase):
    def test_win_threshold_counts_as_lethal(self):
        s = gs(mana=0, opp_hp=14, mine=[mm(1, "Angreifer", 4, 4)])
        self.assertFalse(Planner(fake_db()).plan(s).lethal)
        p = Planner(fake_db()).plan(s, custom_boss(win_hp=10))
        self.assertTrue(p.lethal)
        self.assertIn("SIEGSCHWELLE", p.summary)

    def test_reserve_keeps_removal_for_named_target(self):
        s = gs(mana=4, opp=[mm(10, "Gewöhnlicher Diener", 6, 6)], hand=[card(1, "VERWANDLUNG")])
        self.assertEqual(Planner(fake_db()).plan(s).cids, ["VERWANDLUNG"])
        boss = custom_boss(bias=dict(reserve={"Verwandlung": ("Belagerungsbrecher", 80.0)}))
        self.assertEqual(Planner(fake_db()).plan(s, boss).cids, [])

    def test_reserve_allows_the_named_target(self):
        s = gs(mana=4, opp=[mm(10, "Belagerungsbrecher", 5, 8, taunt=True)], hand=[card(1, "VERWANDLUNG")])
        boss = custom_boss(bias=dict(reserve={"Verwandlung": ("Belagerungsbrecher", 80.0)}))
        self.assertEqual(Planner(fake_db()).plan(s, boss).cids, ["VERWANDLUNG"])

    def test_priority_target_is_removed_first(self):
        s = gs(mana=4, opp=[mm(10, "Harmlos", 3, 3), mm(11, "Wichtig", 3, 3)], hand=[card(1, "FEUERBALL")])
        boss = custom_boss(bias=dict(priority={"Wichtig": 3.0}))
        p = Planner(fake_db()).plan(s, boss)
        self.assertIn("Wichtig", p.steps[0].text)

    def test_survive_boss_discourages_face_race(self):
        # Defensiv: Gesichtsschaden zaehlt wenig, Sicherheit viel
        boss = custom_boss(survive=13)
        s = gs(mana=0, my_hp=12, opp_hp=30, mine=[mm(1, "Angreifer", 5, 5)], opp=[mm(10, "Gegner", 5, 5)])
        p = Planner(fake_db()).plan(s, boss)
        self.assertTrue(p.steps)           # sinnvoller Zug bleibt moeglich, kein Absturz


if __name__ == "__main__":
    unittest.main()


class TestOnlyBossFights(unittest.TestCase):
    def test_regular_heroes_are_not_bosses(self):
        for cid in ("HERO_01", "HERO_08b", "HERO_05bp", "TB_Hero", "Story_01_Jaina", "Story_01_JainaMid", "Story_03_Garrosh", ""):
            self.assertIsNone(bosses.find(cid), cid)

    @unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
    def test_gui_shows_boss_panel_only_for_bosses(self):
        import json
        import os
        import tempfile
        import tkinter

        from hscoach import config

        def run(replace):
            with tempfile.TemporaryDirectory() as d:
                sub = os.path.join(d, "Hearthstone_2026_01_01_00_00_00")
                os.makedirs(sub)
                text = "\n".join(fixture_lines(4)).replace("Story_01_Archimonde", replace)
                # mitten im Spiel enden (Spielende blendet die Boss-Info ohnehin aus)
                lines = text.split("\n")[:3000]
                with open(os.path.join(sub, "Power.log"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(lines) + "\n")
                cfgp = os.path.join(d, "cfg.json")
                with open(cfgp, "w") as f:
                    json.dump({"log_dir": d.replace("\\", "/"), "refresh_ms": 200, "geometry": "1200x900"}, f)
                os.environ["HS_COACH_CONFIG"] = cfgp
                import importlib
                importlib.reload(config)
                from hscoach import gui
                importlib.reload(gui)
                try:
                    app = gui.App()
                except tkinter.TclError:
                    self.skipTest("kein Display")
                out = {}

                def check():
                    out["boss"] = app.boss.name if app.boss else None
                    out["mapped"] = bool(app.boss_frame.winfo_ismapped())
                    app.backend.stop()
                    app.destroy()
                app.after(3500, check)
                app.mainloop()
                del app
                import gc
                gc.collect()
                return out

        try:
            boss_game = run("Story_01_Archimonde")
            normal_game = run("HERO_08")
        finally:
            os.environ.pop("HS_COACH_CONFIG", None)
            import importlib
            importlib.reload(config)
        self.assertEqual(boss_game["boss"], "Archimonde")
        self.assertTrue(boss_game["mapped"])
        self.assertIsNone(normal_game["boss"])
        self.assertFalse(normal_game["mapped"])


@unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
class TestWonBossGame(unittest.TestCase):
    def test_won_game_is_a_won_archimonde_fight(self):
        db = real_db()
        tr = new_tracker()
        tr.feed_lines(fixture_lines(7))
        s = build_state(tr, db)
        self.assertEqual(s.result, "WON")
        self.assertEqual(bosses.find(s.opp_hero_cid).name, "Archimonde")
        self.assertEqual(s.turn, 13)
