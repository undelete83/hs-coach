"""Kartentext (deutsch) -> strukturierter Effekt fuer den Planer.

Bewusst konservativ: was nicht sicher erkannt wird, wird ignoriert bzw. als `unknown`
markiert. Bedingte Effekte ("wenn", "nachdem", ...) werden nicht simuliert.
"""
import re
from dataclasses import dataclass, field

_WORDNUM = {"ein": 1, "eine": 1, "einen": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5}

RACE_WORDS = {
    "elementar": "ELEMENTAL", "elementare": "ELEMENTAL", "drache": "DRAGON", "drachen": "DRAGON",
    "dämon": "DEMON", "dämonen": "DEMON", "mech": "MECHANICAL", "bestie": "BEAST", "bestien": "BEAST",
    "pirat": "PIRATE", "piraten": "PIRATE", "murloc": "MURLOC", "totem": "TOTEM", "untoter": "UNDEAD",
}

_HOLD = re.compile(r",?\s*wenn ihr einen (\w+) auf der hand habt$")
_MISSILES_SPLIT = re.compile(r"verursacht (\d+) schaden, der zufällig auf alle feinde verteilt wird")
_MISSILES_SHOT = re.compile(r"verschießt (\d+) geschosse auf zufällige feinde, die je (\d+) schaden verursachen")
_SELF_BUFF =re.compile(r"erhält \+(\d+)(?: angriff|/\+(\d+))(?: und (spott|eifer|ansturm))?$")
_HOLD_REJECT =re.compile(r"zufällig|verletzt|legendär|anderen|mind|oder mehr|\bmit\b(?!\s+(max|\d+ oder weniger))")
_COND = re.compile(r"\b(wenn|falls|nachdem|sobald|jedes mal|jedesmal|am ende|zu beginn|immer wenn|solange)\b")


@dataclass
class Effect:
    dmg: int = 0                  # Einzelziel-Schaden
    dmg_target: str = ""          # any | minion | enemy | enemy_minion | face | friendly_minion
    aoe_dmg: int = 0
    aoe_scope: str = ""           # enemy_minions | all_minions | enemy_chars | all_chars
    freeze: str = ""              # "" | target | aoe
    freeze_target: str = ""
    cond_frozen_dmg: int = 0      # Zusatzschaden wenn Ziel bereits eingefroren
    destroy: str = ""             # "" | target | aoe
    destroy_target: str = ""
    needs_frozen: bool = False
    transform: tuple = None       # (atk, hp)
    heal: int = 0
    draw: int = 0
    armor: int = 0
    mana_refill: int = 0
    temp_mana: int = 0
    discount: tuple = None        # (kind, amount) kind: spell | minion | RACE
    summon: tuple = None          # (atk, hp, count)
    summon_freezer: bool = False  # beschworener Diener friert Verletzte ein (Wasserelementar)
    secret: bool = False
    conditional: bool = False
    cond_hold: str = ""           # Bedingung "wenn Ihr einen <Volk> auf der Hand habt" (z. B. DRAGON)
    cond_fx: object = None        # Effekt, der nur bei erfuellter Bedingung gilt
    missiles: tuple = None        # (anzahl, schaden_je_geschoss): zufaellig auf alle Feinde (Diener und Held)
    self_buff: tuple = None       # (angriff, leben, schluesselwort) fuer den gespielten Diener selbst
    max_atk: int = 0              # Ziel darf hoechstens so viel Angriff haben (Vernichten)
    payload: object = None        # bei Geheimnissen: der Effekt, der bei Ausloesung eintritt (falls erkannt)
    unknown: bool = True          # True, solange nichts Konkretes erkannt wurde
    notes: list = field(default_factory=list)

    @property
    def target_kind(self):
        """Welche Art von Ziel braucht die Karte? '' = kein Ziel."""
        for k in (self.dmg_target if self.dmg else "", self.freeze_target if self.freeze == "target" else "",
                  self.destroy_target if self.destroy == "target" else "",
                  "minion" if self.transform else ""):
            if k:
                return k
        return ""

    @property
    def concrete(self):
        return not self.unknown


def clean_text(raw):
    """Entfernt Markup und Platzhalter aus dem Rohtext der CardDefs."""
    if not raw:
        return ""
    t = re.sub(r"<[^>]+>", "", raw)
    t = t.replace("[x]", "")
    t = re.sub(r"[\$#](\d+)", r"\1", t)
    t = re.sub(r"(\d+)\s*\|4\(([^,)]*),([^)]*)\)", lambda m: f"{m.group(1)} {m.group(2) if m.group(1) == '1' else m.group(3)}", t)
    t = re.sub(r"\|4\(([^,)]*),[^)]*\)", r"\1", t)
    t = t.replace("_", " ")
    return re.sub(r"\s+", " ", t).strip()


