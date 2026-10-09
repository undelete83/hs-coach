"""Auswahl-Hilfe: bewertet die Karten, die bei "Entdecken" / "Waehlt aus" angeboten werden.

Keine Hellseherei, sondern gut erklaerbare Faustregeln aus Spielstand und Kartentext. Geheimnisse werden nach ihrem
Ausloeser (Angriff auf den Helden, Gegner spielt Diener/Zauber ...) und der Wahrscheinlichkeit bewertet, dass dieser in der
naechsten Gegnerrunde eintritt; Diener nach Werten und Schluesselwoertern; Zauber nach ihrem Effekt auf das aktuelle Brett.
"""
import re
from dataclasses import dataclass

from .effects import clean_text, parse_effect


@dataclass
class Advice:
    name: str
    score: float
    reason: str
    cid: str = ""


def _attackers(s):
    return [m for m in s.opp_minions if m.atk > 0 and not getattr(m, "frozen", False)]


def _secret_advice(o, s):
    t = clean_text(o.text).lower()
    att = len(_attackers(s))
    blockers = len(s.my_minions)
    # Wie wahrscheinlich loest es in der naechsten Gegnerrunde aus?
    if re.search(r"wenn ein (?:feindlicher )?diener euren helden angreift|wenn euer held angegriffen wird", t):
        p = min(0.9, 0.25 + 0.2 * att)
        if blockers >= 2:
            p *= 0.6                                  # die KI greift dann oft deine Diener an
        trig = "der Gegner deinen Helden angreift"
        if att == 0:
            p = 0.15
    elif re.search(r"gegner (?:einen )?diener ausgespielt|gegner einen diener ausspielt", t):
        p = 0.9 if s.opp_hand_count > 0 else (0.3 if s.opp_deck_count > 0 else 0.05)   # ohne Handkarten nur Zugkarte
        trig = "der Gegner einen Diener ausspielt"
    elif re.search(r"gegner (?:einen )?zauber (?:wirkt|gewirkt)", t):
        p = 0.55 if s.opp_hand_count > 0 else 0.1
        trig = "der Gegner einen Zauber wirkt"
    elif re.search(r"wenn ein (?:feindlicher )?diener angreift|wenn ein diener angreift", t):
        p = min(0.9, 0.3 + 0.2 * att)
        trig = "ein Diener angreift"
    elif re.search(r"befreundeter diener stirbt|einer eurer diener stirbt", t):
        p = 0.5
        trig = "einer deiner Diener stirbt"
    else:
        p, trig = 0.4, "der Auslöser eintritt"
    # Wie viel bringt der Effekt?
    m = re.search(r"erhält (?:er )?(\d+) rüstung", t)
    if m:
        value, effect = int(m.group(1)) * 0.7 + (3 if s.my_hp <= 15 else 0), f"{m.group(1)} Rüstung"
    elif "vernichtet" in t or "zerstört" in t:
        value, effect = 6.5, "vernichtet den Angreifer"
    elif "kopie" in t and "herbei" in t:
        best = max((m.atk + m.hp for m in s.opp_minions), default=5)
        value, effect = 4.5 + min(3.0, best * 0.25), "du bekommst eine Kopie seines Dieners"
    elif re.search(r"fügt .*? schaden|verursacht", t):
        n = re.search(r"(\d+) schaden", t)
        value, effect = (int(n.group(1)) * 0.9 if n else 4), "Schaden"
    elif "zieht" in t:
        value, effect = 4, "du ziehst Karten"
    elif "eingefroren" in t or "friert" in t:
        value, effect = 4, "friert ein"
    else:
        value, effect = 3.5, "Geheimnis"
    return Advice(o.name, p * value + 0.2, f"Löst aus, wenn {trig} (ca. {round(p * 100)} %): {effect}.", o.cid)


