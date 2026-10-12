#!/usr/bin/env python3
"""HS Coach - Startdatei. Aufruf: pythonw hs_coach.py (oder python hs_coach.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if "--selftest" in sys.argv:                 # Pruefung des fertigen Pakets (CI), zeigt kein Fenster
        from hscoach.selftest import run
        sys.exit(run())
    from hscoach.gui import main
    main()
