# Checkliste: Veröffentlichung des HS Coach

Stand: 08.10.2026 (Version 2.6.0). Ziel: ein öffentliches Repo und eine Version, die jeder ohne Programmierkenntnisse nutzen kann. Der Claude-API-Zugang ist optional und wird vom Benutzer selbst eingetragen.

## 1. Unabhängig von Hearthstone Deck Tracker (HDT)
- [x] HearthstoneJSON als Standard-Kartenquelle (`https://api.hearthstonejson.com/v1/latest/deDE/cards.json`), Cache in `%LOCALAPPDATA%\hs_coach`, neu laden nach 3 Tagen oder bei fehlendem Cache.
- [x] HDT-Dateien (`CardDefs`, `HearthDb.dll`) nur noch optionaler Fallback (`card_source = hdt` oder `auto`).
- [ ] Optional: passende Karten-Version über die Build-Nummer im Log laden (`/v1/<build>/deDE/cards.json`) statt `latest`.
- Schon unabhängig: Kartenbilder (`art.hearthstonejson.com`), Log-Parser (liest nur `Power.log`).

## 2. Persönliche Daten entfernen
- [x] Defaults ohne Spielernamen und feste Pfade: Log-Ordner wird über Registry und Standardpfade lokaler Laufwerke gefunden, der eigene Spieler automatisch erkannt (Spielername nur bei Bedarf).
- [x] Testpartien anonymisiert (Name, `GameAccountId`).
- [x] Test `tests/test_publication.py` prüft alle versionierten Dateien auf persönliche Zeichenfolgen.
- [x] Frische Git-Historie: dieses Repository beginnt mit einem einzigen Commit; die private Entwicklungshistorie wurde nicht übernommen.
- [x] API-Key nie im Repo: Pre-Commit-Hook und `scripts/check_secrets.py --all` (läuft auch in der CI).

## 3. Erststart und Einstellungen
- [x] Einstellungsfenster (Log-Ordner, Spielername, Kartenquelle, API-Key maskiert, Modelle, Berichte, Kartenbilder, Update-Hinweis). Der Key liegt in `%APPDATA%\HSCoach\api_key.txt`, nie im Repo.
- [x] Prüfung der `log.config` mit Button „Power.log aktivieren“ (sichert eine vorhandene Datei als `.bak`).
- [x] Ohne Key: KI-Funktionen sichtbar aus mit Hinweistext, Regel-Engine voll nutzbar.
- [x] Erster Start öffnet das Einstellungsfenster.

## 4. Installation
- [x] `scripts/build_exe.py` baut `dist/HSCoach-<Version>.zip` mit PyInstaller (ohne Konsolenfenster).
- [x] GitHub-Release `v2.6.0` mit Zip. Ab 2.7.0: Zip und `.sha256` anhängen, Text aus `CHANGELOG.md`.
- [x] Update-Hinweis: beim Start einmal `releases/latest` abfragen, bei neuerer Version Hinweis in der Statuszeile; abschaltbar.
- [x] Selbst-Update der `.exe` (ab 2.7.0): Download nur von `github.com/<repo>/releases/download/`, SHA-256-Prüfung gegen den von GitHub gelieferten Wert, sicheres Entpacken, Austausch nach dem Beenden mit Rückfall auf die alte Version. Nur nach Klick und Bestätigung. Ende-zu-Ende getestet gegen einen lokalen Server (`HS_COACH_UPDATE_URL`, Testhook `HS_COACH_UPDATE_AUTO`).
- [ ] Optional: Release-Zip signieren (Schutz auch gegen einen gekaperten GitHub-Account).
- [ ] Optional: Icon für die `.exe`, Code-Signatur (gegen SmartScreen-Warnung).

## 5. Rechtliches und Quellen
- [x] MIT-Lizenz (`LICENSE`).
- [x] Hinweis im README: kein offizielles Blizzard-Produkt, liest nur die vom Spiel erzeugte Logdatei.
- [x] Quellenangaben im README (HearthstoneJSON, Hearthstone Wiki, Top Decks, Icy Veins). Kartenbilder werden nicht ins Repo gepackt.

## 6. Qualität
- [x] README für Fremde: Schnellstart, Einstellungen, Kosten, FAQ, Grenzen.
- [ ] Screenshots im README.
- [ ] Englische Oberfläche als Option (Texte sind aktuell deutsch; Kartentexte hängen an der Sprache der Kartendaten).
- [ ] Boss-Daten vervollständigen (Rexxar, Valeera, Malfurion, Garrosh/Uther/Anduin-Kapitel).
- [x] Fehlermeldungen im Fenster („Kartendaten konnten nicht geladen werden“, „Hearthstone-Ordner nicht gefunden“, `log.config`-Hinweis).
- [x] Tests laufen ohne HDT und ohne persönliche Daten; CI mit GitHub Actions (`.github/workflows/tests.yml`).
