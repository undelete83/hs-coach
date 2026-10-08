# HS Coach

Live-Coach für **Hearthstone** (Windows). Der Coach liest die Logdatei, die Hearthstone selbst schreibt, und zeigt auf einem zweiten Monitor (oder neben dem Spiel) Spielstand, einen Zugplan und – wenn du möchtest – einen Tipp von Claude. Er greift nicht ins Spiel ein und braucht weder Hearthstone Deck Tracker noch einen Account irgendwo.

> Inoffizielles Fan-Projekt. Nicht von Blizzard Entertainment unterstützt oder verbunden. Hearthstone ist eine Marke von Blizzard Entertainment, Inc. Der Coach liest ausschließlich die Textdatei `Power.log`, die das Spiel selbst erzeugt.

## Was er kann

- **Spielstand live**: Leben, Rüstung, Mana, Boards (bereit / eingefroren / Spott / Gottesschild), deine Hand mit Kartentext, Waffe, Heldenkraft, Geheimnisse, letzte Spielzüge.
- **Zugplan (kostenlos, ohne Internet-Dienst)**: Eine Regel-Engine simuliert Karten, Angriffe, Heldenkraft, Rabatte, Einfrieren, Spott und Lethal und zeigt die Schritte in Reihenfolge – inklusive Warnung bei drohendem Tod.
- **Boss-Wissen** für die Solo-Abenteuer (Book of Heroes): Ziel, Heldenkraft, Tipps und Gefahren des Bosses in einer eigenen Spalte, nur während eines Boss-Kampfs.
- **Mulligan-Hilfe** und **Glossar** (Maus über unterstrichene Begriffe).
- **Optional mit eigenem Anthropic-API-Key**: KI-Tipps pro Zug (Streaming, Kostenanzeige) und eine Spielanalyse nach der Partie. Ohne Key sind diese Funktionen aus – alles andere funktioniert voll.
- **Kartenbilder** der empfohlenen Karten (abschaltbar).
- **Update-Hinweis**: Beim Start wird bei GitHub nachgesehen, ob es eine neuere Version gibt (abschaltbar). Es wird nichts automatisch installiert.

## Schnellstart

### Variante A: fertige Version (empfohlen)

1. Auf der [Release-Seite](https://github.com/undelete83/hs-coach/releases) das Zip `HSCoach-<Version>.zip` laden und entpacken.
2. `HSCoach.exe` starten. Beim ersten Start öffnet sich das Einstellungsfenster.
3. Hearthstone schreibt die Logdatei nur, wenn eine `log.config` existiert. Zeigt der Dialog „✗ …“, klicke auf **„Power.log aktivieren“** und starte Hearthstone danach einmal komplett neu.
4. Spiel starten – der Coach findet den Log-Ordner und deinen Spielernamen selbst.

Windows SmartScreen kann bei der unsignierten `.exe` warnen („Weitere Informationen → Trotzdem ausführen“). Wer das nicht möchte, nutzt Variante B.

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

**Ist das erlaubt?** Der Coach liest nur die Logdatei, die Hearthstone auf Wunsch selbst schreibt (wie andere bekannte Tracker). Er automatisiert nichts im Spiel. Eine Garantie gibt es trotzdem nicht – Nutzung auf eigene Verantwortung.

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
