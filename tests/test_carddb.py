import json
import os
import tempfile
import time
import unittest
from unittest import mock

from hscoach import carddb, config

from tests.helpers import real_db

SAMPLE = [
    {"id": "CS2_024", "name": "Frostblitz", "type": "SPELL", "cost": 2, "mechanics": ["FREEZE"],
     "text": "Fügt einem Charakter $3 Schaden zu und <b>friert</b> ihn ein."},
    {"id": "KAR_037", "name": "Wächtereule", "type": "MINION", "cost": 2, "attack": 2, "health": 2,
     "mechanics": ["BATTLECRY"], "referencedTags": ["TAUNT"],
     "text": "<b>Kampfschrei:</b> Erhält +1/+1 und <b>Spott</b>, wenn Ihr ein Geheimnis kontrolliert."},
    {"id": "CS2_142", "name": "Koboldgeomant", "type": "MINION", "cost": 2, "attack": 2, "health": 2,
     "mechanics": ["SPELLPOWER"], "spellDamage": 1, "race": "ELEMENTAL"},
    {"id": "WEAPON_X", "name": "Beil", "type": "WEAPON", "cost": 1, "attack": 3, "durability": 2},
    {"id": "GAME_005", "name": "Die Münze", "type": "SPELL", "cost": 0, "text": "Erhaltet 1 Manakristall nur für diesen Zug."},
]


class TestParseHsjson(unittest.TestCase):
    def setUp(self):
        self.db = carddb.parse_hsjson(SAMPLE)

    def test_fields(self):
        c = self.db["CS2_024"]
        self.assertEqual((c["name"], c["cardtype"], c["cost"], c.get("freeze")), ("Frostblitz", "SPELL", 2, True))
        self.assertEqual(c["text"], "Fügt einem Charakter 3 Schaden zu und friert ihn ein.")

    def test_referenced_keyword_is_not_a_flag(self):
        self.assertFalse(self.db["KAR_037"].get("taunt"))
        self.assertTrue(self.db["KAR_037"].get("battlecry"))

    def test_race_spellpower_weapon_cost_zero(self):
        self.assertEqual(self.db["CS2_142"]["race"], "ELEMENTAL")
        self.assertEqual(self.db["CS2_142"]["spellpower"], 1)
        self.assertEqual((self.db["WEAPON_X"]["atk"], self.db["WEAPON_X"]["health"]), (3, 2))
        self.assertEqual(self.db["GAME_005"]["cost"], 0)


class FakeResp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class TestDownloadAndFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(config, "APP_DIR", self.tmp.name)
        self.patch.start()
        self.cfg = {"card_source": "auto", "card_language": "deDE", "carddefs_base": os.path.join(self.tmp.name, "b.xml"),
                    "carddefs_de": os.path.join(self.tmp.name, "d.xml")}

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_download_writes_cache_and_is_reused_while_fresh(self):
        data = json.dumps(SAMPLE).encode()
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(data)) as m:
            p = carddb.download_hsjson(self.cfg)
            self.assertTrue(os.path.exists(p))
            carddb.download_hsjson(self.cfg)
            self.assertEqual(m.call_count, 1)

    def test_stale_cache_survives_failed_download(self):
        p = carddb.hsjson_cache_path(self.cfg)
        with open(p, "wb") as f:
            f.write(json.dumps(SAMPLE).encode())
        old = time.time() - 10 * 24 * 3600
        os.utime(p, (old, old))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(carddb.download_hsjson(self.cfg), p)

    def test_html_error_page_is_rejected(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(b"<html>Error</html>")):
            with self.assertRaises(ValueError):
                carddb.download_hsjson(self.cfg)

    def test_load_uses_hsjson(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(json.dumps(SAMPLE).encode())):
            db = carddb.CardDB(self.cfg)
            db.load()
        self.assertEqual((db.source, db.name("CS2_024")), ("hearthstonejson", "Frostblitz"))
        self.assertTrue(db.ready.is_set())

    def test_offline_falls_back_to_hdt(self):
        with open(self.cfg["carddefs_base"], "w") as f:
            f.write("<x/>")
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")), \
                mock.patch.object(carddb, "parse_hdt", return_value={"A": {"name": "Aus HDT"}}):
            db = carddb.CardDB(self.cfg)
            db.load()
        self.assertEqual((db.source, db.name("A")), ("hdt", "Aus HDT"))

    def test_everything_fails_gives_error_message(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            db = carddb.CardDB(self.cfg)
            db.load()
        self.assertTrue(db.ready.is_set())
        self.assertEqual(db.cards, {})
        self.assertIn("hearthstonejson", db.error)


@unittest.skipIf(real_db() is None, "keine Kartendaten verfuegbar")
class TestRealData(unittest.TestCase):
    def test_no_false_keyword_flags_on_real_data(self):
        db = real_db()
        self.assertFalse(db.info("KAR_037").get("taunt"))      # Waechtereule: Spott nur bedingt
        self.assertTrue(db.info("CS2_065").get("taunt"))       # Leerwandler: echter Spott
        self.assertTrue(db.info("CS2_024").get("freeze"))
        self.assertEqual(db.info("Story_01_Archimonde").get("health"), 40)


if __name__ == "__main__":
    unittest.main()
