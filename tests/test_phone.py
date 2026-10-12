import ipaddress
import unittest
from unittest import mock

from hscoach import api, phone_ui


class FakeServer:
    def __init__(self, port=8765, running=True):
        self.port, self.running = port, running


LAN_CFG = {"api_enabled": True, "api_lan": True, "api_token": "abc123"}


class TestPhoneUrl(unittest.TestCase):
    def test_url_with_and_without_token(self):
        self.assertEqual(api.phone_url("192.168.1.5", 8765, "abc"), "http://192.168.1.5:8765/?token=abc")
        self.assertEqual(api.phone_url("10.0.0.2", 9000), "http://10.0.0.2:9000/")

    def test_lan_ip_is_private_or_empty(self):
        ip = api.lan_ip()
        if ip:
            a = ipaddress.ip_address(ip)
            self.assertTrue(a.version == 4 and a.is_private and not a.is_loopback)

    def test_lan_ip_skips_loopback_and_public(self):
        with mock.patch.object(api.socket, "socket", side_effect=OSError), \
             mock.patch.object(api.socket, "gethostbyname_ex", return_value=("h", [], ["127.0.0.1", "8.8.8.8", "192.168.178.20"])):
            self.assertEqual(api.lan_ip(), "192.168.178.20")
        with mock.patch.object(api.socket, "socket", side_effect=OSError), \
             mock.patch.object(api.socket, "gethostbyname_ex", side_effect=OSError):
            self.assertEqual(api.lan_ip(), "")


class TestPhoneState(unittest.TestCase):
    def test_ok_uses_running_port_and_token(self):
        self.assertEqual(phone_ui.phone_state(LAN_CFG, FakeServer(8800), "192.168.1.9"),
                         ("ok", "http://192.168.1.9:8800/?token=abc123"))

    def test_off_when_api_not_in_lan(self):
        for cfg, srv in ((dict(LAN_CFG, api_lan=False), FakeServer()), (dict(LAN_CFG, api_enabled=False), FakeServer()),
                         (LAN_CFG, None), (LAN_CFG, FakeServer(running=False))):
            self.assertEqual(phone_ui.phone_state(cfg, srv, "192.168.1.9")[0], "off")

    def test_no_ip(self):
        self.assertEqual(phone_ui.phone_state(LAN_CFG, FakeServer(), "")[0], "noip")


@unittest.skipUnless(phone_ui.QR_OK, "qrcode nicht installiert")
class TestQrImage(unittest.TestCase):
    def test_square_black_and_white(self):
        img = phone_ui.qr_image("http://192.168.1.127:8765/?token=abc123")
        self.assertEqual(img.size[0], img.size[1])
        self.assertGreaterEqual(img.size[0], 200)
        self.assertLessEqual(set(img.getdata()), {(0, 0, 0), (255, 255, 255)})


class TestPhoneWindow(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
        except Exception:
            self.skipTest("kein Tk")
        self.addCleanup(self.root.destroy)
        self.root.cfg = dict(LAN_CFG)
        self.root.api_server = FakeServer()

    def test_shows_url_and_qr(self):
        with mock.patch.object(api, "lan_ip", return_value="192.168.1.50"):
            win = phone_ui.PhoneWindow(self.root)
        self.assertEqual(win.lbl_url.cget("text"), "http://192.168.1.50:8765/?token=abc123")
        if phone_ui.QR_OK:
            self.assertIsNotNone(win._photo)
        win._close()

    def test_enable_button_switches_api_on(self):
        self.root.cfg = {"api_token": ""}
        self.root.api_server = None
        started = []

        def apply():
            started.append(True)
            self.root.api_server = FakeServer()
        self.root._api_apply = apply
        with mock.patch.object(api, "lan_ip", return_value="192.168.1.50"), \
             mock.patch.object(phone_ui.config, "save") as save:
            win = phone_ui.PhoneWindow(self.root)
            self.assertEqual(win._shown[0], "off")
            win._enable()
        self.assertTrue(started)
        self.assertTrue(self.root.cfg["api_enabled"] and self.root.cfg["api_lan"] and self.root.cfg["api_token"])
        save.assert_called_once()
        self.assertEqual(win._shown[0], "ok")
        win._close()


if __name__ == "__main__":
    unittest.main()
