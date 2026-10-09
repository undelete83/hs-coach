"""Tk-Oberflaeche. Alles Rechnen (Log lesen, Planen, API) passiert in Hintergrund-Threads."""
import logging
import os
import queue
import re
import threading
import time
import tkinter as tk

from . import analysis, bosses, config, detect, glossary, settings, theme, textures, tips, update, version, winstyle
from .ai import ClaudeCoach
from .carddb import CardDB
from .images import ImageCache, PIL_OK
from .logparser import Tracker
from .planner import Planner
from .state import build_state, render_events

log = logging.getLogger("hscoach.gui")

_THEME_KEYS = ("ROOT", "BG", "BG2", "TEXTBG", "HDR", "LINE", "BTN", "BTN_ACTIVE", "DIMFG", "VS", "GREEN", "RED", "YELLOW",
               "BLUE", "GRAY", "GOLD", "BORDER", "BORDER_W", "PARCH", "WOOD", "PLANK", "FRAME_PAD", "TAGS", "CAPTION",
               "CAPTION_TEXT", "CAPTION_BORDER")


def apply_theme(name):
    """Farben des gewaehlten Designs als Modul-Konstanten setzen (vor dem Aufbau des Fensters)."""
    t = theme.get(name)
    g = globals()
    for k in _THEME_KEYS:
        g[k] = t[k]
    return t


apply_theme("klassisch")
SETTLE_MAX_S = 45.0   # Sicherheitsnetz: so lange wartet der Zugbeginn hoechstens auf den Bildschirm
KW_RE = re.compile("|".join(re.escape(k) for k in glossary.KEYWORDS))


GEO_RE = re.compile(r"^(\d+)x(\d+)(?:\+(-?\d+)\+(-?\d+))?$")      # Tk liefert negative Positionen als "+-2223"
DEFAULT_SIZE = "1680x1248"


def virtual_screen():
    """(x, y, breite, hoehe) des gesamten Desktops ueber alle Monitore (Windows), sonst None."""
    try:
        import ctypes
        u = ctypes.windll.user32
        return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
    except Exception:
        return None


def resolve_geometry(geo, screen=None):
    """Gespeicherte Fenstergeometrie pruefen: Groesse und Position werden uebernommen, solange das Fenster noch auf einem
    vorhandenen Monitor sichtbar waere (Monitor abgesteckt/Aufloesung geaendert -> nur die Groesse)."""
    m = GEO_RE.match(geo or "")
    if not m:
        return DEFAULT_SIZE
    w, h = int(m.group(1)), int(m.group(2))
    if m.group(3) is None:
        return f"{w}x{h}"
    x, y = int(m.group(3)), int(m.group(4))
    if screen:
        vx, vy, vw, vh = screen
        visible = vx - w + 120 <= x <= vx + vw - 120 and vy <= y <= vy + vh - 80
    else:
        visible = abs(x) <= 9000 and abs(y) <= 9000
    return f"{w}x{h}+{x}+{y}" if visible else f"{w}x{h}"


def strip_md(text):
    """Das Textfeld zeigt kein Markdown: Fettdruck/Code-Markierungen entfernen."""
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"^#+\s*", "", text, flags=re.M)


