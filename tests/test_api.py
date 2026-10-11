"""Lese-API: Momentaufnahme, Long-Poll, Zugangsregeln und ein echter kurzer Serverlauf auf dem Loopback."""
import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

from hscoach import api
from hscoach.planner import Planner

from tests.helpers import card, fake_db, gs, mm


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode("utf-8")


class TestSnapshot(unittest.TestCase):
    def snap(self, **kw):
        s = gs(mana=3, hand=[card(1, "FEUERBALL")], opp=[mm(10, "Wolf", 2, 2)], mine=[mm(5, "Ei", 0, 2)], **kw)
        s.opp_name = "geheim#1234"
        plan = Planner(fake_db(), 0.3).plan(s, None)
        return api.build_snapshot(s, plan, None, "Text", False, None), plan

    def test_contains_plan_and_board(self):
        snap, plan = self.snap()
        self.assertEqual(snap["phase"], "plan")
        self.assertEqual(snap["board"]["opp"][0]["name"], "Wolf")
        self.assertEqual(len(snap["plan"]["steps"]), len(plan.steps))
        self.assertEqual(snap["me"]["mana"], 3)

    def test_no_player_names_leak(self):
        snap, _ = self.snap()
        self.assertNotIn("geheim", json.dumps(snap, ensure_ascii=False))

    def test_phases(self):
        s = gs(mana=3)
        self.assertEqual(api.phase_of(s, None), "thinking")
        self.assertEqual(api.phase_of(s, None, waiting=True), "waiting")
        s.my_active = False
        self.assertEqual(api.phase_of(s, None), "opponent")
        s.result = "WON"
        self.assertEqual(api.phase_of(s, None), "result")
        self.assertEqual(api.phase_of(None, None), "idle")


class TestHub(unittest.TestCase):
    def test_publish_dedupes_and_wait_wakes(self):
        hub = api.Hub()
        self.assertTrue(hub.publish({"phase": "plan", "text": "a"}))
        self.assertFalse(hub.publish({"phase": "plan", "text": "a", "updated": 5}))
        rev = hub.get()["rev"]
        threading.Timer(0.2, lambda: hub.publish({"phase": "plan", "text": "b"})).start()
        t0 = time.time()
        snap = hub.wait(rev, timeout=3)
        self.assertEqual(snap["text"], "b")
        self.assertLess(time.time() - t0, 2.5)

    def test_wait_times_out(self):
        hub = api.Hub()
        t0 = time.time()
        hub.wait(hub.get()["rev"], timeout=0.3)
        self.assertGreaterEqual(time.time() - t0, 0.25)


class TestAccess(unittest.TestCase):
    def test_client_rules(self):
        self.assertTrue(api.client_allowed("127.0.0.1", False))
        self.assertFalse(api.client_allowed("192.168.1.50", False))
        self.assertTrue(api.client_allowed("192.168.1.50", True))
        self.assertFalse(api.client_allowed("8.8.8.8", True))
        self.assertFalse(api.client_allowed("kaputt", True))

    def test_token(self):
        self.assertTrue(api.token_ok("", ""))
        self.assertTrue(api.token_ok("abc", "abc"))
        self.assertFalse(api.token_ok("abc", ""))
        self.assertFalse(api.token_ok("abc", "abd"))
        self.assertNotEqual(api.new_token(), api.new_token())


class TestServer(unittest.TestCase):
    def setUp(self):
        self.hub = api.Hub()
        self.hub.publish({"phase": "plan", "text": "1. Spiele X", "plan": {"steps": [{"n": 1, "title": "Spiele X", "text": "Spiele X"}]}})
        self.port = free_port()

    def run_server(self, token=""):
        srv = api.ApiServer(self.hub, self.port, False, token)
        self.assertTrue(srv.start(), srv.error)
        self.addCleanup(srv.stop)
        return f"http://127.0.0.1:{self.port}"

    def test_endpoints(self):
        base = self.run_server()
        self.assertEqual(json.loads(get(base + "/api/health")[1])["ok"], True)
        code, body = get(base + "/api/state")
        self.assertEqual((code, json.loads(body)["phase"]), (200, "plan"))
        self.assertEqual(json.loads(get(base + "/api/plan")[1])["plan"]["steps"][0]["title"], "Spiele X")
        self.assertEqual(get(base + "/api/plan.txt")[1], "1. Spiele X")
        code, html = get(base + "/")
        self.assertEqual(code, 200)
        self.assertIn("HS COACH", html)
        self.assertEqual(get(base + "/gibtsnicht")[0], 404)

    def test_token_enforced(self):
        base = self.run_server(token="geheim")
        self.assertEqual(get(base + "/api/state")[0], 401)
        self.assertEqual(get(base + "/api/state?token=falsch")[0], 401)
        self.assertEqual(get(base + "/api/state?token=geheim")[0], 200)
        self.assertEqual(get(base + "/api/state", {"X-Token": "geheim"})[0], 200)
        self.assertEqual(get(base + "/api/state", {"Authorization": "Bearer geheim"})[0], 200)

    def test_long_poll_returns_new_state(self):
        base = self.run_server()
        rev = json.loads(get(base + "/api/state")[1])["rev"]
        threading.Timer(0.3, lambda: self.hub.publish({"phase": "opponent", "text": "Gegner ist am Zug ..."})).start()
        code, body = get(f"{base}/api/state?since={rev}")
        self.assertEqual(json.loads(body)["phase"], "opponent")

    def test_port_in_use_reports_error(self):
        base = self.run_server()
        second = api.ApiServer(self.hub, self.port, False, "")
        self.assertFalse(second.start())
        self.assertIn("nicht verfügbar", second.error)


if __name__ == "__main__":
    unittest.main()


class TestSettingsKeys(unittest.TestCase):
    def test_api_port_is_validated(self):
        from hscoach import config, settings
        cfg = dict(config.DEFAULTS)
        import os, tempfile
        old = config.CONFIG_PATH
        config.CONFIG_PATH = os.path.join(tempfile.mkdtemp(), "c.json")
        try:
            changed = settings.apply(cfg, {"api_enabled": True, "api_port": "9100", "api_lan": True})
            self.assertEqual((cfg["api_port"], cfg["api_enabled"], cfg["api_lan"]), (9100, True, True))
            self.assertIn("api_port", changed)
            settings.apply(cfg, {"api_port": "80"})            # privilegierter Port: Standard bleibt/kehrt zurueck
            self.assertEqual(cfg["api_port"], 8765)
            settings.apply(cfg, {"api_port": "abc"})
            self.assertEqual(cfg["api_port"], 8765)
        finally:
            config.CONFIG_PATH = old
