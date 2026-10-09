"""Spielbrett-Ansicht: Modell (rein berechnet, ohne Fenster) und Zeichnung auf einem tk.Canvas.

`build_model` macht aus Spielstand und Zugplan eine Beschreibung des Bretts (Kacheln, Helden, Pfeile),
`layout` berechnet die Positionen, `BoardView` zeichnet. Alles Gemalte ist selbst gezeichnet; nur die Kartenbilder
(Ausschnitte der von HearthstoneJSON geladenen Karten) kommen von aussen und sind optional.
"""
import math
import re
from dataclasses import dataclass, field

from .effects import clean_text
from .glossary import GLOSSARY

HEIGHT = 380
LEFT = 200                 # linke Spalte fuer die Helden
GAP = 10
MAX_TILE_W = 112
MIN_SLOTS = 5              # so viele Plaetze werden immer eingeplant, damit die Kacheln nicht springen

# Schluesselwoerter -> (Kurztext, Farbschluessel)
BADGES = {
    "SPOTT": ("Spott", "taunt"), "GOTTESSCHILD": ("Schild", "ds"), "GIFT": ("Gift", "poison"),
    "EINGEFROREN": ("Frost", "frozen"), "TARNUNG": ("Tarnung", "stealth"), "WINDZORN": ("Windz.", "wf"),
    "LEBENSRAUB": ("Lebensr.", "ls"), "IMMUN": ("Immun", "ds"), "EIFER": ("Eifer", "rush"), "ANSTURM": ("Ansturm", "wf"),
}


@dataclass
class Tile:
    eid: int
    cid: str
    name: str
    atk: int
    hp: int
    max_hp: int
    mine: bool
    ready: bool = False
    frozen: bool = False
    taunt: bool = False
    ds: bool = False
    stealth: bool = False
    badges: tuple = ()
    marks: tuple = ()          # ((Schritt, "att" | "tgt"), ...)
    text: str = ""             # Kartentext (fuer die Hover-Erklaerung)


@dataclass
class Hero:
    name: str
    hp: int
    armor: int
    hand: int
    deck: int
    secrets: int
    mine: bool
    cid: str = ""
    weapon: str = ""
    marks: tuple = ()          # Schrittnummern, die diesen Helden als Ziel haben
    goal: str = ""             # z. B. "Ziel: <= 10 Leben"


@dataclass
class Arrow:
    n: int
    src: object                # eid des Angreifers oder "hero"
    dst: object                # eid des Ziels oder "face"


@dataclass
class Model:
    opp: Hero
    me: Hero
    opp_tiles: tuple
    my_tiles: tuple
    arrows: tuple = ()
    live: bool = True          # False: Spiel vorbei / noch kein Spiel


def build_model(s, plan=None, goal="", text_of=None):
    """Brett-Modell aus dem Spielstand `s` (state.GameState) und optional dem Zugplan (planner.Plan)."""
    marks = {}                 # eid | "face" -> [(Schritt, Art)]
    arrows = []
    steps = list(plan.steps) if plan is not None else []
    mine_ids = {m.eid for m in s.my_minions}
    opp_ids = {m.eid for m in s.opp_minions}
    for n, st in enumerate(steps, 1):
        dst = st.dst
        d = None
        if dst and dst[0] == "face":
            d = "face"
        elif dst and dst[0] in ("m", "f") and (dst[1] in opp_ids or dst[1] in mine_ids):
            d = dst[1]
        if st.kind in ("attack", "hero_attack"):
            src = "hero" if st.src == 0 else st.src
            if src != "hero" and src not in mine_ids:
                continue
            if d is None:
                continue
            arrows.append(Arrow(n, src, d))
            if src != "hero":
                marks.setdefault(src, []).append((n, "att"))
            marks.setdefault(d, []).append((n, "tgt"))
        elif d is not None:
            marks.setdefault(d, []).append((n, "tgt"))

    def tile(m, mine):
        badges = tuple(BADGES[f][0] for f in m.flags if f in BADGES and f != "EINGEFROREN")
        return Tile(m.eid, m.cid, m.name, m.atk, m.hp, m.max_hp, mine, ready=bool(mine and m.can_attack and not m.frozen),
                    frozen=m.frozen, taunt=m.taunt, ds=m.divine_shield, stealth=m.stealth, badges=badges,
                    marks=tuple(marks.get(m.eid, ())), text=(text_of(m.cid) if text_of and m.cid else ""))

    def weapon(w):
        return f"{w.name} {w.atk}/{w.durability}" if w else ""
    me = Hero(s.my_name or "Du", s.my_hp, s.my_armor, len(s.my_hand), s.my_deck_count, len(s.my_secrets), True,
              cid=s.my_hero_cid, weapon=weapon(s.my_weapon), marks=tuple(n for n, _ in marks.get("hero_me", ())))
    opp = Hero(s.opp_name or "Gegner", s.opp_hp, s.opp_armor, s.opp_hand_count, s.opp_deck_count, s.opp_secret_count, False,
               cid=s.opp_hero_cid, weapon=weapon(s.opp_weapon), marks=tuple(n for n, _ in marks.get("face", ())), goal=goal)
    return Model(opp, me, tuple(tile(m, False) for m in s.opp_minions), tuple(tile(m, True) for m in s.my_minions),
                 tuple(arrows), live=not s.result)


