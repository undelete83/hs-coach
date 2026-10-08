import os
import re
import tempfile
import unittest

import hscoach
from hscoach import version

from tests.helpers import HERE


def make_repo(d, head_text, ref_file=None, ref_hash=None, packed=None):
    git = os.path.join(d, ".git")
    os.makedirs(os.path.join(git, "refs", "heads"))
    with open(os.path.join(git, "HEAD"), "w") as f:
        f.write(head_text)
    if ref_file:
        with open(os.path.join(git, *ref_file.split("/")), "w") as f:
            f.write(ref_hash + "\n")
    if packed:
        with open(os.path.join(git, "packed-refs"), "w") as f:
            f.write("# pack-refs\n" + packed + "\n")


class TestReadHead(unittest.TestCase):
    def test_branch_ref_file(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, "ref: refs/heads/master\n", "refs/heads/master", "abcdef1234567890")
            self.assertEqual(version.read_head(d), "abcdef1")

    def test_detached_head(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, "1234567890abcdef\n")
            self.assertEqual(version.read_head(d), "1234567")

    def test_packed_refs(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, "ref: refs/heads/master\n", packed="fedcba9876543210 refs/heads/master")
            self.assertEqual(version.read_head(d), "fedcba9")

    def test_no_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(version.read_head(d), "")
            self.assertEqual(version.BuildInfo(d).newer_available(), "")


class TestNewerAvailable(unittest.TestCase):
    def test_detects_new_commit(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, "ref: refs/heads/master\n", "refs/heads/master", "aaaaaaa111")
            b = version.BuildInfo(d)
            self.assertEqual(b.newer_available(), "")
            with open(os.path.join(d, ".git", "refs", "heads", "master"), "w") as f:
                f.write("bbbbbbb222\n")
            self.assertEqual(b.newer_available(), "bbbbbbb")
            self.assertIn("v" + hscoach.__version__, b.label)


class TestChangelog(unittest.TestCase):
    def test_current_version_is_documented_at_top(self):
        with open(os.path.join(os.path.dirname(HERE), "CHANGELOG.md"), encoding="utf-8") as f:
            text = f.read()
        first = re.search(r"^## (\d+\.\d+\.\d+)", text, re.M)
        self.assertIsNotNone(first)
        self.assertEqual(first.group(1), hscoach.__version__, "CHANGELOG.md: neuester Eintrag passt nicht zur Version")


if __name__ == "__main__":
    unittest.main()
