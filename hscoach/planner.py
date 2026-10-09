"""Zugplaner: simuliert Karten, Angriffe und Heldenkraft per Beam-Search und bewertet das Ergebnis.

Der Planer kennt nur, was er sicher aus Zahlen und Kartentext lesen kann (Schaden, Einfrieren,
Vernichten, Rabatte, Beschwoerungen, ...). Unbekannte Effekte werden nicht erfunden, sondern als
"Effekt unbekannt" gekennzeichnet.
"""
import dataclasses
import time
from collections import namedtuple
from dataclasses import dataclass, field

from .effects import Effect

M = namedtuple("M", "uid name cid atk hp taunt ds poison frozen stealth immune wf att face lifesteal sp race mine fzr mhp",
               defaults=(False, 0))        # mhp = Maximalleben (0 = unbekannt/voll, dann gilt hp)
FREEZER_TEXT = "friert jeden charakter ein, der von diesem diener verletzt"   # z.B. Wasserelementar (Book of Heroes)
C = namedtuple("C", "idx name cid cost ctype text atk hp race taunt ds charge rush stealth wf poison lifesteal secret fx coin")

MAX_BOARD = 7
BEAM = 48
MAX_DEPTH = 12
AOE_TEXT = {"enemy_minions": "allen feindlichen Dienern", "all_minions": "allen Dienern",
            "enemy_chars": "allen Feinden", "all_chars": "allen Charakteren"}
ALT_MARGIN = 12.0         # Alternativen werden nur gezeigt, wenn sie nicht deutlich schlechter sind


# -- Ergebnis-Typen --------------------------------------------------------------------

@dataclass
class Step:
    kind: str                 # minion | spell | weapon | attack | hero_attack | hero_power
    text: str
    cid: str = ""


@dataclass
class Plan:
    steps: list = field(default_factory=list)
    lethal: bool = False
    score: float = 0.0
    summary: str = ""
    warnings: list = field(default_factory=list)
    cids: list = field(default_factory=list)       # Karten (in Spielreihenfolge) fuer die Bildanzeige
    alternatives: list = field(default_factory=list)   # [Plan] (nur Kurzfassung)
    mana_used: int = 0
    nodes: int = 0
    unknown_cards: list = field(default_factory=list)
    win_hp: int = 0                 # Boss-Siegschwelle (Gegner-Leben, bei dem der Kampf endet)


# -- Simulation ----------------------------------------------------------------------------

class SS:
    __slots__ = ("mana", "max_mana", "my_hp", "my_armor", "opp_hp", "opp_armor", "mine", "opp", "used",
                 "weapon", "hero_atk", "hero_att", "hp_used", "disc", "util", "spent", "path", "uid", "score",
                 "opp_inc_bonus", "opp_spawn_atk", "win_hp", "face_k", "prio", "reserve", "hp_bonus", "def_k", "temp")

    def clone(self):
        n = SS.__new__(SS)
        n.mana, n.max_mana = self.mana, self.max_mana
        n.my_hp, n.my_armor, n.opp_hp, n.opp_armor = self.my_hp, self.my_armor, self.opp_hp, self.opp_armor
        n.mine, n.opp = list(self.mine), list(self.opp)
        n.used, n.weapon, n.hero_atk, n.hero_att = self.used, self.weapon, self.hero_atk, self.hero_att
        n.hp_used, n.disc, n.util, n.spent = self.hp_used, self.disc, self.util, self.spent
        n.path, n.uid, n.score = self.path, self.uid, 0.0
        n.opp_inc_bonus, n.opp_spawn_atk = self.opp_inc_bonus, self.opp_spawn_atk
        n.win_hp, n.face_k, n.prio = self.win_hp, self.face_k, self.prio
        n.reserve, n.hp_bonus, n.def_k = self.reserve, self.hp_bonus, self.def_k
        n.temp = self.temp
        return n


def _flags(m):
    return (m.name, m.atk, m.hp, m.taunt, m.ds, m.poison, m.frozen, m.stealth, m.wf, m.att, m.face, m.lifesteal, m.sp, m.mhp)


def _key(ss):
    return (ss.mana, ss.my_hp, ss.my_armor, ss.opp_hp, ss.opp_armor, ss.weapon, ss.hero_att, ss.hp_used,
            ss.used, ss.disc, tuple(sorted(_flags(m) for m in ss.mine)), tuple(sorted(_flags(m) for m in ss.opp)))


def _mval(m):
    v = m.atk * 1.0 + m.hp * 0.8 + 1.0
    if m.taunt:
        v += 1.5
    if m.ds:
        v += 0.7 * m.atk + 1.0
    if m.poison:
        v += 2.5
    if m.wf > 1:
        v += m.atk * 0.6
    if m.lifesteal:
        v += 1.0
    if m.stealth:
        v += 0.5
    if m.sp:
        v += 1.2 * m.sp
    if m.frozen:
        v *= 0.55
    return v


def _evaluate(ss):
    opp_total = ss.opp_hp + ss.opp_armor - ss.win_hp      # Boss-Siegschwelle: bei <= 0 ist der Kampf gewonnen
    if opp_total <= 0:
        return 100000.0 - len(_unroll(ss.path))
    my_total = ss.my_hp + ss.my_armor
    if my_total <= 0:
        return -100000.0
    sc = -1.0 * ss.temp                         # Angriff, der nur in diesem Zug gilt, zaehlt nicht fuer das Board danach
    for m in ss.mine:
        sc += _mval(m)
    for m in ss.opp:
        sc -= 1.15 * _mval(m) * ss.prio.get(m.name, 1.0)
    sc -= ss.face_k * 4.5 * (opp_total ** 0.5)
    sc += 0.3 * my_total
    block = sum(m.hp for m in ss.mine if m.taunt)
    inc1 = max(0, ss.opp_inc_bonus + sum(m.atk * m.wf for m in ss.opp if not m.frozen and m.atk > 0) - block)
    rem = my_total - inc1                      # Leben nach dem naechsten Gegnerzug
    if rem <= 0:
        sc -= 3000.0 + 12.0 * (-rem)        # auch bei drohendem Tod zaehlt jeder verhinderte Schadenspunkt
    else:
        sc -= 0.3 * inc1 + ss.def_k * 2.2 * max(0, 15 - rem)      # je niedriger der Rest, desto gefaehrlicher
    # Folgezug: auch eingefrorene Diener tauen auf, dazu kommen Beschwoerungen der Gegner-Heldenkraft
    inc2 = max(0, ss.opp_inc_bonus + ss.opp_spawn_atk + sum(m.atk * m.wf for m in ss.opp if m.atk > 0) - block)
    sc -= 0.12 * inc2
    sc += 0.6 * ss.spent + ss.util
    if ss.weapon:
        sc += 0.8 * ss.weapon[0] * min(ss.weapon[1], 3)
    return sc


