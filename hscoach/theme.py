"""Farbwelten der Oberflaeche. `klassisch` = bisheriges dunkelblaues Design, `spielbrett` = Hearthstone-Brett aus Holz,
Stein und Pergament (alle Flaechen selbst gemalt, keine Blizzard-Grafiken)."""

BOARD_KLASSISCH = dict(
    BG="#10182a", EDGE="#2a3b5c", DIM="#8794b0", TEXT="#e8eeff", ART="#0c1220", STRIP="#0a1020", BADGE="#2a3b5c",
    BADGE_TEXT="#e8eeff", TILE_ME="#16314a", TILE_OPP="#3a1d22", TILE_EDGE_ME="#2f6f9f", TILE_EDGE_OPP="#8a3a44",
    READY="#66ff88", TAUNT="#c8d0e0", DS="#66e0ff", FROZEN="#8fd0ff", ATK="#f0b429", HP="#c0392b", HP_HURT="#e8651a",
    ARMOR="#6a7a99", RING_ME="#2f6f9f", RING_OPP="#8a3a44", HERO_FILL_ME="#16314a", HERO_FILL_OPP="#3a1d22",
    MARK_ATT="#2f8f4f", MARK_TGT="#c0392b", ARROW="#7dff9a", ARROW_SHADOW="#0a1a10",
    ATK_MANA="#3aa0ff", MANA_EDGE="#0a3a6b", CARD_SPELL="#4a3a7a",
)

BOARD_SPIELBRETT = dict(
    BG="#4a3d2e", EDGE="#2a2016", DIM="#c9b48a", TEXT="#f6ecd2", ART="#2a2218", STRIP="#241c12", BADGE="#6b4527",
    BADGE_TEXT="#ffe9b8", TILE_ME="#2f5f84", TILE_OPP="#7a3a2a", TILE_EDGE_ME="#a8d8ff", TILE_EDGE_OPP="#e0a080",
    READY="#7dff9a", TAUNT="#e6b84a", DS="#ffe27a", FROZEN="#9fd8ff", ATK="#f0b429", HP="#c0392b", HP_HURT="#e8651a",
    ARMOR="#7a8aa8", RING_ME="#d6a93a", RING_OPP="#d6a93a", HERO_FILL_ME="#2f5f84", HERO_FILL_OPP="#7a3a2a",
    MARK_ATT="#2f8f4f", MARK_TGT="#c0392b", ARROW="#7dff9a", ARROW_SHADOW="#10240f",
    ATK_MANA="#3aa0ff", MANA_EDGE="#0a3a6b", CARD_SPELL="#5a3a7a",
)

KLASSISCH = dict(
    NAME="klassisch", WOOD=False, PLANK=False, FRAME_PAD=0,
    ROOT="#0d0d1a", BG="#0d0d1a", BG2="#111130", TEXTBG="#080818", HDR="#1a1a3e", LINE="#222244",
    BTN="#1a1a3e", BTN_ACTIVE="#2a2a5e", DIMFG="#555577", VS="#444466",
    GREEN="#66ff88", RED="#ff6666", YELLOW="#ffdd44", BLUE="#66aaff", GRAY="#888899", GOLD="#ffd700",
    BOARD=BOARD_KLASSISCH, BORDER="", BORDER_W=0, PARCH="", CAPTION="#12122b", CAPTION_TEXT="#c8c8e8", CAPTION_BORDER="#222244",
    TAGS=dict(step="#e8e8ff", info="#7788aa", dim="#777788", kw="#aabbff", opp="#ff9999", warn="#ffaa44", sleep="#666677",
              no="#666677", ds="#66e0ff", frozen="#99ccff", stealth="#bb99ff"),
)

SPIELBRETT = dict(
    NAME="spielbrett", WOOD=True, PLANK=True, FRAME_PAD=20,
    ROOT="#5a3a22", BG="#2c2620", BG2="#3a3027", TEXTBG="#211d18", HDR="#5a3a22", LINE="#6b5230",
    BTN="#6b4527", BTN_ACTIVE="#8a5a30", DIMFG="#c9b48a", VS="#9a8060",
    GREEN="#8fe08a", RED="#ff9a8a", YELLOW="#ffd36a", BLUE="#8ec8ff", GRAY="#c4b89e", GOLD="#f0c24a",
    BOARD=BOARD_SPIELBRETT, BORDER="#8a6a3a", BORDER_W=2, PARCH="#e6d3a0", CAPTION="#3a2414", CAPTION_TEXT="#f0d9a8", CAPTION_BORDER="#8a6a3a",
    TAGS=dict(step="#f4e9cf", info="#c4b89e", dim="#a89c84", kw="#ffd89a", opp="#ffb0a2", warn="#ffb45a", sleep="#9a8e78",
              no="#9a8e78", ds="#8fe8ff", frozen="#b0d4ff", stealth="#d0b8ff"),
)

# Pergament (heller Untergrund): dunkle Schrift
PARCHMENT_TAGS = dict(
    step="#3b2a14", info="#6b5230", dim="#7a6a4a", kw="#1f3f8a", opp="#8a2a2a", warn="#9a3a1a", sleep="#8a7a5a", no="#8a7a5a",
    ds="#1a6a8a", frozen="#2a5a8a", stealth="#5a3a8a", ready="#2a6a2a", ok="#2a6a2a", me="#2a6a2a", taunt="#8a5a00",
    plan="#7a5a10", head="#7a5a10", lethal="#1f6a2a", arrow="#1f4f8a",
)

THEMES = {"klassisch": KLASSISCH, "spielbrett": SPIELBRETT}
CHOICES = tuple(THEMES)


def get(name):
    return THEMES.get(name or "", KLASSISCH)
