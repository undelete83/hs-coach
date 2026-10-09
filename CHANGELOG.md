# Änderungsverlauf

Neueste Version oben. Die Versionsnummer steht in `hscoach/__init__.py` und im Fenstertitel; in der Statuszeile
zeigt der Coach zusätzlich den Commit und meldet "Neustart empfohlen", wenn im Repo schon etwas Neueres liegt.
Beim Erhöhen der Version bitte hier einen Eintrag ergänzen (ein Test prüft das). Einträge vor 2.6.0 stammen aus der
privaten Entwicklungsphase; das öffentliche Repository beginnt mit 2.6.0.

## 2.9.6 - 09.10.2026
- Behoben: Fensterposition und -größe wurden nicht wiederhergestellt, wenn das Fenster auf einem Monitor links vom Hauptmonitor lag. Tk schreibt solche Positionen als „+-2223“, und das wurde beim Laden nicht erkannt; der Coach startete dann immer mit der Standardgröße. Die Position wird jetzt richtig gelesen und geprüft: Liegt sie nach einer Monitoränderung außerhalb des Desktops, bleibt nur die Größe erhalten.
- Das Fenster merkt sich Position und Größe jetzt schon beim Verschieben bzw. Vergrößern (kurz nach der letzten Änderung), nicht erst beim Beenden. Es geht also auch dann nichts verloren, wenn der Coach beendet wird, ohne ihn zu schließen.

## 2.9.5 - 09.10.2026
- Die Textfelder (Zugplan, Hand, Board, Spielzüge, Boss-Info, KI-Tipp) wachsen jetzt mit ihrem Inhalt bis zu einer Obergrenze mit. Bisher wurden lange Pläne (z. B. 9 Schritte plus Alternativen) nach etwa 10 Zeilen abgeschnitten, die letzten Schritte waren nur durch Scrollen im Feld zu sehen.
- Lehre aus einer verlorenen Partie gegen Thrall (Jaina): Gegner-Diener mit **Lebensraub** (vor allem mit Windzorn, z. B. Wandelnder Brunnen) heilen den Gegner bei jedem Treffer und schlagen doppelt. Der Planer bewertet Lebensraub jetzt nach Angriff und Windzorn, rechnet die Heilung des Gegners im Rennen um sein Leben mit und nimmt solche Diener zuerst ins Visier.
- Boss Thrall (Jaina-Kapitel): Priorität für Wandelnder Brunnen und Frostwolfkriegsfürst, vorsichtigeres Spiel, neue Tipps und Gefahren (Gewittersturm, nicht mit leerem Brett zwei kleine Diener opfern). `knowledge.md` enthält die Lektionen für den KI-Tipp.

## 2.9.4 - 09.10.2026
- Neu verstanden: Karten auf die Hand. „Erhaltet N Token (a/b) auf die Hand“ (Hexenwaldapfel), „Wählt einen Diener. Erhaltet eine Kopie davon auf die Hand“ (Geisterbeschwörung, eigene und feindliche Ziele) sowie „Kopie jedes (verletzten) befreundeten Dieners“ (Echo von Medivh, Blutkrieger). Der Planer rechnet das als Kartenwert ein (stärkere Diener sind mehr wert); er führt die neuen Handkarten nicht weiter aus.
- Varianten mit Zusatzregeln (Finale, „kostet (1)“, mehrere Ziele) bleiben „unbekannt“.

## 2.9.3 - 09.10.2026
- Neu verstanden: „Zieht N Diener (Drachen, Wildtiere, Mechs … / mit Spott). Verleiht ihnen +X/+X.“ (Auf in die Lüfte, Diebesgut). Der Planer zählt die gezogenen Karten und rechnet die Stärkung grob als Wert ein, weil er die Handkarten nicht einzeln weiterführt. Varianten mit Bedingung (z. B. „wenn Ihr mind. 10 Mana habt“) oder Zusatzeffekt (Finale) bleiben „unbekannt“.

## 2.9.2 - 09.10.2026
- Neu verstanden: „Ruft eine Kopie eines befreundeten Dieners herbei“ (Verschmelzung), auf Wunsch mit Spott für die Kopie. Der Planer sucht den besten eigenen Diener zum Kopieren aus; die Kopie kann in diesem Zug nicht angreifen, und ohne Diener oder bei vollem Brett wird die Karte nicht gespielt. Kopien feindlicher Diener und Kopien mit Zusatzregeln bleiben „unbekannt“.

