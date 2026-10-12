#!/usr/bin/env python3
"""Schreibt die Release-Notes einer Version (Abschnitt aus CHANGELOG.md plus Download-Hinweise) als UTF-8-Datei.

Aufruf:  python scripts/release_notes.py 2.17.2 notes.md
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEAD = ("**Downloads**\n"
        "- **Windows**: `HSCoach-{v}.zip` laden, entpacken, `HSCoach.exe` starten. Installierte Versionen ab 2.17.1 "
        "aktualisieren sich per Klick selbst.\n"
        "- **Mac**: `HSCoach-{v}-mac.zip` laden, entpacken, `HSCoach.app` nach `/Applications` ziehen (beim ersten Start "
        "Rechtsklick → Öffnen, die App ist nicht notariell beglaubigt). Ab 2.17.1 aktualisiert sie sich per Klick selbst.\n\n")


def section(changelog, version):
    """Text unter `## <version> - ...` bis zur naechsten Versionsueberschrift; ValueError, wenn es ihn nicht gibt."""
    m = re.search(rf"^## {re.escape(version)} - .*?$(.*?)(?=^## \d|\Z)", changelog, re.M | re.S)
    if not m or not m.group(1).strip():
        raise ValueError(f"Kein CHANGELOG-Eintrag fuer {version}")
    return m.group(1).strip()


def main():
    version, out = sys.argv[1].lstrip("vV"), sys.argv[2]
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        body = section(f.read(), version)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEAD.format(v=version) + body + "\n")


if __name__ == "__main__":
    main()
