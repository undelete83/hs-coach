"""Aus dem Tracker (Entities) einen lesbaren Spielstand bauen."""
from dataclasses import dataclass, field

ZONE_PLAY, ZONE_HAND, ZONE_DECK, ZONE_SECRET = "PLAY", "HAND", "DECK", "SECRET"


@dataclass
class Minion:
    eid: int
    name: str
    cid: str
    atk: int
    hp: int
    max_hp: int
    race: str = ""
    taunt: bool = False
    divine_shield: bool = False
    poisonous: bool = False
    frozen: bool = False
    stealth: bool = False
    windfury: int = 1             # erlaubte Angriffe pro Zug
    lifesteal: bool = False
    reborn: bool = False
    immune: bool = False
    elusive: bool = False
    rush: bool = False
    charge: bool = False
    deathrattle: bool = False
    spellpower: int = 0
    exhausted: bool = False
    attacks_done: int = 0
    turns_in_play: int = 0
    zpos: int = 0

    @property
    def can_attack(self):
        return self.atk > 0 and not self.frozen and not self.exhausted and self.attacks_done < self.windfury

    @property
    def can_attack_face(self):
        if not self.can_attack:
            return False
        return not (self.rush and not self.charge and self.turns_in_play == 0)

    @property
    def flags(self):
        f = []
        if self.taunt:
            f.append("SPOTT")
        if self.divine_shield:
            f.append("GOTTESSCHILD")
        if self.poisonous:
            f.append("GIFT")
        if self.frozen:
            f.append("EINGEFROREN")
        if self.stealth:
            f.append("TARNUNG")
        if self.windfury > 1:
            f.append("WINDZORN")
        if self.lifesteal:
            f.append("LEBENSRAUB")
        if self.immune:
            f.append("IMMUN")
        if self.rush and self.turns_in_play == 0:
            f.append("ANSTURM")
        return f

    def label(self):
        ico = "⚡" if self.can_attack else "  "
        txt = f"{ico} {self.name}  {self.atk}/{self.hp}"
        if self.flags:
            txt += f"  [{', '.join(self.flags)}]"
        return txt


@dataclass
class Card:
    eid: int
    name: str
    cid: str
    cost: int
    cardtype: str
    text: str = ""
    atk: int = 0
    hp: int = 0
    race: str = ""
    zpos: int = 0
    taunt: bool = False
    divine_shield: bool = False
    charge: bool = False
    rush: bool = False
    stealth: bool = False
    windfury: bool = False
    poisonous: bool = False
    lifesteal: bool = False
    secret: bool = False
    targeting: str = None
    is_coin: bool = False

    @property
    def line(self):
        s = f"[{self.cost}💎] {self.name}"
        if self.cardtype == "MINION":
            s += f"  {self.atk}/{self.hp}"
        elif self.cardtype == "WEAPON":
            s += f"  {self.atk}/{self.hp} (Waffe)"
        if self.text:
            s += f"\n     {self.text}"
        return s


@dataclass
class Weapon:
    name: str
    cid: str
    atk: int
    durability: int


@dataclass
class HeroPower:
    name: str
    cid: str
    cost: int
    used: bool
    text: str = ""


