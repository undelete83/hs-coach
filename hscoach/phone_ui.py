"""Fenster "Handy": QR-Code mit der Adresse der Plan-Webseite (aktuelle IP im Heimnetz, Port, Zugangscode).

Mit der Handykamera scannen -> der Zugplan erscheint im Browser. Die Adresse wird alle paar Sekunden neu ermittelt,
damit der Code nach einem IP-Wechsel (anderes WLAN, neue DHCP-Adresse) stimmt.
"""
import tkinter as tk

from . import api, config, widgets, winstyle

BG, FG, GOLD, GRAY, GREEN, ORANGE = "#0d0d1a", "#e8e8ff", "#ffd700", "#888899", "#66ff88", "#ffaa44"
REFRESH_MS = 5000
QR_PX = 300

try:
    import qrcode
    from PIL import ImageTk
    QR_OK = True
except ImportError:            # ohne qrcode-Paket zeigt das Fenster nur die Adresse
    QR_OK = False


def qr_image(text, size=QR_PX):
    """PIL-Bild des QR-Codes (schwarz auf weiss, mit Rand), quadratisch etwa `size` Pixel."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=3)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")
    n = max(1, size // img.size[0])
    return img.resize((img.size[0] * n, img.size[1] * n), 0)       # 0 = NEAREST: Module bleiben scharf


def phone_state(cfg, server, ip):
    """("ok", url) | ("off", hinweis) | ("noip", hinweis) - was das Fenster gerade zeigen soll."""
    if not cfg.get("api_enabled") or not cfg.get("api_lan") or server is None or not getattr(server, "running", False):
        return "off", ("Die Plan-API ist für das Heimnetz noch nicht eingeschaltet. Mit dem Knopf unten wird sie aktiviert "
                       "(nur lesend, mit Zugangscode, nur aus dem Heimnetz erreichbar).")
    if not ip:
        return "noip", "Keine Heimnetz-Adresse gefunden. Ist dieser Rechner mit dem WLAN/LAN verbunden?"
    return "ok", api.phone_url(ip, server.port, cfg.get("api_token", ""))


class PhoneWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Zugplan aufs Handy - HS Coach")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._photo = None
        self._shown = None
        self._job = None
        self._build()
        winstyle.style_titlebar(self)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.refresh()

    def _build(self):
        tk.Label(self, text="📱 Zugplan aufs Handy", bg=BG, fg=GOLD, font=("Segoe UI", 15, "bold")).pack(pady=(14, 2))
        tk.Label(self, text="Mit der Handykamera scannen. Handy und Rechner müssen im selben WLAN sein.",
                 bg=BG, fg=GRAY, font=("Segoe UI", 10)).pack(padx=18)
        self.qr = tk.Label(self, bg=BG)
        self.qr.pack(padx=18, pady=12)
        self.lbl_url = tk.Label(self, text="", bg=BG, fg=FG, font=("Consolas", 11), wraplength=440, justify="center")
        self.lbl_url.pack(padx=18)
        self.lbl_hint = tk.Label(self, text="", bg=BG, fg=GRAY, font=("Segoe UI", 9), wraplength=440, justify="center")
        self.lbl_hint.pack(padx=18, pady=(6, 0))
        bar = tk.Frame(self, bg=BG)
        bar.pack(pady=14)
        self.btn_enable = widgets.Button(bar, text="Plan-API im Heimnetz einschalten", command=self._enable, bg="#2a5a2a",
                                         fg="white", relief="flat", cursor="hand2")
        self.btn_copy = widgets.Button(bar, text="Adresse kopieren", command=self._copy, bg="#1a1a3e", fg=GOLD,
                                       relief="flat", cursor="hand2")
        self.btn_copy.pack(side="left", padx=4)
        widgets.Button(bar, text="Schließen", command=self._close, bg="#1a1a3e", fg=GOLD, relief="flat",
                       cursor="hand2").pack(side="left", padx=4)

    def refresh(self):
        """Zustand neu bestimmen (IP kann wechseln) und nur bei Aenderung neu zeichnen."""
        self._job = None
        if not self.winfo_exists():
            return
        state = phone_state(self.app.cfg, self.app.api_server, api.lan_ip())
        if state != self._shown:
            self._shown = state
            self._render(*state)
        self._job = self.after(REFRESH_MS, self.refresh)

    def _render(self, kind, text):
        if kind == "ok":
            self.btn_enable.pack_forget()
            self.lbl_url.config(text=text, fg=FG)
            if QR_OK:
                self._photo = ImageTk.PhotoImage(qr_image(text))
                self.qr.config(image=self._photo, text="", width=0, height=0)
                self.lbl_hint.config(text="Tipp: In Safari/Chrome „Zum Home-Bildschirm“ wählen. Der Code enthält den "
                                          "Zugangscode – nicht öffentlich teilen.", fg=GRAY)
            else:
                self.qr.config(image="", text="(QR-Code braucht das Paket „qrcode“)", fg=GRAY)
                self.lbl_hint.config(text="Adresse im Handy-Browser eingeben.", fg=GRAY)
        else:
            self._photo = None
            self.qr.config(image="", text="", width=1, height=1)
            self.lbl_url.config(text=text, fg=ORANGE)
            self.lbl_hint.config(text="")
            if kind == "off":
                self.btn_enable.pack(side="left", padx=4, before=self.btn_copy)
            else:
                self.btn_enable.pack_forget()

    def _enable(self):
        cfg = self.app.cfg
        cfg["api_enabled"] = True
        cfg["api_lan"] = True
        if not cfg.get("api_token"):
            cfg["api_token"] = api.new_token()
        config.save(cfg, ["api_enabled", "api_lan", "api_token"])
        self.app._api_apply()
        self._shown = None
        if self.app.api_server is None:
            self.lbl_hint.config(text="Plan-API konnte nicht starten – Port belegt? Siehe ⚙ Einstellungen.", fg=ORANGE)
        if self._job:
            self.after_cancel(self._job)
        self.refresh()

    def _copy(self):
        if self._shown and self._shown[0] == "ok":
            self.clipboard_clear()
            self.clipboard_append(self._shown[1])
            self.lbl_hint.config(text="Adresse kopiert.", fg=GREEN)

    def _close(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.destroy()
