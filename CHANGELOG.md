# Änderungsverlauf

Neueste Version oben. Die Versionsnummer steht in `hscoach/__init__.py` und im Fenstertitel; in der Statuszeile
zeigt der Coach zusätzlich den Commit und meldet "Neustart empfohlen", wenn im Repo schon etwas Neueres liegt.
Beim Erhöhen der Version bitte hier einen Eintrag ergänzen (ein Test prüft das). Einträge vor 2.6.0 stammen aus der
privaten Entwicklungsphase; das öffentliche Repository beginnt mit 2.6.0.

## 2.7.2 - 09.10.2026
- Kampfschreie mit der Bedingung „wenn Ihr einen Drachen auf der Hand habt“ werden jetzt geplant: Der Coach nennt das Ziel (z. B. Schuppenreiterin: 2 Schaden auf …), prüft, ob nach der Spielreihenfolge noch ein Drache auf der Hand ist, und beachtet Grenzen wie „max. 3 Angriff“ (Bücherwyrm). Riskante Varianten (zufällig, verletzt, Flächenschaden) bleiben bewusst unberücksichtigt.
- Schließen nach einem Update läuft ohne Tk-Fehler im Log.

## 2.7.1 - 08.10.2026
- Technische Version, um das Selbst-Update mit einem echten Release zu testen. Keine Änderungen an den Funktionen.

## 2.7.0 - 08.10.2026
- Selbst-Update der Windows-Version: Bei einer neuen Version genügt ein Klick auf den Hinweis in der Statuszeile. Der Coach lädt das Paket, prüft die SHA-256-Prüfsumme, entpackt es sicher, tauscht sich nach dem Beenden aus (mit Rückfall auf die alte Version, falls das Kopieren scheitert) und startet neu. Einstellungen, API-Key und Berichte bleiben erhalten.
- Aus dem Quellcode oder bei nicht beschreibbarem Ordner öffnet der Hinweis weiterhin die Download-Seite.
- `scripts/build_exe.py` schreibt zusätzlich eine `.sha256`-Datei.

## 2.6.0 - 08.10.2026
- Vorbereitung der Veröffentlichung: Kartendaten kommen standardmäßig von HearthstoneJSON, der Hearthstone Deck Tracker ist nicht mehr nötig (nur noch Fallback).
- Keine persönlichen Standardwerte mehr: Log-Ordner (Registry und übliche Pfade) und eigener Spieler werden automatisch erkannt; Einstellungen liegen in `%APPDATA%\HSCoach`.
- Neues Einstellungsfenster (Log-Ordner, Spielername, Kartenquelle, optionaler API-Key, Modelle, Berichte, Kartenbilder) und Prüfung/Anlegen der `log.config` (Power.log).
- Ohne API-Key arbeitet der Coach mit der Regel-Engine; KI-Tipps und Analyse sind dann sichtbar aus.
- Verständliche Fehlermeldungen in der Statuszeile (Kartendaten, Log-Ordner, `log.config`).
- Update-Hinweis über GitHub-Releases (abschaltbar), Windows-Build-Skript, MIT-Lizenz, README für Fremde, CI.
- Testpartien anonymisiert; Test prüft das Repo auf persönliche Daten.

## 2.5.0 - 08.10.2026
- Versionsanzeige: Fenstertitel `HS Coach v2.5.0`, Statuszeile mit Commit und Startzeit, Hinweis "Neustart empfohlen".
- Dieser Änderungsverlauf (`CHANGELOG.md`) und die Checkliste für die Veröffentlichung (`docs/VEROEFFENTLICHUNG.md`).

## 2.4.0 - 08.10.2026
- Der Wasserelementar friert jeden Charakter ein, den er verletzt - der Planer rechnet damit, auch bei Elementaren aus der Heldenkraft.
- Gewonnene Archimonde-Partie als Testfall und Lektion in `knowledge.md`.

## 2.3.0 - 08.10.2026
- Boss-Wissen für die Solo-Abenteuer (Book of Heroes): 39 Bosse, Boss-Spalte im Fenster, Siegschwelle (Archimonde: Kampf endet bei ≤ 10 Leben), Hinweise für die Engine und für Claude.
- Boss-Info nur während eines laufenden Boss-Kampfs; nach Spielende verschwindet sie.
- Archimonde-Hinweise aus dem Guide in `knowledge.md`.

## 2.2.0 - 08.10.2026
- Planer: Rabatt-Zauber (Elementarbeschwörung) nur noch mit passender Karte in der Hand; schwache Alternativen werden ausgeblendet.
- Gleichnamige Ziele werden unterscheidbar ("2. von links"); Flächenzauber nennen "kein Ziel nötig".
- Bei drohendem Tod zählt jeder verhinderte Schadenspunkt weiter.
- Nach der verlorenen Archimonde-Partie: Sicherheitskurve für das Leben, Beschwörungen der Gegner-Heldenkraft, Geheimnisse nach ihrer Wirkung bewertet.

## 2.1.0 - 08.10.2026
- Plan und automatischer KI-Tipp erscheinen erst, wenn der Bildschirm bei deinem Zug ist (PowerTaskList, Schritt `MAIN_ACTION`), nicht schon wenn das Log den Zug meldet.

## 2.0.0 - 08.10.2026
- Neubau als Paket `hscoach/` mit Config, inkrementellem Log-Parser, Karten-DB mit Cache, Zugplaner (Beam-Search), Claude-Anbindung (Haiku 5.5, Streaming, Analyse), Mulligan-Hilfe, Glossar, Kartenbildern, Tests und Secret-Schutz.

## 1.x - 04.-07.10.2026
- Erste Fassung als einzelne Datei: Spielstand, regelbasierter Coach, Claude-Tipp, Kartenbilder, Layout.
