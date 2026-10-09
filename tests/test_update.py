import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from hscoach import update

REPO = "a/b"
ZIP_URL = f"https://github.com/{REPO}/releases/download/v2.7.0/HSCoach-2.7.0.zip"


class FakeResp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

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


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


GOOD_FILES = {"HSCoach/HSCoach.exe": b"exe", "HSCoach/_internal/lib.dll": b"dll", "HSCoach/README.md": b"hi"}


class TestCheck(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(update.parse_version("v2.6.0"), (2, 6, 0))
        self.assertEqual(update.parse_version("2.10"), (2, 10, 0))
        self.assertIsNone(update.parse_version("latest"))
        self.assertTrue(update.is_newer("v2.10.0", "2.9.9"))
        self.assertFalse(update.is_newer("2.6.0", "2.6.0"))
        self.assertFalse(update.is_newer("nonsense", "2.6.0"))

    def test_newer_release_found_with_digest(self):
        sha = "ab" * 32
        r = update.check(REPO, "2.6.0", opener_for({
            "tag_name": "v2.7.0", "html_url": "https://example/r",
            "assets": [{"name": "notes.txt"}, {"name": "HSCoach-2.7.0.zip", "browser_download_url": ZIP_URL,
                                               "size": 123, "digest": "sha256:" + sha.upper()}]}))
        self.assertEqual((r.version, r.url), ("2.7.0", "https://example/r"))
        self.assertEqual((r.asset_name, r.asset_url, r.size, r.sha256), ("HSCoach-2.7.0.zip", ZIP_URL, 123, sha))

    def test_checksum_file_fallback(self):
        sha = "cd" * 32

        def op(req, timeout=None):
            if req.full_url.endswith(".sha256"):
                return FakeResp(f"{sha}  HSCoach-2.7.0.zip\n".encode())
            return FakeResp(json.dumps({"tag_name": "v2.7.0", "assets": [
                {"name": "HSCoach-2.7.0.zip", "browser_download_url": ZIP_URL, "size": 5},
                {"name": "HSCoach-2.7.0.zip.sha256", "browser_download_url": ZIP_URL + ".sha256"}]}).encode())
        self.assertEqual(update.check(REPO, "2.6.0", op).sha256, sha)

    def test_release_without_asset(self):
        r = update.check(REPO, "2.6.0", opener_for({"tag_name": "v2.7.0"}))
        self.assertEqual((r.version, r.asset_url, r.sha256), ("2.7.0", "", ""))

    def test_same_draft_prerelease_ignored(self):
        self.assertIsNone(update.check(REPO, "2.6.0", opener_for({"tag_name": "v2.6.0"})))
        self.assertIsNone(update.check(REPO, "2.6.0", opener_for({"tag_name": "v3.0.0", "draft": True})))
        self.assertIsNone(update.check(REPO, "2.6.0", opener_for({"tag_name": "v3.0.0", "prerelease": True})))

    def test_failures_are_silent(self):
        self.assertIsNone(update.check(REPO, "2.6.0", failing))
        self.assertIsNone(update.check("", "2.6.0", failing))
        self.assertIsNone(update.check("kein-repo", "2.6.0", failing))

    def test_disabled_does_not_start_thread(self):
        called = []
        update.check_async({"update_check": False, "update_repo": REPO}, called.append)
        self.assertEqual(called, [])


class TestCheckNow(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(update.check_now(REPO, "2.7.0", opener_for({"tag_name": "v2.7.0"})), ("current", None))
        status, rel = update.check_now(REPO, "2.7.0", opener_for({"tag_name": "v2.8.0"}))
        self.assertEqual((status, rel.version), ("new", "2.8.0"))
        status, msg = update.check_now(REPO, "2.7.0", failing)
        self.assertEqual(status, "error")
        self.assertIn("offline", msg)
        self.assertEqual(update.check_now("", "2.7.0")[0], "error")

    def test_manual_check_ignores_update_check_setting(self):
        got = []
        import threading
        ev = threading.Event()
        update.check_now_async({"update_check": False, "update_repo": ""}, lambda *a: (got.append(a), ev.set()))
        self.assertTrue(ev.wait(5))
        self.assertEqual(got[0][0], "error")          # leeres Repo -> Fehler, aber die Pruefung lief trotz update_check=False


class TestUpdateButtonHandler(unittest.TestCase):
    """Die Auswertung des Button-Ergebnisses in der GUI (ohne Fenster)."""

    def setUp(self):
        from unittest import mock
        from hscoach import gui
        self.gui, self.mock = gui, mock
        self.app = mock.MagicMock()
        self.app.build.version = "2.7.3"

    def run_handler(self, status, result):
        with self.mock.patch("tkinter.messagebox.showinfo") as info, self.mock.patch("tkinter.messagebox.showwarning") as warn:
            self.gui.App._update_checked(self.app, status, result)
        return info, warn

    def test_current_version_message(self):
        info, warn = self.run_handler("current", None)
        info.assert_called_once()
        self.assertIn("2.7.3", info.call_args[0][1])
        warn.assert_not_called()
        self.app.btn_update.config.assert_called_with(state="normal", text="⟳ Auf Update prüfen")

    def test_error_message(self):
        info, warn = self.run_handler("error", "offline")
        warn.assert_called_once()
        self.assertIn("offline", warn.call_args[0][1])

    def test_new_release_starts_update_flow(self):
        rel = update.Release("2.8.0", "u", "a", "n", 1, "s")
        info, warn = self.run_handler("new", rel)
        self.app._on_release.assert_called_once_with(rel)
        self.app._open_release.assert_called_once()
        info.assert_not_called()


class TestFailureFlag(unittest.TestCase):
    def test_take_failure_reads_and_clears_the_flag(self):
        with tempfile.TemporaryDirectory() as d:
            old = update.APP_DIR
            update.APP_DIR = d
            try:
                self.assertEqual(update.take_failure(), "")
                with open(update.log_file() + ".failed", "w") as f:
                    f.write("x")
                self.assertEqual(update.take_failure(), update.log_file())
                self.assertEqual(update.take_failure(), "")
            finally:
                update.APP_DIR = old


class TestDownload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = b"zipdata" * 1000
        self.sha = hashlib.sha256(self.data).hexdigest()

    def rel(self, **kw):
        base = dict(version="2.7.0", url="u", asset_url=ZIP_URL, asset_name="HSCoach-2.7.0.zip",
                    size=len(self.data), sha256=self.sha)
        base.update(kw)
        return update.Release(**base)

    def op(self, data=None):
        return lambda req, timeout=None: FakeResp(self.data if data is None else data)

    def test_download_ok_with_progress(self):
        seen = []
        p = update.download(self.rel(), REPO, self.tmp.name, lambda d, t: seen.append((d, t)), self.op())
        self.assertEqual(open(p, "rb").read(), self.data)
        self.assertEqual(seen[-1], (len(self.data), len(self.data)))
        self.assertFalse(os.path.exists(p + ".part"))

    def test_wrong_checksum_rejected(self):
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(sha256="00" * 32), REPO, self.tmp.name, opener=self.op())
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_incomplete_download_rejected(self):
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(), REPO, self.tmp.name, opener=self.op(self.data[:-5]))

    def test_foreign_url_and_missing_checksum_rejected(self):
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(asset_url="https://evil.example/HSCoach-2.7.0.zip"), REPO, self.tmp.name, opener=self.op())
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(asset_url="https://github.com/other/repo/releases/download/v1/x.zip"), REPO,
                            self.tmp.name, opener=self.op())
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(sha256=""), REPO, self.tmp.name, opener=self.op())

    def test_network_error_wrapped(self):
        with self.assertRaises(update.UpdateError):
            update.download(self.rel(), REPO, self.tmp.name, opener=failing)


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_extract_ok(self):
        z = os.path.join(self.tmp.name, "a.zip")
        make_zip(z, GOOD_FILES)
        new = update.extract(z, os.path.join(self.tmp.name, "out"))
        self.assertTrue(os.path.isfile(os.path.join(new, "HSCoach.exe")))
        self.assertTrue(os.path.isfile(os.path.join(new, "_internal", "lib.dll")))

    def test_zip_slip_rejected(self):
        z = os.path.join(self.tmp.name, "evil.zip")
        make_zip(z, dict(GOOD_FILES, **{"HSCoach/../../evil.txt": b"x"}))
        with self.assertRaises(update.UpdateError):
            update.extract(z, os.path.join(self.tmp.name, "out"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "evil.txt")))

    def test_incomplete_package_rejected(self):
        z = os.path.join(self.tmp.name, "bad.zip")
        make_zip(z, {"HSCoach/readme.txt": b"x"})
        with self.assertRaises(update.UpdateError):
            update.extract(z, os.path.join(self.tmp.name, "out"))