## 2.9.1 - 09.10.2026
- Neu verstanden: Stärkungen „je Diener, den Ihr kontrolliert“ (Geschenk des Waldes). Der Planer rechnet die Stärkung nach der Zahl deiner Diener zum Zeitpunkt des Ausspielens aus.

## 2.9.0 - 09.10.2026
- Neue verstandene Zauber: **Werte setzen** (z. B. Leben/Angriff eines Dieners auf einen festen Wert, Gleichheit, Schrumpfstrahl), **Kontrolle übernehmen** (Gedankenkontrolle & Co.: der feindliche Diener wechselt auf dein Brett) und Stärkungen mit **Zielbedingungen** („verletzter Diener“, „befreundeter Wildtier/Dämon/Mech …“, „Eure Totems“).
- Der Planer wählt nur noch passende Ziele (verletzt, richtiges Volk) und spielt Karten nicht, wenn sie nichts bewirken würden. Neue Zielart „beliebiger Diener“ (eigene oder gegnerische), z. B. für Dinogröße.
- Wie immer gilt: Karten mit zusätzlichen, nicht verstandenen Sätzen bleiben „unbekannt“, statt halb gerechnet zu werden.

## 2.8.1 - 09.10.2026
- Zauber mit Entdecken oder Zufall, die der Coach nicht genau berechnen kann, bekommen jetzt einen pauschal geschätzten Wert (etwa eine Karte) statt „Effekt unbekannt“. Im Plan steht deutlich „Entdecken/Zufall: Wert pauschal geschätzt (kein genauer Effekt)“ samt Kartentext, damit du selbst entscheidest. Erkannte Effekte schlagen die Pauschale; teilweise erkannte Karten bekommen nichts zusätzlich geschätzt.
- `scripts/audit_effects.py` weist jetzt getrennt aus, wie viele Zauber wirklich unbekannt und wie viele nur grob geschätzt sind.

## 2.8.0 - 09.10.2026
- „Wählt aus“ (Druiden-Zauber) wird geplant: Der Coach spielt jede erkannte Option durch und nimmt die bessere. Im Plan steht, welche Option er empfiehlt, z. B. „Spiele Mal der Natur – Wahl: Verleiht einem Diener +4 Angriff“. Erkannt werden „Mal der Natur“, „Dunkle Einflüsterung“ (nur die Stärkungs-Option), „Aufforstung“, „Eisbeißermine einnehmen“ und „Geheimzutat“ (nur die Held-Option).
- Optionen, die der Coach nicht versteht (Entdecken, Zufall, Beschwören ohne Werte), bleiben außen vor, statt geraten zu werden. Besteht eine Karte nur aus solchen Optionen, bleibt sie „unbekannt“.
- Karten, die einen bestimmten Typ ziehen („Zieht einen Zauber“, „Zieht Eure teuerste Karte“), zählen als eine gezogene Karte, aber nur, wenn die Karte nichts weiter tut.

## 2.7.9 - 09.10.2026
- Drittes Paket der bisher unverstandenen Zauber: Diener heilen. Der Plan kennt jetzt das Maximalleben der Diener und heilt nie darüber hinaus (auch nicht nach einer Stärkung mit +Leben). „Kreis der Heilung“ (alle Diener, auch die des Gegners), „Verbindende Heilung“ (ein Diener und der eigene Held) und „Heilung der Ahnen“ (volles Leben und Spott) werden geplant.
- Der Plan spielt Heilzauber nur, wenn sie wirklich etwas heilen. Er darf dafür auch erst angreifen und danach heilen, etwa bei einem 0-Mana-Zauber wie dem Kreis der Heilung.
- Zauber mit Zusatzbedingungen (Krapfen: Nachbarn und Mana, Baum des Lebens: alle Charaktere) bleiben bewusst „unbekannt“.

## 2.7.8 - 09.10.2026
- Zweites Paket der bisher unverstandenen Zauber: Stärkungen mit Schlüsselwörtern. Gottesschild und Lebensentzug auf einen oder alle eigenen Diener (Hand des Schutzes, Rechtschaffenheit, Siegel des Champions, Segen des Pharaos, Apotheose, Lichtgeschmiedeter Segen), „Stärken“ (nur eigene Diener mit Spott) und Angriff nur für diesen Zug: „Kampfrausch“ (alle Diener), „Wildes Brüllen“ (Diener und Held), „Unerbittliche Jagd“ (Held, die Immunität rechnet der Plan nicht mit).
- Angriff „nur in diesem Zug“ zählt nicht für das Board nach dem Zug, sodass der Plan solche Zauber nur spielt, wenn damit wirklich angegriffen wird. Ein Gottesschild auf einen Diener, der schon eins hat, wird nicht verschwendet.
- Zauber mit mehreren Sätzen und unbekannten Zusätzen (z. B. „Segnen“, „Haltet die Brücke“, Zauberschaden-Stärkungen, Eifer/Ansturm) bleiben bewusst „unbekannt“, statt halb verstanden zu werden.

