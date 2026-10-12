#!/usr/bin/env python3
"""Baut die Mac-Version (`dist/HSCoach.app` + `dist/HSCoach-<version>-mac.zip`) mit PyInstaller.

Aufruf:  python3 scripts/build_mac.py
Voraussetzung: ein Python mit Tk (z. B. Homebrew `python@3.14` + `python-tk@3.14`).
Es wird ein eigenes virtuelles Environment (.venv-build) angelegt, damit nur die noetigen Pakete in der App landen.
"""
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv-build")
sys.path.insert(0, ROOT)

from hscoach import __version__  # noqa: E402


def run(*args, **kw):
    print(">", " ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kw)


def main():
    if sys.platform != "darwin":
        sys.exit("Nur auf macOS. Fuer Windows: scripts/build_exe.py")
    py = os.path.join(VENV, "bin", "python")
    if not os.path.exists(py):
        run(sys.executable, "-m", "venv", VENV)
    run(py, "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(py, "-m", "pip", "install", "--quiet", "-r", "requirements.txt", "pyinstaller")
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    run(py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "HSCoach",
        "--osx-bundle-identifier", "io.github.undelete83.hscoach",
        "--add-data", "knowledge.md:.", "--collect-submodules", "anthropic", "hs_coach.py")
    app = os.path.join(ROOT, "dist", "HSCoach.app")
    plist = os.path.join(app, "Contents", "Info.plist")
    with open(plist, "rb") as f:
        info = plistlib.load(f)
    info.update(CFBundleShortVersionString=__version__, CFBundleVersion=__version__,
                NSHighResolutionCapable=True)
    with open(plist, "wb") as f:
        plistlib.dump(info, f)
    run("codesign", "--force", "--deep", "--sign", "-", app)            # ad-hoc, damit macOS die App startet
    zip_path = os.path.join(ROOT, "dist", f"HSCoach-{__version__}-mac.zip")
    run("ditto", "-c", "-k", "--keepParent", app, zip_path)              # ditto erhaelt Symlinks und Rechte
    with open(zip_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(zip_path + ".sha256", "w", encoding="ascii", newline="\n") as f:
        f.write(f"{digest}  {os.path.basename(zip_path)}\n")
    print(f"\nFertig: {app}\n        {zip_path} ({os.path.getsize(zip_path) / 1e6:.1f} MB)\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
