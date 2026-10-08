"""Updates: Hinweis auf neue GitHub-Releases und (nur bei der .exe) Selbst-Update.

Ablauf des Selbst-Updates: Zip laden -> Pruefsumme (SHA-256 aus der GitHub-Release-API) kontrollieren -> sicher
entpacken -> ein kleines Batch-Skript wartet, bis der Coach beendet ist, ersetzt dann die Programmdateien (mit
Rueckfall auf die alte Version, wenn das Kopieren scheitert) und startet den Coach neu. Einstellungen, API-Key und
Berichte liegen ausserhalb des Programmordners und bleiben unberuehrt.

Schlaegt die Abfrage fehl (offline, kein Release, Rate-Limit), bleibt alles stumm.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile
from collections import namedtuple

from . import __version__

log = logging.getLogger("hscoach.update")

# Fuer Tests (lokaler Server) ueberschreibbar; die Vorlage braucht {repo}.
API_URL = os.environ.get("HS_COACH_UPDATE_URL") or "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT_S = 6
MAX_ZIP_BYTES = 300 * 1024 * 1024
EXE_NAME = "HSCoach.exe"
ASSET_RE = re.compile(r"^HSCoach-[\w.\-]+\.zip$")

Release = namedtuple("Release", "version url asset_url asset_name size sha256")


class UpdateError(Exception):
    pass


def parse_version(text):
    """'v2.6.0' -> (2, 6, 0); None, wenn nichts Brauchbares drinsteht."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def is_newer(latest, current=__version__):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def _fetch(url, opener, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "HSCoach/" + __version__})
    with opener(req, timeout=TIMEOUT_S) as resp:
        return resp.read()


def _asset_info(data, opener):
    """(name, url, size, sha256) des Programm-Zips im Release - oder Leerwerte."""
    assets = data.get("assets") or []
    for a in assets:
        name = str(a.get("name") or "")
        if not ASSET_RE.match(name):
            continue
        sha = str(a.get("digest") or "")
        sha = sha.split(":", 1)[1].lower() if sha.lower().startswith("sha256:") else ""
        if not sha:                                      # ersatzweise Datei "<zip>.sha256" im Release
            for b in assets:
                if b.get("name") == name + ".sha256":
                    try:
                        m = re.match(r"[0-9a-fA-F]{64}", _fetch(b.get("browser_download_url", ""), opener, "*/*").decode("ascii", "ignore"))
                        sha = m.group(0).lower() if m else ""
                    except Exception as ex:
                        log.info("Pruefsummen-Datei nicht lesbar: %s", ex)
        return name, str(a.get("browser_download_url") or ""), int(a.get("size") or 0), sha
    return "", "", 0, ""


def check_now(repo, current=__version__, opener=urllib.request.urlopen):
    """Genaues Ergebnis fuer die manuelle Pruefung: ("new", Release) | ("current", None) | ("error", Meldung). Wirft nie."""
    if not repo or "/" not in repo:
        return "error", "Es ist kein Update-Repository eingestellt."
    try:
        data = json.loads(_fetch(API_URL.format(repo=repo), opener, "application/vnd.github+json").decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        if data.get("draft") or data.get("prerelease") or not is_newer(tag, current):
            return "current", None
        name, url, size, sha = _asset_info(data, opener)
        return "new", Release(tag.lstrip("vV"), data.get("html_url") or f"https://github.com/{repo}/releases",
                              url, name, size, sha)
    except Exception as ex:
        log.info("Update-Abfrage ohne Ergebnis: %s", ex)
        return "error", str(ex)


def check(repo, current=__version__, opener=urllib.request.urlopen):
    """Release-Info, wenn es ein neueres Release gibt, sonst None. Wirft nie."""
    status, result = check_now(repo, current, opener)
    return result if status == "new" else None


def check_async(cfg, callback, current=__version__):
    """Einmal im Hintergrund pruefen; callback(Release) nur bei einem neueren Release."""
    if not cfg.get("update_check"):
        return

    def _run():
        found = check(cfg.get("update_repo", ""), current)
        if found:
            callback(found)
    threading.Thread(target=_run, daemon=True, name="update-check").start()


def check_now_async(cfg, callback, current=__version__):
    """Manuelle Pruefung im Hintergrund (ignoriert die Einstellung `update_check`); callback(status, ergebnis)."""
    def _run():
        callback(*check_now(cfg.get("update_repo", ""), current))
    threading.Thread(target=_run, daemon=True, name="update-check-manual").start()


# -- Selbst-Update ---------------------------------------------------------------------------------

def app_dir():
    return os.path.dirname(os.path.abspath(sys.executable))


def can_self_update(directory=None, frozen=None):
    """Nur die installierte .exe darf sich ersetzen - und nur, wenn der Ordner beschreibbar und das Skript sicher ist."""
    if os.name != "nt" or not (getattr(sys, "frozen", False) if frozen is None else frozen):
        return False
    d = directory or app_dir()
    if not os.path.isfile(os.path.join(d, EXE_NAME)) or not os.path.isdir(os.path.join(d, "_internal")):
        return False
    if any(c in d for c in '%!^&"\r\n'):             # wuerde das Batch-Skript verwirren
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=d):
            pass
    except OSError:
        return False
    return True


def _allowed_url(url, repo):
    if url.startswith(f"https://github.com/{repo}/releases/download/"):
        return True
    override = os.environ.get("HS_COACH_UPDATE_URL")
    if override:                                       # nur zum Testen gegen einen lokalen Server
        o = urllib.parse.urlparse(override)
        return url.startswith(f"{o.scheme}://{o.netloc}/")
    return False


