# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Was das ist

Lokales Spielleiter-Werkzeug für **Mongoose Traveller 2e** (13Mann-Ausgabe). Generiert
Sektoren regelbasiert + deterministisch, speichert sie in SQLite, zeigt eine anklickbare
SVG-Hexkarte mit Detailkarte im SPECTRUM-Look. Flask + Standardbibliothek, kein Build-Schritt.

**Sprache:** Codebase ist durchgängig deutsch — Bezeichner, Kommentare, UI, Commit-Messages.
Diesen Stil beibehalten.

## Befehle

```bash
pip install flask          # einzige Laufzeit-Abhängigkeit; kein requirements.txt/pyproject
python run.py              # http://127.0.0.1:5000  (host 0.0.0.0, port 5000, debug aus Config)

pip install pytest         # Tests sind nicht standardmäßig installiert
python -m pytest           # alle Smoke-Tests
python -m pytest tests/test_smoke.py::test_index   # einzelner Test
```

Konfiguration über `FLASK_ENV` (`development` | `production` | `testing`; Default development).
`production` erzwingt `SECRET_KEY` aus der Umgebung (kein Dev-Fallback).

Die Generator-/Routen-Module sind eigenständig lauffähig (eigener `__main__`-Block mit
Demo bzw. Distanz-Selbsttest):

```bash
python -m app.generators.sektor    # Demo-Subsektor als Texttabelle
python -m app.generators.routen    # Hexdistanz-Selbsttest gegen bekannte Werte
```

## Architektur

Drei Schichten, strikt getrennt: **reine Generatoren → persist (DB-Brücke) → Blueprints/Templates.**

### Generatoren sind reine, seedbare Funktionen (`app/generators/`)
Das oberste Leitprinzip (siehe `ROADMAP.md`). Sie importieren **kein Flask**, nur Stdlib.
Gleicher Seed ⇒ exakt gleicher Sektor. Jede Welt bekommt einen eigenen **Sub-Seed
`master_seed|hex`** (Hexbesetzung zusätzlich über `…|occ`), damit eine einzelne Welt neu
gewürfelt werden kann, ohne die Nachbarn zu verschieben. Mechanik ist deterministisch;
Flavour (Namen) ist hier prozedural und darf später optional an ein LLM gehen. **Diese
Reinheit/Determinismus beim Erweitern erhalten.**

- `sektor.py` — UWP-Generierung nach MgT2-Regeln, `Welt`-Dataclass, eHex, alle Regeltabellen
  als Daten oben im Modul (leicht gegen das Buch anpassbar). `erzeuge_sektor` liefert
  `{subsektor_index 0..15: [Welt]}`.
- `faktionen.py` — 1W3 Fraktionen pro **bewohnter** Welt (importiert Regierungstabelle aus `sektor.py`).
- `routen.py` — Hexdistanz (Parsec) + Routen-**Heuristik** (kein harter Buch-Algorithmus).

### persist.py — einzige Brücke Generatoren ↔ DB
`speichere_sektor()` generiert einen ganzen Sektor und schreibt Welten/Fraktionen/Routen.
`lade_*()` liest zurück und **hydriert** dabei die JSON-Spalten (String → Python-Objekt),
sodass die Renderer sie direkt nutzen. `welt_zu_row()` / `fraktion_zu_row()` mappen die
Dataclass/dicts auf Spaltennamen. Generatoren kennen die DB nicht — alle SQL-Berührung
läuft hier oder in den Blueprints.

### Datenmodell (`schema.sql`) — Prinzipien, die neue Tabellen/Features respektieren müssen
- **Backbone = echte Fremdschlüssel** (`sektor → subsektor → welt → nsc/auftrag`),
  **weiche Querverweise = polymorpher Graph** in `verknuepfung` (bewusst OHNE FK; Dangling
  möglich, per App-Logik aufräumen).
- **Abfragbares → eigene Spalte, Variables/Abgeleitetes → JSON-TEXT.** `welt` führt die
  UWP-Komponenten einzeln (numerisch) UND als gerenderten String + JSON-Felder
  (`handelscodes`, `basen`, `raumhafen_details`, `kultur`, `sternendaten`, `wuerfe`).
- Jede generierte Entität trägt `seed` + `wuerfe` (Reproduzierbarkeit).
- **Entwurf bleibt außerhalb der DB** — erst „Behalten“ schreibt eine Zeile. `status` ist der
  Spiel-Lebenszyklus, nicht Entwurf/fixiert.
