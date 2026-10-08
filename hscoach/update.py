"""Update-Hinweis: fragt bei GitHub nach dem neuesten Release und meldet, wenn es neuer ist als diese Version.

Es wird nichts heruntergeladen oder installiert - nur ein Hinweis mit Link angezeigt. Schlaegt die Abfrage fehl
(offline, kein Release, Rate-Limit), bleibt alles stumm.
"""
import json
import logging
import re
import threading
import urllib.request

from . import __version__

log = logging.getLogger("hscoach.update")

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT_S = 6


def parse_version(text):
    """'v2.6.0' -> (2, 6, 0); None, wenn nichts Brauchbares drinsteht."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def is_newer(latest, current=__version__):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def check(repo, current=__version__, opener=urllib.request.urlopen):
    """(neue_version, url) wenn es ein neueres Release gibt, sonst None. Wirft nie."""
    if not repo or "/" not in repo:
        return None
    try:
        req = urllib.request.Request(API_URL.format(repo=repo), headers={
            "Accept": "application/vnd.github+json", "User-Agent": "HSCoach/" + current})
        with opener(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        if data.get("draft") or data.get("prerelease") or not is_newer(tag, current):
            return None
        return tag.lstrip("vV"), data.get("html_url") or f"https://github.com/{repo}/releases"
    except Exception as ex:
        log.info("Update-Abfrage ohne Ergebnis: %s", ex)
        return None


def check_async(cfg, callback, current=__version__):
    """Einmal im Hintergrund pruefen; callback((version, url)) nur bei einem neueren Release."""
    if not cfg.get("update_check"):
        return

    def _run():
        found = check(cfg.get("update_repo", ""), current)
        if found:
            callback(found)
    threading.Thread(target=_run, daemon=True, name="update-check").start()