def _unroll(path):
    out = []
    while path:
        path, a = path
        out.append(a)
    out.reverse()
    return out


def _find(lst, uid):
    for i, m in enumerate(lst):
        if m.uid == uid:
            return i
    return -1


def _hurt_hero(ss, side_opp, n):
    if n <= 0:
        return
    if side_opp:
        a = min(ss.opp_armor, n)
        ss.opp_armor -= a
        ss.opp_hp -= n - a
    else:
        a = min(ss.my_armor, n)
        ss.my_armor -= a
        ss.my_hp -= n - a


def _damage_minion(ss, side_opp, uid, n, log=None, poison=False):
    """Fuegt einem Diener Schaden zu. Gibt (verloren_gottesschild, gestorben) zurueck."""
    lst = ss.opp if side_opp else ss.mine
    i = _find(lst, uid)
    if i < 0:
        return False, False
    m = lst[i]
    if m.immune or n <= 0:
        return False, False
    if m.ds:
        lst[i] = m._replace(ds=False)
        if log is not None:
            log.append(f"{m.name}: Gottesschild weg")
        return True, False
    if poison or m.hp - n <= 0:
        del lst[i]
        if log is not None:
            log.append(f"{m.name} stirbt")
        return False, True
    lst[i] = m._replace(hp=m.hp - n)
    if log is not None:
        log.append(f"{m.name} -{n} Leben (noch {m.hp - n})")
    return False, False


def _targets(ss, kind):
    """Gueltige Ziele fuer eine Zielart: Liste von None | ('m', uid) | ('face',)."""
    opp_ok = [("m", m.uid) for m in ss.opp if not m.stealth and not m.immune]
    if kind in ("any", ""):
        return opp_ok + [("face",)]
    if kind in ("enemy",):
        return opp_ok + [("face",)]
    if kind in ("minion", "enemy_minion"):
        return opp_ok
    if kind == "face":
        return [("face",)]
    if kind == "friendly_minion":
        return [("f", m.uid) for m in ss.mine]
    if kind == "any_minion":                       # z. B. "Setzt die Werte eines Dieners auf 7/14": eigener oder feindlicher Diener
        return opp_ok + [("f", m.uid) for m in ss.mine]
    return []