@dataclass
class GameState:
    game_no: int = 0
    turn: int = 0
    my_active: bool = False
    step: str = ""
    mulligan: bool = False
    result: str = ""                # WON | LOST | TIED | ""
    my_name: str = ""
    opp_name: str = "Gegner"
    my_hp: int = 30
    my_armor: int = 0
    opp_hp: int = 30
    opp_armor: int = 0
    my_hero_atk: int = 0
    my_hero_can_attack: bool = False
    my_hero_attacks_left: int = 0
    my_mana: int = 0
    my_mana_used: int = 0
    max_mana: int = 0
    my_corpses: int = None
    my_spellpower: int = 0
    my_minions: list = field(default_factory=list)
    opp_minions: list = field(default_factory=list)
    my_hand: list = field(default_factory=list)
    opp_hand_count: int = 0
    my_deck_count: int = 0
    opp_deck_count: int = 0
    my_weapon: Weapon = None
    opp_weapon: Weapon = None
    opp_hero_atk: int = 0
    my_hero_power: HeroPower = None
    opp_hero_power: HeroPower = None
    opp_max_mana: int = 0
    opp_hero_cid: str = ""
    my_secrets: list = field(default_factory=list)
    opp_secret_count: int = 0
    events: list = field(default_factory=list)      # gerenderte Zeilen, aelteste zuerst
    opp_played: list = field(default_factory=list)
    game_type: str = ""
    ui_known: bool = False            # liegen PowerTaskList-Zugmarker vor?
    ui_my_turn: bool = False          # zeigt der Bildschirm schon meinen Zug?
    ui_step: str = ""

    def signature(self):
        return (
            self.game_no, self.turn, self.my_active, self.step, self.ui_my_turn, self.ui_step, self.mulligan, self.result, self.my_hp, self.my_armor,
            self.opp_hp, self.opp_armor, self.my_mana, self.max_mana, self.my_corpses, self.my_hero_atk,
            tuple((m.eid, m.atk, m.hp, m.frozen, m.can_attack, m.taunt, m.divine_shield) for m in self.my_minions),
            tuple((m.eid, m.atk, m.hp, m.frozen, m.taunt, m.divine_shield, m.stealth) for m in self.opp_minions),
            tuple((c.eid, c.cost) for c in self.my_hand),
            (self.my_weapon.atk, self.my_weapon.durability) if self.my_weapon else None,
            (self.opp_weapon.atk, self.opp_weapon.durability) if self.opp_weapon else None,
            self.my_hero_power.used if self.my_hero_power else None, self.opp_secret_count,
        )


def _flag(tags, key, default=False):
    v = tags.get(key)
    if v is None:
        return bool(default)
    return bool(v) and v != "0"


def resolve_name(db, ent):
    cid = ent.get("cardId", "")
    nm = db.name(cid) if cid else ""
    if nm:
        return nm
    nm = ent.get("name", "")
    if nm and "UNKNOWN" not in nm:
        return nm
    return cid or "???"


def _stat(tags, key, db_val):
    v = tags.get(key)
    if isinstance(v, int):
        return v
    return db_val or 0