def download(release, repo, dest_dir, progress=None, opener=urllib.request.urlopen):
    """Laedt das Zip nach dest_dir und prueft Groesse und SHA-256. Gibt den Pfad zurueck."""
    if not release.asset_url or not release.sha256:
        raise UpdateError("Dieses Release enthaelt kein pruefbares Programmpaket.")
    if not _allowed_url(release.asset_url, repo):
        raise UpdateError("Unerwartete Download-Adresse.")
    if release.size > MAX_ZIP_BYTES:
        raise UpdateError("Das Paket ist ungewoehnlich gross.")
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, release.asset_name)
    part = path + ".part"
    h, done = hashlib.sha256(), 0
    req = urllib.request.Request(release.asset_url, headers={"User-Agent": "HSCoach/" + __version__, "Accept": "*/*"})
    try:
        with opener(req, timeout=30) as resp, open(part, "wb") as f:
            total = int(resp.headers.get("Content-Length") or release.size or 0)
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_ZIP_BYTES:
                    raise UpdateError("Das Paket ist ungewoehnlich gross.")
                h.update(chunk)
                f.write(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        raise
    except Exception as ex:
        raise UpdateError(f"Download fehlgeschlagen: {ex}") from ex
    if release.size and done != release.size:
        raise UpdateError("Download unvollstaendig.")
    if h.hexdigest().lower() != release.sha256.lower():
        os.remove(part)
        raise UpdateError("Die Pruefsumme stimmt nicht - das Paket wird nicht installiert.")
    os.replace(part, path)
    return path


def extract(zip_path, dest_dir):
    """Entpackt sicher (kein Ausbruch aus dest_dir) und gibt den Ordner mit der neuen HSCoach.exe zurueck."""
    root = os.path.realpath(dest_dir)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = os.path.realpath(os.path.join(root, info.filename))
            if target != root and not target.startswith(root + os.sep):
                raise UpdateError("Ungueltiges Paket (Pfad ausserhalb des Zielordners).")
        z.extractall(root)
    new = os.path.join(root, "HSCoach")
    if not (os.path.isfile(os.path.join(new, EXE_NAME)) and os.path.isdir(os.path.join(new, "_internal"))):
        raise UpdateError("Ungueltiges Paket (HSCoach.exe oder _internal fehlt).")
    return new


_SYS32 = "%SystemRoot%\\System32\\"      # absolute Pfade: ein anderes `find` im PATH (z. B. von Git) darf nicht stoeren


def build_script(directory, new_dir, work_dir, pid, exe_name=EXE_NAME, proc_name=None):
    """Batch-Skript: wartet auf das Ende des Coaches, tauscht die Dateien aus (mit Rueckfall) und startet neu."""
    return "\r\n".join([
        "@echo off",
        "chcp 65001 >nul",
        f'set "APP={directory}"',
        f'set "NEW={new_dir}"',
        f'set "WORK={work_dir}"',
        "set /a n=0",
        ":wait",
        f'"{_SYS32}tasklist.exe" /FI "PID eq {int(pid)}" /NH 2>nul | "{_SYS32}find.exe" /I "{proc_name or exe_name}" >nul',
        "if errorlevel 1 goto swap",
        "set /a n+=1",
        "if %n% GEQ 90 goto abort",
        f'"{_SYS32}ping.exe" -n 2 127.0.0.1 >nul',
        "goto wait",
        ":swap",
        'if exist "%APP%\\_internal.bak" rmdir /S /Q "%APP%\\_internal.bak"',
        'rename "%APP%\\_internal" _internal.bak',
        "if errorlevel 1 goto start",
        f'"{_SYS32}robocopy.exe" "%NEW%" "%APP%" /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP >nul',
        "if errorlevel 8 goto rollback",
        'rmdir /S /Q "%APP%\\_internal.bak"',
        "goto start",
        ":rollback",
        'if exist "%APP%\\_internal" rmdir /S /Q "%APP%\\_internal"',
        'rename "%APP%\\_internal.bak" _internal',
        ":start",
        f'start "" "%APP%\\{exe_name}"',
        ":abort",
        '(goto) 2>nul & rmdir /S /Q "%WORK%"',
        "",
    ])


def _clean_env():
    """PyInstaller markiert die Umgebung; ein neu gestartetes Programm muss sich frisch entpacken."""
    return {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}


def launch(script_path):
    flags = 0x08000000 | 0x00000200      # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP (DETACHED_PROCESS laesst Pipes im Skript haengen)
    subprocess.Popen(["cmd.exe", "/c", script_path], creationflags=flags, close_fds=True, env=_clean_env(),
                     cwd=os.path.dirname(os.path.dirname(script_path)), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def prepare(release, repo, work_dir, progress=None, opener=urllib.request.urlopen):
    """Download, Pruefung, Entpacken. Gibt den Ordner mit der neuen Version zurueck."""
    shutil.rmtree(work_dir, ignore_errors=True)
    zip_path = download(release, repo, work_dir, progress, opener)
    return extract(zip_path, os.path.join(work_dir, "new"))


def install_and_restart(new_dir, work_dir, directory=None, pid=None):
    """Schreibt und startet das Austausch-Skript. Danach muss sich der Coach sofort beenden."""
    script = os.path.join(work_dir, "update.cmd")
    with open(script, "w", encoding="utf-8", newline="") as f:
        f.write(build_script(directory or app_dir(), new_dir, work_dir, pid or os.getpid()))
    launch(script)
