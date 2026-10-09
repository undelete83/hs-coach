"""HS Coach - Live-Coaching fuer Hearthstone auf Basis von Power.log."""
import logging
import logging.handlers
import os
import sys

__version__ = "2.9.6"
if getattr(sys, "frozen", False):          # als .exe (PyInstaller)
    REPO_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_configured = False


def setup_logging():
    """Log-Datei unter %LOCALAPPDATA%\\hs_coach (unter pythonw gibt es keine Konsole)."""
    global _configured
    if _configured:
        return logging.getLogger("hscoach")
    from .config import APP_DIR
    os.makedirs(APP_DIR, exist_ok=True)
    log = logging.getLogger("hscoach")
    log.setLevel(logging.INFO)
    try:
        h = logging.handlers.RotatingFileHandler(
            os.path.join(APP_DIR, "hs_coach.log"), maxBytes=500_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(h)
    except Exception:
        pass
    _configured = True
    return log
