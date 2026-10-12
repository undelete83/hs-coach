# HS Coach – Hinweise für Claude Code

Live-Coach für Hearthstone unter Windows und macOS (Python/tkinter). Liest `Power.log`, Regel-Engine plant Züge, optional Claude-Tipps.
Repo: github.com/undelete83/hs-coach, Branch `main`. Besitzer: Andreas. Antworten auf Deutsch, lockerer Ton (Duzen) ist erwünscht.

## Stand (12.10.2026, Version 2.17.0)
- Letztes veröffentlichtes Release: v2.16.5. Neu in 2.17.0: Mac-Version (siehe CHANGELOG.md).
- Windows-Release: auf dem PC `python scripts/build_exe.py` → `HSCoach-X.Y.Z.zip`. Mac-Release: auf dem Mac `python3 scripts/build_mac.py` → `HSCoach-X.Y.Z-mac.zip` (beide mit `.sha256`). Der Windows-Updater nimmt nur `HSCoach-<Version>.zip` (`update.ASSET_RE`).
- Plattform-Weichen: `detect.IS_MAC`/`config.IS_MAC` (Pfade), `widgets.Button` (auf dem Mac flacher Label-Knopf statt `tk.Button`). Neue Knöpfe immer über `widgets.Button` anlegen.
- Kartenbasis: 2.304 sammelbare Zauber; rund 1.330 genau, ~700 geschätzt, ~270 unbekannt.

## Aufbau
- `hscoach/effects.py`: deutscher Kartentext (kleingeschrieben) → `Effect`-Dataclass per Regex. `unknown=True`, bis etwas Konkretes erkannt ist.
- `hscoach/planner.py`: Beam-Search über `SS`-Zustände (`_apply_fx`, `_play_card`, `_expand`, `_finish`, `_evaluate`, `_targets`, `_resolve`, `_variants`). `M` hat `mhp` (Maximalleben), `SS.temp` = Angriff nur für diesen Zug. Zielarten: friendly_minion, enemy_minion, any_minion, minion, face, any.
- Nicht simulierbare Dinge (Entdecken, Zufall, Karten auf die Hand) fließen nur als geschätzter Wert (`util`) ein. Neue Handkarten werden nicht weitergeführt.

## Regeln beim Erweitern
- **Solo-Regel**: Neue oder riskante Muster nur akzeptieren, wenn die Karte genau aus diesem einen Satz besteht. Mehrsatz-Karten nur, wenn jeder Satz sicher erkannt wird. Nie halb verstandene Karten rechnen; im Zweifel bleibt sie „unbekannt".
- Alte Tests halten manchmal die alte Regel fest (so bei 2.9.3, `test_choose_one.py`). Bei neuen Mustern prüfen, ob ein Test bewusst „unbekannt" erwartet.
- Testhilfen: `tests/helpers.py` (`CARDS`, `card`, `fake_db`, `gs`, `mm`), Beispiele in `tests/test_*.py`.

## Arbeitsablauf pro Paket
1. `python scripts/audit_effects.py --list` anschauen und eine kleine zusammenhängende Gruppe wählen. Das Skript braucht eine Kartendatei (`cards_deDE.json`). Lokal lädt der Coach sie selbst; in einer Cloud-Umgebung ohne Zugriff auf HearthstoneJSON kann man sie aus dem pip-Paket `hearthstone_data` (CardDefs.xml) bauen.
2. Parser und Planner erweitern, eigene Testdatei in `tests/` anlegen.
3. `python -m unittest discover -s tests -t .` (in der Cloud fehlten tkinter-Tests: 6 Errors, 16 skipped, bekannt).
4. `hscoach/__init__.py` Version erhöhen und oben in `CHANGELOG.md` einen Eintrag ergänzen (Deutsch, Datum tt.mm.jjjj; ein Test prüft das).
5. Commit und Push auf `main`.

## Offene Ideen
- Im echten Spiel mitschreiben, welche Karten „Effekt unbekannt" melden, und genau diese zuerst angehen.
- Restliche unbekannte Zauber sind kleinteilig: Quests, Auren über mehrere Züge, Leichen-Mechaniken, Bekehren (Kopie feindlicher Diener, kostet 1), Todesröcheln vergeben, temporäres Stehlen (Dunkler Wahnsinn), Verbotene Frucht/Flamme (manaabhängig), Tödliches Rezept (Mana-Schwelle).

## Recht / Hinweise
Inoffizielles Fan-Projekt. Der Coach liest nur `Power.log`. Zugplan und KI-Tipps sind eine Grauzone; die README-FAQ sagt das ehrlich (Empfehlung: Solo-Abenteuer und gegen die KI).
