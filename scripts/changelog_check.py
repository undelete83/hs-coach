#!/usr/bin/env python3
"""Zeigt Commits, die noch nicht im CHANGELOG.md erwaehnt sind (Hash in Backticks), damit nichts vergessen wird."""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
text = open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
mentioned = set(re.findall(r"`([0-9a-f]{7})`", text))
START = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=root, capture_output=True, text=True).stdout.split()[0]  # erster Commit
out = subprocess.run(["git", "log", "--format=%h %s", START + "..HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout
missing = [l for l in out.splitlines() if l.split(" ", 1)[0] not in mentioned]
print("Noch nicht im Aenderungsverlauf:" if missing else "Alles erfasst.")
for l in missing:
    print("  " + l)
