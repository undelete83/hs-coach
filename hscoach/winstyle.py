"""Windows-Feinheiten: Titelleiste im dunklen Stil des Programms (Windows 10/11, sonst wirkungslos)."""

CAPTION = "#12122b"      # Titelleiste
TEXT = "#c8c8e8"         # Titeltext
BORDER = "#222244"       # Fensterrahmen (nur Windows 11)


def _colorref(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return r | (g << 8) | (b << 16)


def style_titlebar(win, caption=CAPTION, text=TEXT, border=BORDER):
    """Dunkle Titelleiste fuer ein Tk-Fenster. Gibt True zurueck, wenn Windows die Einstellung angenommen hat."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = int(win.wm_frame(), 16)
        dwm = ctypes.windll.dwmapi

        def put(attr, value):
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), ctypes.sizeof(v)) == 0
        dark = put(20, 1) or put(19, 1)                 # dunkler Modus (Windows 10 20H1+/11, aeltere Builds: 19)
        put(35, _colorref(caption))                      # Titelleistenfarbe (Windows 11)
        put(36, _colorref(text))                         # Titeltext (Windows 11)
        put(34, _colorref(border))                       # Rahmen (Windows 11)
        return dark
    except Exception:
        return False