class TestSelfUpdateGuards(unittest.TestCase):
    def test_not_allowed_from_source(self):
        self.assertFalse(update.can_self_update(frozen=False))

    @unittest.skipUnless(os.name == "nt", "nur Windows")
    def test_directory_checks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(update.can_self_update(d, frozen=True))          # keine HSCoach.exe
            open(os.path.join(d, "HSCoach.exe"), "wb").close()
            os.makedirs(os.path.join(d, "_internal"))
            self.assertTrue(update.can_self_update(d, frozen=True))
        with tempfile.TemporaryDirectory(prefix="x%y") as d:                  # Prozentzeichen im Pfad
            open(os.path.join(d, "HSCoach.exe"), "wb").close()
            os.makedirs(os.path.join(d, "_internal"))
            self.assertFalse(update.can_self_update(d, frozen=True))

    def test_script_contents(self):
        s = update.build_script(r"C:\App", r"C:\W\new", r"C:\W", 4242)
        self.assertIn('PID eq 4242', s)
        self.assertIn('robocopy.exe" "%NEW%" "%APP%"', s)
        self.assertIn(":rollback", s)
        self.assertIn('start "" "%APP%\\HSCoach.exe"', s)

    def test_child_env_has_no_pyinstaller_markers(self):
        os.environ["_PYI_TEST_MARKER"] = "1"
        try:
            self.assertNotIn("_PYI_TEST_MARKER", update._clean_env())
        finally:
            del os.environ["_PYI_TEST_MARKER"]