- `route` ist ungerichtet: `CHECK (welt_a_id < welt_b_id)` erzwingt kanonische Reihenfolge;
  `auto`-Flag trennt generierte von handgezeichneten Routen.
- `nsc_fraktion` ist n:m mit `geheim`-Flag (Doppelagenten → rotes Badge in der Card).

### Flask-Schicht
App-Factory in `app/__init__.py` (`create_app`) registriert Blueprints `main` (`GET /`) und
`sektor` (`/sektor/*`: generieren, Subsektor-Ansicht, `export.txt`, löschen). Eine
SQLite-Verbindung **pro Request** über Flask `g` (`db.py`).

### Rendering
`rendering/hexmap.py` baut die Hexkarte serverseitig als **SVG-String**;
`templates/sektor/subsektor.html` bettet es ein und ergänzt clientseitiges JS: Klick auf ein
`<polygon data-hex>` öffnet ein Detail-Overlay, das aus `WELTEN`/`LINKS` (per `| tojson`
injiziert) gebaut wird. Die eHex-/UWP-Dekodiertabellen und die **deutschen Handelsnamen
(`TRADE`)** liegen im JS dieser Datei.

## Nicht offensichtliche Stolperfallen

- **PRAGMA foreign_keys = ON muss pro Verbindung gesetzt werden** (macht `db.py`), sonst
  ignoriert SQLite die FKs **still**. Gilt auch für jedes eigene `sqlite3.connect`.
- **Schema-Änderungen greifen nicht automatisch.** `init_db_if_needed()` legt das Schema nur
  an, wenn die Tabelle `sektor` fehlt. Nach Bearbeiten von `schema.sql` die `traveller.db`
  (bzw. `test.db`) **löschen**, damit das neue Schema gilt. Die DB ist gitignored und wird
  beim ersten Start neu erzeugt.
- **`_g(obj, key)`** (getattr-oder-getitem) ist in `hexmap.py`, `routen.py`, `faktionen.py`
  dupliziert — damit Renderer/Generatoren **sowohl `Welt`-Objekte als auch DB-dicts** lesen.
  Beim Erweitern beide Pfade bedienen.
- **Hex-Geometrie muss konsistent bleiben:** even-q-Layout, gerade Spalten (02,04,…) ein
  halbes Hex nach **unten** versetzt; 1 Hex = 1 Parsec. `hexmap._center` (Render) und
  `routen._to_cube` (Distanz) müssen dasselbe Layout abbilden.
- **Routen werden nur gezeichnet, wenn beide Enden im selben Subsektor liegen**
  (bewusste v0.1-Grenze, kein subsektorübergreifendes Rendering).
- **Handelscodes intern kanonisch englisch** (`Ag`/`Hi`/`Ht`/…) für Kompatibilität zu
  Traveller Map; Anzeige deutsch via `CODE_DE` (Generator) bzw. `TRADE` (JS). **Achtung:**
  Buch `Di`=`Hi`, Buch `Hi`=`Ht` — vertauscht (Kommentar in `sektor.py`).

## Regelquelle & SPECTRUM

- **`weltenerschaffung.md`** ist das deutsche MgT2-Weltenerschaffungskapitel (13Mann) — die
  **kanonische Regelquelle**, gegen die die Generatoren gebaut sind. Bei Änderungen an der
  Würfellogik hiergegen abgleichen.
- Stellen, die noch gegen das Buch zu prüfen sind, sind im Code mit **`# PRUEFEN`** markiert
  (v. a. Temperatur-Atmosphären-WM).
- **SPECTRUM-Look durchgängig:** dunkle Fläche, Farbe nur für Bedeutung, Mono-Lockups für
  Daten, Nicht-Farb-Signale (Strichelung) als redundantes Signal. Reisezonen-Skala:
  grün = ruhig (kein Ring), amber = tertiary (solider Ring), rot = interdiziert (error,
  **gestrichelter** Ring). Design-Tokens sind doppelt geführt: `static/spectrum.css` (UI)
  und das `C`-dict in `hexmap.py` (SVG) — bei Farbänderungen beide anfassen.

## Roadmap-Kontext

`ROADMAP.md` ist gepflegt und nennt die nächsten Schritte. Nächster vorgesehener: **NSC-Editor
& -Generator** (`app/generators/nsc.py`) — die Detailkarte zeigt NSCs/Aufträge bereits an,
sobald sie in der DB stehen; es fehlt nur das Anlegen. Tabellen `nsc`, `auftrag` stehen schon.
