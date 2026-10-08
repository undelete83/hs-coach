import gzip
import inspect
import os
import subprocess
import tempfile
import unittest

from hscoach import config, detect
from hscoach.logparser import Tracker
from hscoach.state import build_state

from tests.helpers import HERE, fake_db, fixture_lines

NOWHERE = os.path.join(tempfile.gettempdir(), "hs_coach_no_such_dir")


class TestAutoDetectMe(unittest.TestCase):
    def test_fixtures_without_configured_name(self):
        for g in range(8):
            tr = Tracker(NOWHERE, "")
            tr.feed_lines(fixture_lines(g))
            build_state(tr, fake_db())
            self.assertEqual(tr.my_pid, 1, f"Spiel {g}")
            self.assertFalse(tr.me_fixed)

    def test_pvp_second_player_found_by_revealed_hand(self):
        text = """D 1 GameState.DebugPrintPower() - CREATE_GAME
D 1 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=5]
D 1 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=1 lo=7]
D 1 GameState.DebugPrintGame() - PlayerID=1, PlayerName=Gegner#1
D 1 GameState.DebugPrintGame() - PlayerID=2, PlayerName=Ich#2
D 1 GameState.DebugPrintPower() - FULL_ENTITY - Creating ID=10 CardID=CS2_024
D 1 GameState.DebugPrintPower() -     tag=CONTROLLER value=2
D 1 GameState.DebugPrintPower() -     tag=ZONE value=HAND
D 1 GameState.DebugPrintPower() - FULL_ENTITY - Creating ID=11 CardID=CS2_029
D 1 GameState.DebugPrintPower() -     tag=CONTROLLER value=2
D 1 GameState.DebugPrintPower() -     tag=ZONE value=HAND
D 1 GameState.DebugPrintPower() - FULL_ENTITY - Creating ID=12 CardID=
D 1 GameState.DebugPrintPower() -     tag=CONTROLLER value=1
D 1 GameState.DebugPrintPower() -     tag=ZONE value=HAND
"""
        tr = Tracker(NOWHERE, "")
        tr.feed_lines(text.split("\n"))
        s = build_state(tr, fake_db())
        self.assertEqual(tr.my_pid, 2)
        self.assertEqual(len(s.my_hand), 2)
        self.assertEqual(s.opp_hand_count, 1)

    def test_unknown_configured_name_falls_back_to_autodetect(self):
        tr = Tracker(NOWHERE, "Gegner#1")
        tr.feed_lines(fixture_lines(0))
        build_state(tr, fake_db())
        self.assertEqual(tr.my_pid, 1)


