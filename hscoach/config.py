"""Konfiguration: Defaults + optionale JSON-Datei im Benutzerordner (enthaelt keine Secrets; der API-Key liegt separat)."""
import json
import os
import sys

if getattr(sys, "frozen", False):                     # als .exe (PyInstaller): Daten liegen neben/in der Anwendung
    REPO_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or _HOME, "HSCoach")
CONFIG_PATH = os.environ.get("HS_COACH_CONFIG", os.path.join(CONFIG_DIR, "config.json"))
LEGACY_CONFIG_PATH = os.path.join(_HOME, "hs_coach_config.json")        # fruehere Ablage (Version < 2.6)
APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or _HOME, "hs_coach")       # Cache, Logdatei

_HDT = os.path.join(os.environ.get("APPDATA") or _HOME, "HearthstoneDeckTracker")

DEFAULTS = {
    "log_dir": "",                    # leer = automatisch suchen
    "player_name": "",                # leer = automatisch erkennen (BattleTag wie im Spiel, z. B. Name#1234)
    "refresh_ms": 1000,
    "card_source": "auto",            # auto = HearthstoneJSON, ersatzweise HDT-Dateien | hearthstonejson | hdt
    "card_language": "deDE",
    "carddefs_de": os.path.join(_HDT, "CardDefs", "CardDefs.deDE.xml"),
    "carddefs_base": os.path.join(_HDT, "CardDefs", "CardDefs.base.xml"),
    "images_dir": os.path.join(APP_DIR, "portraits"),
    "key_path": os.path.join(CONFIG_DIR, "api_key.txt"),
    "claude_model": "claude-haiku-5-5",
    "analysis_model": "claude-sonnet-5-5",
    "use_claude": False,
    "api_timeout_s": 25,
    "geometry": "1680x1248",
    "always_on_top": False,
    "card_img_w": 200,
    "card_img_h": 303,
    "show_card_images": True,
    "sort_hand": "cost",
    "show_hand_images": False,
    "knowledge_path": os.path.join(REPO_DIR, "knowledge.md"),
    "reports_dir": os.path.join(CONFIG_DIR, "Berichte"),
    "obsidian_dir": "",               # optional: zusaetzlicher Ordner fuer Spielanalysen (z. B. in einem Obsidian-Vault)
    "auto_analysis": False,
    "plan_time_budget_s": 1.2,
    "update_check": True,
    "update_repo": "undelete83/hs-coach",
}

# $ pro 1 Mio Token: (input, output). Cache-Lesen = 10 %, Cache-Schreiben = 125 % vom Input.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5-5": (4.00, 20.00),
}
_FALLBACK_PRICE = (3.00, 15.00)


def price_for(model):
    base = model
    for k in PRICES:
        if model == k or model.startswith(k + "-"):
            base = k
            break
    return PRICES.get(base, _FALLBACK_PRICE)


def cost_usd(model, usage):
    pin, pout = price_for(model)
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    c_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    c_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (inp * pin + out * pout + c_read * pin * 0.1 + c_write * pin * 1.25) / 1_000_000


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def is_first_run():
    return not os.path.exists(CONFIG_PATH) and not os.path.exists(LEGACY_CONFIG_PATH)


def load(autodetect=True):
    cfg = dict(DEFAULTS)
    for path in (LEGACY_CONFIG_PATH, CONFIG_PATH):          # neuere Datei gewinnt
        if path == CONFIG_PATH or "HS_COACH_CONFIG" not in os.environ:
            try:
                cfg.update({k: v for k, v in _read_json(path).items() if k in DEFAULTS})
            except FileNotFoundError:
                pass
            except Exception as ex:                         # defekte Config darf den Start nicht verhindern
                print(f"[config] Fehler beim Lesen von {path}: {ex}")
    if autodetect and not cfg["log_dir"]:
        from . import detect
        cfg["log_dir"] = detect.find_log_dir() or ""
    return cfg


def save(cfg, keys=None):
    """Schreibt nur Werte, die von den Defaults abweichen (und die gewuenschten Schluessel) zurueck."""
    try:
        existing = {}
        try:
            existing = _read_json(CONFIG_PATH)
        except Exception:
            existing = {}
        for k in (keys or cfg.keys()):
            if k in DEFAULTS and cfg.get(k) != DEFAULTS[k]:
                existing[k] = cfg[k]
            else:
                existing.pop(k, None)
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        print(f"[config] Speichern fehlgeschlagen: {ex}")


# -- API-Key (getrennt von der Config, nie im Repo) ------------------------------------------------

def get_api_key(cfg):
    try:
        with open(cfg["key_path"], encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    except OSError:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def has_api_key(cfg):
    return bool(get_api_key(cfg))


def save_api_key(cfg, key):
    key = key.strip()
    os.makedirs(os.path.dirname(cfg["key_path"]), exist_ok=True)
    with open(cfg["key_path"], "w", encoding="utf-8") as f:
        f.write(key)
    try:
        os.chmod(cfg["key_path"], 0o600)
    except OSError:
        pass


def delete_api_key(cfg):
    try:
        os.remove(cfg["key_path"])
    except OSError:
        pass