def build_state(tr, db):
    """Snapshot des aktuellen Spiels. `tr` ist ein logparser.Tracker, `db` eine CardDB."""
    s = GameState(game_no=tr.game_no, game_type=tr.game_type)
    ents = tr.entities
    if not ents:
        return s
    tr.refresh_me()
    me = tr.my_pid or 1
    opp = tr.opp_pid
    ge = ents.get(1, {}).get("tags", {})
    s.turn = ge.get("TURN", 0) or 0
    s.step = ge.get("STEP", "") or ""
    s.ui_known = tr.ui_current_pid is not None
    s.ui_my_turn = tr.ui_current_pid == me
    s.ui_step = tr.ui_step
    s.my_name = tr.pid_name.get(me, "")
    s.opp_name = tr.pid_name.get(opp, "Gegner")

    pt = tr.player_tags(me)
    ot = tr.player_tags(opp)
    res = pt.get("RESOURCES", 0) or 0
    used = pt.get("RESOURCES_USED", 0) or 0
    temp = pt.get("TEMP_RESOURCES", 0) or 0
    locked = pt.get("OVERLOAD_LOCKED", 0) or 0
    s.max_mana = res
    s.my_mana_used = used
    s.opp_max_mana = ot.get("RESOURCES", 0) or 0
    s.my_mana = max(0, res + temp - used - locked)
    s.my_active = bool(pt.get("CURRENT_PLAYER", 0))
    corpses = pt.get("CORPSES")
    if corpses is None:
        corpses = pt.get("CORPSE_COUNT")
    if corpses is not None:
        s.my_corpses = max(0, corpses - (pt.get("CORPSES_SPENT_THIS_GAME", 0) or 0))
    ps = pt.get("PLAYSTATE", "")
    if ps in ("WON", "LOST", "TIED"):
        s.result = ps
    elif ps in ("CONCEDED", "QUIT"):
        s.result = "LOST"
    s.mulligan = s.step == "BEGIN_MULLIGAN" and pt.get("MULLIGAN_STATE") in ("INPUT", "DEALING")

    hero_ids = {me: pt.get("HERO_ENTITY"), opp: ot.get("HERO_ENTITY")}
    for pid, heid in hero_ids.items():
        h = ents.get(heid)
        if not h:
            continue
        t = h["tags"]
        hp = _stat(t, "HEALTH", 30) - (t.get("DAMAGE", 0) or 0)
        armor = t.get("ARMOR", 0) or 0
        atk = t.get("ATK", 0) or 0
        if pid == me:
            s.my_hp, s.my_armor, s.my_hero_atk = hp, armor, atk
            max_att = 2 if _flag(t, "WINDFURY") else 1
            left = max_att - (t.get("NUM_ATTACKS_THIS_TURN", 0) or 0)
            s.my_hero_attacks_left = 0 if _flag(t, "FROZEN") else max(0, left)
            s.my_hero_can_attack = atk > 0 and s.my_hero_attacks_left > 0
        else:
            s.opp_hp, s.opp_armor, s.opp_hero_atk = hp, armor, atk
            s.opp_hero_cid = h.get("cardId", "")
            nm = resolve_name(db, h)
            if nm and nm != "???":
                s.opp_name = nm

    for eid, e in ents.items():
        if not isinstance(eid, int):
            continue
        t = e["tags"]
        ctrl = t.get("CONTROLLER", 0)
        zone = t.get("ZONE", "")
        ctype = t.get("CARDTYPE", "")
        cid = e.get("cardId", "")
        info = db.info(cid) if cid else {}
        if ctrl not in (me, opp):
            continue
        mine = ctrl == me

        if zone == ZONE_PLAY and ctype == "MINION":
            wf = 4 if _flag(t, "MEGA_WINDFURY", info.get("mega_windfury")) else (2 if _flag(t, "WINDFURY", info.get("windfury")) else 1)
            hp_max = _stat(t, "HEALTH", info.get("health"))
            m = Minion(
                eid=eid, name=resolve_name(db, e), cid=cid,
                atk=_stat(t, "ATK", info.get("atk")),
                hp=hp_max - (t.get("DAMAGE", 0) or 0), max_hp=hp_max,
                race=(t.get("CARDRACE") if isinstance(t.get("CARDRACE"), str) else info.get("race", "")),
                taunt=_flag(t, "TAUNT", info.get("taunt")),
                divine_shield=_flag(t, "DIVINE_SHIELD", info.get("divine_shield")),
                poisonous=_flag(t, "POISONOUS", info.get("poisonous")),
                frozen=_flag(t, "FROZEN"),
                stealth=_flag(t, "STEALTH", info.get("stealth")),
                windfury=wf,
                lifesteal=_flag(t, "LIFESTEAL", info.get("lifesteal")),
                reborn=_flag(t, "REBORN", info.get("reborn")),
                immune=_flag(t, "IMMUNE"),
                elusive=_flag(t, "ELUSIVE", info.get("elusive")),
                rush=_flag(t, "RUSH", info.get("rush")),
                charge=_flag(t, "CHARGE", info.get("charge")),
                deathrattle=_flag(t, "DEATHRATTLE", info.get("deathrattle")),
                spellpower=_stat(t, "SPELLPOWER", info.get("spellpower")),
                exhausted=_flag(t, "EXHAUSTED"),
                attacks_done=t.get("NUM_ATTACKS_THIS_TURN", 0) or 0,
                turns_in_play=t.get("NUM_TURNS_IN_PLAY", 0) or 0,
                zpos=t.get("ZONE_POSITION", 0) or 0,
            )
            (s.my_minions if mine else s.opp_minions).append(m)

        elif zone == ZONE_PLAY and ctype == "WEAPON":
            w = Weapon(resolve_name(db, e), cid, _stat(t, "ATK", info.get("atk")),
                       _stat(t, "HEALTH", info.get("health")) - (t.get("DAMAGE", 0) or 0))
            if mine:
                s.my_weapon = w
            else:
                s.opp_weapon = w

        elif zone == ZONE_PLAY and ctype == "HERO_POWER":
            hp = HeroPower(resolve_name(db, e), cid, _stat(t, "COST", info.get("cost")),
                           _flag(t, "EXHAUSTED"), info.get("text", ""))
            if mine:
                s.my_hero_power = hp
            else:
                s.opp_hero_power = hp

        elif zone == ZONE_HAND:
            if mine:
                ct = ctype or info.get("cardtype", "")
                s.my_hand.append(Card(
                    eid=eid, name=resolve_name(db, e), cid=cid,
                    cost=_stat(t, "COST", info.get("cost")), cardtype=ct, text=info.get("text", ""),
                    atk=_stat(t, "ATK", info.get("atk")), hp=_stat(t, "HEALTH", info.get("health")),
                    race=(t.get("CARDRACE") if isinstance(t.get("CARDRACE"), str) else info.get("race", "")),
                    zpos=t.get("ZONE_POSITION", 0) or 0,
                    taunt=_flag(t, "TAUNT", info.get("taunt")), divine_shield=_flag(t, "DIVINE_SHIELD", info.get("divine_shield")),
                    charge=_flag(t, "CHARGE", info.get("charge")), rush=_flag(t, "RUSH", info.get("rush")),
                    stealth=_flag(t, "STEALTH", info.get("stealth")), windfury=_flag(t, "WINDFURY", info.get("windfury")),
                    poisonous=_flag(t, "POISONOUS", info.get("poisonous")), lifesteal=_flag(t, "LIFESTEAL", info.get("lifesteal")),
                    secret=_flag(t, "SECRET", info.get("secret")), targeting=info.get("targeting"),
                    is_coin=cid == "GAME_005",
                ))
            else:
                s.opp_hand_count += 1

        elif zone == ZONE_DECK:
            if mine:
                s.my_deck_count += 1
            else:
                s.opp_deck_count += 1

        elif zone == ZONE_SECRET:
            if mine:
                s.my_secrets.append(resolve_name(db, e))
            else:
                s.opp_secret_count += 1

    s.my_minions.sort(key=lambda m: m.zpos)
    s.opp_minions.sort(key=lambda m: m.zpos)
    s.my_hand.sort(key=lambda c: c.zpos)
    s.my_spellpower = sum(m.spellpower for m in s.my_minions)
    _build_events(s, tr, db, me)
    return s


