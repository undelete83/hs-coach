"""Grundwissen aus den Kartendaten (bosses_auto.py) fuer alle weiteren Solo-Abenteuer."""
import unittest

from hscoach import bosses
from hscoach.bosses_auto import AUTO
from hscoach.bosses_data import BOSSES


class TestAutoBosses(unittest.TestCase):
    def test_adventures_are_covered(self):
        chapters = {d["chapter"] for d in AUTO}
        for name in ("Naxxramas", "Der Schwarzfels", "Die Forscherliga", "Kobolde & Katakomben", "Der Hexenwald", "Rastakhans Rumble",
                     "Der Dalaran-Raubzug", "Gräber des Terrors", "Galakronds Erwachen", "Ritter des Frostthrons", "Book of Mercenaries"):
            self.assertIn(name, chapters)

    def test_lookup_and_title(self):
        b = bosses.find("DALA_BOSS_39h")
        self.assertEqual(b.name, "Aki der Gleißende")
        self.assertIn("Dalaran", b.title)
        self.assertTrue(b.boss_power)
        self.assertIn("BOSS-KAMPF", b.prompt())

    def test_handwritten_knowledge_wins(self):
        curated = {cid for d in BOSSES for cid in d["match"]}
        for d in AUTO:
            self.assertFalse(curated & set(d["match"]), d["name"])
        self.assertEqual(bosses.find("Story_01_Archimonde").name, "Archimonde")

    def test_player_heroes_are_no_bosses(self):
        for cid in ("HERO_01", "HERO_08b", ""):
            self.assertIsNone(bosses.find(cid))


if __name__ == "__main__":
    unittest.main()