def _num(word):
    w = word.lower()
    if w.isdigit():
        return int(w)
    return _WORDNUM.get(w, 0)


def _scope(s):
    """Ziel-Klasse eines Satzes ('' wenn nicht erkennbar)."""
    if re.search(r"allen feindlichen diener|alle feindlichen diener", s):
        return "aoe_enemy_minions"
    if re.search(r"allen (anderen )?feinden|allen feindlichen charakter", s):
        return "aoe_enemy_chars"
    if re.search(r"allen charakter|alle charakter", s):
        return "aoe_all_chars"
    if re.search(r"allen (anderen )?diener|alle (anderen )?diener", s) and "befreundet" not in s:
        return "aoe_all_minions"
    if re.search(r"gegnerischen helden|feindlichen helden|gegnerischer held", s):
        return "face"
    if re.search(r"befreundeten diener", s):
        return "friendly_minion"
    if re.search(r"feindlichen diener", s):
        return "enemy_minion"
    if re.search(r"(einem|einen|ein) (anderen )?diener", s):
        return "minion"
    if re.search(r"(einem|einen|ein) (feind|feindlichen charakter)", s):
        return "enemy"
    if re.search(r"(einem|einen|ein) (anderen )?charakter|dem ziel", s):
        return "any"
    return ""


