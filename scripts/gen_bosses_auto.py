"""Erzeugt hscoach/bosses_auto.py: Grundwissen (Name, Leben, Heldenkraft) fuer alle Gegner der Solo-Abenteuer
direkt aus den Kartendaten (HearthstoneJSON, deDE). Handgepflegtes Wissen steht in bosses_data.py und hat Vorrang.

Aufruf:  python scripts/gen_bosses_auto.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from hscoach.bosses_data import BOSSES  # noqa: E402

# Praefix der Hero-Karten-ID -> (Abenteuer, Reihenfolge der Anzeige)
ADVENTURES = [
    (r"NAX\d", "Naxxramas"),
    (r"BRMA", "Der Schwarzfels"),
    (r"LOEA", "Die Forscherliga"),
    (r"KARA|KAR_", None),                      # Karazhan ist handgepflegt
    (r"LOOTA", "Kobolde & Katakomben"),
    (r"GILA", "Der Hexenwald"),
    (r"TRLA", "Rastakhans Rumble"),
    (r"DALA", "Der Dalaran-Raubzug"),
    (r"ULDA", "Gräber des Terrors"),
    (r"DRGA", "Galakronds Erwachen"),
    (r"ICCA", "Ritter des Frostthrons"),
    (r"BOTA", "Das Boomsday-Projekt"),
    (r"TUTR", "Tutorial"),
    (r"BOM_", "Book of Mercenaries"),
]
CACHE = os.path.expandvars(r"%LOCALAPPDATA%\hs_coach\cards_deDE.json")
OUT = os.path.join(os.path.dirname(HERE), "hscoach", "bosses_auto.py")


def clean(t):
    t = re.sub(r"\[x\]|\[d\]", "", t or "")
    t = re.sub(r"</?[bi]>", "", t)
    t = t.replace("\n", " ").replace("$", "").replace("#", "")
    return re.sub(r"\s+", " ", t).strip()


def main():
    cards = json.load(open(CACHE, encoding="utf-8"))
    by_id = {c["id"]: c for c in cards}
    by_dbf = {c["dbfId"]: c for c in cards if "dbfId" in c}
    known = {cid for b in BOSSES for cid in b["match"]}
    groups = {}
    for c in cards:
        if c.get("type") != "HERO" or c["id"] in known:
            continue
        adv = None
        for pat, name in ADVENTURES:
            if re.match(pat, c["id"]):
                adv = name or ""
                break
        if not adv:
            continue
        hp = by_dbf.get(c.get("heroPowerDbfId"))
        power = ""
        if hp:
            power = clean(hp.get("text"))
            if hp.get("name"):
                cost = hp.get("cost")
                head = f"{hp['name']}" + (f" ({cost} Mana)" if cost not in (None, 0) else "")
                power = f"{head}: {power}" if power else head
        name = clean(c.get("name"))
        if not name:
            continue
        key = (adv, name, power)
        g = groups.setdefault(key, dict(match=[], hp=0))
        g["match"].append(c["id"])
        g["hp"] = max(g["hp"], c.get("health") or 0)
    lines = ['"""Automatisch erzeugt von scripts/gen_bosses_auto.py - nicht von Hand aendern (Handwissen: bosses_data.py)."""',
             "", "AUTO = ["]
    for (adv, name, power), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        lines.append("    " + repr(dict(match=sorted(g["match"]), name=name, chapter=adv, start_hp=g["hp"] or None, boss_power=power)) + ",")
    lines.append("]")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    per = {}
    for (adv, _n, _p) in groups:
        per[adv] = per.get(adv, 0) + 1
    print(len(groups), "Eintraege", per)


if __name__ == "__main__":
    main()
