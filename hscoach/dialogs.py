"""Rueckfragen und Meldungen. Windows: tkinter.messagebox. macOS: eigene Tk-Fenster.

Grund: Auf macOS zeigt tk_messageBox einen nativen NSAlert. macOS 26 haengt daran eine Gamecontroller-Navigation
(GameControllerUI), deren Objekt Tk 9 beim Leeren seines Autorelease-Pools in falscher Reihenfolge freigibt - die App
stuerzt dann ab (EXC_BREAKPOINT in GCUINavigationSession.AlertPresentationAssertion). Eigene Fenster umgehen das.
"""
import sys
import tkinter as tk

from . import widgets

USE_NATIVE = sys.platform != "darwin"
BG, FG, GOLD = "#0d0d1a", "#e8e8ff", "#ffd700"
ICONS = {"info": "ℹ️", "warning": "⚠️", "error": "⛔", "question": "❓"}


class _Dialog(tk.Toplevel):
    def __init__(self, parent, title, message, kind, buttons):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        if parent is not None and parent.winfo_viewable():
            self.transient(parent)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(18, 8))
        tk.Label(body, text=ICONS.get(kind, ""), bg=BG, fg=FG, font=("Segoe UI", 26)).pack(side="left", anchor="n",
                                                                                            padx=(0, 14))
        tk.Label(body, text=message, bg=BG, fg=FG, font=("Segoe UI", 12), justify="left", wraplength=440,
                 anchor="w").pack(side="left", fill="both", expand=True)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=20, pady=(4, 16))
        self.buttons = {}
        for i, (label, value) in enumerate(buttons):
            primary = i == 0
            b = widgets.Button(bar, text=label, command=lambda v=value: self._done(v), relief="flat", cursor="hand2",
                               bg="#2a5a2a" if primary else "#1a1a3e", fg="white" if primary else GOLD, width=12)
            b.pack(side="right", padx=4)
            self.buttons[value] = b
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(buttons[-1][1]))
        self.bind("<Return>", lambda e: self._done(buttons[0][1]))
        self.bind("<Escape>", lambda e: self._done(buttons[-1][1]))
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        if parent is not None and parent.winfo_viewable():
            x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _done(self, value):
        self.result = value
        self.destroy()

    def run(self):
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()
        return self.result


def _show(parent, title, message, kind, buttons):
    return _Dialog(parent, title, message, kind, buttons).run()


def ask_yes_no(title, message, parent=None):
    if USE_NATIVE:
        from tkinter import messagebox
        return messagebox.askyesno(title, message, parent=parent)
    return bool(_show(parent, title, message, "question", [("Ja", True), ("Nein", False)]))


def show_info(title, message, parent=None):
    if USE_NATIVE:
        from tkinter import messagebox
        return messagebox.showinfo(title, message, parent=parent)
    _show(parent, title, message, "info", [("OK", True)])


def show_warning(title, message, parent=None):
    if USE_NATIVE:
        from tkinter import messagebox
        return messagebox.showwarning(title, message, parent=parent)
    _show(parent, title, message, "warning", [("OK", True)])


def show_error(title, message, parent=None):
    if USE_NATIVE:
        from tkinter import messagebox
        return messagebox.showerror(title, message, parent=parent)
    _show(parent, title, message, "error", [("OK", True)])
