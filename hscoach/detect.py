"""Automatische Erkennung: Hearthstone-Log-Ordner, log.config (damit Power.log geschrieben wird)."""
import glob
import os
import string

LOG_CONFIG_TEXT = """[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=False
ScreenPrinting=False
Verbose=True
"""

_SUBDIRS = [r"Program Files (x86)\Hearthstone", r"Program Files\Hearthstone", r"Games\Blizzard\Hearthstone",
            r"Blizzard\Hearthstone", r"Games\Hearthstone", r"Hearthstone", r"Battle.net\Hearthstone",
            r"Program Files (x86)\Battle.net\Hearthstone"]


def _registry_install_dirs():
    out = []
    try:
        import winreg
    except ImportError:
        return out
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        with winreg.OpenKey(key, winreg.EnumKey(key, i)) as sub:
                            name = winreg.QueryValueEx(sub, "DisplayName")[0]
                            if str(name).strip().lower() == "hearthstone":
                                loc = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                if loc:
                                    out.append(loc)
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def candidate_install_dirs():
    dirs = []
    env = os.environ.get("HS_INSTALL_DIR")
    if env:
        dirs.append(env)
    dirs += _registry_install_dirs()
    for root in _fixed_drives():
        dirs += [os.path.join(root, sub) for sub in _SUBDIRS]
    return dirs


def _fixed_drives():
    """Nur lokale Festplatten (Netzlaufwerke koennen beim Abfragen minutenlang haengen)."""
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        roots = []
        for i, letter in enumerate(string.ascii_uppercase):
            root = f"{letter}:\\"
            if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(root) == 3:    # DRIVE_FIXED
                roots.append(root)
        return roots
    except Exception:
        return [f"{letter}:\\" for letter in "CDEFG" if os.path.exists(f"{letter}:\\")]


def find_log_dir(extra_candidates=()):
    """Ordner `.../Hearthstone/Logs` suchen. Bevorzugt den mit den neuesten Log-Unterordnern. None, wenn nicht gefunden."""
    best, best_time = None, -1
    for d in list(extra_candidates) + candidate_install_dirs():
        base = os.path.basename(d.rstrip("\\/"))
        logs = os.path.join(d, "Logs") if base.lower() != "logs" else d
        if not os.path.isdir(logs):
            continue
        subs = glob.glob(os.path.join(logs, "Hearthstone_*"))
        newest = max((os.path.getmtime(p) for p in subs), default=0)
        if subs and newest > best_time:
            best, best_time = logs, newest
        elif best is None and os.path.isdir(os.path.join(os.path.dirname(logs), "Hearthstone_Data")):
            best = logs                # Installation vorhanden, nur noch kein Log
    return best


def log_config_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Blizzard", "Hearthstone", "log.config")


def check_log_config(path=None):
    """'ok' | 'missing' | 'no_power' | 'disabled'  - schreibt Hearthstone die Power.log?"""
    path = path or log_config_path()
    if not os.path.exists(path):
        return "missing"
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return "missing"
    section, found, printing = None, False, False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].lower()
            found = found or section == "power"
        elif section == "power" and "=" in line:
            k, v = [x.strip().lower() for x in line.split("=", 1)]
            if k == "fileprinting":
                printing = v == "true"
    if not found:
        return "no_power"
    return "ok" if printing else "disabled"


def write_log_config(path=None):
    """Legt [Power] an bzw. aktiviert es; vorhandene Abschnitte bleiben erhalten. Sichert die alte Datei als .bak."""
    path = path or log_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            old = f.read()
        with open(path + ".bak", "w", encoding="utf-8") as f:
            f.write(old)
    # vorhandenen [Power]-Abschnitt entfernen, dann frisch anhaengen
    out, skip = [], False
    for raw in old.splitlines():
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            skip = s[1:-1].lower() == "power"
        if not skip:
            out.append(raw)
    text = "\n".join(out).rstrip()
    text = (text + "\n\n" if text else "") + LOG_CONFIG_TEXT
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path
