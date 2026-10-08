#!/usr/bin/env python3
"""Installiert den Pre-Commit-Hook (lokal in .git/hooks, wird nicht mitversioniert)."""
import os
import stat

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hook = os.path.join(root, ".git", "hooks", "pre-commit")
with open(hook, "w", newline="\n") as f:
    f.write('#!/bin/sh\nroot="$(git rev-parse --show-toplevel)"\nexec python "$root/scripts/check_secrets.py"\n')
os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)
print("Hook installiert:", hook)
