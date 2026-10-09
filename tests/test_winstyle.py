import unittest

from hscoach import winstyle


class TestWinStyle(unittest.TestCase):
    def test_colorref_is_bgr(self):
        self.assertEqual(winstyle._colorref("#102030"), 0x302010)
        self.assertEqual(winstyle._colorref("#ffffff"), 0xFFFFFF)

    def test_style_never_raises_on_bad_window(self):
        class Broken:
            def update_idletasks(self):
                raise RuntimeError("kein Fenster")
        self.assertFalse(winstyle.style_titlebar(Broken()))


if __name__ == "__main__":
    unittest.main()
