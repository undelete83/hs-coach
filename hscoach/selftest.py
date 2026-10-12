"""Selbsttest der gebauten App: `HSCoach --selftest` (bzw. `python hs_coach.py --selftest`).

Prueft das, was im fertigen Paket schiefgehen kann, ohne Fenster zu zeigen: Tk laesst sich starten, alle Module laden,
eine HTTPS-Verbindung zu GitHub wird mit Zertifikatspruefung aufgebaut, der QR-Code laesst sich erzeugen.
Ergebnis auf stdout und in `<APP_DIR>/selftest.txt`; Exit-Code 0 = alles in Ordnung.
"""
import os
import sys
import urllib.error
import urllib.request

from . import __version__

URL = "https://github.com/"           # keine API: deren Limit fuer anonyme Abfragen trifft geteilte CI-Rechner


def run(stream=sys.stdout):
    results = []

    def check(name, fn):
        try:
            detail = fn() or ""
            results.append((True, name, detail))
        except Exception as ex:          # jede Ausnahme ist ein Befund
            results.append((False, name, f"{type(ex).__name__}: {ex}"))

    def tk_check():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        version = root.tk.call("info", "patchlevel")
        root.destroy()
        return f"Tk {version}"

    def modules():
        from . import api, board, gui, phone_ui, planner, update  # noqa: F401
        return "gui, planner, update, api, phone_ui"

    def https():
        req = urllib.request.Request(URL, headers={"User-Agent": "HSCoach/" + __version__})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return f"HTTP {resp.status}"
        except urllib.error.HTTPError as ex:     # Antwort kam an: Verbindung und Zertifikat sind in Ordnung
            return f"HTTP {ex.code} (Zertifikat in Ordnung)"

    def qr():
        from . import phone_ui
        if not phone_ui.QR_OK:
            raise RuntimeError("qrcode fehlt")
        return f"{phone_ui.qr_image('http://192.168.1.2:8765/?token=x').size[0]} px"

    check("Tk", tk_check)
    check("Module", modules)
    check("HTTPS (Zertifikate)", https)
    check("QR-Code", qr)
    ok = all(r[0] for r in results)
    lines = [f"HS Coach {__version__} Selbsttest: {'OK' if ok else 'FEHLER'}"]
    lines += [f"  {'✓' if good else '✗'} {name}: {detail}" for good, name, detail in results]
    text = "\n".join(lines) + "\n"
    try:
        stream.write(text)
        stream.flush()
    except Exception:
        pass
    try:
        from .config import APP_DIR
        os.makedirs(APP_DIR, exist_ok=True)
        with open(os.path.join(APP_DIR, "selftest.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    return 0 if ok else 1
