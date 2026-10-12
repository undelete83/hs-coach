import os
import sys
import unittest
from unittest import mock

import hscoach
from hscoach import dialogs, update


class TestOwnDialogs(unittest.TestCase):
    """Die eigenen Fenster (macOS-Weg) auf jeder Plattform pruefen: Knopf druecken -> Ergebnis."""

    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
        except Exception:
            self.skipTest("kein Tk")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        patcher = mock.patch.object(dialogs, "USE_NATIVE", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def press_after_open(self, value):
        def press():
            for w in self.root.winfo_children():
                if isinstance(w, dialogs._Dialog):
                    w.buttons[value].invoke()
                    return
            self.root.after(20, press)
        self.root.after(20, press)

    def test_yes_and_no(self):
        self.press_after_open(True)
        self.assertIs(dialogs.ask_yes_no("Update", "Installieren?", parent=self.root), True)
        self.press_after_open(False)
        self.assertIs(dialogs.ask_yes_no("Update", "Installieren?", parent=self.root), False)

    def test_info_closes(self):
        self.press_after_open(True)
        dialogs.show_info("Update", "Aktuell.", parent=self.root)
        self.assertFalse([w for w in self.root.winfo_children() if isinstance(w, dialogs._Dialog)])

    def test_native_only_off_mac(self):
        with mock.patch("tkinter.messagebox.askyesno", return_value=True) as native, \
             mock.patch.object(dialogs, "USE_NATIVE", True):
            self.assertTrue(dialogs.ask_yes_no("a", "b"))
        native.assert_called_once()


class TestTls(unittest.TestCase):
    def test_mac_uses_certifi_when_unset(self):
        with mock.patch.object(hscoach.sys, "platform", "darwin"), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SSL_CERT_FILE", None)
            hscoach.setup_tls()
            try:
                import certifi
            except ImportError:
                self.skipTest("certifi fehlt")
            self.assertEqual(os.environ.get("SSL_CERT_FILE"), certifi.where())

    def test_existing_setting_and_other_platforms_untouched(self):
        with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "/eigene.pem"}):
            hscoach.setup_tls()
            self.assertEqual(os.environ["SSL_CERT_FILE"], "/eigene.pem")
        with mock.patch.object(hscoach.sys, "platform", "win32"), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SSL_CERT_FILE", None)
            hscoach.setup_tls()
            self.assertNotIn("SSL_CERT_FILE", os.environ)


class TestCleanEnv(unittest.TestCase):
    def test_test_hooks_not_inherited(self):
        with mock.patch.dict(os.environ, {"HS_COACH_UPDATE_URL": "http://x", "HS_COACH_UPDATE_AUTO": "1"}):
            env = update._clean_env()
        self.assertNotIn("HS_COACH_UPDATE_URL", env)
        self.assertNotIn("HS_COACH_UPDATE_AUTO", env)


class TestSelftest(unittest.TestCase):
    def test_http_error_still_proves_tls(self):
        import io
        import urllib.error
        from hscoach import selftest
        err = urllib.error.HTTPError(selftest.URL, 429, "rate limit", {}, None)
        with mock.patch.object(selftest.urllib.request, "urlopen", side_effect=err), \
             mock.patch.object(selftest, "os") as fake_os:
            fake_os.makedirs.side_effect = OSError
            out = io.StringIO()
            self.assertEqual(selftest.run(out), 0)
        self.assertIn("HTTP 429", out.getvalue())

    def test_reports_failures_with_exit_code(self):
        import io
        from hscoach import selftest
        with mock.patch.object(selftest.urllib.request, "urlopen", side_effect=OSError("offline")), \
             mock.patch.object(selftest, "os") as fake_os:
            fake_os.makedirs.side_effect = OSError
            out = io.StringIO()
            code = selftest.run(out)
        self.assertEqual(code, 1)
        self.assertIn("✗ HTTPS", out.getvalue())


if __name__ == "__main__":
    unittest.main()
