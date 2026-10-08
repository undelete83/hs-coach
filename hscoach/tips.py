"""Texte fuer die Oberflaeche: Zugplan, Mulligan, Spielende."""


def render_plan(s, plan):
    """Formatiert einen Plan als mehrzeiligen Text."""
    out = []
    if s.result:
        return {"WON": "Spiel gewonnen - gut gespielt!", "LOST": "Spiel verloren. Mit „Analyse“ bekommst du eine Auswertung.",
                "TIED": "Unentschieden."}.get(s.result, "Spiel beendet.")
    if plan.lethal and plan.win_hp:
        out.append(f"★ SIEGSCHWELLE - mit diesem Zug bringst du den Boss auf ≤ {plan.win_hp} Leben, der Kampf endet!")
    elif plan.lethal:
        out.append("★ LETHAL - mit diesem Zug gewinnst du!")
    if not plan.steps:
        out.append("Keine sinnvolle Aktion gefunden - Zug beenden"
                   + (" (Mana für Reaktionen aufheben)." if s.my_mana else "."))
    for i, st in enumerate(plan.steps, 1):
        out.append(f"{i}. {st.text}")
    left = s.my_mana - plan.mana_used
    if plan.steps and left > 0 and not plan.lethal:
        out.append(f"   (Noch {left} Mana übrig.)")
    if plan.summary and not plan.lethal:
        out.append("→ " + plan.summary)
    for w in plan.warnings:
        out.append("⚠ " + w)
    if plan.unknown_cards:
        out.append("ℹ Effekt dem Planer unbekannt: " + ", ".join(sorted(set(plan.unknown_cards)))
                   + " - bitte Kartentext lesen.")
    for alt in plan.alternatives:
        if alt.steps:
            out.append("Alternative: " + " → ".join(st.text.split("  →")[0] for st in alt.steps[:4])
                       + (" …" if len(alt.steps) > 4 else ""))
    return "\n".join(out)


def mulligan_advice(s, db=None, boss=None):
    """Einfache Mulligan-Hilfe: billige Karten behalten, teure tauschen."""
    hand = [c for c in s.my_hand if not c.is_coin]
    second = len(hand) >= 4
    keep_cost = 3 if second else 2
    lines = [f"Mulligan - du gehst {'ZWEITER (du bekommst die Münze)' if second else 'ERSTER'}. Empfehlung:"]
    kept = 0
    for c in sorted(hand, key=lambda c: (c.cost, c.name)):
        fx = db.effect(c.cid) if db and c.cid else None
        cheap_spell = c.cardtype == "SPELL" and c.cost <= 2 and fx is not None and fx.concrete
        if boss and c.name in boss.mulligan:
            verdict, why = "BEHALTEN", f"Boss-Tipp gegen {boss.name}"
            kept += 1
        elif c.cost <= keep_cost and (c.cardtype in ("MINION", "WEAPON") or cheap_spell):
            verdict, why = "BEHALTEN", "günstig - kommt früh aufs Board"
            kept += 1
        elif c.cost == keep_cost + 1 and second and kept >= 1 and c.cardtype == "MINION":
            verdict, why = "BEHALTEN", "als zweiter Spieler mit Münze gut spielbar"
            kept += 1
        elif c.cost <= 2:
            verdict, why = "OPTIONAL", "billig, aber ohne Ziel/Wirkung früh wenig Wert"
        else:
            verdict, why = "TAUSCHEN", f"zu teuer ({c.cost} Mana) für die Startphase"
        lines.append(f"  {verdict:9} [{c.cost}💎] {c.name} - {why}")
    return "\n".join(lines)