## 2.7.7 - 09.10.2026
- Erstes Paket der bisher unverstandenen Zauber: Schaden nach Wert wird jetzt geplant. „Das Licht! Es brennt!“ (Schaden = Angriff des Ziels), „Lichtbombe“ (jeder Diener, beide Seiten, bekommt Schaden in Höhe seines Angriffs), „Unbändigkeit“ (Schaden = Angriff deines Helden) und „Rundumschlag“ (verbraucht die ganze Rüstung, ebenso viel Schaden an alle Diener). Ohne nutzbaren Wert (kein Angriff, keine Rüstung) spielt der Plan die Karte nicht.
- „Strangulieren“ vernichtet den feindlichen Diener mit dem höchsten Angriff (bei Gleichstand rechnet der Plan mit dem mit dem meisten Leben, im echten Spiel entscheidet der Zufall).
- Der Anteil der unverstandenen sammelbaren Zauber sinkt damit auf 45 %. Die übrigen Zauber folgen in weiteren kleinen Paketen.

## 2.7.6 - 09.10.2026
- Mehr Karten werden verstanden und geplant, statt als „Effekt unbekannt“ zu enden: Arkane Geschosse und ähnliche Zufalls-Geschosse (ohne gegnerische Diener exakt, sonst als Erwartungswert), Heilen des eigenen Helden, Schweigen, Gegner-Diener zurück auf die Hand oder „aus dem Spiel entfernen“, leere Manakristalle, „Füllt Eure Seite des Schlachtfelds“ (Fokussierungsiris), Selbststärkung je anderem Diener bzw. je Handkarte (Frostwolfkriegsfürst, Zwielichtdrache), Shandris Mondfeder (linker und rechter Gegner-Diener), „Euer nächster Zauber kostet (0), wenn Ihr einen Drachen auf der Hand habt“ sowie Stärkungszauber (+X/+Y auf einen Diener oder alle, Held +Angriff in diesem Zug).
- Bei Karten, die der Planer weiterhin nicht simulieren kann (Entdecken, zufällige Karten, Quests ...), zeigt der Plan jetzt den Kartentext direkt an, statt nur „Kartentext lesen“.
- `scripts/audit_effects.py` zeigt, wie viele sammelbare Zauber der Parser versteht (aktuell 55 %; der Rest sind überwiegend Entdecken-, Zufalls- und Questkarten).
- Der Kartentext-Marker `[d]` mitten in Wörtern wird entfernt.

## 2.7.5 - 09.10.2026
- Behoben: Frisch gespielte Diener mit Eifer (z. B. Schuppenwurm) wurden als „erschöpft“ gewertet, der Plan sagte deshalb „Keine sinnvolle Aktion“. Sie dürfen sofort Diener angreifen (den Helden nicht) und werden jetzt so eingeplant.

## 2.7.4 - 09.10.2026
- Neuer Button „⟳ Auf Update prüfen“: sucht sofort bei GitHub nach einer neuen Version, ohne den Coach neu zu starten. Bei einem Update folgt die gewohnte Rückfrage und Installation; ohne Update meldet er „Du hast bereits die neueste Version“, bei Verbindungsproblemen eine Fehlermeldung.
- Zusätzlich sucht der Coach alle 30 Minuten still nach Updates, sodass der Hinweis in der Statuszeile auch bei langer Laufzeit erscheint.

## 2.7.3 - 09.10.2026
- Selbststärkung per Kampfschrei („Erhält +1 Angriff und Eifer/Spott/Ansturm, wenn Ihr einen Drachen auf der Hand habt“, z. B. Schuppenwurm) wird geplant: Der Coach rechnet mit den echten Werten (5/4) und lässt den Diener bei Eifer sofort angreifen.
- Begriffe korrigiert: **Eifer** = sofort angreifen, aber nur Diener; **Ansturm** = sofort angreifen, auch den Helden. Die Anzeige am Board und das Glossar nutzen jetzt die richtigen Wörter.

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
