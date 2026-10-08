#!/usr/bin/env python3
"""HS Coach - Startdatei. Aufruf: pythonw hs_coach.py (oder python hs_coach.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hscoach.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
