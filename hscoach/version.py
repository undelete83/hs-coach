"""Versionsinfo: Programmversion, laufender Commit und Hinweis, wenn im Repo schon etwas Neueres liegt."""
import os
import time

from . import REPO_DIR, __version__


def read_head(repo=REPO_DIR):
    """Kurz-Hash (7 Zeichen) des aktuellen Commits - direkt aus .git gelesen, ohne git-Aufruf. '' wenn unbekannt."""
    git = os.path.join(repo, ".git")
    try:
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head[:7]
        ref = head.split(":", 1)[1].strip()
        p = os.path.join(git, *ref.split("/"))
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()[:7]
        packed = os.path.join(git, "packed-refs")
        if os.path.exists(packed):
            with open(packed, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(" ")
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0][:7]
    except OSError:
        pass
    return ""


class BuildInfo:
    """Beim Programmstart festgehalten: Version, Commit, Startzeit."""

    def __init__(self, repo=REPO_DIR):
        self.repo = repo
        self.version = __version__
        self.commit = read_head(repo)
        self.started = time.strftime("%H:%M")

    @property
    def label(self):
        return f"v{self.version}" + (f" · {self.commit}" if self.commit else "")

    def newer_available(self):
        """Neuer Commit-Hash, wenn das Repo inzwischen weiter ist als das laufende Programm, sonst ''."""
        head = read_head(self.repo)
        return head if head and self.commit and head != self.commit else ""