class TestDetect(unittest.TestCase):
    def test_find_log_dir_from_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            logs = os.path.join(d, "Hearthstone", "Logs")
            os.makedirs(os.path.join(logs, "Hearthstone_2026_01_01_00_00_00"))
            self.assertEqual(detect.find_log_dir([os.path.join(d, "Hearthstone")]), logs)
            self.assertEqual(detect.find_log_dir([logs]), logs)

    def test_log_config_states(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.config")
            self.assertEqual(detect.check_log_config(p), "missing")
            with open(p, "w") as f:
                f.write("[Zone]\nLogLevel=1\n")
            self.assertEqual(detect.check_log_config(p), "no_power")
            with open(p, "w") as f:
                f.write("[Power]\nLogLevel=1\nFilePrinting=False\n")
            self.assertEqual(detect.check_log_config(p), "disabled")
            detect.write_log_config(p)
            self.assertEqual(detect.check_log_config(p), "ok")

    def test_write_keeps_other_sections_and_backs_up(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.config")
            with open(p, "w") as f:
                f.write("[Zone]\nLogLevel=1\nFilePrinting=True\n\n[Power]\nLogLevel=1\nFilePrinting=False\n")
            detect.write_log_config(p)
            with open(p) as f:
                text = f.read()
            self.assertIn("[Zone]", text)
            self.assertEqual(text.count("[Power]"), 1)
            self.assertTrue(os.path.exists(p + ".bak"))


class TestConfigDefaults(unittest.TestCase):
    def test_defaults_contain_no_personal_values(self):
        src = inspect.getsource(config)
        for bad in ("Her" + "ol", "undelete" + "#", "Gam" + "es"):
            self.assertNotIn(bad, src)
        self.assertEqual(config.DEFAULTS["player_name"], "")
        self.assertEqual(config.DEFAULTS["log_dir"], "")

    def test_api_key_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"key_path": os.path.join(d, "sub", "api_key.txt")}
            old = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                self.assertFalse(config.has_api_key(cfg))
                config.save_api_key(cfg, "  test-key-123  ")
                self.assertEqual(config.get_api_key(cfg), "test-key-123")
                config.delete_api_key(cfg)
                self.assertFalse(config.has_api_key(cfg))
                os.environ["ANTHROPIC_API_KEY"] = "env-key"
                self.assertEqual(config.get_api_key(cfg), "env-key")
            finally:
                os.environ.pop("ANTHROPIC_API_KEY", None)
                if old:
                    os.environ["ANTHROPIC_API_KEY"] = old


class TestSettingsApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._cfg_path, config.CONFIG_PATH = config.CONFIG_PATH, os.path.join(self.tmp.name, "config.json")
        self.addCleanup(setattr, config, "CONFIG_PATH", self._cfg_path)
        self.cfg = dict(config.DEFAULTS, key_path=os.path.join(self.tmp.name, "key.txt"))
        self._env = os.environ.pop("ANTHROPIC_API_KEY", None)
        self.addCleanup(lambda: self._env and os.environ.__setitem__("ANTHROPIC_API_KEY", self._env))

    def test_changes_are_reported_and_saved(self):
        from hscoach import settings
        changed = settings.apply(self.cfg, {"player_name": "  Name#123 ", "update_check": False, "unbekannt": 1})
        self.assertEqual(sorted(changed), ["player_name", "update_check"])
        self.assertEqual(self.cfg["player_name"], "Name#123")
        self.assertTrue(settings.needs_restart(changed))
        self.assertEqual(settings.apply(self.cfg, {"player_name": "Name#123"}), [])
        import json
        with open(config.CONFIG_PATH, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"player_name": "Name#123", "update_check": False})

    def test_empty_model_falls_back_to_default(self):
        from hscoach import settings
        settings.apply(self.cfg, {"claude_model": "x"})
        settings.apply(self.cfg, {"claude_model": ""})
        self.assertEqual(self.cfg["claude_model"], config.DEFAULTS["claude_model"])

    def test_api_key_saved_and_removed(self):
        from hscoach import settings
        self.assertEqual(settings.apply(self.cfg, {}, api_key="k-1"), ["api_key"])
        self.assertTrue(config.has_api_key(self.cfg))
        settings.apply(self.cfg, {}, api_key="")
        self.assertFalse(config.has_api_key(self.cfg))
        self.assertEqual(settings.apply(self.cfg, {}, api_key=None), [])


class TestNoPersonalDataInRepo(unittest.TestCase):
    def test_tracked_files_are_clean(self):
        root = os.path.dirname(HERE)
        try:
            files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
        except Exception:
            self.skipTest("kein git")
        # Teile getrennt, damit diese Datei sich nicht selbst findet
        bad = ("Users" + os.sep + "Her" + "ol", "undelete" + "#", "27" + "16", "zweites " + "Gehirn")
        for f in files:
            p = os.path.join(root, f)
            if not f or not os.path.isfile(p) or f.endswith((".png", ".pyc", ".exe", ".ico")):
                continue
            if f.endswith(".gz"):
                with gzip.open(p, "rt", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            else:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            for b in bad:
                self.assertNotIn(b, text, f"{f}: enthaelt '{b}'")


if __name__ == "__main__":
    unittest.main()
