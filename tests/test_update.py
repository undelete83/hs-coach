import io
import json
import unittest

from hscoach import update


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(payload):
    def op(req, timeout=None):
        return FakeResp(json.dumps(payload).encode("utf-8"))
    return op


def failing(req, timeout=None):
    raise OSError("offline")


class TestUpdate(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(update.parse_version("v2.6.0"), (2, 6, 0))
        self.assertEqual(update.parse_version("2.10"), (2, 10, 0))
        self.assertIsNone(update.parse_version("latest"))
        self.assertTrue(update.is_newer("v2.10.0", "2.9.9"))
        self.assertFalse(update.is_newer("2.6.0", "2.6.0"))
        self.assertFalse(update.is_newer("nonsense", "2.6.0"))

    def test_newer_release_found(self):
        r = update.check("a/b", "2.6.0", opener_for({"tag_name": "v2.7.0", "html_url": "https://example/r"}))
        self.assertEqual(r, ("2.7.0", "https://example/r"))

    def test_same_draft_prerelease_ignored(self):
        self.assertIsNone(update.check("a/b", "2.6.0", opener_for({"tag_name": "v2.6.0"})))
        self.assertIsNone(update.check("a/b", "2.6.0", opener_for({"tag_name": "v3.0.0", "draft": True})))
        self.assertIsNone(update.check("a/b", "2.6.0", opener_for({"tag_name": "v3.0.0", "prerelease": True})))

    def test_failures_are_silent(self):
        self.assertIsNone(update.check("a/b", "2.6.0", failing))
        self.assertIsNone(update.check("", "2.6.0", failing))
        self.assertIsNone(update.check("kein-repo", "2.6.0", failing))

    def test_disabled_does_not_start_thread(self):
        called = []
        update.check_async({"update_check": False, "update_repo": "a/b"}, called.append)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
