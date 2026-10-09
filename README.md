# HS Coach

Live-Coach für **Hearthstone** (Windows). Der Coach liest die Logdatei, die Hearthstone selbst schreibt, und zeigt auf einem zweiten Monitor (oder neben dem Spiel) Spielstand, einen Zugplan und – wenn du möchtest – einen Tipp von Claude. Er greift nicht ins Spiel ein und braucht weder Hearthstone Deck Tracker noch einen Account irgendwo.

> Inoffizielles Fan-Projekt. Nicht von Blizzard Entertainment unterstützt oder verbunden. Hearthstone ist eine Marke von Blizzard Entertainment, Inc. Der Coach liest ausschließlich die Textdatei `Power.log`, die das Spiel selbst erzeugt.

## Was er kann

- **Spielstand live**: Leben, Rüstung, Mana, Boards (bereit / eingefroren / Spott / Gottesschild), deine Hand mit Kartentext, Waffe, Heldenkraft, Geheimnisse, letzte Spielzüge.
- **Zugplan (kostenlos, ohne Internet-Dienst)**: Eine Regel-Engine simuliert Karten, Angriffe, Heldenkraft, Rabatte, Einfrieren, Spott und Lethal und zeigt die Schritte in Reihenfolge – inklusive Warnung bei drohendem Tod.
- **Boss-Wissen** für alle Solo-Abenteuer (Book of Heroes, Eine Nacht in Karazhan, Galakronds Erwachen, Dalaran-Raubzug, Gräber des Terrors, Naxxramas, Schwarzfels, Forscherliga, Kobolde & Katakomben, Hexenwald, Rastakhans Rumble, Eiskrone, Book of Mercenaries u. a.): Name, Leben und Heldenkraft des Bosses stehen überall; für viele Bosse gibt es zusätzlich Ziel, Tipps und Gefahren (eigene Spalte, nur während eines Boss-Kampfs).
- **Spielbrett-Ansicht**: Helden als Porträts, Diener als Kacheln (mit Kartenmotiv, Spott, Schilden, Frost ...), der Zugplan als Pfeile mit Schrittnummern direkt auf dem Brett. Ein Knopf neben den Einstellungen schaltet auf die reine Textansicht um.
- **Mulligan-Hilfe** und **Glossar** (Maus über unterstrichene Begriffe).
- **Optional mit eigenem Anthropic-API-Key**: KI-Tipps pro Zug (Streaming, Kostenanzeige) und eine Spielanalyse nach der Partie. Ohne Key sind diese Funktionen aus – alles andere funktioniert voll.
- **Kartenbilder** der empfohlenen Karten (abschaltbar).
- **Updates mit einem Klick**: Beim Start wird bei GitHub nachgesehen, ob es eine neuere Version gibt (abschaltbar). Dann erscheint in der Statuszeile ein Hinweis; ein Klick lädt das Update, prüft die SHA-256-Prüfsumme, ersetzt die Programmdateien und startet den Coach neu. Einstellungen, API-Key und Berichte bleiben erhalten. Ohne Rückfrage geschieht nichts.

## Schnellstart

### Variante A: fertige Version (empfohlen)

