"""Claude-Anbindung: Zug-Tipps (Streaming) und Spielanalyse nach der Partie."""
import logging
import os
import threading

from . import config

log = logging.getLogger("hscoach.ai")

SYSTEM_PROMPT = """\
Du bist ein erfahrener Hearthstone-Coach für einen Einsteiger. Antworte auf Deutsch, kurz und konkret (max. 5 Sätze).
Die Regel-Engine hat Mana, Ziele, Spott, Einfrieren und Rabatte bereits korrekt simuliert und liefert Vorschläge
(A/B/C). Wähle den besten Vorschlag oder begründe kurz, warum eine leichte Abwandlung besser ist.
Regeln:
- Das verfügbare Mana ist ein hartes Limit; schlage nie mehr vor, als die Summe erlaubt.
- Nenne immer das genaue Ziel (Diener oder Held) und die Reihenfolge.
- Erkläre Fachbegriffe (Kampfschrei, Spott, ...) nur, wenn sie für den Zug wichtig sind, in einem halben Satz.
- Mana am Zugende ist verschwendet - nutze es effizient, aber behalte Gefahren für die nächste Runde im Blick.
- Vernachlässige Schaden zum gegnerischen Helden nicht komplett.
- Kein Markdown (keine Sterne, keine Überschriften), nur normaler Text.
"""

ANALYSIS_PROMPT = """\
Du bist ein Hearthstone-Coach. Analysiere die folgende Partie eines Einsteigers auf Deutsch (Markdown).
Gliederung: 1) Ergebnis in einem Satz, 2) Die drei wichtigsten Wendepunkte/Fehler (mit Rundenangabe), 3) Was gut lief,
4) Drei konkrete Lektionen für das nächste Mal (kurze Sätze, die man in eine Wissensdatei übernehmen kann).
Sei ehrlich, konkret und nenne Kartennamen. Erfinde nichts, was nicht in den Daten steht.
"""


def load_knowledge(cfg, limit=6000):
    try:
        with open(cfg["knowledge_path"], encoding="utf-8") as f:
            txt = f.read().strip()
        return txt[:limit]
    except OSError:
        return ""


def _model_extras(model):
    """Zusatzparameter je Modell (Haiku 5.5: Denken aus + niedriger Aufwand = schnell und billig)."""
    if model.startswith("claude-haiku-5"):
        return {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}
    if model.startswith(("claude-sonnet-5", "claude-opus-5")):
        return {"output_config": {"effort": "low"}}
    return {}


def state_to_text(s, plan=None, boss=None):
    """Spielstand als Text fuer den Prompt (inkl. Mechaniken, Verlauf und Plan der Regel-Engine)."""
    L = []
    if boss:
        L.append(boss.prompt())
    L.append(f"Runde {s.turn} | Ich: {s.my_hp} LP" + (f" +{s.my_armor} Rüstung" if s.my_armor else "")
             + f" | Gegner ({s.opp_name}): {s.opp_hp} LP" + (f" +{s.opp_armor} Rüstung" if s.opp_armor else ""))
    L.append(f"Verfügbares Mana: {s.my_mana} von {s.max_mana}"
             + (f" | Leichen: {s.my_corpses}" if s.my_corpses is not None else ""))
    if s.my_weapon:
        L.append(f"Meine Waffe: {s.my_weapon.name} {s.my_weapon.atk}/{s.my_weapon.durability}")
    if s.my_hero_power:
        hp = s.my_hero_power
        L.append(f"Heldenkraft: {hp.name} ({hp.cost} Mana, {'schon benutzt' if hp.used else 'bereit'}) - {hp.text}")
    L.append("MEIN BOARD: " + (" | ".join(m.label().strip() + (" (bereit)" if m.can_attack else " (kann nicht angreifen)")
                                         for m in s.my_minions) or "leer"))
    L.append("GEGNER BOARD: " + (" | ".join(m.label().strip() for m in s.opp_minions) or "leer"))
    L.append("HAND:")
    for c in s.my_hand:
        stats = f" {c.atk}/{c.hp}" if c.cardtype in ("MINION", "WEAPON") else ""
        L.append(f"  - [{c.cost} Mana] {c.name} ({c.cardtype}{stats}): {c.text}")
    if s.opp_hero_power:
        L.append(f"Gegner-Heldenkraft: {s.opp_hero_power.name} ({s.opp_hero_power.cost} Mana) - {s.opp_hero_power.text}")
    L.append(f"Gegner: {s.opp_hand_count} Handkarten, {s.opp_deck_count} im Deck, {s.opp_secret_count} Geheimnis(se).")
    if getattr(s, "choice", None):
        L.append("OFFENE AUSWAHL" + (f" (durch {s.choice.source})" if s.choice.source else "") + ": "
                 + " | ".join(f"{o.name} [{o.cardtype}] {o.text}" for o in s.choice.options))
    if s.opp_played:
        L.append("Gegner hat bisher gespielt: " + ", ".join(s.opp_played[-12:]))
    if s.events:
        L.append("Letzte Spielzüge:\n  " + "\n  ".join(s.events[-8:]))
    if plan is not None:
        L.append("\nVORSCHLÄGE DER REGEL-ENGINE:")
        plans = [plan] + list(plan.alternatives)
        for lab, p in zip("ABC", plans):
            if not p.steps and lab != "A":
                continue
            L.append(f"{lab}) " + (" ; ".join(st.text for st in p.steps) if p.steps else "nichts spielen / Zug beenden")
                     + f"  [{p.summary}]" + ("  [LETHAL]" if p.lethal else ""))
            for w in p.warnings:
                L.append("   Warnung: " + w)
    return "\n".join(L)


