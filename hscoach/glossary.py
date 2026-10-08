"""Kurze Erklaerungen der wichtigsten Hearthstone-Begriffe (fuer Einsteiger)."""

GLOSSARY = {
    "Kampfschrei": "Effekt, der einmalig ausgelöst wird, wenn du die Karte aus der Hand spielst.",
    "Todesröcheln": "Effekt, der ausgelöst wird, wenn der Diener stirbt.",
    "Spott": "Der Gegner muss zuerst Diener mit Spott angreifen, bevor er andere Ziele oder dein Gesicht treffen darf.",
    "Gottesschild": "Der nächste Schaden an diesem Diener wird komplett ignoriert, danach ist der Schild weg.",
    "Eifer": "Der Diener darf sofort angreifen, aber nur andere Diener - nicht den Helden.",
    "Ansturm": "Der Diener darf sofort angreifen, auch den gegnerischen Helden.",
    "Windzorn": "Der Diener darf pro Zug zweimal angreifen.",
    "Gift": "Jeder Schaden von diesem Diener zerstört den getroffenen Diener.",
    "Lebensraub": "Schaden, den dieser Charakter austeilt, heilt deinen Helden.",
    "Tarnung": "Kann nicht angegriffen oder gezielt werden, bis der Diener selbst angreift.",
    "Geheimnis": "Wird verdeckt gelegt und löst automatisch aus, sobald die Bedingung beim Gegner eintritt.",
    "Zwillingszauber": "Nach dem Wirken bekommst du eine Kopie des Zaubers (ohne Zwillingszauber) auf die Hand.",
    "Überladung": "Sperrt im nächsten Zug die angegebene Anzahl Manakristalle.",
    "Combo": "Zusatzeffekt, wenn du in diesem Zug schon eine andere Karte gespielt hast.",
    "Entdecken": "Du wählst eine von drei zufälligen Karten.",
    "Wiedergeburt": "Kehrt nach dem ersten Tod einmalig mit 1 Leben zurück.",
    "Eingefroren": "Kann in seinem nächsten Zug nicht angreifen.",
    "einfrieren": "Das Ziel kann in seinem nächsten Zug nicht angreifen.",
    "friert": "Das Ziel kann in seinem nächsten Zug nicht angreifen.",
    "Leichen": "Todesritter-Ressource: sammelt sich, wenn Diener sterben, und wird von manchen Karten verbraucht.",
    "Zauberschaden": "Erhöht den Schaden deiner Zauber.",
    "Rüstung": "Absorbiert Schaden, bevor dein Leben sinkt.",
    "Handelbar": "Du kannst die Karte gegen eine neue aus dem Deck tauschen.",
}

# Reihenfolge: laengere Begriffe zuerst, damit "Todesröcheln" nicht von kuerzeren Treffern ueberdeckt wird
KEYWORDS = sorted(GLOSSARY, key=len, reverse=True)
