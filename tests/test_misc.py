import os
import re
import subprocess
import unittest

from hscoach import config, tips
from hscoach.planner import Planner
from hscoach.state import GameState

from tests.helpers import HERE, card, fake_db, gs, mm


class Usage:
    def __init__(self, i, o, cr=0, cw=0):
        self.input_tokens, self.output_tokens = i, o
        self.cache_read_input_tokens, self.cache_creation_input_tokens = cr, cw


class TestConfig(unittest.TestCase):
    def test_price_lookup(self):
        self.assertEqual(config.price_for("claude-haiku-5-5"), (0.10, 0.50))
        self.assertEqual(config.price_for("claude-sonnet-5-5"), (2.00, 10.00))
        self.assertEqual(config.price_for("claude-haiku-4-5-20251001"), (1.00, 5.00))
        self.assertEqual(config.price_for("unbekannt"), (3.00, 15.00))

    def test_cost(self):
        c = config.cost_usd("claude-haiku-5-5", Usage(1_000_000, 1_000_000))
        self.assertAlmostEqual(c, 0.60, places=6)
        c2 = config.cost_usd("claude-sonnet-5-5", Usage(0, 0, cr=1_000_000))
        self.assertAlmostEqual(c2, 0.20, places=6)


class TestMinion(unittest.TestCase):
    def test_can_attack_rules(self):
        self.assertTrue(mm(1, "A", 2, 2).can_attack)
        self.assertFalse(mm(1, "A", 0, 2).can_attack)
        self.assertFalse(mm(1, "A", 2, 2, exhausted=True).can_attack)
        self.assertFalse(mm(1, "A", 2, 2, frozen=True).can_attack)
        self.assertFalse(mm(1, "A", 2, 2, attacks_done=1).can_attack)
        self.assertTrue(mm(1, "A", 2, 2, windfury=2, attacks_done=1).can_attack)

    def test_rush_vs_charge_face(self):
        self.assertFalse(mm(1, "A", 2, 2, rush=True, turns_in_play=0).can_attack_face)
        self.assertTrue(mm(1, "A", 2, 2, rush=True, turns_in_play=1).can_attack_face)
        self.assertTrue(mm(1, "A", 2, 2, rush=True, charge=True, turns_in_play=0).can_attack_face)

    def test_flags_include_frozen(self):
        self.assertIn("EINGEFROREN", mm(1, "A", 2, 2, frozen=True).flags)


class TestTips(unittest.TestCase):
    def test_render_empty_plan(self):
        s = gs(mana=2)
        txt = tips.render_plan(s, Planner(fake_db()).plan(s))
        self.assertIn("Zug beenden", txt)

    def test_turn_done_after_spending_mana(self):
        s = gs(mana=1, hand=[card(1, "ELEM", cost=5, atk=5, hp=5)], my_mana_used=3)
        txt = tips.render_plan(s, Planner(fake_db()).plan(s))
        self.assertIn("Zug fertig", txt)
        self.assertIn("Bleibt auf der Hand: Wasserelementar (5)", txt)
        self.assertNotIn("Keine sinnvolle Aktion", txt)

    def test_render_numbered_and_warning(self):
        s = gs(mana=2, my_hp=3, opp=[mm(10, "Brecher", 5, 5)], hand=[card(1, "FROSTBLITZ")])
        txt = tips.render_plan(s, Planner(fake_db()).plan(s))
        self.assertTrue(txt.startswith("1. "))

    def test_game_over_text(self):
        s = GameState(result="WON")
        self.assertIn("gewonnen", tips.render_plan(s, None))

    def test_mulligan_second_player(self):
        db = fake_db()
        hand = [card(1, "FROSTSTRAHL"), card(2, "ELEM", cost=5, atk=5, hp=5), card(3, "FEUERBALL"), card(4, "WEAPON")]
        s = gs(hand=hand)
        txt = tips.mulligan_advice(s, db)
        self.assertIn("ZWEITER", txt)
        self.assertIn("TAUSCHEN", txt)
        self.assertRegex(txt, r"BEHALTEN\s+\[1")

    def test_mulligan_keeps_one_four_drop_when_everything_is_expensive(self):
        db = fake_db()
        hand = [card(1, "ELEM", cost=4, atk=4, hp=5), card(2, "ELEM", cost=5, atk=5, hp=5), card(3, "ELEM", cost=6, atk=6, hp=6),
                card(4, "ELEM", cost=7, atk=7, hp=7)]
        txt = tips.mulligan_advice(gs(hand=hand), db)
        self.assertEqual(txt.count("BEHALTEN"), 1)
        self.assertRegex(txt, r"BEHALTEN\s+\[4")

    def test_mulligan_first_player_keeps_three_drops(self):
        db = fake_db()
        hand = [card(1, "ELEM", cost=3, atk=3, hp=4), card(2, "ELEM", cost=5, atk=5, hp=5), card(3, "ELEM", cost=6, atk=6, hp=6)]
        txt = tips.mulligan_advice(gs(hand=hand), db)
        self.assertIn("ERSTER", txt)
        self.assertRegex(txt, r"BEHALTEN\s+\[3")


class TestNoSecrets(unittest.TestCase):
    PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")

    def test_no_api_key_in_repo(self):
        root = os.path.dirname(HERE)
        try:
            files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
        except Exception:
            files = []
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
                files += [os.path.relpath(os.path.join(dp, f), root) for f in fn]
        self.assertNotIn("hs_coach_key.txt", [os.path.basename(f) for f in files])
        for f in files:
            p = os.path.join(root, f)
            if not f or not os.path.isfile(p) or f.endswith((".gz", ".png", ".pyc")):
                continue
            with open(p, encoding="utf-8", errors="ignore") as fh:
                self.assertIsNone(self.PATTERN.search(fh.read()), f"API-Key-Muster in {f}")


if __name__ == "__main__":
    unittest.main()


class TestExtract(unittest.TestCase):
    def test_extract_from_fake_dll(self):
        import struct
        import tempfile
        from hscoach import extract
        xml = b'<?xml version="1.0" encoding="utf-8"?>\n<CardDefs build="1">\n' + b"<Entity CardID='A'/>\n" * 60000 + b"</CardDefs>"
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "app-9.9.9")
            os.makedirs(sub)
            dll = os.path.join(sub, "HearthDb.dll")
            with open(dll, "wb") as f:
                f.write(b"MZ" + b"\0" * 100 + struct.pack("<I", len(xml)) + xml + b"\0" * 50)
            out = os.path.join(d, "out", "CardDefs.base.xml")
            self.assertEqual(extract.find_dll(os.path.join(d, "app-*", "HearthDb.dll")), dll)
            self.assertTrue(extract.extract_base_xml(dll, out))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), xml)
            cfg = {"carddefs_base": out}
            self.assertFalse(extract.ensure_base_xml(cfg, os.path.join(d, "app-*", "HearthDb.dll")))   # aktuell
            os.utime(dll, (os.path.getmtime(out) + 100,) * 2)
            self.assertTrue(extract.ensure_base_xml(cfg, os.path.join(d, "app-*", "HearthDb.dll")))    # DLL neuer
