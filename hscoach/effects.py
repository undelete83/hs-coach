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
_MISSILES_SPLIT = re.compile(r"verursacht (\d+) schaden, der zufällig auf alle (?:feinde|feindlichen charaktere) verteilt wird")
_MISSILES_SHOT = re.compile(r"verschießt (\d+) geschosse auf zufällige feinde, die je (\d+) schaden verursachen")
_SELF_BUFF = re.compile(r"erhält \+(\d+)(?: angriff|/\+(\d+))(?: und (spott|eifer|ansturm))?$")
_BUFF_PER = re.compile(r"erhält \+(\d+)(?:/\+(\d+)| (angriff|leben)) für (jeden anderen befreundeten diener auf dem schlachtfeld|jede karte auf eurer hand)$")
_HERO_BUFF = re.compile(r"verleiht eurem helden (?:in diesem zug )?\+(\d+) angriff(?: in diesem zug)?(?: und (\d+) rüstung)?(?: und immunität)?$")
_TEAM_BUFF = re.compile(r"verleiht euren (dienern|charakteren)(?: (mit spott))? (.+)$")
_MINION_BUFF = re.compile(r"verleiht einem (?:befreundeten )?diener (.+)$")
_TEMP_ATK = re.compile(r"\+(\d+) angriff in diesem zug$")
_BUFF_STATS = re.compile(r"\+(\d+)(?:/\+(\d+)| (angriff|leben))")
_BUFF_KW = ("spott", "gottesschild", "lebensentzug")
_HEAL_HERO = re.compile(r"stellt bei (?:eurem helden|jedem helden|allen befreundeten charakteren|allen charakteren) (\d+) leben wieder her")
_RAMP = re.compile(r"erhaltet (einen|zwei|drei|\d+) leeren? manakristall")
_FILL = re.compile(r"füllt eure seite des schlachtfelds mit (?:\w+ )?(\w+) \((\d+)/(\d+)\)")
_HOLD_REJECT =re.compile(r"zufällig|verletzt|legendär|anderen|mind|oder mehr|\bmit\b(?!\s+(max|\d+ oder weniger))")
_SCALED_DMG = [   # wertabhaengiger Schaden: (Muster, Art, Ziel/Geltungsbereich)
    (re.compile(r"^fügt einem diener schaden zu, der seinem angriff entspricht$"), "target_atk", "minion"),
    (re.compile(r"^fügt einem diener schaden zu, der dem angriff eures helden entspricht$"), "hero_atk", "minion"),
    (re.compile(r"^fügt jedem diener schaden zu, der seinem angriff entspricht$"), "own_atk", ""),
    (re.compile(r"^verbraucht eure gesamte rüstung\. fügt allen dienern ebenso viel schaden zu$"), "armor", ""),
]
_HEAL_ALL_MINIONS = re.compile(r"^stellt bei allen dienern (\d+) leben wieder her$")
_HEAL_MINION_HERO = re.compile(r"^stellt bei einem diener und eurem helden (\d+) leben wieder her$")
_HEAL_MINION = re.compile(r"^stellt bei einem (?:befreundeten )?diener (\d+) leben wieder her$")
_HEAL_FULL_TAUNT = re.compile(r"^stellt das volle leben eines dieners wieder her und verleiht ihm spott$")
_DRAW_TYPED = re.compile(r"^zieht (einen|eine|zwei|drei|\d+) (?:zauber|diener)$|^zieht eure (?:teuerste karte|karte mit den niedrigsten kosten)$")
_CHOOSE_SPLIT = re.compile(r";\s*oder\s+", re.I)
_DESTROY_HIGHEST = re.compile(r"^vernichtet den feindlichen diener mit dem höchsten angriff$")
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
    buff_per: tuple = None        # ("minions" | "hand", angriff, leben) je anderem Diener bzw. je Handkarte
    buff: tuple = None            # (angriff, leben, spott) auf einen befreundeten Diener (Zauber mit Ziel)
    buff_kw: tuple = ()           # zusaetzliche Schluesselwoerter dazu: gottesschild | lebensentzug
    choices: tuple = ()           # "Waehlt aus": je ein Effekt pro erkannter Option (die Karte spielt genau eine davon)
    choice_labels: tuple = ()     # Anzeigetexte dazu
    heal_minion: int = 0          # heilt einen eigenen Diener um N (999 = volles Leben); zusammen mit `heal` auch den Helden
    heal_all_minions: int = 0     # heilt ALLE Diener (beide Seiten) um N
    team_buff: tuple = None       # (angriff, leben, spott) auf alle eigenen Diener
    team_kw: tuple = ()           # Schluesselwoerter fuer alle eigenen Diener: gottesschild | lebensentzug
    team_taunt_only: bool = False # Staerkung nur fuer eigene Diener mit Spott
    temp_atk: int = 0             # +Angriff in diesem Zug fuer alle eigenen Diener
    temp_hero: bool = False       # ... und fuer den Helden ("Charaktere")
    hero_atk_buff: int = 0        # Held erhaelt +N Angriff in diesem Zug
    silence: str = ""             # "" | target | aoe (feindliche Diener)
    bounce: str = ""              # "" | target: feindlichen Diener auf die Hand zurueck
    ramp: int = 0                 # leere Manakristalle (wirken ab der naechsten Runde)
    fill_summon: bool = False     # summon fuellt die eigene Seite des Schlachtfelds
    destroy_ends: bool = False    # vernichtet den linken und den rechten feindlichen Diener
    dmg_scale: str = ""           # wertabhaengiger Schaden: target_atk | hero_atk (Einzelziel), own_atk | armor (alle Diener)
    destroy_highest: bool = False # vernichtet den feindlichen Diener mit dem hoechsten Angriff (kein Ziel noetig)
    max_atk: int = 0              # Ziel darf hoechstens so viel Angriff haben (Vernichten)
    payload: object = None        # bei Geheimnissen: der Effekt, der bei Ausloesung eintritt (falls erkannt)
    unknown: bool = True          # True, solange nichts Konkretes erkannt wurde
    notes: list = field(default_factory=list)

    @property
    def target_kind(self):
        """Welche Art von Ziel braucht die Karte? '' = kein Ziel."""
        for k in (self.dmg_target if self.dmg else "", "minion" if self.dmg_scale in ("target_atk", "hero_atk") else "",
                  self.freeze_target if self.freeze == "target" else "",
                  self.destroy_target if self.destroy == "target" else "",
                  "enemy_minion" if self.silence == "target" or self.bounce == "target" else "",
                  "friendly_minion" if (self.buff or self.heal_minion) else "",
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
    t = t.replace("[x]", "").replace("[d]", "")           # [d] = Geschlechts-Markierung mitten im Wort
    t = re.sub(r"[\$#](\d+)", r"\1", t)
    t = re.sub(r"(\d+)\s*\|4\(([^,)]*),([^)]*)\)", lambda m: f"{m.group(1)} {m.group(2) if m.group(1) == '1' else m.group(3)}", t)
    t = re.sub(r"\|4\(([^,)]*),[^)]*\)", r"\1", t)
    t = t.replace("_", " ")
    return re.sub(r"\s+", " ", t).strip()


def _parse_buff_tail(rest):
    """'+2/+3 und Spott' / '+3 Angriff und Gottesschild' / 'Gottesschild' -> (angriff, leben, schluesselwoerter, schlicht) oder None; 'schlicht' = nur +X/+Y, +X Angriff, Spott.
    Bleibt etwas Unbekanntes uebrig (z. B. 'Zauberschaden +1', 'Todesroecheln ...'), wird nichts erkannt."""
    r = rest.strip().rstrip(".")
    atk = hp = 0
    m = _BUFF_STATS.search(r)
    if m:
        if m.group(2) is not None:
            atk, hp = int(m.group(1)), int(m.group(2))
        elif m.group(3) == "angriff":
            atk = int(m.group(1))
        else:
            hp = int(m.group(1))
        r = r[:m.start()] + " " + r[m.end():]
    kws = [k for k in _BUFF_KW if re.search(rf"\b{k}\b", r)]
    for k in kws:
        r = re.sub(rf"\b{k}\b", " ", r)
    if re.sub(r"\b(und)\b|[,\s]", "", r):
        return None
    if not m and not kws:
        return None
    plain = not [k for k in kws if k != "spott"] and not (m and m.group(3) == "leben")
    return atk, hp, tuple(kws), plain


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


def _parse_choose_one(text, e):
    """'Waehlt aus: A; oder B.' -> jede erkannte Option als eigener Effekt (der Planer waehlt die bessere)."""
    ct = clean_text(text)
    body = re.sub(r"^wählt aus:\s*", "", ct, flags=re.I)
    body = re.sub(r"\.\s*\([^()]*\)$", ".", body).rstrip(".").strip()      # Hinweis in Klammern am Ende entfernen
    parts = [p.strip() for p in _CHOOSE_SPLIT.split(body)]
    if len(parts) < 2:
        return e
    mp = re.match(r"(verleiht [^+]*?)\s*(?=\+)", parts[0].lower())
    good, labels = [], []
    for p in parts:
        q = p.lower().replace("max. ", "max ").replace("mind. ", "mind ")
        if q.startswith("+") and mp:                   # "+4 Leben und Spott" erbt das Verb der ersten Option
            q = mp.group(1) + " " + q
        o = parse_effect(q, "SPELL")
        if o.concrete and not o.choices:
            good.append(o)
            labels.append(p[:1].upper() + p[1:])
    if good:
        e.choices, e.choice_labels, e.unknown = tuple(good), tuple(labels), False
    return e


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

    if cardtype == "SPELL" and t.startswith("wählt aus:"):
        return _parse_choose_one(text, e)

    flat = t.rstrip(".").strip()
    for rx, kind, tk in _SCALED_DMG:                   # ganzer Text ist genau so ein Zauber (z. B. Lichtbombe, Rundumschlag)
        if rx.match(flat):
            e.dmg_scale = kind
            e.dmg_target = tk
            e.unknown = False
            return e
    m = _HEAL_ALL_MINIONS.match(flat)
    if m:                                              # Kreis der Heilung
        e.heal_all_minions, e.unknown = int(m.group(1)), False
        return e
    m = _HEAL_MINION_HERO.match(flat)
    if m:                                              # Verbindende Heilung: ein Diener und der eigene Held
        e.heal_minion = e.heal = int(m.group(1))
        e.unknown = False
        return e
    m = _HEAL_MINION.match(flat)
    if m:
        e.heal_minion, e.unknown = int(m.group(1)), False
        return e
    if _HEAL_FULL_TAUNT.match(flat):                   # Heilung der Ahnen
        e.heal_minion, e.buff, e.unknown = 999, (0, 0, True), False
        return e
    if _DESTROY_HIGHEST.match(flat):                   # Strangulieren
        e.destroy_highest, e.unknown = True, False
        return e

    sents = [x.strip().rstrip(".") for x in re.split(r"(?<=[.!?])\s+", t)
             if x.strip() and not x.strip().startswith(("zwillingszauber", "("))]
    solo = len(sents) == 1                              # die Karte besteht nur aus diesem einen Satz

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
            single = (cf.dmg and not cf.aoe_dmg and not cf.freeze and not cf.transform) or cf.destroy == "target" or bool(cf.discount)
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

        m = _FILL.search(s)
        if m:                                           # Fokussierungsiris: Seite des Schlachtfelds auffuellen
            e.summon = (int(m.group(2)), int(m.group(3)), 0)
            e.fill_summon = True
            e.summon_freezer = "wasserelementar" in s
            e.unknown = False
            continue
        m = _BUFF_PER.match(s)
        if m:                                           # Staerkung je anderem Diener / je Handkarte
            val = int(m.group(1))
            atk, hp = (val, int(m.group(2))) if m.group(2) else ((val, 0) if m.group(3) == "angriff" else (0, val))
            e.buff_per = ("minions" if m.group(4).startswith("jeden") else "hand", atk, hp)
            e.unknown = False
            continue
        m = _HERO_BUFF.match(s)
        if m and ("immunität" not in s or solo):        # Held +N Angriff in diesem Zug (ggf. mit Ruestung)
            e.hero_atk_buff = int(m.group(1))
            e.armor += int(m.group(2) or 0)
            e.unknown = False
            continue
        m = _TEAM_BUFF.match(s)
        if m:                                           # eigene Diener (oder Charaktere) staerken
            tail = m.group(3)
            mt = _TEMP_ATK.fullmatch(tail)
            if mt and not m.group(2) and solo:          # "+N Angriff in diesem Zug"
                e.temp_atk, e.temp_hero = int(mt.group(1)), m.group(1) == "charakteren"
                e.unknown = False
                continue
            pb = _parse_buff_tail(tail) if m.group(1) == "dienern" else None
            if pb and (pb[3] or solo):
                e.team_buff = (pb[0], pb[1], "spott" in pb[2])
                e.team_kw = tuple(k for k in pb[2] if k != "spott")
                e.team_taunt_only = bool(m.group(2))
                e.unknown = False
                continue
        m = _MINION_BUFF.match(s)
        if m:                                           # einen Diener staerken
            pb = _parse_buff_tail(m.group(1))
            if pb and (pb[3] or solo):
                e.buff = (pb[0], pb[1], "spott" in pb[2])
                e.buff_kw = tuple(k for k in pb[2] if k != "spott")
                e.unknown = False
                continue
        if "bringt einen diener zum schweigen" in s:
            e.silence, e.unknown = "target", False
            continue
        if "bringt alle feindlichen diener zum schweigen" in s and "vernichtet" not in s:
            e.silence, e.unknown = "aoe", False
            continue
        if re.search(r"lasst einen feindlichen diener auf (?:seine|eure) hand zurückkehren", s):
            e.bounce, e.unknown = "target", False
            continue
        if "entfernt einen diener aus dem spiel" in s:                 # wie Vernichten (Lebenslaenglich)
            e.destroy, e.destroy_target, e.unknown = "target", "enemy_minion", False
            continue
        if "vernichtet die feindlichen diener, die sich ganz links und ganz rechts befinden" in s:
            e.destroy_ends, e.unknown = True, False
            continue
        m = _RAMP.search(s)
        if m:
            e.ramp += _num(m.group(1))
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

        m = _HEAL_HERO.search(s) or re.search(r"stellt (\d+) leben wieder her", s)
        if m:
            e.heal = int(m.group(1))
            e.unknown = False

        m = _DRAW_TYPED.match(s) if solo else None
        if m:                                           # "Zieht einen Zauber" / "Zieht Eure teuerste Karte": je 1 Karte
            e.draw += _num(m.group(1)) if m.group(1) else 1
            e.unknown = False
            continue
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

        m = re.search(r"nächste[rnms]?\s+(\w+)[^.]*?kostet\s*\(0\)", s)
        if m:                                           # "Euer naechster Zauber kostet (0)"
            w = m.group(1)
            kind = "spell" if w.startswith("zauber") else ("minion" if w.startswith("diener") else RACE_WORDS.get(w, "minion"))
            e.discount = (kind, 99)
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
    if e.dmg_scale:
        parts.append("Schaden nach Wert")
    if e.destroy or e.destroy_highest:
        parts.append("vernichtet")
    if e.transform:
        parts.append("verwandelt")
    return ", ".join(parts)
