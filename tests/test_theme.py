import unittest

from hscoach import gui, textures, theme


class TestThemes(unittest.TestCase):
    def test_all_palettes_have_every_key(self):
        for name, t in theme.THEMES.items():
            for key in gui._THEME_KEYS:
                self.assertIn(key, t, f"{name}: {key} fehlt")

    def test_unknown_or_empty_name_falls_back_to_classic(self):
        self.assertIs(theme.get("gibt-es-nicht"), theme.KLASSISCH)
        self.assertIs(theme.get(""), theme.KLASSISCH)
        self.assertIs(theme.get(None), theme.KLASSISCH)

    def test_apply_theme_sets_module_constants_and_restores(self):
        try:
            gui.apply_theme("spielbrett")
            self.assertTrue(gui.WOOD)
            self.assertTrue(gui.PLANK)
            self.assertEqual(gui.BG, theme.SPIELBRETT["BG"])
            self.assertTrue(gui.PARCH)
            gui.apply_theme("klassisch")
            self.assertFalse(gui.WOOD)
            self.assertEqual(gui.FRAME_PAD, 0)
            self.assertEqual(gui.BG, theme.KLASSISCH["BG"])
        finally:
            gui.apply_theme("klassisch")

    def test_parchment_tags_are_dark_text(self):
        for color in theme.PARCHMENT_TAGS.values():
            r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            self.assertLess(0.299 * r + 0.587 * g + 0.114 * b, 150, color)    # lesbar auf hellem Pergament

    def test_choices_match_themes(self):
        self.assertEqual(set(theme.CHOICES), set(theme.THEMES))


@unittest.skipUnless(textures.PIL_OK, "Pillow fehlt")
class TestTextures(unittest.TestCase):
    def test_wood_size_and_mode(self):
        img = textures.wood(300, 200)
        self.assertEqual(img.size, (300, 200))
        self.assertEqual(img.mode, "RGB")

    def test_wood_is_not_flat(self):
        lo, hi = textures.wood(200, 120).convert("L").getextrema()
        self.assertGreater(hi - lo, 30)

    def test_tiny_sizes_do_not_crash(self):
        self.assertEqual(textures.wood(1, 1).size, (8, 8))


if __name__ == "__main__":
    unittest.main()
