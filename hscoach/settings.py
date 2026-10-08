"""Einstellungsdialog (tkinter). Die reine Logik (apply) ist von der Oberflaeche getrennt und einzeln testbar."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config, detect

BG, BG2, FG, GOLD, GRAY = "#0d0d1a", "#111130", "#e8e8ff", "#ffd700", "#888899"

# Schluessel, deren Aenderung erst nach einem Neustart wirkt
RESTART_KEYS = ("log_dir", "player_name", "card_source")

LOG_CONFIG_TEXT = {
    "ok": ("✓ Hearthstone schreibt die Power.log (log.config ist in Ordnung).", "#66ff88"),
    "missing": ("✗ Keine log.config gefunden - ohne sie schreibt Hearthstone kein Power.log.", "#ff6666"),
    "no_power": ("✗ In der log.config fehlt der Abschnitt [Power].", "#ff6666"),
    "disabled": ("✗ In der log.config ist [Power] ausgeschaltet.", "#ff6666"),
}


def apply(cfg, values, api_key=None):
    """Uebernimmt Formularwerte in cfg und speichert sie. Gibt die Liste der geaenderten Schluessel zurueck.

    api_key: None = unveraendert, "" = loeschen, sonst speichern.
    """
    changed = []
    for k, v in values.items():
        if k not in config.DEFAULTS:
            continue
        default = config.DEFAULTS[k]
        if isinstance(default, bool):
            v = bool(v)
        elif isinstance(default, str):
            v = str(v).strip()
            if not v and k in ("claude_model", "analysis_model", "card_source"):
                v = default
        if cfg.get(k) != v:
            cfg[k] = v
            changed.append(k)
    if changed:
        config.save(cfg, changed)
    if api_key is not None:
        if api_key.strip():
            config.save_api_key(cfg, api_key)
            changed.append("api_key")
        else:
            config.delete_api_key(cfg)
            changed.append("api_key")
    return changed


def needs_restart(changed):
    return any(k in RESTART_KEYS for k in changed)


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.cfg = app.cfg
        self.title("Einstellungen - HS Coach")
        self.configure(bg=BG)
        self.transient(app)
        self.resizable(False, False)
        self.vars = {}
        self._build()
        self.update_idletasks()
        x = app.winfo_rootx() + max(0, (app.winfo_width() - self.winfo_width()) // 2)
        y = app.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    # -- Aufbau ----------------------------------------------------------------------------------------
    def _section(self, text):
        tk.Label(self, text=text, bg=BG, fg=GOLD, font=("Segoe UI", 11, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(12, 2))

    def _row(self, label, key, browse=False, width=52):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=14, pady=2)
        tk.Label(f, text=label, bg=BG, fg=FG, width=22, anchor="w", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=str(self.cfg.get(key, "")))
        self.vars[key] = var
        tk.Entry(f, textvariable=var, width=width, bg="#1a1a3e", fg=FG, insertbackground=FG, relief="flat").pack(
            side="left", padx=4)
        if browse:
            tk.Button(f, text="…", command=lambda: self._browse(var), bg="#1a1a3e", fg=GOLD, relief="flat").pack(side="left")
        return var

    def _check(self, label, key):
        var = tk.BooleanVar(value=bool(self.cfg.get(key)))
        self.vars[key] = var
        tk.Checkbutton(self, text=label, variable=var, bg=BG, fg=FG, selectcolor="#1a1a3e", activebackground=BG,
                       activeforeground=GOLD, anchor="w", font=("Segoe UI", 10)).pack(fill="x", padx=14)

    def _build(self):
        self._section("Hearthstone")
        v = self._row("Log-Ordner", "log_dir", browse=True)
        tk.Label(self, text="Leer lassen = automatisch suchen. Erwartet wird der Ordner „Hearthstone\\Logs“.",
                 bg=BG, fg=GRAY, font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=14)
        self._row("Dein Spielername", "player_name")
        tk.Label(self, text="Leer lassen = automatisch erkennen (nur nötig, falls das falsch liegt, z. B. Name#1234).",
                 bg=BG, fg=GRAY, font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=14)
        self.lbl_logcfg = tk.Label(self, text="", bg=BG, fg=GRAY, font=("Segoe UI", 10), anchor="w", justify="left",
                                   wraplength=640)
        self.lbl_logcfg.pack(fill="x", padx=14, pady=(8, 2))
        self.btn_logcfg = tk.Button(self, text="Power.log aktivieren (log.config anlegen)", command=self._write_logcfg,
                                    bg="#1a1a3e", fg=GOLD, relief="flat", cursor="hand2")
        self._refresh_logcfg()

        self._section("Kartendaten")
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=14, pady=2)
        tk.Label(f, text="Quelle", bg=BG, fg=FG, width=22, anchor="w", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=self.cfg.get("card_source", "auto"))
        self.vars["card_source"] = var
        ttk.Combobox(f, textvariable=var, values=("auto", "hearthstonejson", "hdt"), width=20, state="readonly").pack(
            side="left", padx=4)
        tk.Label(f, text="auto = HearthstoneJSON (Internet), ersatzweise Hearthstone Deck Tracker", bg=BG, fg=GRAY,
                 font=("Segoe UI", 9)).pack(side="left", padx=6)

        self._section("Claude (optional)")
        tk.Label(self, text="Der Coach funktioniert vollständig ohne API-Key. Mit eigenem Key kommen KI-Tipps und "
                 "Spielanalysen dazu (kostenpflichtig bei Anthropic).", bg=BG, fg=GRAY, font=("Segoe UI", 9),
                 anchor="w", justify="left", wraplength=640).pack(fill="x", padx=14)
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=14, pady=2)
        tk.Label(f, text="API-Key", bg=BG, fg=FG, width=22, anchor="w", font=("Segoe UI", 10)).pack(side="left")
        self.var_key = tk.StringVar()
        tk.Entry(f, textvariable=self.var_key, show="•", width=52, bg="#1a1a3e", fg=FG, insertbackground=FG,
                 relief="flat").pack(side="left", padx=4)
        self.lbl_key = tk.Label(self, text="", bg=BG, fg=GRAY, font=("Segoe UI", 9), anchor="w")
        self.lbl_key.pack(fill="x", padx=14)
        self._refresh_key_label()
        self._row("Modell (Zug-Tipp)", "claude_model")
        self._row("Modell (Analyse)", "analysis_model")

        self._section("Ablage und Anzeige")
        self._row("Berichte speichern in", "reports_dir", browse=True)
        self._row("Zusätzlich kopieren nach", "obsidian_dir", browse=True)
        self._check("Kartenbilder anzeigen (werden von Blizzard-Servern geladen)", "show_card_images")
        self._check("Beim Start nach einer neuen Version suchen (GitHub)", "update_check")

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=14, pady=14)
        tk.Button(bar, text="Speichern", command=self._save, bg="#2a5a2a", fg="white", relief="flat", width=14,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(bar, text="Abbrechen", command=self.destroy, bg="#1a1a3e", fg=GOLD, relief="flat", width=12,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(bar, text="API-Key entfernen", command=self._remove_key, bg="#1a1a3e", fg="#ff9999", relief="flat",
                  cursor="hand2").pack(side="left")

    # -- Aktionen --------------------------------------------------------------------------------------------
    def _browse(self, var):
        d = filedialog.askdirectory(parent=self, initialdir=var.get() or os.path.expanduser("~"))
        if d:
            var.set(os.path.normpath(d))

    def _refresh_logcfg(self):
        state = detect.check_log_config()
        text, color = LOG_CONFIG_TEXT[state]
        self.lbl_logcfg.config(text=text, fg=color)
        if state == "ok":
            self.btn_logcfg.pack_forget()
        else:
            self.btn_logcfg.pack(anchor="w", padx=14, pady=2)

    def _write_logcfg(self):
        try:
            p = detect.write_log_config()
        except OSError as ex:
            messagebox.showerror("Fehler", f"log.config konnte nicht geschrieben werden:\n{ex}", parent=self)
            return
        messagebox.showinfo("Erledigt", f"{p} wurde angelegt.\n\nHearthstone einmal komplett neu starten, "
                            "damit die Datei gelesen wird.", parent=self)
        self._refresh_logcfg()

    def _refresh_key_label(self):
        if config.has_api_key(self.cfg):
            self.lbl_key.config(text="✓ Ein Key ist hinterlegt (leer lassen = unverändert).", fg="#66ff88")
        else:
            self.lbl_key.config(text="Kein Key hinterlegt - Claude-Funktionen sind aus.", fg=GRAY)

    def _remove_key(self):
        if messagebox.askyesno("API-Key entfernen", "Gespeicherten API-Key löschen?", parent=self):
            config.delete_api_key(self.cfg)
            self.var_key.set("")
            self._refresh_key_label()
            self.app.on_settings_changed(["api_key"])

    def _save(self):
        values = {k: (v.get() if isinstance(v, (tk.StringVar, tk.BooleanVar)) else v) for k, v in self.vars.items()}
        key = self.var_key.get()
        changed = apply(self.cfg, values, api_key=key if key.strip() else None)
        self.destroy()
        self.app.on_settings_changed(changed)