BADGE_GLOSS = {"Spott": "Spott", "Schild": "Gottesschild", "Gift": "Gift", "Tarnung": "Tarnung", "Windz.": "Windzorn",
               "Lebensr.": "Lebensraub", "Eifer": "Eifer", "Ansturm": "Ansturm"}
HAND_H = 150
CARD_KINDS = {"MINION": "Diener", "SPELL": "Zauber", "WEAPON": "Waffe", "HERO": "Held", "LOCATION": "Ort"}


@dataclass
class HCard:
    cid: str
    name: str
    cost: int
    atk: int
    hp: int
    kind: str                  # MINION | SPELL | WEAPON | ...
    text: str = ""
    playable: bool = True      # genug Mana und mein Zug
    marks: tuple = ()          # Schritte des Plans, in denen die Karte gespielt wird
    coin: bool = False


@dataclass
class HandModel:
    cards: tuple
    mana: int
    max_mana: int
    my_turn: bool = False
    overload: int = 0


def build_hand(s, plan=None):
    """Handkarten (nach Kosten sortiert, wie in der Textansicht) mit den Plan-Schritten, die sie spielen."""
    order = sorted(s.my_hand, key=lambda c: (c.cost, c.zpos))
    steps = {}
    if plan is not None:
        for n, st in enumerate(plan.steps, 1):
            if st.kind in ("minion", "spell", "weapon") and st.cid:
                steps.setdefault(st.cid, []).append(n)
    cards = []
    for c in order:
        marks = (steps[c.cid].pop(0),) if steps.get(c.cid) else ()
        cards.append(HCard(c.cid, c.name, c.cost, c.atk, c.hp, c.cardtype, clean_text(c.text or ""),
                           playable=bool(s.my_active and c.cost <= s.my_mana), marks=marks, coin=bool(c.is_coin)))
    return HandModel(tuple(cards), s.my_mana, s.max_mana, my_turn=bool(s.my_active and not s.result))


def gloss_lines(text, extra=()):
    """Erklaerungen der Fachbegriffe, die im Text vorkommen (oder in `extra` genannt sind)."""
    out, seen = [], set()
    for key in list(extra) + [k for k in GLOSSARY if re.search(re.escape(k), text or "", re.I)]:
        if key in GLOSSARY and key not in seen and key.lower() not in ("einfrieren", "friert"):
            seen.add(key)
            out.append(f"{key}: {GLOSSARY[key]}")
    return out[:4]


def tile_tip(t):
    title = f"{t.name}   {t.atk}/{t.hp}" + (f"  (max. {t.max_hp})" if t.hp < t.max_hp else "")
    extra = [BADGE_GLOSS[b] for b in t.badges if b in BADGE_GLOSS] + (["Eingefroren"] if t.frozen else [])
    parts = ([clean_text(t.text)] if t.text else []) + gloss_lines(t.text, extra)
    return title, "\n".join(parts)


