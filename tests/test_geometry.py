import unittest

from hscoach.gui import DEFAULT_SIZE, resolve_geometry

TRIPLE = (-3840, 0, 7680, 1440)      # drei Monitore, einer links vom Hauptmonitor
SINGLE = (0, 0, 1920, 1080)


class TestResolveGeometry(unittest.TestCase):
    def test_negative_position_is_kept(self):
        """Tk schreibt Positionen links vom Hauptmonitor als '+-2223' - das ging frueher verloren."""
        self.assertEqual(resolve_geometry("1874x1293+-2223+25", TRIPLE), "1874x1293+-2223+25")

    def test_normal_position_and_size_only(self):
        self.assertEqual(resolve_geometry("1500x900+100+50", SINGLE), "1500x900+100+50")
        self.assertEqual(resolve_geometry("1200x900", SINGLE), "1200x900")

    def test_garbage_falls_back_to_default(self):
        for bad in ("", None, "abc", "1200x", "1200x900+5"):
            self.assertEqual(resolve_geometry(bad, SINGLE), DEFAULT_SIZE, bad)

    def test_monitor_gone_drops_only_the_position(self):
        self.assertEqual(resolve_geometry("1874x1293+-2223+25", SINGLE), "1874x1293")
        self.assertEqual(resolve_geometry("1500x900+5000+50", SINGLE), "1500x900")
        self.assertEqual(resolve_geometry("1500x900+100+2000", SINGLE), "1500x900")

    def test_partly_visible_window_is_kept(self):
        self.assertEqual(resolve_geometry("1500x900+-1000+50", SINGLE), "1500x900+-1000+50")

    def test_without_screen_info_only_extreme_values_are_dropped(self):
        self.assertEqual(resolve_geometry("1500x900+-2223+25"), "1500x900+-2223+25")
        self.assertEqual(resolve_geometry("1500x900+-20000+25"), "1500x900")


if __name__ == "__main__":
    unittest.main()
