#!/usr/bin/env python3
"""Pre-Commit-Schutz: bricht ab, wenn ein Anthropic-API-Key oder die Key-Datei committet werden soll."""
import re
import subprocess
import sys

PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")
FORBIDDEN_NAMES = ("hs_coach_key.txt", "api_key.txt", ".env")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    if "--all" in sys.argv:          # alle versionierten Dateien (z. B. in der CI), nicht nur Gestagetes
        staged = [f for f in git("ls-files").stdout.split("\n") if f]
        ref = "HEAD"
    else:
        staged = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACM").stdout.split("\n") if f]
        ref = ""
    bad = []
    for f in staged:
        if f.replace("\\", "/").split("/")[-1] in FORBIDDEN_NAMES:
            bad.append(f"{f}: verbotene Datei")
            continue
        if f.endswith((".gz", ".png", ".pyc")):
            continue
        content = git("show", f"{ref}:{f}").stdout
        if PATTERN.search(content):
            bad.append(f"{f}: sieht aus wie ein Anthropic-API-Key")
    if bad:
        print("COMMIT ABGEBROCHEN - moegliche Secrets:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
