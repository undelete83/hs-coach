import os
import tempfile
import unittest

from hscoach.logparser import Tracker
from hscoach.state import build_state

from tests.helpers import fake_db, fixture_lines, new_tracker, real_db


class TestTracker(unittest.TestCase):
    def test_player_detection_and_events(self):
        tr = new_tracker()
        tr.feed_lines(fixture_lines(5))
        self.assertEqual(tr.my_pid, 1)
        self.assertEqual(tr.pid_name[1], "Spieler#1234")
        self.assertEqual(tr.game_type, "GT_VS_AI")
        types = [e["type"] for e in tr.events]
        # nur GameState-Zeilen -> keine doppelten Ereignisse
        self.assertEqual((types.count("PLAY"), types.count("ATTACK")), (26, 7))

    def test_chunked_equals_whole(self):
        lines = fixture_lines(2)
        a = new_tracker()
        a.feed_lines(lines)
        b = new_tracker()
        for i in range(0, len(lines), 97):
            b.feed_lines(lines[i:i + 97])
        self.assertEqual({k: v["tags"] for k, v in a.entities.items()}, {k: v["tags"] for k, v in b.entities.items()})
        self.assertEqual(len(a.events), len(b.events))

    def test_second_game_resets_state(self):
        tr = new_tracker()
        tr.feed_lines(fixture_lines(0))
        n0 = len(tr.entities)
        tr.feed_lines(fixture_lines(1))
        self.assertEqual(tr.game_no, 2)
        self.assertNotEqual(len(tr.entities), n0)

    def test_player_two_is_me(self):
        text = """D 1 GameState.DebugPrintPower() - CREATE_GAME
D 1 GameState.DebugPrintPower() -     GameEntity EntityID=1
D 1 GameState.DebugPrintPower() -         tag=TURN value=3
D 1 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=5]
D 1 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=1 lo=7]
D 1 GameState.DebugPrintGame() - PlayerID=1, PlayerName=Gegnerin#1
D 1 GameState.DebugPrintGame() - PlayerID=2, PlayerName=Spieler#1234
D 1 GameState.DebugPrintPower() - TAG_CHANGE Entity=Spieler#1234 tag=RESOURCES value=4
D 1 GameState.DebugPrintPower() - TAG_CHANGE Entity=Spieler#1234 tag=CURRENT_PLAYER value=1
D 1 GameState.DebugPrintPower() - FULL_ENTITY - Creating ID=10 CardID=X1
D 1 GameState.DebugPrintPower() -     tag=CONTROLLER value=2
D 1 GameState.DebugPrintPower() -     tag=ZONE value=HAND
D 1 GameState.DebugPrintPower() -     tag=COST value=3
D 1 GameState.DebugPrintPower() -     tag=CARDTYPE value=SPELL
"""
        tr = new_tracker()
        tr.feed_lines(text.split("\n"))
        self.assertEqual(tr.my_pid, 2)
        s = build_state(tr, fake_db())
        self.assertEqual((s.my_mana, s.max_mana, s.my_active), (4, 4, True))
        self.assertEqual([c.cost for c in s.my_hand], [3])

    def test_unknown_name_falls_back_to_human_account(self):
        text = """D 1 GameState.DebugPrintPower() - CREATE_GAME
D 1 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=0 lo=0]
D 1 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=9 lo=9]
D 1 GameState.DebugPrintGame() - PlayerID=1, PlayerName=KI
D 1 GameState.DebugPrintGame() - PlayerID=2, PlayerName=Anderer#1
"""
        tr = new_tracker()
        tr.feed_lines(text.split("\n"))
        self.assertEqual(tr.my_pid, 2)