def render_events(tr, db, me):
    """Alle Spielzuege als Textzeilen (aelteste zuerst) + Liste der vom Gegner gespielten Karten."""
    ents = tr.entities
    seen_opp = []
    lines = []
    for ev in list(tr.events):
        a = ents.get(ev["actor"])
        if not a:
            continue
        who = "Du" if ev["pid"] == me else "Gegner"
        an = resolve_name(db, a)
        if an == "???":
            continue
        ctype = a["tags"].get("CARDTYPE", "")
        if ev["type"] == "ATTACK":
            tgt = ents.get(ev["target"]) if ev["target"] is not None else None
            tn = resolve_name(db, tgt) if tgt else "?"
            lines.append(f"R{ev['turn']}  {who}: {an}  ⚔  {tn}")
        elif ctype == "HERO_POWER":
            lines.append(f"R{ev['turn']}  {who} nutzt Heldenkraft: {an}")
        else:
            lines.append(f"R{ev['turn']}  {who} {'spielst' if who == 'Du' else 'spielt'}: {an}")
            if who == "Gegner" and an not in seen_opp:
                seen_opp.append(an)
    return lines, seen_opp


def _build_events(s, tr, db, me):
    lines, seen_opp = render_events(tr, db, me)
    s.events = lines[-40:]
    s.opp_played = seen_opp