class Backend:
    """Liest das Log in einem eigenen Thread und stellt den neuesten Spielstand bereit."""

    def __init__(self, cfg, db):
        self.cfg, self.db = cfg, db
        self.tracker = Tracker(cfg["log_dir"], cfg["player_name"])
        self.latest = None
        self.version = 0
        self.log_path = None
        self._lock = threading.Lock()
        self._stop = False
        self.force = False
        threading.Thread(target=self._loop, daemon=True, name="poller").start()

    def stop(self):
        self._stop = True

    def _loop(self):
        self.db.ready.wait(timeout=60)
        while not self._stop:
            try:
                changed = self.tracker.update() or self.force
                self.log_path = self.tracker.path
                if changed and self.tracker.entities:
                    self.force = False
                    s = build_state(self.tracker, self.db)
                    with self._lock:
                        self.latest, self.version = s, self.version + 1
            except Exception:
                log.exception("Poller-Fehler")
            time.sleep(max(0.2, self.cfg["refresh_ms"] / 1000))

    def get(self):
        with self._lock:
            return self.latest, self.version


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.build = version.BuildInfo()
        self._newer_checked = 0.0
        self._newer = ""
        self._release = None          # update.Release eines neueren GitHub-Releases
        self._auto_update = False     # darf sich diese Installation selbst aktualisieren?
        self._closed = False
        self._geo_job = None
        self._img_job = None
        self._wood_job = None
        self._wood_key = None
        self._wood_photo = None
        self._updating = False
        self._update_msg = ""
        self._logcfg_state = detect.check_log_config()
        self.title(f"HS Coach {self.build.label}")
        apply_theme(self.cfg.get("design"))
        self.configure(bg=ROOT)
        self._apply_geometry()
        self.minsize(1100, 760)

        self.db = CardDB(self.cfg)
        self.db.load_async()
        self.backend = Backend(self.cfg, self.db)
        self.planner = Planner(self.db, self.cfg["plan_time_budget_s"])
        self.coach = ClaudeCoach(self.cfg)
        self.coach.preload()
        self.images = ImageCache(self.cfg)

        self._calls = queue.Queue()
        self._seen_version = 0
        self._state = None
        self._plan = None
        self._plan_sig = None
        self._plan_job = None
        self._planning = False
        self._rich_sig = {}
        self._last_active = False
        self._claude_turn = -1
        self._claude_want = False
        self._sig_changed_at = time.time()
        self._active_since = 0.0
        self._plan_visible = False
        self._present_pending = False
        self._ai_busy = False
        self._ai_token = 0
        self._game_no = None
        self._tips_log = []
        self._turn_logged = -1
        self._counted = set()
        self.wins = self.losses = 0
        self._img_cids = []
        self._img_labels = []
        self._kw_bound = set()
        self._analysis_busy = False
        self.boss = None

        self.var_top = tk.BooleanVar(value=bool(self.cfg["always_on_top"]))
        self.var_claude = tk.BooleanVar(value=bool(self.cfg["use_claude"]))
        self.var_hand_img = tk.BooleanVar(value=bool(self.cfg["show_hand_images"]))
        self._build()
        self.attributes("-topmost", self.var_top.get())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<F5>", lambda e: self._replan(force=True))
        self.report_callback_exception = lambda *a: log.error("Tk-Callback-Fehler", exc_info=a)
        self.after(150, self._drain)
        self.after(30, lambda: winstyle.style_titlebar(self, CAPTION, CAPTION_TEXT, CAPTION_BORDER))
        self.after(60, self._wood_refresh)
        self.after(600, self._first_run)
        self.bind("<Configure>", self._on_configure, add="+")
        self.lbl_status.bind("<Button-1>", self._open_release)
        update.check_async(self.cfg, lambda found: self.post(lambda: self._on_release(found)))
        self.after(30 * 60 * 1000, self._periodic_update_check)

    # -- Aufbau -------------------------------------------------------------------------------
    def _apply_geometry(self):
        self.geometry(resolve_geometry(self.cfg["geometry"], virtual_screen()))

    def _text(self, parent, height, fg, max_height=None, parchment=False, **pack):
        bg = PARCH if parchment else TEXTBG
        t = tk.Text(parent, bg=bg, fg=fg, height=height, font=("Consolas", 11), relief="flat", bd=6,
                    state="disabled", wrap="word", cursor="arrow", highlightthickness=BORDER_W,
                    highlightbackground=BORDER or bg, highlightcolor=BORDER or bg)
        t.pack(fill=pack.get("fill", "x"), expand=pack.get("expand", False), padx=10, pady=(0, 4))
        t._min_h, t._max_h = height, max_height or height          # waechst bei langem Inhalt bis max_height mit
        if t._max_h > t._min_h:
            t.bind("<Configure>", lambda e, w=t: self._autosize(w), add="+")
        bold = ("Consolas", 11, "bold")
        tags = {
            "ready": dict(foreground=GREEN, font=bold), "sleep": dict(foreground="#666677"),
            "taunt": dict(foreground=YELLOW, font=bold), "ds": dict(foreground="#66e0ff"),
            "frozen": dict(foreground="#99ccff"), "stealth": dict(foreground="#bb99ff"),
            "ok": dict(foreground=GREEN), "no": dict(foreground="#666677"), "plan": dict(foreground=GOLD, font=bold),
            "warn": dict(foreground="#ffaa44", font=bold), "lethal": dict(foreground=GREEN, font=("Consolas", 12, "bold")),
            "info": dict(foreground="#7788aa"), "me": dict(foreground=GREEN), "opp": dict(foreground="#ff9999"),
            "dim": dict(foreground="#777788"), "step": dict(foreground="#e8e8ff"), "arrow": dict(foreground=BLUE),
            "head": dict(foreground=GOLD, font=bold), "kw": dict(underline=True, foreground="#aabbff"),
        }
        for name, color in (theme.PARCHMENT_TAGS if parchment else TAGS).items():
            if name in tags:
                tags[name]["foreground"] = color
        for name, kw in tags.items():
            t.tag_configure(name, **kw)
        return t

    def _section(self, parent, title, color):
        tk.Frame(parent, bg=LINE, height=1).pack(fill="x", padx=10)
        if PLANK:                                    # Spielbrett: Titel auf einer Holzleiste
            lbl = tk.Label(parent, text=title, bg=HDR, fg=color, font=("Segoe UI", 11, "bold"), anchor="w", padx=8, pady=3)
            lbl.pack(fill="x", padx=10, pady=(6, 3))
        else:
            lbl = tk.Label(parent, text=title, bg=BG, fg=color, font=("Segoe UI", 11, "bold"))
            lbl.pack(anchor="w", padx=12, pady=(6, 2))
        return lbl

    def _build(self):
        # Statuszeile zuerst packen: sie behaelt ihren Platz auch bei kleinen Fenstern (dort steht der Update-Hinweis)
        self.lbl_status = tk.Label(self, text="", bg=ROOT, fg=DIMFG, font=("Consolas", 8))
        self.lbl_status.pack(side="bottom", pady=3)
        self._wood_label = None
        if WOOD and textures.PIL_OK:                 # Holztextur als Rahmen: liegt hinter dem Inhalt, nur am Rand sichtbar
            self._wood_label = tk.Label(self, bd=0, bg=ROOT)
            self._wood_label.place(x=0, y=0, relwidth=1, relheight=1)
            self._wood_label.lower()
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=FRAME_PAD, pady=(FRAME_PAD, 0))
        hdr = tk.Frame(self.body, bg=HDR, pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚔  HEARTHSTONE COACH", bg=HDR, fg=GOLD, font=("Segoe UI", 18, "bold")).pack()
        self.lbl_turn = tk.Label(hdr, text="Warte auf Hearthstone...", bg=HDR, fg=GRAY, font=("Segoe UI", 13))
        self.lbl_turn.pack()

        bar = tk.Frame(self.body, bg=BG2, pady=3)
        bar.pack(fill="x")

        def chk(text, var, cmd):
            return tk.Checkbutton(bar, text=text, variable=var, command=cmd, bg=BG2, fg=GRAY, selectcolor=HDR,
                                  activebackground=BG2, activeforeground=GOLD, font=("Segoe UI", 10), cursor="hand2")

        chk("Immer im Vordergrund", self.var_top, self._toggle_top).pack(side="left", padx=8)
        chk("Hand als Bilder", self.var_hand_img, self._toggle_hand_img).pack(side="left", padx=8)
        chk("Claude API", self.var_claude, self._toggle_claude).pack(side="left", padx=8)

        def btn(text, cmd):
            return tk.Button(bar, text=text, command=cmd, bg=BTN, fg=GOLD, relief="flat",
                             font=("Segoe UI", 10), cursor="hand2", activebackground=BTN_ACTIVE, activeforeground=GOLD)

        btn("⚙ Einstellungen", self._open_settings).pack(side="right", padx=8)
        self.btn_update = btn("⟳ Auf Update prüfen", self._check_update)
        self.btn_update.pack(side="right", padx=4)
        self.btn_analysis = btn("📝 Analyse", self._analyze)
        self.btn_analysis.pack(side="right", padx=8)
        self.btn_ai = btn("💡 KI-Tipp", lambda: self._ask_claude(manual=True))
        self.btn_ai.pack(side="right", padx=4)
        btn("🔄 Plan neu (F5)", lambda: self._replan(force=True)).pack(side="right", padx=4)

        hp = tk.Frame(self.body, bg=BG2, pady=8)
        hp.pack(fill="x")
        lf = tk.Frame(hp, bg=BG2)
        lf.pack(side="left", expand=True)
        tk.Label(lf, text="DU", bg=BG2, fg=GREEN, font=("Segoe UI", 12, "bold")).pack()
        self.lbl_my_hp = tk.Label(lf, text="❤  30", bg=BG2, fg=GREEN, font=("Segoe UI", 32, "bold"))
        self.lbl_my_hp.pack()
        self.lbl_my_armor = tk.Label(lf, text="", bg=BG2, fg=BLUE, font=("Segoe UI", 13))
        self.lbl_my_armor.pack()
        self.lbl_my_info = tk.Label(lf, text="", bg=BG2, fg=GRAY, font=("Segoe UI", 10))
        self.lbl_my_info.pack()
        tk.Label(hp, text="vs", bg=BG2, fg=VS, font=("Segoe UI", 18)).pack(side="left", padx=16)
        rf = tk.Frame(hp, bg=BG2)
        rf.pack(side="left", expand=True)
        self.lbl_opp_name = tk.Label(rf, text="GEGNER", bg=BG2, fg=RED, font=("Segoe UI", 12, "bold"))
        self.lbl_opp_name.pack()
        self.lbl_opp_hp = tk.Label(rf, text="❤  30", bg=BG2, fg=RED, font=("Segoe UI", 32, "bold"))
        self.lbl_opp_hp.pack()
        self.lbl_opp_armor = tk.Label(rf, text="", bg=BG2, fg=BLUE, font=("Segoe UI", 13))
        self.lbl_opp_armor.pack()
        self.lbl_opp_info = tk.Label(rf, text="", bg=BG2, fg=GRAY, font=("Segoe UI", 10))
        self.lbl_opp_info.pack()

        res = tk.Frame(self.body, bg=BG)
        res.pack(pady=4)
        self.lbl_mana = tk.Label(res, text="💎  Mana: —", bg=BG, fg=BLUE, font=("Segoe UI", 15, "bold"))
        self.lbl_mana.pack(side="left", padx=10)
        self.lbl_corpses = tk.Label(res, text="", bg=BG, fg="#cc88ff", font=("Segoe UI", 15, "bold"))
        self.lbl_corpses.pack(side="left", padx=10)
        self.lbl_extra = tk.Label(res, text="", bg=BG, fg=GRAY, font=("Segoe UI", 11))
        self.lbl_extra.pack(side="left", padx=10)

        self.lbl_opp_power = tk.Label(self.body, text="", bg=BG, fg=TAGS["opp"], font=("Segoe UI", 10), wraplength=1500)
        self.lbl_opp_power.pack()

        boards = tk.Frame(self.body, bg=BG)
        boards.pack(fill="x")
        of = tk.Frame(boards, bg=BG)
        of.pack(side="left", fill="both", expand=True)
        self._section(of, "👹  GEGNER BOARD", RED)
        self.t_opp = self._text(of, 6, RED, 10)
        tk.Frame(boards, bg=LINE, width=1).pack(side="left", fill="y", pady=4)
        mf = tk.Frame(boards, bg=BG)
        mf.pack(side="left", fill="both", expand=True)
        self._section(mf, "🛡  DEIN BOARD", GREEN)
        self.t_mine = self._text(mf, 6, GREEN, 10)

        mid = tk.Frame(self.body, bg=BG)
        mid.pack(fill="x")
        hf = tk.Frame(mid, bg=BG)
        hf.pack(side="left", fill="both", expand=True)
        self._section(hf, "🃏  HAND  (★ = im Plan, unterstrichen = Begriff, Maus drüber für Erklärung)", YELLOW)
        self.t_hand = self._text(hf, 9, YELLOW, 14)
        self.lbl_gloss = tk.Label(hf, text="", bg=BG, fg="#aabbff", font=("Segoe UI", 10), anchor="w", justify="left",
                                  wraplength=760)
        self.lbl_gloss.pack(fill="x", padx=12)
        tk.Frame(mid, bg=LINE, width=1).pack(side="left", fill="y", pady=4)
        ef = tk.Frame(mid, bg=BG)
        ef.pack(side="left", fill="both", expand=True)
        self._section(ef, "📜  LETZTE SPIELZÜGE", GRAY)
        self.t_events = self._text(ef, 9, GRAY, 12)

        tip = tk.Frame(self.body, bg=BG)
        tip.pack(fill="x")
        pf = tk.Frame(tip, bg=BG)
        pf.pack(side="left", fill="both", expand=True)
        self._section(pf, "🧭  ZUGPLAN  (Regel-Engine, live)", GOLD)
        self.t_plan = self._text(pf, 10, GOLD, 26, parchment=bool(PARCH))
        # Boss-Spalte: nur sichtbar, wenn ein bekannter Boss spielt (Spalte zwischen Plan und KI)
        self.boss_frame = tk.Frame(tip, bg=BG)
        tk.Frame(self.boss_frame, bg=LINE, width=1).pack(side="left", fill="y", pady=4)
        bcol = tk.Frame(self.boss_frame, bg=BG)
        bcol.pack(side="left", fill="both", expand=True)
        self.lbl_boss = self._section(bcol, "📖  BOSS-INFO", "#ffcc88")
        self.t_boss = self._text(bcol, 12, "#ffcc88", 18)
        self.ai_frame = tk.Frame(tip, bg=BG)
        self.ai_frame.pack(side="left", fill="both", expand=True)
        tk.Frame(self.ai_frame, bg=LINE, width=1).pack(side="left", fill="y", pady=4)
        af = tk.Frame(self.ai_frame, bg=BG)
        af.pack(side="left", fill="both", expand=True)
        self._section(af, "🤖  KI-TIPP  (Claude)", "#aaccff")
        self.t_ai = self._text(af, 10, "#aaccff", 16)
        self.lbl_cost = tk.Label(af, text="", bg=BG, fg=GRAY, font=("Consolas", 8))
        self.lbl_cost.pack(anchor="e", padx=14)

        self.img_frame = tk.Frame(self.body, bg=BG)
        self.img_frame.pack(fill="x", padx=10, pady=(2, 4))
        self._set_ai_idle()

    # -- Hilfen ----------------------------------------------------------------------------------
    def _autosize(self, widget):
        """Textfeld so hoch machen, dass der Inhalt (mit Zeilenumbruechen) sichtbar ist - hoechstens bis _max_h."""
        lo, hi = getattr(widget, "_min_h", 0), getattr(widget, "_max_h", 0)
        if hi <= lo or widget.winfo_width() < 60:
            return
        try:
            res = widget.count("1.0", "end-1c", "displaylines")
        except tk.TclError:
            return
        n = res[0] if isinstance(res, tuple) else (res or 1)
        want = max(lo, min(hi, int(n)))
        if int(widget.cget("height")) != want:
            widget.config(height=want)
            self._schedule_img_refresh()

    def _set_rich(self, key, widget, segments):
        sig = tuple(segments)
        if self._rich_sig.get(key) == sig:
            return
        self._rich_sig[key] = sig
        top = widget.yview()[0]
        widget.config(state="normal")
        widget.delete("1.0", "end")
        for text, tag in segments:
            if tag and tag.startswith("kw:"):
                self._bind_kw(widget, tag)
                widget.insert("end", text, (tag, "kw"))
            else:
                widget.insert("end", text, (tag,) if tag else ())
        widget.config(state="disabled")
        self._autosize(widget)
        widget.yview_moveto(top)

    def _bind_kw(self, widget, tag):
        key = (str(widget), tag)
        if key in self._kw_bound:
            return
        self._kw_bound.add(key)
        word = tag[3:]
        widget.tag_bind(tag, "<Enter>", lambda e, w=word: self.lbl_gloss.config(text=f"{w}: {glossary.GLOSSARY[w]}"))
        widget.tag_bind(tag, "<Leave>", lambda e: self.lbl_gloss.config(text=""))

    @staticmethod
    def _kw_segments(text, base=None):
        segs, pos = [], 0
        for m in KW_RE.finditer(text):
            if m.start() > pos:
                segs.append((text[pos:m.start()], base))
            segs.append((m.group(0), "kw:" + m.group(0)))
            pos = m.end()
        if pos < len(text):
            segs.append((text[pos:], base))
        return segs

    # -- Einstellungen --------------------------------------------------------------------------
    def _toggle_top(self):
        self.attributes("-topmost", self.var_top.get())
        self.cfg["always_on_top"] = self.var_top.get()
        config.save(self.cfg, ["always_on_top"])

    def _toggle_hand_img(self):
        self.cfg["show_hand_images"] = self.var_hand_img.get()
        config.save(self.cfg, ["show_hand_images"])
        self._refresh_images(force=True)

    def _toggle_claude(self):
        if self.var_claude.get() and not config.has_api_key(self.cfg):
            self.var_claude.set(False)
            self._set_ai_idle()
            self._open_settings()
        self.cfg["use_claude"] = self.var_claude.get()
        config.save(self.cfg, ["use_claude"])

    def _set_ai_idle(self):
        if config.has_api_key(self.cfg):
            msg = ("Claude ist aus. Schalte oben „Claude API“ ein und klicke auf „KI-Tipp“ - "
                   "oder nutze den kostenlosen Zugplan links.")
        else:
            msg = ("Der Coach arbeitet ohne KI: Der Zugplan links ist die Regel-Engine und kostet nichts.\n"
                   "Optional: Unter „⚙ Einstellungen“ einen eigenen Anthropic-API-Key eintragen, dann gibt es "
                   "zusätzlich KI-Tipps und Spielanalysen.")
        self._set_rich("ai", self.t_ai, [(msg, "dim")])

    def _open_settings(self):
        settings.SettingsDialog(self)

    def on_settings_changed(self, changed):
        if not changed:
            return
        if "api_key" in changed or "claude_model" in changed or "analysis_model" in changed:
            self.coach._client = None                  # neuer Key / neues Modell -> Client neu aufbauen
            self.coach.preload()
        if "api_key" in changed and not config.has_api_key(self.cfg):
            self.var_claude.set(False)
            self.cfg["use_claude"] = False
            config.save(self.cfg, ["use_claude"])
        self._set_ai_idle()
        if "show_card_images" in changed:
            self._refresh_images(force=True)
        if settings.needs_restart(changed):
            self._set_rich("ai", self.t_ai, [("Gespeichert. Log-Ordner, Spielername und Kartenquelle wirken nach einem "
                                              "Neustart des Coaches.", "info")])

    def _first_run(self):
        if config.is_first_run():
            self._open_settings()

    def _on_release(self, found):
        self._release = found
        self._auto_update = bool(found.asset_url and found.sha256 and update.can_self_update())
        if self._auto_update and os.environ.get("HS_COACH_UPDATE_URL") and os.environ.get("HS_COACH_UPDATE_AUTO"):
            self._start_update(found)          # Testhook: Ende-zu-Ende-Test gegen einen lokalen Server, ohne Klick

    def _check_update(self):
        """Button: sofort bei GitHub nachsehen - ohne den Coach neu zu starten."""
        if self._updating:
            return
        self.btn_update.config(state="disabled", text="⏳ Prüfe ...")

        def done(status, result):
            self.post(lambda: self._update_checked(status, result))
        update.check_now_async(self.cfg, done)

    def _update_checked(self, status, result):
        from tkinter import messagebox
        self.btn_update.config(state="normal", text="⟳ Auf Update prüfen")
        if status == "new":
            self._on_release(result)
            self._open_release()
        elif status == "current":
            messagebox.showinfo("Update", f"Du hast bereits die neueste Version ({self.build.version}).", parent=self)
        else:
            messagebox.showwarning("Update", f"Die Suche nach Updates ist fehlgeschlagen:\n{result}\n\n"
                                   "Internetverbindung prüfen und später erneut versuchen.", parent=self)

    def _periodic_update_check(self):
        """Alle 30 Minuten still nachsehen, damit der Hinweis auch ohne Neustart erscheint."""
        if not self._closed and self.cfg.get("update_check") and not self._release and not self._updating:
            update.check_async(self.cfg, lambda found: self.post(lambda: self._on_release(found)))
        if not self._closed:
            self.after(30 * 60 * 1000, self._periodic_update_check)

    def _open_release(self, _event=None):
        r = self._release
        if not r or self._updating:
            return
        if not self._auto_update:
            import webbrowser
            webbrowser.open(r.url)
            return
        from tkinter import messagebox
        s = self._state
        warn = "\n\nAchtung: Es läuft gerade eine Partie - der Coach wird kurz beendet." if (
            s is not None and not s.result and (s.turn or s.mulligan)) else ""
        if messagebox.askyesno("Update", f"Version {r.version} jetzt installieren?\n\nDer Coach lädt das Update, prüft es "
                               "und startet danach neu. Einstellungen und API-Key bleiben erhalten." + warn, parent=self):
            self._start_update(r)

    def _start_update(self, r):
        import os
        self._updating = True
        self._update_msg = f"⬇ Update {r.version} wird geladen ..."
        work_dir = os.path.join(config.APP_DIR, "update")

        def progress(done, total):
            pct = f" {done * 100 // total}%" if total else ""
            self.post(lambda: setattr(self, "_update_msg", f"⬇ Update {r.version} wird geladen ...{pct}"))

        def work():
            try:
                new_dir = update.prepare(r, self.cfg["update_repo"], work_dir, progress)
                self.post(lambda: setattr(self, "_update_msg", f"⟳ Update {r.version} wird installiert - der Coach startet neu ..."))
                update.install_and_restart(new_dir, work_dir)
            except Exception as ex:
                log.exception("Update fehlgeschlagen")
                self.post(lambda: self._update_failed(str(ex), r))
                return
            self.post(self._on_close)
        threading.Thread(target=work, daemon=True, name="self-update").start()

    def _update_failed(self, err, r):
        from tkinter import messagebox
        self._updating = False
        self._update_msg = ""
        messagebox.showerror("Update fehlgeschlagen", f"{err}\n\nDu kannst das Paket auch von Hand laden:\n{r.url}",
                             parent=self)

    def _schedule_wood(self):
        if self._wood_label is not None and self._wood_job is None and not self._closed:
            self._wood_job = self.after(250, self._wood_refresh)

    def _wood_refresh(self):
        """Holzrahmen fuer die aktuelle Fenstergroesse malen (in 64-Pixel-Stufen, damit nicht jedes Pixel neu gemalt wird)."""
        self._wood_job = None
        if self._closed or self._wood_label is None:
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        key = ((w + 63) // 64 * 64, (h + 63) // 64 * 64)
        if key == self._wood_key:
            return
        try:
            from PIL import ImageTk
            self._wood_photo = ImageTk.PhotoImage(textures.wood(*key))
            self._wood_label.config(image=self._wood_photo)
            self._wood_key = key
        except Exception:
            log.exception("Holztextur konnte nicht gemalt werden")
            self._wood_label = None

    def _on_configure(self, event):
        """Fenster verschoben oder in der Groesse geaendert: nach kurzer Ruhe speichern (nicht erst beim Schliessen)."""
        if event.widget is not self or self._closed:
            return
        self._schedule_img_refresh()
        self._schedule_wood()
        if self._geo_job:
            self.after_cancel(self._geo_job)
        self._geo_job = self.after(1500, self._save_geometry)

    def _save_geometry(self):
        self._geo_job = None
        try:
            if self._closed or self.state() != "normal":
                return
            geo = self.geometry()
            if geo != self.cfg.get("geometry"):
                self.cfg["geometry"] = geo
                config.save(self.cfg, ["geometry"])
        except Exception:
            pass

    def _on_close(self):
        self._save_geometry()
        self._closed = True
        self.backend.stop()
        self.destroy()

    # -- Zustand empfangen -------------------------------------------------------------------------
    def post(self, fn):
        """Thread-sicher: fn wird im GUI-Thread ausgefuehrt."""
        self._calls.put(fn)

    def _drain(self):
        if self._closed:
            return
        while True:
            try:
                fn = self._calls.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                log.exception("GUI-Callback-Fehler")
            if self._closed:             # ein Callback (z. B. Update) hat das Fenster geschlossen
                return
        try:
            s, v = self.backend.get()
            if s is not None and v != self._seen_version:
                self._seen_version = v
                self._on_state(s)
            self._update_status()
            if (self._present_pending and self._state is not None and self._plan is not None
                    and not self._plan_stale(self._state) and not self._settling()):
                self._present(self._state, self._plan)
            self._maybe_ask_claude()
        except Exception:
            log.exception("GUI-Update-Fehler")
        self.after(100, self._drain)

    def _maybe_ask_claude(self):
        """Automatischer KI-Tipp erst, wenn der Zugbeginn abgeklungen ist (Mana/Hand sind nachgezogen)."""
        s = self._state
        if not (self._claude_want and s is not None and self.var_claude.get()):
            return
        if not s.my_active or s.result or s.mulligan:
            self._claude_want = False
            return
        if not self._settling() and self._plan is not None and not self._plan_stale(s) and not self._planning:
            self._claude_want = False
            self._ask_claude()

    def _update_status(self):
        if not self.db.ready.is_set():
            txt = "⏳ Kartendaten werden geladen ..."
        elif not self.db.cards:
            txt = (f"❌ Kartendaten konnten nicht geladen werden ({self.db.error or 'unbekannter Fehler'}) - "
                   "Internet prüfen oder in den Einstellungen die Quelle wechseln")
        elif not self.cfg["log_dir"]:
            txt = "❌ Hearthstone-Ordner nicht gefunden - bitte unter „⚙ Einstellungen“ den Log-Ordner angeben"
        elif not self.backend.tracker.path:
            txt = "⏳ Hearthstone-Log nicht gefunden (ist das Spiel gestartet?)"
            if self._logcfg_state != "ok":
                txt += " - Hinweis: log.config fehlt oder ist unvollständig, siehe „⚙ Einstellungen“"
        else:
            import os
            txt = (f"✓ live {time.strftime('%H:%M:%S')} - {os.path.basename(os.path.dirname(self.backend.tracker.path))}"
                   f"   |   Sitzung: {self.wins} Siege / {self.losses} Niederlagen")
            if self.coach.session_cost:
                txt += f"   |   Claude-Kosten: ${self.coach.session_cost:.4f}"
        now = time.time()
        if now - self._newer_checked > 15:             # alle 15 s nachsehen, ob das Repo weiter ist als dieses Programm
            self._newer_checked = now
            self._newer = self.build.newer_available()
        txt += f"   |   {self.build.label} (gestartet {self.build.started})"
        if self._update_msg:
            self.lbl_status.config(text=self._update_msg, fg="#ffaa44", cursor="")
            return
        if self._newer:
            txt += f"   |   ⟳ NEUSTART EMPFOHLEN - neuer Stand {self._newer}"
        if self._release:
            txt += f"   |   ⬆ Neue Version {self._release[0]} verfügbar ({'Klick: jetzt aktualisieren' if self._auto_update else 'Klick: Download-Seite'})"
        self.lbl_status.config(text=txt, fg="#ffaa44" if (self._newer or self._release) else DIMFG,
                               cursor="hand2" if self._release else "")

    def _on_state(self, s):
        prev = self._state
        self._state = s
        if prev is None and s.result:
            self._counted.add(s.game_no)      # beim Start bereits beendetes Spiel nicht mitzaehlen
        if self._game_no != s.game_no:
            self._game_no = s.game_no
            self._tips_log = []
            self._turn_logged = -1
            self._plan = None
            self._last_active = False
            self._claude_turn = -1
        self._render_state(s)

        became_active = s.my_active and not self._last_active
        self._last_active = s.my_active
        if became_active:
            self._active_since = time.time()
            self._plan_visible = False
        if became_active and s.turn != self._claude_turn and not s.mulligan and not s.result:
            self._claude_turn = s.turn
            self._claude_want = self.var_claude.get()

        if s.result and s.game_no not in self._counted:
            self._counted.add(s.game_no)
            if s.result == "WON":
                self.wins += 1
            elif s.result == "LOST":
                self.losses += 1
            if self.cfg["auto_analysis"]:
                self._analyze()

        if PIL_OK and s.my_hand and self.cfg["show_card_images"]:
            self.images.ensure([c.cid for c in s.my_hand], lambda cid, ok: None)

        sig = s.signature()
        if sig != self._plan_sig:
            self._plan_sig = sig
            self._sig_changed_at = time.time()
            self._schedule_plan()

    # -- Darstellung ------------------------------------------------------------------------------------
    def _render_state(self, s):
        if s.result:
            txt = {"WON": "SIEG 🏆", "LOST": "NIEDERLAGE", "TIED": "UNENTSCHIEDEN"}[s.result]
        elif s.mulligan:
            txt = "Mulligan - Startkarten wählen"
        else:
            txt = f"Runde {s.turn}" if s.turn else "—"
            my_turn = s.my_active and (s.ui_my_turn or not s.ui_known)
            if my_turn:
                txt += "   ← DEIN ZUG"
            elif s.my_active:
                txt += "   (Gegner-Zug wird noch angezeigt ...)"
        self.lbl_turn.config(text=txt, fg=GREEN if s.my_active and not s.result and (s.ui_my_turn or not s.ui_known) else GRAY)

        self.lbl_my_hp.config(text=f"❤  {s.my_hp}", fg="#ff4444" if s.my_hp <= 10 else GREEN)
        self.lbl_opp_hp.config(text=f"❤  {s.opp_hp}", fg="#88ff88" if s.opp_hp <= 10 else RED)
        self.lbl_my_armor.config(text=f"🛡 {s.my_armor}" if s.my_armor else "")
        self.lbl_opp_armor.config(text=f"🛡 {s.opp_armor}" if s.opp_armor else "")
        boss = None if s.result else bosses.find(s.opp_hero_cid)      # nur während eines laufenden Boss-Kampfs
        self._show_boss(boss)
        goal = f"   (Ziel: ≤ {boss.win_hp} Leben)" if boss and boss.win_hp else ""
        self.lbl_opp_name.config(text=s.opp_name.upper() + goal)
        self.lbl_my_info.config(text=f"✋ {len(s.my_hand)}   📚 {s.my_deck_count}"
                                     + (f"   🔒 {len(s.my_secrets)}" if s.my_secrets else ""))
        self.lbl_opp_info.config(text=f"✋ {s.opp_hand_count}   📚 {s.opp_deck_count}"
                                      + (f"   🔒 {s.opp_secret_count}" if s.opp_secret_count else ""))
        self.lbl_mana.config(text=f"💎  Mana: {s.my_mana} / {s.max_mana}")
        self.lbl_corpses.config(text=f"💀  Leichen: {s.my_corpses}" if s.my_corpses is not None else "")
        extra = []
        if s.my_weapon:
            extra.append(f"⚔ {s.my_weapon.name} {s.my_weapon.atk}/{s.my_weapon.durability}")
        if s.my_hero_power:
            hp = s.my_hero_power
            extra.append(f"🔮 {hp.name} ({hp.cost}💎, {'benutzt' if hp.used else 'bereit'})")
        self.lbl_extra.config(text="   ".join(extra))
        ohp = s.opp_hero_power
        self.lbl_opp_power.config(text=f"Gegner-Heldenkraft: {ohp.name} ({ohp.cost}💎) - {ohp.text}" if ohp else "")

        def board(minions):
            segs = []
            for m in minions:
                if m.frozen:
                    segs.append(("❄ ", "frozen"))
                elif m.can_attack:
                    segs.append(("⚡ ", "ready"))
                else:
                    segs.append(("   ", None))
                segs.append((f"{m.name}  {m.atk}/{m.hp}", None))
                for f in m.flags:
                    tag = {"SPOTT": "taunt", "GOTTESSCHILD": "ds", "EINGEFROREN": "frozen", "TARNUNG": "stealth"}.get(f, "dim")
                    segs.append((f"  [{f}]", tag))
                segs.append(("\n", None))
            return segs or [("(leer)", "dim")]

        self._set_rich("opp", self.t_opp, board(s.opp_minions))
        self._set_rich("mine", self.t_mine, board(s.my_minions))

        in_plan = set(self._plan.cids) if self._plan and self._plan_visible and not self._plan_stale(s) else set()
        hand = list(s.my_hand)
        if self.cfg["sort_hand"] == "cost":
            hand.sort(key=lambda c: (c.cost, c.zpos))
        segs = []
        for c in hand:
            marker = "★ " if c.cid in in_plan else "  "
            tag = "plan" if c.cid in in_plan else ("ok" if c.cost <= s.my_mana else "no")
            stats = f"  {c.atk}/{c.hp}" if c.cardtype in ("MINION", "WEAPON") else ""
            segs.append((f"{marker}[{c.cost}💎] {c.name}{stats}\n", tag))
            if c.text:
                segs.append(("      ", None))
                segs += self._kw_segments(c.text, "dim")
                segs.append(("\n", None))
        self._set_rich("hand", self.t_hand, segs or [("(Hand leer)", "dim")])

        ev = []
        for line in reversed(s.events[-14:]):
            ev.append((line + "\n", "me" if " Du" in line[:12] else "opp"))
        if s.opp_played:
            ev.append(("\nGegner bisher gespielt: " + ", ".join(s.opp_played[-14:]), "dim"))
        self._set_rich("events", self.t_events, ev or [("(noch nichts)", "dim")])

    def _show_boss(self, boss):
        if boss is self.boss:
            return
        self.boss = boss
        if boss is None:
            self.boss_frame.pack_forget()
            self._rich_sig.pop("boss", None)
            self._replan(force=True)
            return
        self.lbl_boss.config(text="📖  BOSS-INFO: " + boss.title)
        segs = []
        for line in boss.lines():
            tag = "info"
            if line.startswith("Ziel"):
                tag = "plan"
            elif line.startswith(("Siegschwelle", "Überleben")):
                tag = "lethal"
            elif line.startswith("•"):
                tag = "step"
            elif line.startswith("⚠"):
                tag = "warn"
            elif line.startswith("Quelle"):
                tag = "dim"
            segs.append((line + "\n", tag))
        self._set_rich("boss", self.t_boss, segs)
        self.boss_frame.pack(side="left", fill="both", expand=True, before=self.ai_frame)
        self._replan(force=True)

    def _plan_stale(self, s):
        return self._plan is None or self._plan_sig != s.signature()

    def _render_plan(self, s, plan):
        if s.mulligan:
            self._set_rich("plan", self.t_plan, [(tips.mulligan_advice(s, self.db, self.boss), "step")])
            return
        if s.result:
            self._set_rich("plan", self.t_plan, [(tips.render_plan(s, plan or None), "step")])
            return
        if not s.my_active:
            self._set_rich("plan", self.t_plan, [("Gegner ist am Zug ...\nDer Plan erscheint, sobald du dran bist.", "dim")])
            return
        if plan is None:
            self._set_rich("plan", self.t_plan, [("Berechne Plan ...", "dim")])
            return
        segs = [(f"[{s.my_mana}/{s.max_mana} Mana, Runde {s.turn}]\n", "info")]
        for line in tips.render_plan(s, plan).split("\n"):
            tag = "step"
            if line.startswith("★"):
                tag = "lethal"
            elif line.startswith("⚠"):
                tag = "warn"
            elif line.startswith("→"):
                tag = "arrow"
            elif line.startswith(("Alternative", "ℹ", "   (")):
                tag = "dim"
            segs.append((line + "\n", tag))
        self._set_rich("plan", self.t_plan, segs)

    # -- Planen (Hintergrund) ---------------------------------------------------------------------------
    def _schedule_plan(self):
        if self._plan_job:
            self.after_cancel(self._plan_job)
        self._plan_job = self.after(350, self._replan)

    def _replan(self, force=False):
        self._plan_job = None
        s = self._state
        if s is None:
            return
        if force:
            self._rich_sig.pop("plan", None)
        if s.mulligan or s.result or not s.my_active:
            self._plan = None
            self._render_plan(s, None)
            self._img_cids = [c.cid for c in s.my_hand] if s.mulligan else []
            self._refresh_images()
            return
        if self._planning:
            self._schedule_plan()
            return
        self._planning = True
        sig = s.signature()

        def work():
            try:
                plan = self.planner.plan(s, self.boss)
            except Exception:
                log.exception("Planer-Fehler")
                plan = None
            self.post(lambda: self._plan_done(s, sig, plan))
        threading.Thread(target=work, daemon=True, name="planner").start()

    def _plan_done(self, s, sig, plan):
        self._planning = False
        cur = self._state
        if plan is None:
            self._set_rich("plan", self.t_plan, [("Planer-Fehler - siehe Log-Datei.", "warn")])
            return
        if cur is not None and cur.signature() != sig:
            self._schedule_plan()          # Spielstand hat sich waehrenddessen geaendert
            return
        self._plan = plan
        self._present(s, plan)

    def _settling(self):
        """Zugbeginn: erst planen, wenn der BILDSCHIRM so weit ist. Die Spiellogik (GameState) eilt der Anzeige voraus -
        der Gegner animiert noch, waehrend das Log schon meinen Zug enthaelt. Massgeblich ist daher die PowerTaskList:
        mein Zug + Schritt MAIN_ACTION (dann sind auch Mana und Zugkarte da)."""
        s = self._state
        now = time.time()
        if s is None or not s.my_active or now - self._active_since > SETTLE_MAX_S:
            return False
        if s.my_mana_used > 0:       # du hast schon gespielt - nicht noch laenger warten
            return False
        step, mine = (s.ui_step, s.ui_my_turn) if s.ui_known else (s.step, True)
        return not (mine and step == "MAIN_ACTION" and now - self._sig_changed_at >= 0.4)

    def _present(self, s, plan):
        if s.my_active and not s.mulligan and self._settling():
            self._present_pending = True
            self._plan_visible = False
            msg = ("⏳ Der Gegner spielt noch (Animation läuft) - der Plan erscheint, sobald du dran bist ..."
                   if s.ui_known and not s.ui_my_turn else
                   "⏳ Zugbeginn - ich warte kurz, bis alle Karten nachgezogen sind ...")
            self._set_rich("plan", self.t_plan, [(msg, "dim")])
            return
        self._present_pending = False
        self._plan_visible = True
        self._render_plan(s, plan)
        self._render_state(s)              # Sterne in der Hand aktualisieren
        self._img_cids = list(plan.cids) if not self.var_hand_img.get() else [c.cid for c in s.my_hand]
        self._refresh_images()
        if s.turn != self._turn_logged and s.my_active and plan.steps:
            self._turn_logged = s.turn
            self._tips_log.append((s.turn, "Plan", tips.render_plan(s, plan)))

    # -- Kartenbilder -------------------------------------------------------------------------------------------
    def _img_space(self):
        """Hoehe, die unter den Textfeldern fuer Kartenbilder bleibt (None = Fenster noch nicht angezeigt)."""
        try:
            if self.winfo_height() <= 1:                 # Fenster noch nicht angezeigt
                return None
            top = self.img_frame.winfo_rooty() - self.winfo_rooty()        # Oberkante der Bilderleiste im Fenster
            h = self.winfo_height() - top - self.lbl_status.winfo_height() - 20
        except tk.TclError:
            return None
        return max(0, h)

    def _schedule_img_refresh(self):
        if self._img_job is None and not self._closed:
            self._img_job = self.after(250, self._img_refresh_now)

    def _img_refresh_now(self):
        self._img_job = None
        if not self._closed:
            self._refresh_images()

    def _refresh_images(self, force=False):
        s = self._state
        if self.var_hand_img.get() and s is not None and not s.mulligan:
            cids = [c.cid for c in sorted(s.my_hand, key=lambda c: (c.cost, c.zpos))]
        else:
            cids = list(self._img_cids)
        if not PIL_OK:
            return
        if not self.cfg["show_card_images"]:
            for lbl in self._img_labels:
                lbl.pack_forget()
            return
        n = max(1, len(cids))
        w = self.cfg["card_img_w"]
        avail_w = self.winfo_width() - 20 - 2 * FRAME_PAD
        if n * (w + 8) > max(600, avail_w):
            w = max(90, (max(600, avail_w)) // n - 8)
        ratio = self.cfg["card_img_h"] / self.cfg["card_img_w"]
        space = self._img_space()
        if space is not None and space < 110:      # kaum Platz: lieber keine Karten als abgeschnittene Streifen
            for lbl in self._img_labels:
                lbl.pack_forget()
            self._rich_sig.pop("imgs", None)
            return
        if space is not None:                      # nicht hoeher als der Platz unter den Textfeldern, sonst wird abgeschnitten
            w = min(w, max(70, int((space - 6) / ratio)))
        w = max(70, (w // 8) * 8)                  # in Stufen, damit beim Ziehen am Fenster nicht jedes Pixel neu gerendert wird
        h = int(w * ratio)
        key = (tuple(cids), w)
        if not force and self._rich_sig.get("imgs") == key and not any(
                self.images.have(c) and lbl.cget("image") == "" for c, lbl in zip(cids, self._img_labels)):
            return
        self._rich_sig["imgs"] = key
        while len(self._img_labels) < len(cids):
            lbl = tk.Label(self.img_frame, bg=BG, bd=0, fg=DIMFG, font=("Segoe UI", 9))
            lbl.pack(side="left", padx=3)
            self._img_labels.append(lbl)
        missing = []
        for i, lbl in enumerate(self._img_labels):
            if i < len(cids):
                ph = self.images.photo(cids[i], w, h)
                if ph is not None:
                    lbl.config(image=ph, text="", width=w, height=h)
                    lbl.image = ph
                else:
                    lbl.config(image="", text="…", width=4, height=1)
                    lbl.image = None
                    missing.append(cids[i])
                if not lbl.winfo_ismapped():
                    lbl.pack(side="left", padx=3)
            else:
                lbl.pack_forget()
        if missing:
            self.images.ensure(missing, lambda cid, ok: self.post(lambda: self._refresh_images(force=True)) if ok else None)

    # -- Claude -----------------------------------------------------------------------------------------------------
    def _ask_claude(self, manual=False):
        s = self._state
        if s is None or self._ai_busy or s.result or s.mulligan:
            return
        if not config.has_api_key(self.cfg):
            if manual:
                self._open_settings()
            return
        if manual:
            self.var_claude.set(True)
            self._toggle_claude()
        plan = self._plan if self._plan is not None and not self._plan_stale(s) else None
        if plan is None:
            try:
                plan = self.planner.plan(s, self.boss)
            except Exception:
                log.exception("Planer-Fehler (Claude-Pfad)")
        self._ai_busy = True
        self._ai_token += 1
        token, turn = self._ai_token, s.turn
        header = f"[{self.cfg['claude_model']} | {s.my_mana}/{s.max_mana} Mana, Runde {s.turn}]\n"
        self.btn_ai.config(state="disabled", text="⏳ Denke nach ...")
        self.lbl_cost.config(text="")
        self._set_rich("ai", self.t_ai, [(header, "info"), ("…", "dim")])

        def on_text(acc):
            self.post(lambda: self._ai_partial(token, header, acc))

        def on_done(text, cost, total, err):
            self.post(lambda: self._ai_done(token, turn, header, text, cost, total, err))
        self.coach.ask_tip(s, plan, on_text, on_done, self.boss)

    def _ai_partial(self, token, header, acc):
        if token == self._ai_token:
            self._set_rich("ai", self.t_ai, [(header, "info"), (strip_md(acc), "step")])

    def _ai_done(self, token, turn, header, text, cost, total, err):
        self._ai_busy = False
        self.btn_ai.config(state="normal", text="💡 KI-Tipp")
        if token != self._ai_token:
            return
        if err:
            self._set_rich("ai", self.t_ai, [(header, "info"), (f"❌ {err}", "warn")])
            return
        cur = self._state
        if cur is not None and cur.turn != turn and not cur.my_active:
            text = "(veraltet - Zug hat gewechselt)\n" + text
        self._set_rich("ai", self.t_ai, [(header, "info"), (strip_md(text), "step")])
        self.lbl_cost.config(text=f"Letzte Anfrage: ${cost:.5f}  |  Sitzung gesamt: ${total:.4f}")
        self._tips_log.append((turn, "KI", text))

    # -- Analyse ----------------------------------------------------------------------------------------------------------
    def _analyze(self):
        s = self._state
        if s is None or self._analysis_busy:
            return
        if not config.has_api_key(self.cfg):
            self._set_rich("ai", self.t_ai, [("Die Spielanalyse braucht einen Anthropic-API-Key "
                                              "(⚙ Einstellungen). Der Zugplan funktioniert auch ohne.", "warn")])
            return
        me =self.backend.tracker.my_pid or 1
        lines, _ = render_events(self.backend.tracker, self.db, me)
        summary = analysis.build_summary(s, self._tips_log, lines)
        self._analysis_busy = True
        self.btn_analysis.config(state="disabled", text="⏳ Analysiere ...")

        def done(text, cost, err):
            def ui():
                self._analysis_busy = False
                self.btn_analysis.config(state="normal", text="📝 Analyse")
                if err:
                    self._set_rich("ai", self.t_ai, [(f"❌ Analyse fehlgeschlagen: {err}", "warn")])
                    return
                paths = analysis.save_report(self.cfg, s, text)
                self._show_report(text, paths, cost)
            self.post(ui)
        self.coach.analyze(summary, done)

    def _show_report(self, text, paths, cost):
        win = tk.Toplevel(self)
        win.title("Spielanalyse")
        win.configure(bg=BG)
        win.geometry("900x700")
        t = tk.Text(win, bg=TEXTBG, fg="#e8e8ff", font=("Segoe UI", 11), wrap="word", relief="flat", bd=10)
        t.pack(fill="both", expand=True)
        t.insert("end", text + "\n\n---\n" + ("Gespeichert: " + " | ".join(paths) if paths else "Nicht gespeichert.")
                 + (f"\nKosten: ${cost:.4f}" if cost else ""))
        t.config(state="disabled")


def main():
    from . import setup_logging
    setup_logging()
    App().mainloop()