def _minion_advice(o, s):
    t = clean_text(o.text).lower()
    v = (o.atk + o.hp) * 0.85
    notes = [f"{o.atk}/{o.hp}"]
    if "spott" in t:
        v += 2.5 if (s.my_hp <= 15 or len(_attackers(s)) >= 2) else 1.0
        notes.append("Spott schützt dich")
    if "gottesschild" in t:
        v += 1.5
        notes.append("Gottesschild")
    if "lebensraub" in t:
        v += 1.2
        notes.append("Lebensraub")
    if "windzorn" in t:
        v += 1.2
    if re.search(r"ansturm|eifer", t):
        v += 1.5
        notes.append("greift sofort an")
    if "kampfschrei" in t:
        v += 1.2
    if "todesröcheln" in t:
        v += 0.8
    return Advice(o.name, v, ", ".join(notes) + ".", o.cid)


def _spell_advice(o, s, db):
    fx = parse_effect(o.text, "SPELL", secret=o.secret)
    foes = s.opp_minions
    notes, v = [], 2.5
    if fx.aoe_dmg:
        kills = sum(1 for m in foes if m.hp <= fx.aoe_dmg)
        v = 1.5 + 2.2 * kills + 0.4 * len(foes)
        notes.append(f"{fx.aoe_dmg} Schaden an allen, würde {kills} Diener töten")
    elif fx.dmg:
        kills = [m for m in foes if m.hp <= fx.dmg]
        v = 2.0 + fx.dmg * 0.5 + (2.0 if kills else 0)
        notes.append(f"{fx.dmg} Schaden" + (f", tötet {kills[0].name}" if kills else ""))
    elif fx.destroy:
        big = max((m.atk + m.hp for m in foes), default=0)
        v = 2.5 + (big * 0.5 if foes else -1)
        notes.append("vernichtet einen Diener" + ("" if foes else " (kein Ziel!)"))
    elif fx.draw:
        v = 2.0 + 1.6 * fx.draw
        notes.append(f"zieht {fx.draw} Karte(n)")
    elif fx.armor or fx.heal:
        low = s.my_hp <= 15
        v = 2.0 + (fx.armor + fx.heal) * (0.5 if low else 0.25)
        notes.append("schützt dein Leben")
    elif fx.freeze:
        v = 3.0 + 0.3 * len(foes)
        notes.append("friert ein")
    elif fx.summon:
        a, h, c = fx.summon
        v = 1.5 + (a + h) * 0.7 * max(1, c)
        notes.append(f"ruft {c}x {a}/{h} herbei")
    elif fx.unknown:
        notes.append("Wirkung nicht genau berechenbar")
    return Advice(o.name, v, ("; ".join(notes) or "Zauber") + ".", o.cid)


def advise(choice, s, db=None):
    """Bewertet jede angebotene Karte (hoeher = besser). Gibt eine absteigend sortierte Liste von Advice zurueck."""
    out = []
    for o in choice.options:
        if o.secret or clean_text(o.text).lower().startswith("geheimnis:"):
            a = _secret_advice(o, s)
        elif o.cardtype == "MINION":
            a = _minion_advice(o, s)
        elif o.cardtype == "WEAPON":
            a = Advice(o.name, o.atk * o.hp * 0.8 + 1.5, f"Waffe {o.atk}/{o.hp}.", o.cid)
        else:
            a = _spell_advice(o, s, db)
        out.append(a)
    out.sort(key=lambda a: -a.score)
    return out


def render(choice, s, db=None):
    """Text fuer das Plan-Feld: Empfehlung zuerst, dann die Alternativen mit Begruendung."""
    ranked = advise(choice, s, db)
    head = f"AUSWAHL OFFEN" + (f" ({choice.source})" if choice.source else "") + " - Empfehlung:"
    lines = [head, f"★ {ranked[0].name}: {ranked[0].reason}"]
    for a in ranked[1:]:
        lines.append(f"   {a.name}: {a.reason}")
    return "\n".join(lines), ranked
