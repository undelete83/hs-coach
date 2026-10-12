import importlib.util
import os
import tempfile
import unittest

from hscoach import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("release_notes", os.path.join(ROOT, "scripts", "release_notes.py"))
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

LOG = "# Verlauf\n\n## 2.1.0 - 01.01.2026\n- neu A\n- neu B\n\n## 2.0.0 - 01.12.2025\n- alt\n"


class TestReleaseNotes(unittest.TestCase):
    def test_section_stops_at_next_version(self):
        self.assertEqual(release_notes.section(LOG, "2.1.0"), "- neu A\n- neu B")
        self.assertEqual(release_notes.section(LOG, "2.0.0"), "- alt")

    def test_missing_version_raises(self):
        with self.assertRaises(ValueError):
            release_notes.section(LOG, "2.2.0")

    def test_current_version_has_notes(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "n.md")
            import sys
            argv, sys.argv = sys.argv, ["x", "v" + __version__, out]
            try:
                release_notes.main()
            finally:
                sys.argv = argv
            text = open(out, encoding="utf-8").read()
        self.assertIn(f"HSCoach-{__version__}-mac.zip", text)
        self.assertIn(f"HSCoach-{__version__}.zip", text)


if __name__ == "__main__":
    unittest.main()
