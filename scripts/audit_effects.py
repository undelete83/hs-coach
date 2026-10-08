#!/usr/bin/env python3
"""Prueft, wie viele sammelbare Karten der Effekt-Parser versteht.

Aufruf:  python scripts/audit_effects.py [--list] [--cards <Name,Name,...>]

Liest die von HS Coach zwischengespeicherten HearthstoneJSON-Daten (erst einmal den Coach starten). Zeigt den Anteil der
Zauber ohne erkannten Effekt und mit `--list` die unbekannten Zauber samt Text, damit neue Muster gezielt ergaenzt
werden koennen. Mit `--cards` werden nur Karten mit diesen Namen untersucht.
"""
import collections
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hscoach import config  # noqa: E402
from hscoach.effects import clean_text, parse_effect  # noqa: E402


def main():
    path = os.path.join(config.APP_DIR, "cards_deDE.json")
    if not os.path.exists(path):
        sys.exit(f"Kartendaten fehlen ({path}). Bitte den Coach einmal starten, damit sie geladen werden.")
    with open(path, encoding="utf-8") as f:
        cards = json.load(f)
    names = None
    if "--cards" in sys.argv:
        names = {n.strip().lower() for n in sys.argv[sys.argv.index("--cards") + 1].split(",")}
    spells = [c for c in cards if c.get("collectible") and c.get("type") == "SPELL"
              and (names is None or c.get("name", "").lower() in names)]
    unknown = [c for c in spells if parse_effect(c.get("text", ""), "SPELL", secret=bool(c.get("secret"))).unknown]
    print(f"Sammelbare Zauber: {len(spells)}, davon ohne erkannten Effekt: {len(unknown)} "
          f"({100 * len(unknown) / max(1, len(spells)):.0f} %)")
    by_class = collections.Counter(c.get("cardClass", "?") for c in unknown)
    print("Nach Klasse:", ", ".join(f"{k} {v}" for k, v in by_class.most_common()))
    if "--list" in sys.argv:
        for c in sorted(unknown, key=lambda c: (c.get("cardClass", ""), c.get("name", ""))):
            print(f"  [{c.get('cardClass', '?')}] {c.get('name')} ({c.get('cost')}): {clean_text(c.get('text', ''))[:160]}")


if __name__ == "__main__":
    main()