def _apply_fx(ss, fx, tgt, is_spell, name, log):
    """Wendet einen Effekt an. Gibt False zurueck, wenn er (z.B. mangels Ziel) nicht ausfuehrbar ist."""
    sp = sum(m.sp for m in ss.mine) if is_spell else 0
    target_frozen_before = False
    tgt_uid = tgt[1] if tgt and tgt[0] == "m" else None
    if tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        if i < 0:
            return False
        target_frozen_before = ss.opp[i].frozen

    if fx.destroy == "target" and tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        if fx.needs_frozen and not ss.opp[i].frozen:
            return False
        m = ss.opp[i]
        if fx.max_atk and m.atk > fx.max_atk:
            return False
        del ss.opp[i]
        if log is not None:
            log.append(f"{m.name} wird vernichtet")
    if fx.destroy_highest:                       # Strangulieren: hoechster Angriff (bei Gleichstand der mit dem meisten Leben)
        if not ss.opp:
            return False
        top = max(ss.opp, key=lambda m: (m.atk, m.hp))
        i = _find(ss.opp, top.uid)
        del ss.opp[i]
        if log is not None:
            log.append(f"{top.name} wird vernichtet (höchster Angriff)")
    if fx.steal and tgt_uid is not None:                 # Gedankenkontrolle: Diener wechselt die Seite, kann aber noch nicht angreifen
        if len(ss.mine) >= MAX_BOARD:
            return False
        i = _find(ss.opp, tgt_uid)
        m = ss.opp.pop(i)
        ss.mine.append(m._replace(att=0, mine=True, frozen=m.frozen))
        if log is not None:
            log.append(f"{m.name} wechselt auf deine Seite (kann in diesem Zug nicht angreifen)")
    if fx.set_stats:                                     # Werte auf feste Zahlen setzen (Leben setzt auch das Maximum)
        a, h = fx.set_stats

        def _set(m):
            return m._replace(atk=m.atk if a is None else a, hp=m.hp if h is None else h, mhp=m.mhp if h is None else h)
        if fx.set_scope == "target" and tgt and tgt[0] in ("m", "f"):
            lst = ss.opp if tgt[0] == "m" else ss.mine
            i = _find(lst, tgt[1])
            if i < 0:
                return False
            new = _set(lst[i])
            if new == lst[i]:
                return False
            lst[i] = new
            if log is not None:
                log.append(f"{new.name} wird zu {new.atk}/{new.hp}")
        elif fx.set_scope == "all":
            new_opp, new_mine = [_set(m) for m in ss.opp], [_set(m) for m in ss.mine]
            if new_opp == ss.opp and new_mine == ss.mine:
                return False
            ss.opp[:], ss.mine[:] = new_opp, new_mine
            if log is not None:
                log.append("alle Diener (auch deine!) bekommen die neuen Werte")
    if fx.dmg_scale == "target_atk" and tgt_uid is not None:
        m = ss.opp[_find(ss.opp, tgt_uid)]
        if m.atk <= 0:
            return False
        _damage_minion(ss, True, tgt_uid, m.atk, log)
    if fx.dmg_scale == "hero_atk" and tgt_uid is not None:
        if ss.hero_atk <= 0:
            return False
        _damage_minion(ss, True, tgt_uid, ss.hero_atk, log)
    if fx.dmg_scale == "own_atk":                # Lichtbombe: jeder Diener bekommt Schaden in Hoehe seines Angriffs
        if not (ss.opp or ss.mine):
            return False
        for side_opp, lst in ((True, list(ss.opp)), (False, list(ss.mine))):
            for m in lst:
                _damage_minion(ss, side_opp, m.uid, m.atk, log)
    if fx.dmg_scale == "armor":                  # Rundumschlag: gesamte Ruestung verbrauchen, ebenso viel Schaden an alle Diener
        n = ss.my_armor
        if n <= 0:
            return False
        ss.my_armor = 0
        if log is not None:
            log.append(f"verbraucht {n} Rüstung: {n} Schaden an allen Dienern")
        for m in list(ss.opp):
            _damage_minion(ss, True, m.uid, n, log)
        for m in list(ss.mine):
            _damage_minion(ss, False, m.uid, n, log)
    if (fx.buff or fx.heal_minion) and tgt and tgt[0] == "f":
        i = _find(ss.mine, tgt[1])
        if i < 0:
            return False
        orig = m = ss.mine[i]
        if fx.buff_hurt_only and not _is_hurt(m):
            return False
        if not _race_ok(m, fx.buff_race):
            return False
        if fx.heal_minion:
            m = _healed(m, fx.heal_minion)
        if fx.buff:
            a, h, taunt = fx.buff
            m = _grant(_buffed(m, (a, h, "spott" if taunt else "")), fx.buff_kw)
        ss.mine[i] = m
        if m == orig and not (fx.heal and ss.my_hp < 30):      # nichts Neues (z. B. unverletzt, schon Gottesschild): verschwendet
            return False
        if log is not None:
            if m.hp != orig.hp and fx.heal_minion:
                log.append(f"{m.name} wird um {m.hp - orig.hp} geheilt (jetzt {m.hp} Leben)")
            if fx.buff:
                a, h, taunt = fx.buff
                extra = "".join(f" mit {k.capitalize()}" for k in (["spott"] if taunt else []) + list(fx.buff_kw))
                if a or h or extra:
                    log.append(f"{m.name} wird zu {m.atk}/{m.hp}" + extra)
    if fx.heal_all_minions:
        new_mine = [_healed(m, fx.heal_all_minions) for m in ss.mine]
        new_opp = [_healed(m, fx.heal_all_minions) for m in ss.opp]
        if new_mine == ss.mine and new_opp == ss.opp:
            return False
        ss.mine[:], ss.opp[:] = new_mine, new_opp
        if log is not None:
            log.append(f"alle Diener werden um {fx.heal_all_minions} geheilt (auch die des Gegners)")
    if fx.team_buff or fx.team_kw:
        a, h, taunt = fx.team_buff or (0, 0, False)
        sel = {m.uid for m in ss.mine if (m.taunt or not fx.team_taunt_only) and _race_ok(m, fx.team_race)}
        if not sel:
            return False
        new = [_grant(_buffed(m, (a, h, "spott" if taunt else "")), fx.team_kw) if m.uid in sel else m for m in ss.mine]
        if new == ss.mine:
            return False
        ss.mine[:] = new
        if log is not None:
            who = "alle deine Diener mit Spott" if fx.team_taunt_only else "alle deine Diener"
            extra = "".join(f" und {k.capitalize()}" for k in ((["spott"] if taunt else []) + list(fx.team_kw)))
            log.append(f"{who} +{a}/{h}{extra}" if (a or h) else f"{who}:{extra[4:]}")
    if fx.temp_atk:
        can_hero = fx.temp_hero and ss.hero_att > 0
        if not can_hero and not any(m.att > 0 and not m.frozen for m in ss.mine):
            return False                         # niemand koennte in diesem Zug angreifen
        ss.mine[:] = [m._replace(atk=m.atk + fx.temp_atk) for m in ss.mine]
        ss.temp += fx.temp_atk * len(ss.mine)
        if fx.temp_hero:
            ss.hero_atk += fx.temp_atk
        if log is not None:
            log.append(f"deine Diener{' und der Held' if fx.temp_hero else ''} +{fx.temp_atk} Angriff in diesem Zug")
    if fx.hero_atk_buff:
        ss.hero_atk += fx.hero_atk_buff
        if log is not None:
            log.append(f"Held +{fx.hero_atk_buff} Angriff in diesem Zug")
    if fx.silence == "target" and tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        ss.opp[i] = _silenced(ss.opp[i])
        if log is not None:
            log.append(f"{ss.opp[i].name} verliert Spott/Schilde/Effekte")
    if fx.silence == "aoe":
        ss.opp[:] = [_silenced(m) for m in ss.opp]
        if log is not None and ss.opp:
            log.append("alle feindlichen Diener zum Schweigen gebracht")
    if fx.bounce == "target" and tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        m = ss.opp[i]
        del ss.opp[i]
        ss.util += 0.5                       # der Gegner muss die Karte erneut ausspielen
        if log is not None:
            log.append(f"{m.name} geht zurück auf die Hand")
    if fx.destroy_ends and ss.opp:
        gone = {ss.opp[0].uid, ss.opp[-1].uid}
        if log is not None:
            log.append("vernichtet " + " und ".join(m.name for m in ss.opp if m.uid in gone))
        ss.opp[:] = [m for m in ss.opp if m.uid not in gone]
    if fx.transform and tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        m = ss.opp[i]
        ss.opp[i] = m._replace(atk=fx.transform[0], hp=fx.transform[1], taunt=False, ds=False, poison=False,
                               stealth=False, wf=1, lifesteal=False, sp=0, frozen=False)
        if log is not None:
            log.append(f"{m.name} wird zu {fx.transform[0]}/{fx.transform[1]}")

    if fx.dmg and tgt is not None:
        n = fx.dmg + sp
        if tgt[0] == "face":
            _hurt_hero(ss, True, n)
            if log is not None:
                log.append(f"{n} Schaden ins Gesicht")
        else:
            if _find(ss.opp, tgt[1]) >= 0:
                _damage_minion(ss, True, tgt[1], n, log)
    if fx.cond_frozen_dmg and target_frozen_before and tgt_uid is not None and _find(ss.opp, tgt_uid) >= 0:
        _damage_minion(ss, True, tgt_uid, fx.cond_frozen_dmg + sp, log)
    if fx.freeze == "target" and tgt_uid is not None:
        i = _find(ss.opp, tgt_uid)
        if i >= 0:
            ss.opp[i] = ss.opp[i]._replace(frozen=True)
            if log is not None:
                log.append(f"{ss.opp[i].name} wird eingefroren")

    if fx.aoe_dmg:
        n = fx.aoe_dmg + sp
        scope = fx.aoe_scope
        if log is not None:
            log.append(f"{n} Schaden an {AOE_TEXT.get(scope, 'allen')} (kein Ziel nötig)")
        if scope in ("enemy_minions", "enemy_chars", "all_minions", "all_chars"):
            for m in list(ss.opp):
                if tgt_uid is not None and m.uid == tgt_uid and scope == "enemy_chars":
                    continue
                _damage_minion(ss, True, m.uid, n, log)
        if scope in ("all_minions", "all_chars"):
            for m in list(ss.mine):
                _damage_minion(ss, False, m.uid, n, log)
        if scope in ("enemy_chars", "all_chars") and not (tgt and tgt[0] == "face" and scope == "enemy_chars"):
            _hurt_hero(ss, True, n)
        if scope == "all_chars":
            _hurt_hero(ss, False, n)
    if fx.missiles:
        cnt, per = fx.missiles
        per += sp
        k = len(ss.opp)
        if k == 0:                                   # nur der Held ist ein Ziel: jedes Geschoss trifft ihn
            face = cnt * per
            note = f"{face} Schaden ans Gesicht (zufällige Ziele - nur der Held ist übrig)"
        else:                                        # Erwartungswert: jedes Geschoss trifft den Helden mit 1/(k+1)
            face = int(round(cnt * per / (k + 1)))
            ss.util += 0.8                           # der Rest trifft Diener - ungenau, aber nicht wertlos
            note = f"{cnt} Geschosse à {per} Schaden, zufällig verteilt (ca. {face} ins Gesicht)"
        _hurt_hero(ss, True, face)
        if log is not None:
            log.append(note)
    if fx.freeze == "aoe":
        ss.opp[:] =[m._replace(frozen=True) for m in ss.opp]
        if log is not None and ss.opp:
            log.append("alle feindlichen Diener eingefroren")
    if fx.destroy == "aoe":
        for m in list(ss.opp):
            _damage_minion(ss, True, m.uid, 999, log, poison=True)

    if fx.heal:
        ss.my_hp = min(30, ss.my_hp + fx.heal)
        ss.util += min(fx.heal, 8) * 0.25
    if fx.est_value:                             # Entdecken/Zufall: nicht simulierbar, pauschaler Wert
        ss.util += fx.est_value
        if log is not None:
            log.append(f"{fx.est_label}: Wert pauschal geschätzt (kein genauer Effekt) – {fx.est_note}")
    if fx.armor:
        ss.my_armor += fx.armor
        ss.util += fx.armor * 0.3
    if fx.draw:
        ss.util += fx.draw * 1.5
        if log is not None:
            log.append(f"zieht {fx.draw} Karte(n)")
    if fx.mana_refill:
        ss.mana = min(ss.max_mana, ss.mana + fx.mana_refill)
        ss.util -= 0.5
        if log is not None:
            log.append(f"+{fx.mana_refill} Mana")
    if fx.temp_mana:
        ss.mana += fx.temp_mana
        ss.util -= 0.5
        if log is not None:
            log.append(f"+{fx.temp_mana} Mana (nur dieser Zug)")
    if fx.discount:
        ss.disc = ss.disc + (fx.discount,)
        if log is not None:
            log.append("nächste passende Karte billiger")
    if fx.ramp:
        ss.util += 0.6 * fx.ramp             # mehr Mana ab der naechsten Runde
        if log is not None:
            log.append(f"+{fx.ramp} Manakristall(e) ab der nächsten Runde")
    if fx.summon and len(ss.mine) < MAX_BOARD:
        atk, hp, cnt = fx.summon
        if fx.fill_summon:
            cnt = MAX_BOARD - len(ss.mine)
        for _ in range(cnt):
            if len(ss.mine) >= MAX_BOARD:
                break
            ss.uid += 1
            ss.mine.append(M(ss.uid, "Beschworener Diener", "", atk, hp, False, False, False, False, False, False,
                             1, 0, False, False, 0, "", True, bool(fx.summon_freezer)))
        if log is not None:
            log.append(f"beschwört {cnt}x {atk}/{hp}")
    return True