def parse_effect(text, cardtype="SPELL", secret=False):
    """Parst den (bereinigten) Text. Bei Dienern/Waffen nur den Kampfschrei."""
    e = Effect()
    t = clean_text(text or "").lower().replace("max. ", "max ").replace("mind. ", "mind ")   # Abkuerzungspunkt trennt keine Saetze
    if not t:
        e.unknown = cardtype in ("SPELL",)
        return e
    if secret or t.startswith("geheimnis:"):
        e.secret = True
        body = t.split("geheimnis:", 1)[1].strip() if "geheimnis:" in t else t
        m = re.match(r"(?:wenn|sobald|nachdem)[^,]*,\s*(.*)", body)
        body = m.group(1) if m else re.split(r",?\s*(?:nachdem|wenn|sobald|falls)\b", body, maxsplit=1)[0]
        if body and body != t:
            pl = parse_effect(body, "SPELL")
            if pl.concrete and not pl.secret:
                e.payload = pl
    if cardtype in ("MINION", "WEAPON"):
        if "kampfschrei:" not in t:
            e.unknown = False
            return e
        t = t.split("kampfschrei:", 1)[1].strip()

    last_scope = ""
    for s in re.split(r"(?<=[.!?])\s+", t):
        s = s.strip().rstrip(".")
        if not s or s.startswith("zwillingszauber"):
            continue
        mh = _HOLD.search(s)
        if mh and RACE_WORDS.get(mh.group(1)) and not _HOLD_REJECT.search(s[:mh.start()]):
            core = s[:mh.start()]
            mb = _SELF_BUFF.match(core)
            if mb:                                                # Selbststaerkung (z. B. Schuppenwurm: +1 Angriff und Eifer)
                e.conditional = True
                e.cond_hold = RACE_WORDS[mh.group(1)]
                e.cond_fx = Effect(unknown=False, self_buff=(int(mb.group(1)), int(mb.group(2) or 0), mb.group(3) or ""))
                e.notes.append(s)
                continue
            cf = parse_effect(core, "SPELL")           # nur Einzelziel-Schaden/-Vernichten werden simuliert
            single = (cf.dmg and not cf.aoe_dmg and not cf.freeze and not cf.transform) or cf.destroy == "target"
            if single and not (cf.aoe_dmg or cf.destroy == "aoe"):
                e.conditional = True
                e.cond_hold, e.cond_fx = RACE_WORDS[mh.group(1)], cf
                e.notes.append(s)
                continue
        if _COND.search(s) and "bereits eingefroren" not in s:
            e.conditional = True
            e.notes.append(s)
            continue
        sc = _scope(s)

        m = _MISSILES_SPLIT.search(s) or _MISSILES_SHOT.search(s)
        if m:                                           # Arkane Geschosse & Co.: zufaellig auf alle Feinde
            n, per = (int(m.group(1)), 1) if m.re is _MISSILES_SPLIT else (int(m.group(1)), int(m.group(2)))
            e.missiles = (n, per)
            e.unknown = False
            continue

        m = re.search(r"(\d+) schaden", s)
        if m and ("fügt" in s or "verursacht" in s or "schaden zu" in s):
            n = int(m.group(1))
            if "zufällig" in s:
                e.notes.append(s)
            elif "bereits eingefroren" in s:
                e.cond_frozen_dmg = n
                e.unknown = False
            elif sc.startswith("aoe_"):
                e.aoe_dmg, e.aoe_scope = n, sc.replace("aoe_", "")
                e.unknown = False
            else:
                e.dmg, e.dmg_target = n, (sc or "any")
                e.unknown = False
                last_scope = e.dmg_target

        if re.search(r"\bfriert\b|\bfriere\b|einfrieren", s) and "bereits eingefroren" not in s:
            if sc.startswith("aoe_"):
                e.freeze = "aoe"
                e.unknown = False
            elif sc or last_scope or re.search(r"\b(ihn|sie|es)\b ein|das ziel", s):
                e.freeze, e.freeze_target = "target", (sc or last_scope or "any")
                last_scope = e.freeze_target
                e.unknown = False

        m = re.search(r"mit (?:max |höchstens )?(\d+) (?:oder weniger )?angriff", s)
        if m and ("vernichtet" in s or "zerstört" in s):
            e.max_atk = int(m.group(1))

        m = re.search(r"(vernichtet|zerstört) (einen|alle|jeden)\s+(\w+\s+)?(feindlichen\s+)?(eingefrorenen\s+)?diener", s)
        if m:
            if "eingefroren" in s:
                e.needs_frozen = True
            if m.group(2) == "einen":
                e.destroy, e.destroy_target = "target", "enemy_minion" if e.needs_frozen or "feindlich" in s else "minion"
            else:
                e.destroy = "aoe"
            e.unknown = False

        m = re.search(r"verwandelt (einen|jeden) diener in .*?\((\d+)/(\d+)\)", s)
        if m:
            e.transform = (int(m.group(2)), int(m.group(3)))
            e.unknown = False

        m = re.search(r"stellt (\d+) leben wieder her", s)
        if m:
            e.heal = int(m.group(1))
            e.unknown = False

        m = re.search(r"\bzieht (\d+|eine|einen|zwei|drei) karte", s)
        if m:
            e.draw += _num(m.group(1))
            e.unknown = False

        m = re.search(r"(\d+) rüstung", s)
        if m and ("erhaltet" in s or "erhält" in s or "gewährt" in s):
            e.armor += int(m.group(1))
            e.unknown = False

        m = re.search(r"füllt (\d+|einen|zwei) manakristall", s)
        if m:
            e.mana_refill = _num(m.group(1))
            e.unknown = False
        m = re.search(r"erhaltet (\d+|einen|ein|zwei) manakristall", s)
        if m and "nur für diesen zug" in s:
            e.temp_mana = _num(m.group(1))
            e.unknown = False

        m = re.search(r"nächste[rnms]?\s+(\w+)[^.]*?kostet\s*\((\d+)\)\s*weniger", s)
        if m:
            w = m.group(1)
            kind = "spell" if w.startswith("zauber") else ("minion" if w.startswith("diener") else RACE_WORDS.get(w, "minion"))
            e.discount = (kind, int(m.group(2)))
            e.unknown = False

        m = re.search(r"ruft (?:einen |eine |zwei |drei )?.*?\((\d+)/(\d+)\)", s)
        if m and "herbei" in s:
            mc = re.search(r"ruft (\d+|einen|eine|zwei|drei)\b", s)
            cnt = max(1, _num(mc.group(1))) if mc else 1
            e.summon = (int(m.group(1)), int(m.group(2)), cnt)
            e.summon_freezer = "wasserelementar" in s
            e.unknown = False

    if e.secret or cardtype in ("MINION", "WEAPON", "HERO_POWER"):
        e.unknown = False
    return e


def effect_summary(e):
    """Kurze deutsche Beschreibung dessen, was der Planer von der Karte weiss."""
    parts = []
    if e.dmg:
        parts.append(f"{e.dmg} Schaden")
    if e.aoe_dmg:
        parts.append(f"{e.aoe_dmg} Schaden an allen")
    if e.freeze:
        parts.append("friert ein")
    if e.destroy:
        parts.append("vernichtet")
    if e.transform:
        parts.append("verwandelt")
    return ", ".join(parts)