@unittest.skipUnless(os.name == "nt", "nur Windows")
class TestRealSwap(unittest.TestCase):
    """Fuehrt das echte Austausch-Skript aus: wartet auf das Ende eines Prozesses, tauscht Dateien, startet neu."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(self.cleanup_root)
        self.app = os.path.join(self.root, "App Ordner")           # Leerzeichen im Pfad
        os.makedirs(os.path.join(self.app, "_internal"))
        self.exe_src = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "rundll32.exe")      # GUI-Programm ohne Fenster: beim Neustart darf nichts aufpoppen
        shutil.copy(self.exe_src, os.path.join(self.app, "HSCoach.exe"))
        open(os.path.join(self.app, "_internal", "old.dll"), "w").write("old")
        self.work = os.path.join(self.root, "work")
        self.new = os.path.join(self.work, "new", "HSCoach")
        os.makedirs(os.path.join(self.new, "_internal"))
        shutil.copy(self.exe_src, os.path.join(self.new, "HSCoach.exe"))
        open(os.path.join(self.new, "_internal", "new.dll"), "w").write("new")
        open(os.path.join(self.new, "VERSION.txt"), "w").write("new")

    def cleanup_root(self):
        for _ in range(20):                  # der neu gestartete Prozess gibt seine Datei erst kurz spaeter frei
            shutil.rmtree(self.root, ignore_errors=True)
            if not os.path.exists(self.root):
                return
            time.sleep(0.3)

    def run_script(self, new_dir, **kw):
        waiter = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
        script = os.path.join(self.work, "update.cmd")
        with open(script, "w", encoding="utf-8", newline="") as f:
            f.write(update.build_script(self.app, new_dir, self.work, waiter.pid, proc_name="python.exe", **kw))
        t0 = time.time()
        update.launch(script)
        return waiter, t0

    def wait_for(self, cond, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.3)
        return False

    @unittest.skipUnless(os.path.basename(sys.executable).lower() == "python.exe", "braucht python.exe als Prozessname")
    def test_swap_waits_for_exit_and_replaces(self):
        waiter, t0 = self.run_script(self.new)
        time.sleep(0.8)
        self.assertTrue(os.path.exists(os.path.join(self.app, "_internal", "old.dll")), "darf nicht vor dem Prozessende tauschen")
        self.assertTrue(self.wait_for(lambda: os.path.exists(os.path.join(self.app, "VERSION.txt"))))
        self.assertTrue(self.wait_for(lambda: not os.path.exists(self.work)), "Arbeitsordner wird aufgeraeumt")
        self.assertFalse(os.path.exists(os.path.join(self.app, "_internal", "old.dll")))
        self.assertTrue(os.path.exists(os.path.join(self.app, "_internal", "new.dll")))
        self.assertFalse(os.path.exists(os.path.join(self.app, "_internal.bak")))

    @unittest.skipUnless(os.path.basename(sys.executable).lower() == "python.exe", "braucht python.exe als Prozessname")
    def test_second_instance_from_same_folder_is_closed(self):
        """Ein zweites Coach-Fenster aus demselben Ordner haelt die Dateien fest - das Skript beendet es und tauscht dann."""
        ping = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "ping.exe")
        shutil.copy(ping, os.path.join(self.app, "HSCoach.exe"))
        other = subprocess.Popen([os.path.join(self.app, "HSCoach.exe"), "-n", "300", "127.0.0.1"], stdout=subprocess.DEVNULL)
        self.addCleanup(lambda: other.poll() is None and other.kill())
        log = os.path.join(self.root, "update.log")
        self.run_script(self.new, log_path=log)
        self.assertTrue(self.wait_for(lambda: os.path.exists(os.path.join(self.app, "VERSION.txt"))), "Austausch muss gelingen")
        self.assertTrue(self.wait_for(lambda: other.poll() is not None), "das zweite Fenster muss beendet sein")
        self.assertTrue(self.wait_for(lambda: "erfolgreich" in open(log, encoding="utf-8", errors="replace").read()))
        self.assertFalse(os.path.exists(log + ".failed"))

    @unittest.skipUnless(os.path.basename(sys.executable).lower() == "python.exe", "braucht python.exe als Prozessname")
    def test_locked_files_end_in_a_clean_failure(self):
        """Haelt ein fremder Prozess Dateien im Ordner fest, bleibt die alte Version intakt und es gibt eine Fehlermarke."""
        held = os.path.join(self.app, "_internal", "old.dll")
        holder = subprocess.Popen([sys.executable, "-c", f"import time; f = open({held!r}, 'rb'); time.sleep(60)"])
        self.addCleanup(lambda: holder.poll() is None and holder.kill())
        time.sleep(1.0)
        log = os.path.join(self.root, "update.log")
        self.run_script(self.new, log_path=log, rename_retries=2, retry_wait=1)
        self.assertTrue(self.wait_for(lambda: os.path.exists(log + ".failed"), 30), "Fehlermarke fehlt")
        self.assertTrue(os.path.exists(held), "alte Version muss erhalten bleiben")
        self.assertFalse(os.path.exists(os.path.join(self.app, "VERSION.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.app, "_internal.bak")))
        self.assertIn("gescheitert", open(log, encoding="utf-8", errors="replace").read())

    @unittest.skipUnless(os.path.basename(sys.executable).lower() == "python.exe", "braucht python.exe als Prozessname")
    def test_rollback_when_copy_fails(self):
        waiter, t0 = self.run_script(os.path.join(self.root, "gibt-es-nicht"))
        self.assertTrue(self.wait_for(lambda: not os.path.exists(self.work)))
        self.assertTrue(os.path.exists(os.path.join(self.app, "_internal", "old.dll")), "alte Version muss zurueckkommen")
        self.assertFalse(os.path.exists(os.path.join(self.app, "_internal.bak")))


if __name__ == "__main__":
    unittest.main()
