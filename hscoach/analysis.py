"""Spielzusammenfassung fuer die Analyse und Ablage der Berichte (lokal + Obsidian)."""
import os
import re
import time


def build_summary(s, tips, tracker_events_lines):
    """Text fuer Claude: Ergebnis, Endstand, alle Zuege und die gegebenen Tipps."""
    res = {"WON": "GEWONNEN", "LOST": "VERLOREN", "TIED": "UNENTSCHIEDEN"}.get(s.result, "unklar")
    L = [f"Ergebnis: {res} | Gegner: {s.opp_name} | Runden: {s.turn} | Spieltyp: {s.game_type}",
         f"Endstand: Ich {s.my_hp} LP, Gegner {s.opp_hp} LP",
         "Mein Board am Ende: " + (", ".join(f"{m.name} {m.atk}/{m.hp}" for m in s.my_minions) or "leer"),
         "Gegner Board am Ende: " + (", ".join(f"{m.name} {m.atk}/{m.hp}" for m in s.opp_minions) or "leer"),
         "Gegner hat gespielt: " + (", ".join(s.opp_played) or "?"),
         "", "ALLE ZÜGE (aus dem Log):"]
    L += tracker_events_lines
    if tips:
        L += ["", "TIPPS DES COACHES WÄHREND DER PARTIE:"]
        for turn, src, text in tips[-40:]:
            L.append(f"[R{turn} {src}] " + text.replace("\n", " ")[:400])
    return "\n".join(L)


def _slug(name):
    return re.sub(r"[^A-Za-z0-9äöüÄÖÜß_-]+", "_", name).strip("_")[:40] or "Spiel"


def save_report(cfg, s, markdown):
    """Speichert den Bericht lokal (und in Obsidian, falls vorhanden). Gibt die Pfade zurueck."""
    stamp = time.strftime("%Y-%m-%d_%H-%M")
    res = {"WON": "Sieg", "LOST": "Niederlage", "TIED": "Remis"}.get(s.result, "Spiel")
    fname = f"{stamp}_{res}_vs_{_slug(s.opp_name)}.md"
    head = f"# {res} gegen {s.opp_name} ({time.strftime('%d.%m.%Y %H:%M')})\n\n"
    paths = []
    for key in ("reports_dir", "obsidian_dir"):
        d = cfg.get(key)
        if not d:
            continue
        parent = os.path.dirname(d.rstrip("\\/"))
        if key == "obsidian_dir" and not os.path.isdir(parent):
            continue
        try:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, fname)
            with open(p, "w", encoding="utf-8") as f:
                f.write(head + markdown + "\n")
            paths.append(p)
        except OSError:
            pass
    return paths