def hero_tip(h):
    title = f"{h.name}   {h.hp} Leben" + (f" + {h.armor} Rüstung" if h.armor else "")
    parts = [f"Handkarten: {h.hand}   Deck: {h.deck}" + (f"   Geheimnisse: {h.secrets}" if h.secrets else "")]
    if h.weapon:
        parts.append("Waffe: " + h.weapon)
    if h.goal:
        parts.append(h.goal)
    return title, "\n".join(parts)


def card_tip(c):
    stats = f"   {c.atk}/{c.hp}" if c.kind in ("MINION", "WEAPON") else ""
    title = f"{c.name}   [{c.cost} Mana]{stats}   ({CARD_KINDS.get(c.kind, c.kind.title())})"
    parts = ([c.text] if c.text else []) + gloss_lines(c.text)
    if c.marks:
        parts.append(f"Im Plan: Schritt {c.marks[0]}")
    return title, "\n".join(parts)


def show_tip(canvas, x, y, title, body, pal, width=340):
    """Erklaerungsfeld direkt auf das Canvas zeichnen (am Mauszeiger, innerhalb der Flaeche gehalten)."""
    canvas.delete("tip")
    cw, ch = canvas.winfo_width(), canvas.winfo_height()
    t1 = canvas.create_text(0, 0, text=title, anchor="nw", width=width, fill=pal["TEXT"], font=("Segoe UI", 10, "bold"), tags="tip")
    b1 = canvas.bbox(t1)
    h1 = b1[3] - b1[1]
    t2 = canvas.create_text(0, 0, text=body, anchor="nw", width=width, fill=pal["DIM"], font=("Segoe UI", 9), tags="tip") if body else None
    b2 = canvas.bbox(t2) if t2 else (0, 0, 0, 0)
    w = max(b1[2] - b1[0], b2[2] - b2[0]) + 20
    h = h1 + (b2[3] - b2[1] + 6 if t2 else 0) + 16
    tx = min(max(6, x + 16), max(6, cw - w - 6))
    ty = y + 20 if y + 20 + h < ch - 4 else max(4, y - h - 10)
    box = canvas.create_polygon(tx, ty, tx + w, ty, tx + w, ty + h, tx, ty + h, fill=pal["STRIP"], outline=pal["EDGE"], width=2, tags="tip")
    canvas.tag_lower(box, t1)
    canvas.coords(t1, tx + 10, ty + 8)
    if t2:
        canvas.coords(t2, tx + 10, ty + 8 + h1 + 6)