def _secret_value(ss, payload):
    """Erwarteter Wert eines Geheimnisses: Wirkung (z.B. Flaechenschaden) auf das aktuelle Gegner-Board, zu 50 % gewichtet."""
    if payload is None or not (payload.aoe_dmg or payload.freeze == "aoe" or payload.destroy == "aoe"):
        return 0.0
    tmp = ss.clone()
    before = sum(_mval(m) for m in tmp.opp)
    _apply_fx(tmp, payload, None, False, "", None)
    return max(0.0, 0.5 * 1.15 * (before - sum(_mval(m) for m in tmp.opp)))


def _discount_matches(c, kind):
    return (kind == "spell" and c.ctype == "SPELL") or (kind == "minion" and c.ctype == "MINION") or \
        (c.ctype == "MINION" and (c.race == kind or c.race == "ALL"))


def _discount_only(fx):
    """True, wenn der Zauber ausser einem Rabatt fuer die naechste Karte nichts bewirkt."""
    return bool(fx.discount) and not (fx.dmg or fx.aoe_dmg or fx.freeze or fx.destroy or fx.transform or fx.heal
                                      or fx.draw or fx.armor or fx.mana_refill or fx.temp_mana or fx.summon)


def _card_cost(ss, c):
    """Kosten unter Beruecksichtigung aktiver Rabatte. Gibt (kosten, rabatt_index) zurueck."""
    for i, (kind, amt) in enumerate(ss.disc):
        if _discount_matches(c, kind):
            return max(0, c.cost - amt), i
    return c.cost, -1