class TestIncrementalFile(unittest.TestCase):
    def test_growing_file_with_partial_line(self):
        lines = fixture_lines(4)
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "Hearthstone_2026_01_01_00_00_00")
            os.makedirs(sub)
            path = os.path.join(sub, "Power.log")
            tr = Tracker(d, "Spieler#1234")
            self.assertFalse(tr.update())
            half = len(lines) // 2
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines[:half]) + "\n" + lines[half][:20])      # letzte Zeile unvollstaendig
            self.assertTrue(tr.update())
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(lines[half][20:] + "\n" + "\n".join(lines[half + 1:]) + "\n")
            self.assertTrue(tr.update())
            self.assertFalse(tr.update())
            ref = new_tracker()
            ref.feed_lines(lines)
            self.assertEqual({k: v["tags"] for k, v in tr.entities.items()}, {k: v["tags"] for k, v in ref.entities.items()})

    def test_starts_at_last_game(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "Hearthstone_2026_01_01_00_00_00")
            os.makedirs(sub)
            with open(os.path.join(sub, "Power.log"), "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(fixture_lines(0) + fixture_lines(1)) + "\n")
            tr = Tracker(d, "Spieler#1234")
            tr.update()
            ref = new_tracker()
            ref.feed_lines(fixture_lines(1))
            self.assertEqual(len(tr.entities), len(ref.entities))
            self.assertEqual(tr.game_no, 1)


@unittest.skipIf(real_db() is None, "HDT-CardDefs nicht vorhanden")
class TestStateOnRealGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = real_db()
        tr = new_tracker()
        tr.feed_lines(fixture_lines(5))
        cls.s = build_state(tr, cls.db)

    def test_final_state(self):
        s = self.s
        self.assertEqual((s.result, s.turn), ("LOST", 20))
        self.assertEqual(s.opp_name, "Archimonde")
        self.assertEqual(s.my_hp, -2)
        self.assertEqual([m.name for m in s.opp_minions],
                         ["Belagerungsbrecher", "Übler Schreckenslord", "Höllenbestie", "Höllenbestie"])
        self.assertTrue(s.opp_minions[0].taunt)
        self.assertEqual([c.name for c in s.my_hand], ["Feuerball", "Flammenfalle"])

    def test_names_never_unknown(self):
        for ev in self.s.events:
            self.assertNotIn("UNKNOWN", ev)
            self.assertNotIn("???", ev)

    def test_hero_power_found(self):
        self.assertIsNotNone(self.s.my_hero_power)
        self.assertEqual(self.s.my_hero_power.cost, 4)

    def test_minion_attack_flags_mid_game(self):
        saw_ready = saw_sleeping = False
        tr = new_tracker()
        lines = fixture_lines(5)
        for i in range(0, len(lines), 40):
            tr.feed_lines(lines[i:i + 40])
            s = build_state(tr, self.db)
            for m in s.my_minions:
                saw_ready |= m.can_attack
                saw_sleeping |= not m.can_attack
        self.assertTrue(saw_ready and saw_sleeping)


if __name__ == "__main__":
    unittest.main()


class TestScreenSync(unittest.TestCase):
    """GameState eilt der Anzeige voraus; PowerTaskList zeigt, was der Bildschirm schon abgespielt hat."""

    def test_synthetic_lag(self):
        text = """D 1 GameState.DebugPrintPower() - CREATE_GAME
D 1 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=5]
D 1 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=0 lo=0]
D 1 GameState.DebugPrintGame() - PlayerID=1, PlayerName=Spieler#1234
D 1 GameState.DebugPrintGame() - PlayerID=2, PlayerName=Gastwirt
D 1 GameState.DebugPrintPower() - TAG_CHANGE Entity=Spieler#1234 tag=CURRENT_PLAYER value=1
D 1 GameState.DebugPrintPower() - TAG_CHANGE Entity=GameEntity tag=STEP value=MAIN_ACTION
"""
        tr = new_tracker()
        tr.feed_lines(text.split("\n"))
        s = build_state(tr, fake_db())
        self.assertTrue(s.my_active)
        self.assertFalse(s.ui_known)                        # noch keine PowerTaskList-Marker
        tr.feed_lines(["D 2 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=Boss tag=CURRENT_PLAYER value=1"])
        s = build_state(tr, fake_db())
        self.assertTrue(s.ui_known and not s.ui_my_turn)    # Bildschirm zeigt noch den Gegner (Alias -> Spieler 2)
        tr.feed_lines(["D 3 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=Spieler#1234 tag=CURRENT_PLAYER value=1",
                       "D 3 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=GameEntity tag=STEP value=MAIN_ACTION"])
        s = build_state(tr, fake_db())
        self.assertTrue(s.ui_my_turn)
        self.assertEqual(s.ui_step, "MAIN_ACTION")

    def test_screen_lags_behind_game_logic_in_real_game(self):
        tr = new_tracker()
        lines = fixture_lines(6)
        lag_seen = caught_up = False
        for i in range(0, len(lines), 3):
            tr.feed_lines(lines[i:i + 3])
            s = build_state(tr, fake_db())
            if s.my_active and s.ui_known and not s.ui_my_turn:
                lag_seen = True
            if s.my_active and s.ui_my_turn and s.ui_step == "MAIN_ACTION":
                caught_up = True
        self.assertTrue(lag_seen)
        self.assertTrue(caught_up)


class TestMeDetectionAgainstHumans(unittest.TestCase):
    """PvP: der Gegner heisst im Log 'UNKNOWN HUMAN PLAYER' - dann bin ich der andere Spieler (auch ohne gesetzten Namen)."""

    def feed(self, tr, p1, p2):
        tr._game(f"PlayerID=1, PlayerName={p1}")
        tr._game(f"PlayerID=2, PlayerName={p2}")

    def test_hidden_opponent_name_identifies_me_as_player_2(self):
        from tests.helpers import new_tracker
        tr = new_tracker()
        tr.player_name = ""
        self.feed(tr, "UNKNOWN HUMAN PLAYER", "Ich#4711")
        self.assertEqual(tr.my_pid, 2)
        self.assertTrue(tr.me_fixed)

    def test_hidden_opponent_name_identifies_me_as_player_1(self):
        from tests.helpers import new_tracker
        tr = new_tracker()
        tr.player_name = ""
        self.feed(tr, "Ich#4711", "UNKNOWN HUMAN PLAYER")
        self.assertEqual(tr.my_pid, 1)

    def test_configured_name_still_wins(self):
        from tests.helpers import new_tracker
        tr = new_tracker()
        self.feed(tr, "Spieler#1234", "UNKNOWN HUMAN PLAYER")
        self.assertEqual(tr.my_pid, 1)