1. Auf der [Release-Seite](https://github.com/undelete83/hs-coach/releases) das Zip `HSCoach-<Version>.zip` laden und entpacken.
2. `HSCoach.exe` starten. Beim ersten Start öffnet sich das Einstellungsfenster.
3. Hearthstone schreibt die Logdatei nur, wenn eine `log.config` existiert. Zeigt der Dialog „✗ …“, klicke auf **„Power.log aktivieren“** und starte Hearthstone danach einmal komplett neu.
4. Spiel starten – der Coach findet den Log-Ordner und deinen Spielernamen selbst.

Windows SmartScreen kann bei der unsignierten `.exe` warnen („Weitere Informationen → Trotzdem ausführen“). Wer das nicht möchte, nutzt Variante B.

Spätere Updates installiert der Coach auf Wunsch selbst (Klick auf den Hinweis in der Statuszeile). Liegt der Programmordner an einem geschützten Ort (z. B. `C:\Program Files`) oder läuft der Coach aus dem Quellcode, öffnet der Hinweis stattdessen die Download-Seite; dann das neue Zip wie oben entpacken und den alten Ordner ersetzen (`git pull` bei Variante B).

Python muss für Variante A nicht installiert sein. Meldet Windows beim Start, dass eine Datei wie `VCRUNTIME140.dll` fehlt, hilft das kostenlose [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe); auf aktuellem Windows 10/11 ist es normalerweise schon vorhanden.

### Variante B: aus dem Quellcode

Voraussetzungen: Python 3.11 oder neuer.

```bash
git clone https://github.com/undelete83/hs-coach.git
cd hs-coach
pip install -r requirements.txt
pythonw hs_coach.py        # ohne Konsolenfenster; mit "python" siehst du Meldungen
```

## Einstellungen

Alles Wichtige steht im Fenster unter **⚙ Einstellungen**:

| Einstellung | Bedeutung |
|---|---|
| Log-Ordner | Leer = automatisch suchen (Registry und übliche Pfade auf lokalen Laufwerken). Erwartet wird `…\Hearthstone\Logs`. |
| Dein Spielername | Leer = automatisch erkennen. Nur nötig, falls das falsch liegt (z. B. `Name#1234`). |
| Kartendaten | `auto` lädt die Karten von HearthstoneJSON (einmalig ca. 10 MB, danach Cache) und nutzt ersatzweise vorhandene Hearthstone-Deck-Tracker-Dateien. |
| API-Key (optional) | Wird in deinem Benutzerordner gespeichert (`%APPDATA%\HSCoach\api_key.txt`), nie im Klartext angezeigt. Alternativ die Umgebungsvariable `ANTHROPIC_API_KEY`. |
| Modelle | Standard: `claude-haiku-5-5` für Tipps, `claude-sonnet-5-5` für Analysen. |
| Berichte | Wohin Spielanalysen als Markdown-Datei geschrieben werden (optional zusätzlich in einen zweiten Ordner, z. B. einen Notiz-Vault). |

Die Einstellungen liegen in `%APPDATA%\HSCoach\config.json`, Cache und Logdatei in `%LOCALAPPDATA%\hs_coach`.

## Kosten der KI-Funktionen

Der API-Key gehört dir, die Abrechnung läuft direkt bei Anthropic. Mit Haiku kostet ein Zug-Tipp typischerweise einen Bruchteil eines Cents; der Coach zeigt die Kosten der letzten Anfrage und der Sitzung an. Wer keinen Key einträgt, zahlt nichts.

## FAQ

**Der Coach zeigt „Hearthstone-Log nicht gefunden“.** Ist das Spiel gestartet? Hat es seit dem Anlegen der `log.config` einen Neustart gegeben? Liegt Hearthstone auf einem ungewöhnlichen Pfad, im Einstellungsfenster den Ordner `Logs` von Hand wählen.

**Er erkennt mich falsch / zeigt den Gegner als „Du“.** Im Einstellungsfenster den Spielernamen (BattleTag wie im Spiel) eintragen.

**Funktioniert das mit Wild/Standard/Duellen/Schlachtfeldern?** Entwickelt und getestet wurde der Coach vor allem mit den Solo-Abenteuern und normalen Partien. Schlachtfelder (Battlegrounds) und Söldner werden nicht unterstützt.

**Ist das erlaubt? Kann ich gebannt werden?** Das lässt sich nicht verbindlich beantworten. Blizzard hat dazu keine offizielle Freigabe veröffentlicht. Was feststeht:

- Der Coach liest nur die Logdatei `Power.log`, die Hearthstone auf Wunsch selbst schreibt (wie andere bekannte Tracker). Er verändert keine Spieldateien, liest nicht den Arbeitsspeicher des Spiels und automatisiert nichts im Spiel (keine Mausklicks, keine Eingaben).
- Der **Zugplan** und die **KI-Tipps** gehen über reines Mitzählen hinaus, weil sie Züge berechnen und empfehlen. Ob Blizzard das in Wettkampfmodi als unerlaubten Vorteil wertet, ist offen.
- Empfehlung: Nutze den Coach in den Solo-Abenteuern und gegen die KI, wofür er entwickelt und getestet wurde. In Ranglistenspielen, Arena und Turnieren (dort ist er in der Regel ausdrücklich nicht erlaubt) auf eigenes Risiko, oder lass den Zugplan und die KI-Tipps weg. Im Zweifel frage den Blizzard-Support.
- Es gibt keine Garantie, dass dir nichts passiert. Nutzung auf eigene Verantwortung, ohne Gewährleistung (siehe Lizenz).

## Bekannte Grenzen

- Oberfläche und Coach-Texte sind deutsch; Kartentexte kommen in der eingestellten Kartensprache (`deDE`).
- Der Planer versteht Kartentexte per Textanalyse. Seltene oder neue Effekte kennt er nicht immer; dann verhält sich die Karte im Plan wie ein „Diener ohne Effekt“. Das gilt auch für Zufallseffekte.
- Das Boss-Wissen ist für das Jaina-Kapitel gut belegt, für andere Kapitel teils lückenhaft.
- Der Plan ist ein Vorschlag, keine Garantie für den besten Zug.

## Für Entwickler

```bash
python -m unittest discover -s tests -t .       # Tests (laufen ohne Hearthstone und ohne Internet)
python scripts/install_hooks.py                 # Pre-Commit-Hook: blockiert versehentliche API-Keys
python scripts/build_exe.py                     # baut dist/HSCoach-<Version>.zip (PyInstaller)
```

| Modul | Aufgabe |
|---|---|
| `hscoach/logparser.py` | inkrementeller Parser für `Power.log` |
| `hscoach/state.py` | Entities → Spielstand |
| `hscoach/carddb.py`, `extract.py` | Kartendaten (HearthstoneJSON, ersatzweise HDT-Dateien) mit Cache |
| `hscoach/effects.py` | Kartentext → Effekt (Schaden, Einfrieren, Rabatt …) |
| `hscoach/planner.py`, `bosses*.py` | Zug-Simulation (Beam-Search), Boss-Wissen |
| `hscoach/ai.py`, `analysis.py` | optionale Claude-Anbindung |
| `hscoach/detect.py`, `settings.py`, `update.py` | Erkennung von Log-Ordner/`log.config`, Einstellungsdialog, Update-Hinweis |
| `hscoach/gui.py` | tkinter-Oberfläche |

Der Änderungsverlauf steht in [CHANGELOG.md](CHANGELOG.md). Die Testpartien in `tests/fixtures/` sind anonymisierte Ausschnitte echter Partien.

## Quellen und Dank

- Kartendaten und Kartenbilder: [HearthstoneJSON](https://hearthstonejson.com) (HearthSim). Die Karten und Bilder gehören Blizzard Entertainment; sie werden nicht im Repository mitgeliefert, sondern beim Benutzer geladen.
- Boss-Wissen, in eigenen Worten zusammengefasst: Hearthstone Wiki (Fandom), Top Decks, Icy Veins.
- Idee des Log-Lesens: die Community rund um Hearthstone Deck Tracker und HearthSim.

## Lizenz

[MIT](LICENSE) – ohne jede Gewährleistung.