class ClaudeCoach:
    def __init__(self, cfg):
        self.cfg = cfg
        self._client = None
        self._lock = threading.Lock()
        self._extras_ok = {}
        self.session_cost = 0.0

    # -- Client ----------------------------------------------------------------------
    def client(self):
        with self._lock:
            if self._client is None:
                import anthropic
                key = config.get_api_key(self.cfg)
                if not key:
                    raise RuntimeError("Kein API-Key hinterlegt - bitte unter Einstellungen eintragen "
                                       "(oder die Umgebungsvariable ANTHROPIC_API_KEY setzen).")
                self._client = anthropic.Anthropic(api_key=key, timeout=float(self.cfg["api_timeout_s"]), max_retries=1)
            return self._client

    def preload(self):
        def _w():
            try:
                self.client()
            except Exception as ex:
                log.info("Claude-Preload: %s", ex)
        threading.Thread(target=_w, daemon=True, name="claude-preload").start()

    def _create_kwargs(self, **kw):
        model = kw["model"]
        if self._extras_ok.get(model, True):
            kw.update(_model_extras(model))
        return kw

    # -- Zug-Tipp (Streaming) ----------------------------------------------------------------
    def ask_tip(self, s, plan, on_text, on_done, boss=None):
        """Laeuft im Hintergrund. on_text(acc) waehrend des Streams, on_done(text, cost, total, err)."""
        def _run():
            model = self.cfg["claude_model"]
            try:
                client = self.client()
                import anthropic
                know = load_knowledge(self.cfg)
                system = SYSTEM_PROMPT + (f"\nGelerntes Wissen:\n{know}" if know else "")
                user = state_to_text(s, plan, boss) + (
                    "\n\nAufgabe: Welchen Zug empfiehlst du? Nenne Option (A/B/C oder Abwandlung), Reihenfolge, genaue Ziele "
                    f"und kurz warum. Gesamtkosten der Karten dürfen {s.my_mana} Mana nicht überschreiten.")
                kw = self._create_kwargs(model=model, max_tokens=600, system=system,
                                         messages=[{"role": "user", "content": user}])
                acc = ""
                for attempt in (0, 1):
                    try:
                        with client.messages.stream(**kw) as stream:
                            for t in stream.text_stream:
                                acc += t
                                on_text(acc)
                            final = stream.get_final_message()
                        break
                    except anthropic.BadRequestError as ex:
                        if attempt == 0 and ("thinking" in kw or "output_config" in kw):
                            log.warning("Extras abgelehnt (%s) - Retry ohne", ex)
                            self._extras_ok[model] = False
                            kw.pop("thinking", None)
                            kw.pop("output_config", None)
                            acc = ""
                            continue
                        raise
                cost = config.cost_usd(model, final.usage)
                self.session_cost += cost
                text = "".join(b.text for b in final.content if getattr(b, "type", "") == "text").strip() or acc
                on_done(text, cost, self.session_cost, None)
            except Exception as ex:
                log.exception("Claude-Tipp fehlgeschlagen")
                on_done("", None, self.session_cost, str(ex))
        threading.Thread(target=_run, daemon=True, name="claude-tip").start()

    # -- Analyse nach dem Spiel -------------------------------------------------------------------
    def analyze(self, summary, on_done):
        def _run():
            model = self.cfg["analysis_model"]
            try:
                client = self.client()
                know = load_knowledge(self.cfg)
                kw = self._create_kwargs(model=model, max_tokens=3000,
                                         system=ANALYSIS_PROMPT + (f"\nBekanntes Wissen:\n{know}" if know else ""),
                                         messages=[{"role": "user", "content": summary}])
                try:
                    msg = client.messages.create(**kw)
                except Exception:
                    kw.pop("thinking", None)
                    kw.pop("output_config", None)
                    msg = client.messages.create(**kw)
                cost = config.cost_usd(model, msg.usage)
                self.session_cost += cost
                text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
                on_done(text, cost, None)
            except Exception as ex:
                log.exception("Analyse fehlgeschlagen")
                on_done("", None, str(ex))
        threading.Thread(target=_run, daemon=True, name="claude-analysis").start()
