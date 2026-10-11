"""Sammlung (HSReplay): Link, Abruf, Besitz, Filter und Deckpruefung."""
import json
import os
import tempfile
import unittest
from unittest import mock

from hscoach import collection, config

CARDS = [
    {"dbfId": 1, "id": "A", "name": "Anregen", "cost": 0, "type": "SPELL", "cardClass": "DRUID", "rarity": "RARE", "set": "CORE",
     "collectible": True, "text": "Erhaltet 1 Manakristall."},
    {"dbfId": 2, "id": "B", "name": "Fandral", "cost": 4, "type": "MINION", "cardClass": "DRUID", "rarity": "LEGENDARY", "set": "CORE",
     "collectible": True, "attack": 3, "health": 6, "text": "Wählt aus"},
    {"dbfId": 3, "id": "C", "name": "Alter Schinken", "cost": 3, "type": "MINION", "cardClass": "NEUTRAL", "rarity": "EPIC", "set": "OG",
     "collectible": True, "attack": 2, "health": 2, "text": ""},
    {"dbfId": 4, "id": "D", "name": "Nicht sammelbar", "cost": 1, "type": "MINION", "cardClass": "NEUTRAL", "set": "CORE"},
    {"dbfId": 9, "id": "H", "name": "Held", "type": "HERO", "cardClass": "DRUID", "collectible": True, "set": "CORE"},
]
RAW = {"collection": {"1": [1, 1, 0, 0], "2": [1, 1], "3": [0, 0, 0, 0], "99": [2, 0]}, "dust": 1234, "_fetched_at": 1}


class FakeResp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class TestAccount(unittest.TestCase):
    def test_parse_link_and_pair(self):
        self.assertEqual(collection.parse_account("https://hsreplay.net/collection/2/12345678/"), (2, 12345678))
        self.assertEqual(collection.parse_account("2/12345678"), (2, 12345678))
        self.assertIsNone(collection.parse_account(""))
        self.assertIsNone(collection.parse_account("hallo"))


class TestFetch(unittest.TestCase):
    def test_fetch_uses_honest_user_agent_and_caches(self):
        seen = {}

        def fake(req, timeout=0):
            seen["ua"] = req.get_header("User-agent")
            seen["url"] = req.full_url
            return FakeResp(json.dumps({"collection": {"1": [1, 0]}}).encode())
        with tempfile.TemporaryDirectory() as d, mock.patch.object(config, "APP_DIR", d):
            raw = collection.fetch({"hsreplay_collection": "2/777"}, urlopen=fake)
            self.assertIn("HSCoach", seen["ua"])
            self.assertIn("region=2&account_lo=777", seen["url"])
            self.assertEqual(collection.load_cached()["collection"], raw["collection"])
            self.assertTrue(os.path.exists(os.path.join(d, "collection.json")))

    def test_errors_are_reported(self):
        with self.assertRaises(collection.CollectionError):
            collection.fetch({"hsreplay_collection": ""})
        with self.assertRaises(collection.CollectionError):
            collection.fetch({"hsreplay_collection": "2/7"}, urlopen=lambda *a, **k: FakeResp(b'{"fehler": 1}'))
        with self.assertRaises(collection.CollectionError):
            collection.fetch({"hsreplay_collection": "2/7"}, urlopen=mock.Mock(side_effect=OSError("kaputt")))


class TestOwnership(unittest.TestCase):
    def setUp(self):
        self.coll = collection.Collection(RAW)
        self.rows = collection.card_rows({"standard_sets": ["CORE"]}, cards=CARDS)

    def test_rows_only_collectible_non_heroes(self):
        self.assertEqual(sorted(r["dbf"] for r in self.rows), [1, 2, 3])

    def test_counts_are_capped(self):
        self.assertEqual(self.coll.owned(1, "RARE"), 2)
        self.assertEqual(self.coll.owned(2, "LEGENDARY"), 1)       # 2 Exemplare, aber Legendaer zaehlt nur 1
        self.assertEqual(self.coll.owned(3, "EPIC"), 0)
        self.assertEqual(self.coll.owned(12345), 0)

    def test_filters(self):
        f = lambda **kw: [r["name"] for r in collection.filter_rows(self.rows, self.coll, **kw)]
        self.assertEqual(f(), ["Anregen", "Alter Schinken", "Fandral"])
        self.assertEqual(f(fmt="standard"), ["Anregen", "Fandral"])
        self.assertEqual(f(cls="DRUID", own="have"), ["Anregen", "Fandral"])
        self.assertEqual(f(own="missing"), ["Alter Schinken"])
        self.assertEqual(f(cost="4"), ["Fandral"])
        self.assertEqual(f(text="manakristall"), ["Anregen"])
        self.assertEqual(f(rarity="EPIC"), ["Alter Schinken"])


class TestDecks(unittest.TestCase):
    def setUp(self):
        self.coll = collection.Collection(RAW)
        self.rows = collection.card_rows({"standard_sets": ["CORE"]}, cards=CARDS)

    def test_roundtrip(self):
        cards = [(1, 2), (2, 1), (3, 2)]
        fmt, heroes, back = collection.decode_deck(collection.encode_deck(2, 274, cards))
        self.assertEqual((fmt, heroes, sorted(back)), (2, [274], sorted(cards)))

    def test_known_real_code(self):
        fmt, heroes, cards = collection.decode_deck(
            "AAECAZICAv/TBMXOBg6mnwShoASA1ASB1ASc1ASj1AT75Qab8gatkgfJrAfLrQeS8QeT8QfA8QcA")
        self.assertEqual((fmt, heroes, sum(c for _d, c in cards)), (2, [274], 30))

    def test_check_reports_missing_and_dust(self):
        code = collection.encode_deck(2, 274, [(1, 2), (2, 1), (3, 2)])
        res = collection.check_deck(code, self.rows, self.coll)
        self.assertEqual([(m["row"]["name"], m["lack"]) for m in res["missing"]], [("Alter Schinken", 2)])
        self.assertEqual(res["dust"], 800)                          # 2 x episch = 2 x 400
        self.assertTrue(any("nicht Standard" in n for n in res["notes"]))
        self.assertTrue(any("5 statt 30" in n for n in res["notes"]))
        self.assertIn("Alter Schinken", collection.render_check(res))

    def test_garbage_is_rejected(self):
        for bad in ("", "hallo", "AAAA"):
            with self.assertRaises(collection.CollectionError):
                collection.decode_deck(bad)


if __name__ == "__main__":
    unittest.main()