def _silenced(m):
    return m._replace(taunt=False, ds=False, poison=False, lifesteal=False, stealth=False, sp=0, fzr=False, wf=1)


def _is_hurt(m):
    return m.hp < max(m.mhp, m.hp)


def _race_ok(m, race):
    return not race or m.race == race or m.race == "ALL"


def _healed(m, n):
    """Heilt einen Diener um n (hoechstens bis zum Maximalleben; unbekanntes Maximum = aktuelles Leben)."""
    return m._replace(hp=min(max(m.mhp, m.hp), m.hp + n))


def _grant(m, kws):
    """Schluesselwoerter aus Stärkungszaubern: Gottesschild, Lebensentzug."""
    for kw in kws:
        if kw == "gottesschild":
            m = m._replace(ds=True)
        elif kw == "lebensentzug":
            m = m._replace(lifesteal=True)
    return m


def _buffed(m, buff):
    """Selbststaerkung des gerade gespielten Dieners (Kampfschrei): +Angriff/+Leben und Spott/Eifer/Ansturm."""
    atk, hp, kw = buff
    m = m._replace(atk=m.atk + atk, hp=m.hp + hp, mhp=m.mhp + hp if m.mhp else 0)
    if kw == "spott":
        m = m._replace(taunt=True)
    elif kw == "eifer":                      # Rush: sofort angreifen, aber nur Diener
        m = m._replace(att=max(m.att, m.wf), face=False)
    elif kw == "ansturm":                    # Charge: sofort angreifen, auch den Helden
        m = m._replace(att=max(m.att, m.wf), face=True)
    return m


RACE_DE = {"DRAGON": "Drache", "ELEMENTAL": "Elementar", "DEMON": "Dämon", "BEAST": "Bestie", "MURLOC": "Murloc",
           "PIRATE": "Pirat", "MECHANICAL": "Mech", "UNDEAD": "Untoter", "TOTEM": "Totem"}


def _resolve(ss, c, cards):
    """Kampfschrei mit Bedingung 'wenn Ihr einen <Volk> auf der Hand habt': gilt nur, solange noch eine andere
    passende Karte unausgespielt in der Hand ist (Reihenfolge im Plan zaehlt). Gibt die Karte mit dem wirksamen Effekt zurueck."""
    fx = c.fx
    if fx.buff_per:                           # Staerkung je anderem Diener / je Handkarte: jetzt in feste Werte umrechnen
        kind, a, h = fx.buff_per
        n = len(ss.mine) if kind == "minions" else sum(1 for o in cards if o.idx not in ss.used and o.idx != c.idx)
        return c._replace(fx=dataclasses.replace(fx, self_buff=(a * n, h * n, ""), buff_per=None))
    if not fx.cond_hold or fx.cond_fx is None:
        return c
    if any(o.idx not in ss.used and o.idx != c.idx and (o.race == fx.cond_hold or o.race == "ALL") for o in cards):
        return c._replace(fx=fx.cond_fx)
    return c


def _variants(c):
    """'Waehlt aus': jede erkannte Option ist eine eigene Spielvariante der Karte; sonst nur die Karte selbst."""
    if c.fx.choices:
        return [(i, c._replace(fx=o)) for i, o in enumerate(c.fx.choices)]
    return [(None, c)]


def _play_card(ss, c, tgt, log=None, opt=None):
    """Spielt Karte `c` (C-Tuple) mit Ziel `tgt`. Gibt neuen Zustand oder None zurueck."""
    cost, di = _card_cost(ss, c)
    if cost > ss.mana:
        return None
    n = ss.clone()
    n.mana -= cost
    n.spent += cost
    n.used = ss.used + (c.idx,)
    if di >= 0:
        n.disc = ss.disc[:di] + ss.disc[di + 1:]
    fx = c.fx
    rs = ss.reserve.get(c.name)          # Boss-Tipp: Karte fuer ein bestimmtes Ziel aufheben
    if rs:
        tname = ""
        if tgt and tgt[0] == "m":
            ti = _find(ss.opp, tgt[1])
            tname = ss.opp[ti].name if ti >= 0 else ""
        if rs[0].lower() not in tname.lower():
            n.util -= rs[1]
    if c.ctype == "MINION":
        if len(n.mine) >= MAX_BOARD:
            return None
        n.uid += 1
        wf = 2 if c.wf else 1
        ready = wf if (c.charge or c.rush) else 0
        n.mine.append(M(n.uid, c.name, c.cid, c.atk, c.hp, c.taunt, c.ds, c.poison, False, c.stealth, False, wf,
                        ready, bool(c.charge) or not c.rush, c.lifesteal, 0, c.race, True,
                        FREEZER_TEXT in (c.text or "").lower()))
        if fx.self_buff:
            n.mine[-1] = _buffed(n.mine[-1], fx.self_buff)
        if fx.concrete and not _apply_fx(n, fx, tgt, False, c.name, log):
            return None
    elif c.ctype == "WEAPON":
        n.weapon = (c.atk, c.hp)
        n.hero_atk = c.atk
        if fx.concrete and not _apply_fx(n, fx, tgt, False, c.name, log):
            return None
    else:
        if c.secret:
            n.util += 2.5 + _secret_value(n, fx.payload)
        elif fx.concrete:
            if not _apply_fx(n, fx, tgt, True, c.name, log):
                return None
        else:
            n.util += 1.2
        if c.coin:
            n.util -= 0.3
    n.path = (ss.path, ("play", c.idx, tgt, opt))
    return n


