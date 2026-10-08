#!/usr/bin/env python3
"""Baut die Windows-Version (Ordner `dist/HSCoach/` + `dist/HSCoach-<version>.zip`) mit PyInstaller.

Aufruf:  python scripts/build_exe.py
Es wird ein eigenes virtuelles Environment (.venv-build) angelegt, damit nur die noetigen Pakete in der .exe landen.
"""
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv-build")
sys.path.insert(0, ROOT)

from hscoach import __version__  # noqa: E402


def run(*args, **kw):
    print(">", " ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kw)


def main():
    py = os.path.join(VENV, "Scripts", "python.exe")
    if not os.path.exists(py):
        run(sys.executable, "-m", "venv", VENV)
    run(py, "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(py, "-m", "pip", "install", "--quiet", "-r", "requirements.txt", "pyinstaller")
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    run(py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "HSCoach",
        "--add-data", "knowledge.md;.", "--collect-submodules", "anthropic", "hs_coach.py")
    out = os.path.join(ROOT, "dist", "HSCoach")
    for extra in ("README.md", "LICENSE", "CHANGELOG.md"):
        shutil.copy(os.path.join(ROOT, extra), out)
    zip_path = os.path.join(ROOT, "dist", f"HSCoach-{__version__}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(out):
            for f in files:
                p = os.path.join(base, f)
                z.write(p, os.path.join("HSCoach", os.path.relpath(p, out)))
    print(f"\nFertig: {zip_path} ({os.path.getsize(zip_path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
