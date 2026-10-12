"""Plattform-Feinheiten fuer Widgets: auf macOS ignoriert tk.Button die Hintergrundfarbe (Aqua zeichnet ihn grau),
daher dort ein flacher Knopf auf Basis von tk.Label, der dieselben Optionen versteht."""
import sys
import tkinter as tk


class FlatButton(tk.Label):
    """tk.Label, das sich wie ein flacher tk.Button verhaelt: command, state, activebackground beim Ueberfahren."""

    def __init__(self, master=None, command=None, **kw):
        kw.setdefault("padx", 8)
        kw.setdefault("pady", 3)
        self._command = command
        super().__init__(master, **kw)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<ButtonRelease-1>", self._click)

    def configure(self, cnf=None, **kw):
        if "command" in kw:
            self._command = kw.pop("command")
        return super().configure(cnf, **kw)

    config = configure

    def _hover(self, inside):
        if str(self.cget("state")) != "disabled":
            super().configure(state="active" if inside else "normal")

    def _click(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if inside and self._command and str(self.cget("state")) != "disabled":
            self._command()

    def invoke(self):
        if self._command and str(self.cget("state")) != "disabled":
            return self._command()


Button = FlatButton if sys.platform == "darwin" else tk.Button
