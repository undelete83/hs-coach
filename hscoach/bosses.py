"""Boss-Wissen: Erkennung des Gegners (Hero-Karte) und Aufbereitung fuer Oberflaeche, Engine und KI."""
from .bosses_data import BOSSES


class Boss:
    def __init__(self, d):
        self.d = d
        self.id = d["id"]
        self.name = d["name"]
        self.chapter = d["chapter"]
        self.order = d.get("order", 0)
        self.start_hp = d.get("start_hp")
        self.win_hp = d.get("win_hp", 0) or 0
        self.win_verified = bool(d.get("win_verified"))
        self.survive = d.get("survive")
        self.boss_power = d.get("boss_power", "")
        self.goal = d.get("goal", "")
        self.tips = list(d.get("tips", []))
        self.mulligan = list(d.get("mulligan", []))
        self.dangers = list(d.get("dangers", []))
        self.bias = dict(d.get("bias", {}))
        self.source = d.get("source", "")

    @property
    def title(self):
        return f"{self.name}  ({self.chapter}-Kapitel, Boss {self.order})" if self.order else self.name

    def lines(self):
        """Anzeigezeilen fuer die Boss-Info im Fenster."""
        out = []
        if self.goal:
            out.append("Ziel: " + self.goal)
        if self.win_hp:
            out.append(f"Siegschwelle: Kampf endet bei ≤ {self.win_hp} Boss-Leben"
                       + ("" if self.win_verified else " (laut Guide, nicht bestätigt)"))
        if self.survive:
            out.append(f"Überleben: {self.survive} Runden")
        if self.boss_power:
            out.append("Boss-Heldenkraft: " + self.boss_power)
        for t in self.tips:
            out.append("• " + t)
        if self.mulligan:
            out.append("Mulligan-Tipp: " + ", ".join(self.mulligan))
        for d in self.dangers:
            out.append("⚠ " + d)
        if self.source:
            out.append("Quelle: " + self.source)
        return out

    def prompt(self):
        """Kompakter Text fuer den KI-Prompt."""
        parts = [f"BOSS-KAMPF: {self.title}."]
        if self.goal:
            parts.append("Ziel: " + self.goal + ".")
        if self.win_hp:
            parts.append(f"Der Kampf endet, sobald der Boss {self.win_hp} Leben oder weniger hat.")
        if self.survive:
            parts.append(f"Es genügt, {self.survive} Runden zu überleben.")
        if self.boss_power:
            parts.append("Boss-Heldenkraft: " + self.boss_power + ".")
        if self.tips:
            parts.append("Guide-Tipps: " + " ".join(self.tips))
        if self.dangers:
            parts.append("Gefahren: " + "; ".join(self.dangers) + ".")
        return " ".join(parts)


_INDEX = {}
for _d in BOSSES:
    _b = Boss(_d)
    for _cid in _d["match"]:
        _INDEX[_cid] = _b


def find(opp_hero_cid):
    """Boss zu einer Hero-Karten-ID des Gegners (oder None)."""
    return _INDEX.get(opp_hero_cid or "")


def all_bosses():
    return list({id(b): b for b in _INDEX.values()}.values())
