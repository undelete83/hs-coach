"""Fenster "Sammlung": Karten durchsuchen/filtern (mit Besitz) und Decks gegen die Sammlung pruefen."""
import threading
import tkinter as tk
from tkinter import ttk

from . import collection, widgets, winstyle

BG, BG2, FG, GOLD, GRAY, GREEN, RED = "#0d0d1a", "#111130", "#e8e8ff", "#ffd700", "#888899", "#66ff88", "#ff6666"

ALL = "Alle"
CLASS_CHOICES = [ALL] + [collection.CLASS_DE[k] for k in collection.CLASS_DE]
RARITY_CHOICES = [ALL] + [collection.RARITY_DE[k] for k in ("COMMON", "RARE", "EPIC", "LEGENDARY")]
TYPE_CHOICES = [ALL] + [collection.TYPE_DE[k] for k in ("MINION", "SPELL", "WEAPON", "LOCATION")]
COST_CHOICES = [ALL] + [str(i) for i in range(7)] + ["7+"]
FORMAT_CHOICES = ["Standard", "Alle (Wild)"]
OWN_CHOICES = [ALL, "Besitze ich", "Vollständig (2x / 1x)", "Fehlt mir"]


def _rev(d):
    return {v: k for k, v in d.items()}


class CollectionWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.cfg = app.cfg
        self.title("Sammlung - HS Coach")
        self.configure(bg=BG)
        self.geometry("1100x720")
        self.coll = None
        self.rows = []
        self._busy = False
        self._build()
        winstyle.style_titlebar(self)
        cached = collection.load_cached()
        if cached:
            self.coll = collection.Collection(cached)
        self._load_cards_async(refresh=self.coll is None and bool(collection.parse_account(self.cfg.get("hsreplay_collection", ""))))

    # -- Aufbau -------------------------------------------------------------------------------------
    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 2))
        self.lbl_status = tk.Label(top, text="", bg=BG, fg=GRAY, font=("Segoe UI", 10), anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        self.btn_refresh = widgets.Button(top, text="⟳ Von HSReplay aktualisieren", command=self.refresh, bg="#1a1a3e", fg=GOLD,
                                     relief="flat", cursor="hand2")
        self.btn_refresh.pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=6)
        self.tab_cards = tk.Frame(nb, bg=BG)
        self.tab_deck = tk.Frame(nb, bg=BG)
        nb.add(self.tab_cards, text="  Karten  ")
        nb.add(self.tab_deck, text="  Deck prüfen  ")
        self._build_cards()
        self._build_deck()

    def _combo(self, parent, label, values, default, width=14):
        tk.Label(parent, text=label, bg=BG, fg=GRAY, font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        var = tk.StringVar(value=default)
        cb = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        return var

    def _build_cards(self):
        f = tk.Frame(self.tab_cards, bg=BG)
        f.pack(fill="x", pady=4)
        tk.Label(f, text="Suche", bg=BG, fg=GRAY, font=("Segoe UI", 9)).pack(side="left")
        self.var_text = tk.StringVar()
        e = tk.Entry(f, textvariable=self.var_text, width=24, bg="#1a1a3e", fg=FG, insertbackground=FG, relief="flat")
        e.pack(side="left", padx=4)
        self.var_text.trace_add("write", lambda *_a: self._apply_filter())
        self.var_class = self._combo(f, "Klasse", CLASS_CHOICES, ALL, 13)
        self.var_fmt = self._combo(f, "Format", FORMAT_CHOICES, FORMAT_CHOICES[0], 12)
        f2 = tk.Frame(self.tab_cards, bg=BG)
        f2.pack(fill="x", pady=2)
        self.var_cost = self._combo(f2, "Kosten", COST_CHOICES, ALL, 5)
        self.var_rarity = self._combo(f2, "Seltenheit", RARITY_CHOICES, ALL, 11)
        self.var_type = self._combo(f2, "Art", TYPE_CHOICES, ALL, 9)
        self.var_own = self._combo(f2, "Besitz", OWN_CHOICES, ALL, 20)

        cols = ("name", "cost", "type", "cls", "rarity", "set", "own")
        heads = ("Name", "Kosten", "Art", "Klasse", "Seltenheit", "Set", "Besitz")
        widths = (260, 60, 80, 110, 100, 170, 70)
        wrap = tk.Frame(self.tab_cards, bg=BG)
        wrap.pack(fill="both", expand=True, pady=4)
        style = ttk.Style(self)
        style.configure("Coll.Treeview", background="#111130", fieldbackground="#111130", foreground=FG, rowheight=22)
        style.configure("Coll.Treeview.Heading", background="#1a1a3e", foreground=GOLD)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", style="Coll.Treeview", selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("name", "set") else "center")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("full", foreground=GREEN)
        self.tree.tag_configure("none", foreground=RED)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.lbl_detail = tk.Label(self.tab_cards, text="", bg=BG2, fg=FG, font=("Segoe UI", 10), anchor="w", justify="left",
                                   wraplength=1040)
        self.lbl_detail.pack(fill="x", pady=(2, 0), ipady=4)
        self.lbl_count = tk.Label(self.tab_cards, text="", bg=BG, fg=GRAY, font=("Segoe UI", 9), anchor="w")
        self.lbl_count.pack(fill="x")

    def _build_deck(self):
        tk.Label(self.tab_deck, text="Deckcode einfügen (aus Hearthstone: Deck > Kopieren; oder von hsreplay.net):", bg=BG, fg=GRAY,
                 font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(8, 2))
        f = tk.Frame(self.tab_deck, bg=BG)
        f.pack(fill="x")
        self.var_code = tk.StringVar()
        tk.Entry(f, textvariable=self.var_code, bg="#1a1a3e", fg=FG, insertbackground=FG, relief="flat").pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        widgets.Button(f, text="Aus Zwischenablage", command=self._paste_code, bg="#1a1a3e", fg=GOLD, relief="flat",
                  cursor="hand2").pack(side="left", padx=2)
        widgets.Button(f, text="Prüfen", command=self._check_deck, bg="#2a5a2a", fg="white", relief="flat", width=10,
                  cursor="hand2").pack(side="left", padx=2)
        self.txt_deck = tk.Text(self.tab_deck, bg="#080818", fg=FG, relief="flat", font=("Consolas", 10), wrap="word")
        self.txt_deck.pack(fill="both", expand=True, pady=8)
        self.txt_deck.tag_configure("miss", foreground=RED)
        self.txt_deck.tag_configure("ok", foreground=GREEN)
        self.txt_deck.tag_configure("head", foreground=GOLD)

    # -- Daten ------------------------------------------------------------------------------------
    def _set_status(self, text, color=GRAY):
        self.lbl_status.config(text=text, fg=color)

    def _load_cards_async(self, refresh=False):
        self._set_status("Lade Kartendaten ...")

        def work():
            try:
                rows = collection.card_rows(self.cfg)
                err = None
            except collection.CollectionError as ex:
                rows, err = [], str(ex)
            self.app.post(lambda: self._cards_loaded(rows, err, refresh))
        threading.Thread(target=work, daemon=True, name="coll-cards").start()

    def _cards_loaded(self, rows, err, refresh):
        if not self.winfo_exists():
            return
        if err:
            self._set_status(err, RED)
            return
        self.rows = rows
        self._update_status()
        self._apply_filter()
        if refresh:
            self.refresh()

    def refresh(self):
        if self._busy:
            return
        if not collection.parse_account(self.cfg.get("hsreplay_collection", "")):
            self._set_status("Kein Sammlungs-Link eingetragen: ⚙ Einstellungen > Sammlung (HSReplay).", RED)
            return
        self._busy = True
        self.btn_refresh.config(state="disabled")
        self._set_status("Rufe die Sammlung bei HSReplay ab ...")

        def work():
            try:
                raw = collection.fetch(self.cfg)
                err = None
            except collection.CollectionError as ex:
                raw, err = None, str(ex)
            self.app.post(lambda: self._fetched(raw, err))
        threading.Thread(target=work, daemon=True, name="coll-fetch").start()

    def _fetched(self, raw, err):
        self._busy = False
        if not self.winfo_exists():
            return
        self.btn_refresh.config(state="normal")
        if err:
            self._set_status(err, RED)
            return
        self.coll = collection.Collection(raw)
        self._update_status()
        self._apply_filter()

    def _update_status(self):
        if self.coll is None:
            self._set_status("Noch keine Sammlung geladen - Link unter ⚙ Einstellungen > Sammlung eintragen, dann „Aktualisieren“.")
            return
        n = sum(1 for r in self.rows if self.coll.owned(r["dbf"], r["rarity"]) > 0)
        dust = self.coll.dust
        self._set_status(f"Sammlung von HSReplay, Stand {collection.age_text(self.coll)}"
                         + (f"  |  Staub: {dust}" if dust is not None else "") + f"  |  {n} verschiedene Karten besessen")

    # -- Karten ------------------------------------------------------------------------------------
    def _apply_filter(self):
        if not self.rows:
            return
        coll = self.coll or collection.Collection({"collection": {}})
        cost = self.var_cost.get()
        own = {OWN_CHOICES[1]: "have", OWN_CHOICES[2]: "full", OWN_CHOICES[3]: "missing"}.get(self.var_own.get(), "")
        rows = collection.filter_rows(
            self.rows, coll, text=self.var_text.get(),
            cls=_rev(collection.CLASS_DE).get(self.var_class.get(), ""),
            fmt="standard" if self.var_fmt.get() == FORMAT_CHOICES[0] else "",
            rarity=_rev(collection.RARITY_DE).get(self.var_rarity.get(), ""),
            cost="" if cost == ALL else ("7" if cost == "7+" else cost),
            own=own, ctype=_rev(collection.TYPE_DE).get(self.var_type.get(), ""))
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for r in rows[:2500]:
            have = coll.owned(r["dbf"], r["rarity"])
            cap = 1 if r["rarity"] == "LEGENDARY" else 2
            tag = "full" if have >= cap else ("none" if have == 0 else "")
            iid = self.tree.insert("", "end", values=(r["name"], r["cost"], collection.TYPE_DE.get(r["type"], r["type"]),
                                                      collection.CLASS_DE.get(r["cls"], r["cls"]),
                                                      collection.RARITY_DE.get(r["rarity"], r["rarity"]), r["set"],
                                                      f"{have}/{cap}"), tags=(tag,) if tag else ())
            self._by_iid[iid] = r
        shown = min(len(rows), 2500)
        self.lbl_count.config(text=f"{shown} Karten angezeigt" + (f" (von {len(rows)} - Filter enger setzen)" if len(rows) > 2500 else ""))
        self.lbl_detail.config(text="")

    def _on_select(self, _e):
        sel = self.tree.selection()
        r = getattr(self, "_by_iid", {}).get(sel[0]) if sel else None
        if not r:
            return
        stats = f"  {r['atk']}/{r['hp']}" if r["atk"] is not None and r["type"] == "MINION" else ""
        self.lbl_detail.config(text=f"{r['name']}  [{r['cost']}]{stats}  -  {r['text']}")

    # -- Deck pruefen ----------------------------------------------------------------------------
    def _paste_code(self):
        try:
            self.var_code.set(self.clipboard_get().strip())
        except tk.TclError:
            pass
        self._check_deck()

    def _check_deck(self):
        t = self.txt_deck
        t.delete("1.0", "end")
        if self.coll is None or not self.rows:
            t.insert("end", "Die Sammlung ist noch nicht geladen.\n", "miss")
            return
        try:
            res = collection.check_deck(self.var_code.get(), self.rows, self.coll)
        except collection.CollectionError as ex:
            t.insert("end", f"{ex}\n", "miss")
            return
        t.insert("end", collection.render_check(res) + "\n\n", "ok" if not res["missing"] and not res["notes"] else "head")
        t.insert("end", "Karten im Deck:\n", "head")
        for e in res["entries"]:
            r = e["row"]
            name = r["name"] if r else f"(dbfId {e['dbf']})"
            cost = r["cost"] if r else "?"
            ok = e["have"] >= e["need"]
            t.insert("end", f"  {e['need']}x [{cost}] {name}   (du hast {e['have']})\n", "ok" if ok else "miss")