def layout(n_opp, n_me, width, height=HEIGHT):
    """Positionen: Kachelgroesse, linke obere Ecken beider Reihen, Heldenmitten. Reine Rechnung."""
    avail = max(300, width - LEFT - 14)
    slots = max(n_opp, n_me, MIN_SLOTS)
    tw = int(min(MAX_TILE_W, (avail - GAP * (slots - 1)) // slots))
    tw = max(60, tw)
    th = int(tw * 1.32)
    th = min(th, (height - 28 - 24) // 2)                 # zwei Reihen muessen mit Abstand in die Hoehe passen
    tw = max(50, min(tw, int(th / 1.32)))
    th = int(tw * 1.32)
    top_y = 14
    bot_y = height - 14 - th

    def row(count, y):
        total = count * tw + max(0, count - 1) * GAP
        x0 = LEFT + max(0, (avail - total) // 2)
        return [(x0 + i * (tw + GAP), y) for i in range(count)]
    mid_y = (top_y + th + bot_y) // 2
    return dict(tw=tw, th=th, opp=row(n_opp, top_y), me=row(n_me, bot_y), mid_y=mid_y,
                hero_opp=(LEFT // 2, 120 if height >= 360 else 106), hero_me=(LEFT // 2, mid_y + (62 if height >= 360 else 54)),
                hero_r=44 if height >= 360 else 36,
                width=width, height=height)


def height_for(window_height):
    """Hoehe der Brettflaeche: bei kleinen Fenstern kompakter, damit Plan und Boss-Info noch Platz haben."""
    return int(max(300, min(HEIGHT, window_height * 0.30)))


def edge_point(box, tx, ty):
    """Punkt, an dem der Strahl vom Mittelpunkt von `box` = (cx, cy, halbe_breite, halbe_hoehe, rund) zu (tx, ty) den Rand trifft."""
    cx, cy, hw, hh, circle = box
    dx, dy = tx - cx, ty - cy
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return cx, cy
    if circle:
        k = hw / dist
    else:
        k = min(hw / abs(dx) if dx else float("inf"), hh / abs(dy) if dy else float("inf"))
    return cx + dx * k, cy + dy * k


def arrow_points(src, dst, gap=3):
    """Anfang und Spitze eines Angriffspfeils: Er beginnt am Rand des Angreifers und endet genau am Rand des Ziels."""
    dy_c = dst[1] - src[1]
    if not src[4] and not dst[4] and abs(dy_c) > (src[3] + dst[3]) * 0.6:
        # Kachel gegen Kachel in verschiedenen Reihen: Pfeil endet mittig am Rand des Ziels (eindeutig lesbar)
        up = dy_c < 0
        sx, sy = src[0], src[1] + (-src[3] if up else src[3])
        ex, ey = dst[0], dst[1] + (dst[3] if up else -dst[3])
    else:
        sx, sy = edge_point(src, dst[0], dst[1])
        ex, ey = edge_point(dst, src[0], src[1])
    dx, dy = ex - sx, ey - sy
    dist = math.hypot(dx, dy)
    if dist > 2 * gap + 6:                          # kleiner Abstand, damit Rand und Pfeilspitze nicht verschmelzen
        ux, uy = dx / dist, dy / dist
        sx, sy, ex, ey = sx + ux * gap, sy + uy * gap, ex - ux * gap, ey - uy * gap
    return sx, sy, ex, ey


def _fit(text, chars):
    return text if len(text) <= chars else text[:max(1, chars - 1)] + "…"


class BoardView:
    """Zeichnet ein Modell auf ein Canvas. `images` ist der ImageCache (optional), `pal` die Farbwelt (theme.BOARD)."""

    def __init__(self, canvas, images, pal):
        self.c, self.images, self.p = canvas, images, pal
        self._last = None
        self._h = HEIGHT
        self.hits = []             # (x1, y1, x2, y2, titel, text) fuer die Hover-Erklaerung

    # -- Hilfen --------------------------------------------------------------------------------
    def rrect(self, x1, y1, x2, y2, r=10, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
               x1, y1 + r, x1, y1]
        return self.c.create_polygon(pts, smooth=True, **kw)

    def gem(self, x, y, r, fill, text, fg="#ffffff", size=13, outline="#000000"):
        self.c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=2)
        self.c.create_text(x, y, text=str(text), fill=fg, font=("Segoe UI", size, "bold"))

    def mark(self, x, y, n, kind):
        col = self.p["MARK_ATT"] if kind == "att" else self.p["MARK_TGT"]
        self.gem(x, y, 11, col, n, fg="#ffffff", size=10)

    # -- Zeichnen ---------------------------------------------------------------------------------
    def draw(self, model, width, height=HEIGHT, force=False):
        key = (model, width, height)
        if not force and key == self._last:
            return
        self._last = key
        self._h = height
        c, p = self.c, self.p
        lay = layout(len(model.opp_tiles), len(model.my_tiles), width, height)
        c.delete("all")
        self.hits = []
        c.create_rectangle(0, 0, width, height, fill=p["BG"], outline="")
        c.create_line(LEFT - 8, 8, LEFT - 8, height - 8, fill=p["EDGE"], width=2)
        c.create_line(LEFT, lay["mid_y"], width - 12, lay["mid_y"], fill=p["EDGE"], width=2, dash=(10, 8))
        centers = {}
        for t, (x, y) in zip(model.opp_tiles, lay["opp"]):
            self._tile(t, x, y, lay["tw"], lay["th"])
            centers[t.eid] = (x + lay["tw"] / 2, y + lay["th"] / 2, lay["tw"] / 2, lay["th"] / 2, False)
            self.hits.append((x, y, x + lay["tw"], y + lay["th"]) + tile_tip(t))
        for t, (x, y) in zip(model.my_tiles, lay["me"]):
            self._tile(t, x, y, lay["tw"], lay["th"])
            centers[t.eid] = (x + lay["tw"] / 2, y + lay["th"] / 2, lay["tw"] / 2, lay["th"] / 2, False)
            self.hits.append((x, y, x + lay["tw"], y + lay["th"]) + tile_tip(t))
        for hero, key in ((model.opp, "hero_opp"), (model.me, "hero_me")):
            self._hero(hero, *lay[key], lay["hero_r"])
            hx, hy = lay[key]
            self.hits.append((hx - lay["hero_r"], hy - lay["hero_r"], hx + lay["hero_r"], hy + lay["hero_r"]) + hero_tip(hero))
        r = lay["hero_r"] + 5
        centers["hero"] = (*lay["hero_me"], r, r, True)
        centers["face"] = (*lay["hero_opp"], r, r, True)
        for a in model.arrows:
            self._arrow(a, centers, lay)
        if not model.opp_tiles and not model.my_tiles:
            c.create_text(LEFT + (width - LEFT) // 2, lay["mid_y"] - 22, text="Noch keine Diener auf dem Brett", fill=p["DIM"],
                          font=("Segoe UI", 12))

    def _tile(self, t, x, y, w, h):
        c, p = self.c, self.p
        base = p["TILE_ME"] if t.mine else p["TILE_OPP"]
        edge = p["READY"] if t.ready else (p["TILE_EDGE_ME"] if t.mine else p["TILE_EDGE_OPP"])
        self.rrect(x, y, x + w, y + h, 12, fill=base, outline=edge, width=4 if t.ready else 2)
        if any(kind == "tgt" for _, kind in t.marks):                 # Ziel im Plan: roter Ring um die ganze Kachel
            self.rrect(x - 4, y - 4, x + w + 4, y + h + 4, 15, fill="", outline=p["MARK_TGT"], width=3)
        if t.taunt:
            self.rrect(x + 3, y + 3, x + w - 3, y + h - 3, 10, fill="", outline=p["TAUNT"], width=3)
        if t.ds:
            self.rrect(x + 6, y + 6, x + w - 6, y + h - 6, 8, fill="", outline=p["DS"], width=2)
        ax1, ay1, ax2, ay2 = x + 9, y + 9, x + w - 9, y + int(h * 0.50)
        photo = self.images.art(t.cid, ax2 - ax1, ay2 - ay1) if self.images is not None and t.cid else None
        if photo is not None:
            c.create_image((ax1 + ax2) // 2, (ay1 + ay2) // 2, image=photo)
            c.create_rectangle(ax1, ay1, ax2, ay2, outline=p["EDGE"], width=1)
        else:
            c.create_rectangle(ax1, ay1, ax2, ay2, fill=p["ART"], outline=p["EDGE"])
            c.create_text((ax1 + ax2) // 2, (ay1 + ay2) // 2, text=(t.name[:1] or "?").upper(), fill=p["DIM"],
                          font=("Segoe UI", 26, "bold"))
        sy = y + int(h * 0.52)
        c.create_rectangle(x + 6, sy, x + w - 6, sy + 20, fill=p["STRIP"], outline="")
        c.create_text(x + w // 2, sy + 10, text=_fit(t.name, int((w - 14) / 6.4)), fill=p["TEXT"], font=("Segoe UI", 9, "bold"))
        bx = x + 8
        by = sy + 24
        for text in t.badges[:3]:
            bw = 7 * len(text) + 8
            if bx + bw > x + w - 6:
                break
            self.rrect(bx, by, bx + bw, by + 14, 5, fill=p["BADGE"], outline="")
            c.create_text(bx + bw / 2, by + 7, text=text, fill=p["BADGE_TEXT"], font=("Segoe UI", 8, "bold"))
            bx += bw + 4
        if t.frozen:
            self.rrect(x, y, x + w, y + h, 12, fill=p["FROZEN"], outline="", stipple="gray50")
            c.create_text(x + w - 16, y + 18, text="❄", fill="#e8f6ff", font=("Segoe UI Symbol", 16, "bold"))
        elif t.stealth:
            self.rrect(x, y, x + w, y + h, 12, fill="#000000", outline="", stipple="gray25")
        hurt = t.hp < t.max_hp
        self.gem(x + 16, y + h - 16, 15, p["ATK"], t.atk, fg="#2b1a00")
        self.gem(x + w - 16, y + h - 16, 15, p["HP_HURT"] if hurt else p["HP"], t.hp)
        for i, (n, kind) in enumerate(t.marks[:3]):
            self.mark(x + 12 + i * 24, y - 2 if y < self._h // 2 else y + 2, n, kind)

    def _hero(self, hero, cx, cy, r):
        c, p = self.c, self.p
        ring = p["RING_ME"] if hero.mine else p["RING_OPP"]
        c.create_oval(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5, fill=ring, outline=p["EDGE"], width=2)
        photo = self.images.art(hero.cid, 2 * r - 6, 2 * r - 6, hero=True) if self.images is not None and hero.cid else None
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=p["HERO_FILL_ME"] if hero.mine else p["HERO_FILL_OPP"], outline="")
        if photo is not None:
            c.create_image(cx, cy, image=photo)
        else:
            c.create_text(cx, cy, text=(hero.name[:1] or "?").upper(), fill=p["TEXT"], font=("Segoe UI", 34, "bold"))
        low = hero.hp <= 10
        self.gem(cx + r - 4, cy + r - 8, 20, p["HP_HURT"] if low else p["HP"], hero.hp, size=16)
        if hero.armor:
            self.gem(cx - r + 4, cy + r - 8, 16, p["ARMOR"], hero.armor, size=13)
        # Textblock: beim Gegner ueber dem Kreis, bei mir darunter
        base = cy - r - 46 if not hero.mine else cy + r + 18
        lines = [(_fit(hero.name, 22), ("Segoe UI", 11, "bold"), p["TEXT"]),
                 (f"Hand {hero.hand}  ·  Deck {hero.deck}" + (f"  ·  Geh. {hero.secrets}" if hero.secrets else ""),
                  ("Segoe UI", 9), p["DIM"])]
        if hero.weapon:
            lines.append(("⚔ " + _fit(hero.weapon, 22), ("Segoe UI", 9), p["DIM"]))
        for i, (text, font, fg) in enumerate(lines):
            if base + i * 16 <= self._h - 8:                       # nichts ausserhalb der Flaeche zeichnen
                c.create_text(cx, base + i * 16, text=text, fill=fg, font=font)
        if hero.goal:
            c.create_text(cx, cy + r + 20, text=hero.goal, fill=p["MARK_TGT"], font=("Segoe UI", 9, "bold"))
        if hero.marks:
            c.create_oval(cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10, outline=p["MARK_TGT"], width=3)
        for i, n in enumerate(hero.marks[:4]):
            self.mark(cx + r + 6, cy - r + 6 + i * 24, n, "tgt")

    def _arrow(self, a, centers, lay):
        src, dst = centers.get(a.src), centers.get(a.dst)
        if not src or not dst:
            return
        sx, sy, ex, ey = arrow_points(src, dst)
        self.c.create_line(sx, sy, ex, ey, fill=self.p["ARROW_SHADOW"], width=8, arrow="last", arrowshape=(16, 18, 7),
                           capstyle="round")
        self.c.create_line(sx, sy, ex, ey, fill=self.p["ARROW"], width=4, arrow="last", arrowshape=(14, 16, 6), capstyle="round")
        self.gem((sx + ex) / 2, (sy + ey) / 2, 11, self.p["ARROW"], a.n, fg="#143015", size=10)


def hand_layout(n, width, height):
    """Kartengroesse und linke Ecken der Handkarten; links bleibt die Manaspalte (LEFT) frei."""
    avail = max(300, width - LEFT - 14)
    gap = 8
    cw = int(min(104, (avail - gap * (max(n, 1) - 1)) // max(n, 1, 5)))
    cw = max(54, cw)
    ch = min(int(cw * 1.3), height - 16)
    cw = max(54, min(cw, int(ch / 1.3)))
    ch = int(cw * 1.3)
    total = n * cw + max(0, n - 1) * gap
    x0 = LEFT + max(0, (avail - total) // 2)
    y = (height - ch) // 2
    return dict(cw=cw, ch=ch, xs=[(x0 + i * (cw + gap), y) for i in range(n)], height=height, width=width)


class HandView:
    """Handkarten als Kartenreihe und die Manakristalle links davon."""

    def __init__(self, canvas, images, pal):
        self.c, self.images, self.p = canvas, images, pal
        self._last = None
        self.hits = []

    def draw(self, model, width, height=HAND_H, force=False):
        key = (model, width, height)
        if not force and key == self._last:
            return
        self._last = key
        c, p = self.c, self.p
        c.delete("all")
        self.hits = []
        c.create_rectangle(0, 0, width, height, fill=p["BG"], outline="")
        c.create_line(LEFT - 8, 8, LEFT - 8, height - 8, fill=p["EDGE"], width=2)
        self._mana(model, height)
        lay = hand_layout(len(model.cards), width, height)
        for card, (x, y) in zip(model.cards, lay["xs"]):
            self._card(card, x, y, lay["cw"], lay["ch"])
            self.hits.append((x, y, x + lay["cw"], y + lay["ch"]) + card_tip(card))
        if not model.cards:
            c.create_text(LEFT + (width - LEFT) // 2, height // 2, text="Keine Handkarten", fill=p["DIM"], font=("Segoe UI", 12))

    def _gem(self, x, y, r, fill, text, fg="#ffffff", size=11):
        self.c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="#000000", width=2)
        self.c.create_text(x, y, text=str(text), fill=fg, font=("Segoe UI", size, "bold"))

    def _mana(self, model, height):
        c, p = self.c, self.p
        mx = max(model.max_mana, model.mana, 1)
        per_row = 5
        x0, y0 = 26, height // 2 - 26
        for i in range(mx):
            cx = x0 + (i % per_row) * 30
            cy = y0 + (i // per_row) * 34
            full = i < model.mana
            pts = [cx, cy - 13, cx + 11, cy, cx, cy + 13, cx - 11, cy]
            c.create_polygon(pts, fill=p["ATK_MANA"] if full else p["BG"], outline=p["MANA_EDGE"], width=2)
            if full:
                c.create_line(cx - 4, cy - 2, cx, cy - 8, fill="#ffffff", width=2)
        c.create_text(x0 + 60, y0 + ((mx - 1) // per_row + 1) * 34 + 6, text=f"Mana {model.mana} / {model.max_mana}", fill=p["TEXT"],
                      font=("Segoe UI", 11, "bold"))

    def _card(self, card, x, y, w, h):
        c, p = self.c, self.p
        base = p["TILE_ME"] if card.kind == "MINION" else p["CARD_SPELL"]
        edge = p["READY"] if (card.marks and card.playable) else (p["TILE_EDGE_ME"] if card.playable else p["EDGE"])
        BoardView.rrect(self, x, y, x + w, y + h, 10, fill=base, outline=edge, width=4 if card.marks else 2)
        ax1, ay1, ax2, ay2 = x + 7, y + 8, x + w - 7, y + int(h * 0.50)
        photo = self.images.art(card.cid, ax2 - ax1, ay2 - ay1) if self.images is not None and card.cid else None
        if photo is not None:
            c.create_image((ax1 + ax2) // 2, (ay1 + ay2) // 2, image=photo)
            c.create_rectangle(ax1, ay1, ax2, ay2, outline=p["EDGE"])
        else:
            c.create_rectangle(ax1, ay1, ax2, ay2, fill=p["ART"], outline=p["EDGE"])
            c.create_text((ax1 + ax2) // 2, (ay1 + ay2) // 2, text=(card.name[:1] or "?").upper(), fill=p["DIM"],
                          font=("Segoe UI", 20, "bold"))
        sy = y + int(h * 0.52)
        c.create_rectangle(x + 5, sy, x + w - 5, sy + 18, fill=p["STRIP"], outline="")
        c.create_text(x + w // 2, sy + 9, text=_fit(card.name, int((w - 12) / 6.2)), fill=p["TEXT"], font=("Segoe UI", 9, "bold"))
        self._gem(x + 13, y + 14, 12, p["ATK_MANA"], card.cost, size=11)
        if card.kind in ("MINION", "WEAPON"):
            self._gem(x + 14, y + h - 14, 12, p["ATK"], card.atk, fg="#2b1a00", size=11)
            self._gem(x + w - 14, y + h - 14, 12, p["HP"], card.hp, size=11)
        if not card.playable:
            BoardView.rrect(self, x, y, x + w, y + h, 10, fill="#000000", outline="", stipple="gray50")
        if card.marks:
            self._gem(x + w - 14, y + 14, 12, p["MARK_ATT"], card.marks[0], size=11)