def _attack(ss, att_uid, tgt, log=None):
    """Angriff eines Dieners (att_uid) oder des Helden (att_uid == 0)."""
    n = ss.clone()
    if att_uid == 0:
        atk = n.hero_atk
        n.hero_att -= 1
        a = None
    else:
        i = _find(n.mine, att_uid)
        if i < 0:
            return None
        a = n.mine[i]
        atk = a.atk
        n.mine[i] = a._replace(att=a.att - 1)
    if tgt[0] == "face":
        _hurt_hero(n, True, atk)
        if log is not None:
            log.append(f"{atk} Schaden ans Gesicht")
        if a is not None and a.lifesteal:
            n.my_hp = min(30, n.my_hp + atk)
    else:
        j = _find(n.opp, tgt[1])
        if j < 0:
            return None
        d = n.opp[j]
        # gleichzeitiger Schlagabtausch
        d_atk = d.atk
        ds_lost, d_dead = _damage_minion(n, True, d.uid, atk, log, poison=bool(a and a.poison and atk > 0))
        if a is None:
            _hurt_hero(n, False, d_atk)
            if log is not None and d_atk:
                log.append(f"Held nimmt {d_atk} Schaden")
        else:
            _damage_minion(n, False, a.uid, d_atk, log, poison=d.poison and d_atk > 0)
            if a.lifesteal and not ds_lost:
                n.my_hp = min(30, n.my_hp + atk)
            if a.fzr and atk > 0 and not ds_lost and not d_dead:       # Wasserelementar friert Verletzte ein
                k = _find(n.opp, d.uid)
                if k >= 0:
                    n.opp[k] = n.opp[k]._replace(frozen=True)
                    if log is not None:
                        log.append(f"{d.name} wird eingefroren")
    if att_uid == 0 and n.weapon:
        dur = n.weapon[1] - 1
        if dur <= 0:
            n.weapon, n.hero_atk = None, 0
        else:
            n.weapon = (n.weapon[0], dur)
    n.path = (ss.path, ("att", att_uid, tgt))
    return n


