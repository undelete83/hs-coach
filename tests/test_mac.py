import os
import unittest
from unittest import mock

from hscoach import detect


class TestMacPaths(unittest.TestCase):
    def test_log_config_in_library_preferences(self):
        with mock.patch.object(detect, "IS_MAC", True):
            self.assertEqual(detect.log_config_path(),
                             os.path.expanduser("~/Library/Preferences/Blizzard/Hearthstone/log.config"))

    def test_install_dirs_are_applications(self):
        with mock.patch.object(detect, "IS_MAC", True), mock.patch.dict(os.environ, {"HS_INSTALL_DIR": ""}):
            dirs = detect.candidate_install_dirs()
        self.assertEqual(dirs, ["/Applications/Hearthstone", os.path.expanduser("~/Applications/Hearthstone")])

    def test_app_bundle_counts_as_installation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "Hearthstone.app"))
            os.makedirs(os.path.join(root, "Logs"))
            with mock.patch.object(detect, "candidate_install_dirs", return_value=[]):
                self.assertEqual(detect.find_log_dir([root]), os.path.join(root, "Logs"))


if __name__ == "__main__":
    unittest.main()