class Planner:
    def __init__(self, db, time_budget=1.2):
        self.db = db
        self.time_budget = time_budget

    # -- Aufbau -----------------------------------------------------------------------
    def _cards(self, s):
        cards = []
        for i, c in enumerate(s.my_hand):
            fx = self.db.effect(c.cid) if c.cid else Effect()
            if c.is_coin and not fx.concrete:
                fx = Effect(temp_mana=1, unknown=False)
            cards.append(C(i, c.name, c.cid, c.cost, c.cardtype, c.text, c.atk, c.hp, c.race, c.taunt,
                           c.divine_shield, c.charge, c.rush, c.stealth, c.windfury, c.poisonous, c.lifesteal,
                           c.secret or fx.secret, fx, c.is_coin))
        return cards

    def _initial(self, s):
        ss = SS()
        ss.mana, ss.max_mana = s.my_mana, s.max_mana
        ss.my_hp, ss.my_armor, ss.opp_hp, ss.opp_armor = s.my_hp, s.my_armor, s.opp_hp, s.opp_armor
        ss.uid = 1000
        ss.mine, ss.opp = [], []
        for m in s.my_minions:
            ready = max(0, m.windfury - m.attacks_done) if m.can_attack else 0
            ss.mine.append(M(m.eid, m.name, m.cid, m.atk, m.hp, m.taunt, m.divine_shield, m.poisonous, m.frozen,
                             m.stealth, m.immune, m.windfury, ready, m.can_attack_face, m.lifesteal, m.spellpower,
                             m.race, True, FREEZER_TEXT in self.db.info(m.cid).get("text", "").lower(), m.max_hp))
        for m in s.opp_minions:
            ss.opp.append(M(m.eid, m.name, m.cid, m.atk, m.hp, m.taunt, m.divine_shield, m.poisonous, m.frozen,
                            m.stealth, m.immune, m.windfury, 0, True, m.lifesteal, 0, m.race, False, False, m.max_hp))
        ss.used = ()
        ss.weapon = (s.my_weapon.atk, s.my_weapon.durability) if s.my_weapon else None
        ss.hero_atk = s.my_hero_atk
        ss.hero_att = s.my_hero_attacks_left
        ss.hp_used = (s.my_hero_power is None) or s.my_hero_power.used
        ss.disc = ()
        ss.util = 0.0
        ss.spent = 0
        ss.path = None
        ss.opp_inc_bonus = s.opp_hero_atk if s.opp_weapon else 0
        b = getattr(self, "_boss", None)
        bias = b.bias if b else {}
        defensive = bool(bias.get("defensive")) or bool(b and b.survive)
        ss.win_hp = b.win_hp if b else 0
        ss.hp_bonus = bias.get("hp_bonus", 0.0)
        ss.def_k = 1.6 if defensive else 1.0
        ss.face_k = bias.get("face", 0.25 if defensive else 1.0)
        ss.prio = dict(bias.get("priority", {}))
        ss.reserve = dict(bias.get("reserve", {}))
        ss.opp_spawn_atk = 0
        ss.temp = 0
        ohp = s.opp_hero_power
        if ohp and ohp.cid and ohp.cost <= s.opp_max_mana + 1:
            summ = self.db.effect(ohp.cid).summon
            if summ:
                ss.opp_spawn_atk = summ[0] * summ[2]
        ss.score = 0.0
        return ss

    # -- Expansion --------------------------------------------------------------------------
    def _expand(self, ss, cards, s, hp_fx):
        out = []
        taunts = [m for m in ss.opp if m.taunt and not m.stealth]
        targets = [("m", m.uid) for m in (taunts if taunts else ss.opp) if not m.stealth]
        face_ok = not taunts
        for m in ss.mine:
            if m.att > 0 and not m.frozen and m.atk > 0:
                for t in targets:
                    n = _attack(ss, m.uid, t)
                    if n:
                        out.append(n)
                if face_ok and m.face:
                    out.append(_attack(ss, m.uid, ("face",)))
        if ss.hero_att > 0 and ss.hero_atk > 0:
            for t in targets:
                n = _attack(ss, 0, t)
                if n:
                    out.append(n)
            if face_ok:
                out.append(_attack(ss, 0, ("face",)))
        seen_names = set()
        for c in cards:
            if c.idx in ss.used:
                continue
            cost, _ = _card_cost(ss, c)
            if cost > ss.mana:
                continue
            c = _resolve(ss, c, cards)
            for opt_i, c in _variants(c):
                key = (c.cid, c.name, opt_i)
                if key in seen_names:      # identische Karten in der Hand nur einmal expandieren
                    continue
                seen_names.add(key)
                if _discount_only(c.fx) and not any(
                        o.idx not in ss.used and o.idx != c.idx and _discount_matches(o, c.fx.discount[0]) for o in cards):
                    continue            # reiner Rabatt-Zauber ohne passende Karte in der Hand waere wirkungslos
                kind = c.fx.target_kind if c.fx.concrete else ""
                if kind:
                    opts = _targets(ss, kind)
                    if c.fx.buff_hurt_only or c.fx.buff_race:
                        opts = [t for t in opts if t[0] == "f" and (not c.fx.buff_hurt_only or _is_hurt(ss.mine[_find(ss.mine, t[1])]))
                                and _race_ok(ss.mine[_find(ss.mine, t[1])], c.fx.buff_race)]
                    if c.fx.needs_frozen:
                        opts = [t for t in opts if t[0] == "m" and ss.opp[_find(ss.opp, t[1])].frozen]
                    if c.fx.max_atk:
                        opts = [t for t in opts if t[0] == "m" and ss.opp[_find(ss.opp, t[1])].atk <= c.fx.max_atk]
                    if c.fx.silence == "target" and not (c.fx.dmg or c.fx.destroy or c.fx.freeze or c.fx.transform):
                        opts = [t for t in opts if t[0] == "m" and _silenced(ss.opp[_find(ss.opp, t[1])]) != ss.opp[_find(ss.opp, t[1])]]
                    if c.fx.freeze == "target" and c.fx.dmg == 0 and c.fx.cond_frozen_dmg == 0 and c.fx.destroy == "":
                        opts = [t for t in opts if t[0] == "m"]
                    for t in opts:
                        n = _play_card(ss, c, t, None, opt_i)
                        if n:
                            out.append(n)
                    if c.ctype == "MINION" and not opts:
                        n = _play_card(ss, c, None, None, opt_i)
                        if n:
                            out.append(n)
                else:
                    n = _play_card(ss, c, None, None, opt_i)
                    if n:
                        out.append(n)
        if not ss.hp_used and s.my_hero_power and s.my_hero_power.cost <= ss.mana:
            hp = s.my_hero_power
            kind = hp_fx.target_kind if hp_fx.concrete else ""
            for t in (_targets(ss, kind) if kind else [None]):
                n = ss.clone()
                n.mana -= hp.cost
                n.spent += hp.cost
                n.hp_used = True
                if hp_fx.concrete:
                    if not _apply_fx(n, hp_fx, t, False, hp.name, None):
                        continue
                else:
                    n.util += 0.6
                n.util += ss.hp_bonus
                n.path = (ss.path, ("hp", t))
                out.append(n)
        return out

    # -- Hauptfunktion ---------------------------------------------------------------------------
    def plan(self, s, boss=None):
        self._boss = boss
        t0 = time.time()
        cards = self._cards(s)
        hp_fx = self.db.effect(s.my_hero_power.cid) if s.my_hero_power and s.my_hero_power.cid else Effect()
        start = self._initial(s)
        start.score = _evaluate(start)
        best = start
        seen = {_key(start)}
        frontier = [start]
        alts = {(): start}
        nodes = 0
        for _ in range(MAX_DEPTH):
            cand = []
            for st in frontier:
                if st.opp_hp + st.opp_armor - st.win_hp <= 0:
                    continue
                for ns in self._expand(st, cards, s, hp_fx):
                    k = _key(ns)
                    if k in seen:
                        continue
                    seen.add(k)
                    ns.score = _evaluate(ns)
                    nodes += 1
                    cand.append(ns)
                    if ns.score > best.score:
                        best = ns
                    sig = tuple(sorted(a[1] for a in _unroll(ns.path) if a[0] == "play")) + \
                        (("hp",) if ns.hp_used and not start.hp_used else ())
                    old = alts.get(sig)
                    if old is None or ns.score > old.score:
                        alts[sig] = ns
            if not cand or time.time() - t0 > self.time_budget:
                break
            cand.sort(key=lambda x: -x.score)
            frontier = cand[:BEAM]
        plan = self._finish(s, cards, hp_fx, start, best)
        plan.nodes = nodes
        ranked = sorted((v for k, v in alts.items() if k != () and v is not best and v.score >= best.score - ALT_MARGIN),
                        key=lambda x: -x.score)
        plan.alternatives = [self._finish(s, cards, hp_fx, start, v, brief=True) for v in ranked[:2]]
        return plan

    # -- Ausgabe -----------------------------------------------------------------------------------
    def _finish(self, s, cards, hp_fx, start, end, brief=False):
        plan = Plan(score=end.score)
        plan.lethal = end.opp_hp + end.opp_armor - end.win_hp <= 0
        plan.win_hp = end.win_hp
        ss = self._initial(s)
        by_idx = {c.idx: c for c in cards}
        names = {m.eid: m for m in s.my_minions}
        names.update({m.eid: m for m in s.opp_minions})
        for act in _unroll(end.path):
            log = []
            if act[0] == "play":
                c0 = by_idx[act[1]]
                c = _resolve(ss, c0, cards)
                opt = act[3] if len(act) > 3 else None
                label = ""
                if opt is not None and c.fx.choices:
                    label = c.fx.choice_labels[opt]
                    c = c._replace(fx=c.fx.choices[opt])
                nxt = _play_card(ss, c, act[2], log, opt)
                if nxt is None:
                    break
                if c is not c0 and c0.fx.cond_hold:
                    log.insert(0, f"Kampfschrei aktiv ({RACE_DE.get(c0.fx.cond_hold, 'passende Karte')} auf der Hand)")
                plan.cids.append(c.cid)
                tname = self._tname(ss, act[2])
                if c.ctype == "MINION":
                    b = c.fx.self_buff or (0, 0, "")
                    head = f"Spiele {c.name} ({c.atk + b[0]}/{c.hp + b[1]})"
                    kind = "minion"
                elif c.ctype == "WEAPON":
                    head = f"Lege {c.name} an ({c.atk}/{c.hp})"
                    kind = "weapon"
                else:
                    head = f"Spiele {c.name}" + (f" – Wahl: {label}" if label else "")
                    kind = "spell"
                    if not c.fx.concrete and not c.secret:
                        plan.unknown_cards.append(c.name)
                        txt_ = (c.text or "").strip()
                        log.append("Effekt unbekannt: " + (txt_[:150] + ("…" if len(txt_) > 150 else "") if txt_ else "Kartentext lesen"))
                if c.secret:
                    log.append("Geheimnis wird vorbereitet")
                txt = head + (f" auf {tname}" if tname and act[2] else "")
                if log:
                    txt += "  →  " + "; ".join(log)
                plan.steps.append(Step(kind, txt, c.cid))
                ss = nxt
            elif act[0] == "att":
                if act[1] == 0:
                    who = f"Held ({ss.hero_atk} Angriff)"
                    nxt = _attack(ss, 0, act[2], log)
                else:
                    a = ss.mine[_find(ss.mine, act[1])]
                    who = f"{a.name} ({a.atk}/{a.hp})"
                    nxt = _attack(ss, act[1], act[2], log)
                if nxt is None:
                    break
                tname = self._tname(ss, act[2])
                txt = f"{who} greift {tname} an"
                if log:
                    txt += "  →  " + "; ".join(log)
                plan.steps.append(Step("hero_attack" if act[1] == 0 else "attack", txt))
                ss = nxt
            elif act[0] == "hp":
                hp = s.my_hero_power
                n = ss.clone()
                n.mana -= hp.cost
                n.spent += hp.cost
                n.hp_used = True
                if hp_fx.concrete:
                    _apply_fx(n, hp_fx, act[1], False, hp.name, log)
                tname = self._tname(ss, act[1])
                txt = f"Heldenkraft: {hp.name} ({hp.cost} Mana)" + (f" auf {tname}" if tname and act[1] else "")
                if log:
                    txt += "  →  " + "; ".join(log)
                plan.steps.append(Step("hero_power", txt))
                ss = n
        plan.mana_used = end.spent
        plan.summary = self._summary(s, end)
        plan.warnings = self._warnings(s, end)
        return plan

    @staticmethod
    def _tname(ss, tgt):
        if not tgt:
            return ""
        if tgt[0] == "face":
            return "den gegnerischen Helden"
        for lst in (ss.opp, ss.mine):
            i = _find(lst, tgt[1])
            if i >= 0:
                m = lst[i]
                label = f"{m.name} ({m.atk}/{m.hp})"
                same = [x for x in lst if x.name == m.name]
                if len(same) > 1:        # gleichnamige Diener unterscheidbar machen
                    label += f" [{i + 1}. von links]"
                return label
        return "?"

    @staticmethod
    def _summary(s, end):
        if end.opp_hp + end.opp_armor - end.win_hp <= 0:
            if end.win_hp:
                return f"SIEGSCHWELLE - der Boss fällt auf {max(end.opp_hp, 0)} Leben (Kampfende bei ≤ {end.win_hp})!"
            return "LETHAL - mit diesem Zug gewinnst du!"
        parts = []
        parts.append(f"Gegner: {max(end.opp_hp, 0)} HP" + (f" +{end.opp_armor} Rüstung" if end.opp_armor else "")
                     + f", {len(end.opp)} Diener")
        parts.append(f"Du: {end.my_hp} HP, {len(end.mine)} Diener")
        return " | ".join(parts)

    @staticmethod
    def _warnings(s, end):
        w = []
        my_total = end.my_hp + end.my_armor
        inc = end.opp_inc_bonus + sum(m.atk * m.wf for m in end.opp if not m.frozen and m.atk > 0)
        block = sum(m.hp for m in end.mine if m.taunt)
        face_inc = max(0, inc - block)
        if face_inc >= my_total:
            w.append(f"GEFAHR: Der Gegner kann dich nächste Runde töten ({inc} Schaden bei {my_total} Leben) - "
                     f"nach Möglichkeit Diener entfernen/einfrieren oder Spott legen.")
        elif my_total - face_inc <= 10 and face_inc > 0:
            w.append(f"GEFAHR: Nach dem nächsten Gegnerzug hättest du nur noch ca. {my_total - face_inc} Leben "
                     f"(bis zu {inc} Schaden bei {my_total}).")
        elif face_inc * 2 >= my_total:
            w.append(f"Vorsicht: Der Gegner droht nächste Runde bis zu {inc} Schaden (du hast {my_total}).")
        if end.opp_spawn_atk:
            w.append(f"Der Gegner beschwört mit seiner Heldenkraft regelmäßig Verstärkung (+{end.opp_spawn_atk} Angriff) - "
                     f"lange Spiele werden gefährlicher.")
        if s.opp_secret_count:
            w.append(f"Gegner hat {s.opp_secret_count} Geheimnis(se) - Angriffe mit wertvollen Dienern gut abwägen.")
        return w
