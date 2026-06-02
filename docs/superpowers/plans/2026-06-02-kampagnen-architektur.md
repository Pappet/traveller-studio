# Kampagnen-zentrierte Architektur — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Werkzeug kampagnen-zentriert machen: `Kampagne` als Wurzel (1:n Sektoren), NSC/Fraktion/Auftrag direkt an der Kampagne, NSC-Orte (Herkunft/Aufenthalt), Dashboard mit eigenständigen Editoren, Kaskaden+Such-Fraktions-Picker, Multi-Relations-Hexkarte.

**Architecture:** Schema bekommt `kampagne`-Tabelle + `kampagne_id`-FKs auf sektor/nsc/fraktion/auftrag; `nsc.welt_id`→`aufenthalt_welt_id`. Generatoren bleiben rein. persist.py bleibt einzige DB-Brücke. Orte teils Backbone-FK (Aufenthalt), teils `verknuepfung`-Graph (Herkunft/wirkt_in). Navigation: Kampagnen-Liste = Startseite → Kampagnen-Dashboard → Editoren.

**Tech Stack:** Flask + Stdlib, SQLite, Jinja2, serverseitiges SVG, Vanilla-JS in den Templates. Tests via pytest + `TestingConfig` (Wegwerf-DB pro Test).

**Keine Migration:** DB enthält nur Testdaten. Nach Schema-Änderung `traveller.db` löschen, frisch generieren (Phase A, Task A8).

**Referenz-Spec:** `docs/superpowers/specs/2026-06-02-kampagnen-architektur-design.md`

---

## Datei-Struktur (Überblick)

**Neu:**
- `app/blueprints/kampagne.py` — Kampagnen-CRUD, Liste (Home), Dashboard.
- `app/templates/kampagne_liste.html` — Startseite (Kampagnen-Karten).
- `app/templates/kampagne_dashboard.html` — Hub: Sektoren/NSC/Fraktion/Auftrag-Listen.
- `app/templates/kampagne_form.html` — Kampagne anlegen/bearbeiten.
- `tests/test_kampagne.py` — Phase A/B Integrationstests.
- `tests/test_orte.py` — Phase C (NSC-Orte, Picker, Hexkarte).

**Geändert:**
- `app/schema.sql` — kampagne-Tabelle, FKs, Rename, Indizes.
- `app/db.py` — Guard-Tabelle `sektor`→`kampagne`.
- `app/persist.py` — kampagne-CRUD, kampagne_id durchreichen, baue_links-Rename, Orte-Queries.
- `app/generators/nsc.py` — `nsc_zu_row` Signatur (+kampagne_id, aufenthalt).
- `app/generators/faktionen.py` — `fraktion_zu_row` Signatur (+kampagne_id).
- `app/blueprints/main.py` — index → Kampagnen-Liste.
- `app/blueprints/sektor.py` — Generierung unter Kampagne, home_url→Dashboard.
- `app/blueprints/{nsc,auftrag,fraktion,welt}.py` — kampagne_id auflösen/durchreichen, Redirects.
- `app/templates/nsc_form.html` — Fraktions-Picker (Kaskade+Suche), Orte-Felder.
- `app/templates/sektor/subsektor.html` — Hexkarte: Orte nach Relation gruppiert.
- `tests/test_prep.py`, `tests/test_smoke.py` — an neues Schema anpassen.

---

# PHASE A — Kampagne-Wurzel + Datenmodell

Fundament. Nach dieser Phase: Kampagnen anlegen/löschen, Sektoren unter einer Kampagne generieren, alte Funktionen laufen mit kampagne_id weiter. Tests grün.

### Task A1: Schema — kampagne-Tabelle + FKs + Rename

**Files:**
- Modify: `app/schema.sql`
- Modify: `app/db.py:33` (Guard-Tabellenname)

- [ ] **Step 1: kampagne-Tabelle einfügen** (vor `CREATE TABLE sektor`, nach Zeile 18-Kommentarblock)

```sql
CREATE TABLE kampagne (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    notizen     TEXT,
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: sektor.kampagne_id ergänzen** (in `CREATE TABLE sektor`, nach `id`-Zeile)

```sql
    kampagne_id INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
```

- [ ] **Step 3: nsc — welt_id umbenennen + kampagne_id** (ersetze Zeile 100)

```sql
    kampagne_id  INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
    aufenthalt_welt_id INTEGER REFERENCES welt(id) ON DELETE SET NULL, -- aktueller Aufenthalt; NULL = schiffsgebunden/unverortet
```

- [ ] **Step 4: fraktion.kampagne_id** (in `CREATE TABLE fraktion`, nach `id`)

```sql
    kampagne_id  INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
```

- [ ] **Step 5: auftrag.kampagne_id** (in `CREATE TABLE auftrag`, nach `id`)

```sql
    kampagne_id   INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
```

- [ ] **Step 6: Indizes anpassen** (ersetze `idx_nsc_welt`, ergänze kampagne-Indizes)

```sql
CREATE INDEX idx_sektor_kampagne   ON sektor(kampagne_id);
CREATE INDEX idx_nsc_kampagne      ON nsc(kampagne_id);
CREATE INDEX idx_nsc_aufenthalt    ON nsc(aufenthalt_welt_id);
CREATE INDEX idx_fraktion_kampagne ON fraktion(kampagne_id);
CREATE INDEX idx_auftrag_kampagne  ON auftrag(kampagne_id);
```
(Lösche die Zeile `CREATE INDEX idx_nsc_welt ON nsc(welt_id);`.)

- [ ] **Step 7: db.py Guard-Tabelle** — `app/db.py` Zeile 33: `name='sektor'` → `name='kampagne'`.

- [ ] **Step 8: Commit**

```bash
git add app/schema.sql app/db.py
git commit -m "feat(schema): kampagne-Tabelle, kampagne_id-FKs, nsc.welt_id->aufenthalt_welt_id"
```

---

### Task A2: persist — Kampagnen-CRUD

**Files:**
- Modify: `app/persist.py` (neue Funktionen am Ende der Editier-Schicht)
- Test: `tests/test_kampagne.py` (neu)

- [ ] **Step 1: Failing test** — `tests/test_kampagne.py`

```python
from __future__ import annotations
import pytest
from app import create_app
from app.config import TestingConfig
from app import db as dbmod
from app import persist


@pytest.fixture
def app_ctx(tmp_path):
    TestingConfig.DB_PATH = str(tmp_path / "test.db")
    app = create_app("testing")
    with app.app_context():
        yield app


def test_kampagne_crud(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "Reft-Kampagne", "Notiz")
    assert isinstance(kid, int)
    k = persist.lade_kampagne(db, kid)
    assert k["name"] == "Reft-Kampagne"
    assert persist.liste_kampagnen(db)[0]["id"] == kid
    persist.aktualisiere_kampagne(db, kid, {"name": "Neu"})
    assert persist.lade_kampagne(db, kid)["name"] == "Neu"
    persist.loesche_kampagne(db, kid)
    assert persist.lade_kampagne(db, kid) is None
```

- [ ] **Step 2: Run, expect FAIL** — `python -m pytest tests/test_kampagne.py::test_kampagne_crud -v` → `AttributeError: erstelle_kampagne`.

- [ ] **Step 3: Implement** — in `app/persist.py` ergänzen (nutzt vorhandene `_insert`/`_update`):

```python
# ---------------------------------------------------------------------
#  Kampagne (Wurzel)
# ---------------------------------------------------------------------
_KAMPAGNE_EDIT = {"name", "notizen"}


def erstelle_kampagne(db: sqlite3.Connection, name: str, notizen: str | None = None) -> int:
    return _insert(db, "kampagne", {"name": name or "Unbenannte Kampagne",
                                    "notizen": notizen})


def lade_kampagne(db: sqlite3.Connection, kampagne_id: int) -> dict | None:
    r = db.execute("SELECT * FROM kampagne WHERE id=?", (kampagne_id,)).fetchone()
    return dict(r) if r else None


def liste_kampagnen(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT id, name, notizen FROM kampagne ORDER BY erstellt_am DESC").fetchall()
    out = []
    for k in rows:
        sek = db.execute("SELECT COUNT(*) c FROM sektor WHERE kampagne_id=?", (k["id"],)).fetchone()["c"]
        nsc = db.execute("SELECT COUNT(*) c FROM nsc WHERE kampagne_id=?", (k["id"],)).fetchone()["c"]
        out.append({"id": k["id"], "name": k["name"], "notizen": k["notizen"],
                    "sektoren": sek, "nscs": nsc})
    return out


def aktualisiere_kampagne(db: sqlite3.Connection, kampagne_id: int, felder: dict) -> None:
    _update(db, "kampagne", kampagne_id, felder, _KAMPAGNE_EDIT)


def loesche_kampagne(db: sqlite3.Connection, kampagne_id: int) -> None:
    db.execute("DELETE FROM kampagne WHERE id=?", (kampagne_id,))
    db.commit()
```

- [ ] **Step 4: Run, expect PASS** — `python -m pytest tests/test_kampagne.py::test_kampagne_crud -v`.

- [ ] **Step 5: Commit** — `git add app/persist.py tests/test_kampagne.py && git commit -m "feat(persist): Kampagnen-CRUD"`

---

### Task A3: Generatoren-Signaturen (kampagne_id, aufenthalt)

**Files:**
- Modify: `app/generators/nsc.py` (`nsc_zu_row`)
- Modify: `app/generators/faktionen.py` (`fraktion_zu_row`)
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test** — ergänze in `tests/test_kampagne.py`:

```python
def test_zu_row_signaturen():
    from app.generators.nsc import erzeuge_nsc, nsc_zu_row
    from app.generators.faktionen import fraktion_zu_row
    n = erzeuge_nsc("S")
    row = nsc_zu_row(n, kampagne_id=5, aufenthalt_welt_id=9)
    assert row["kampagne_id"] == 5 and row["aufenthalt_welt_id"] == 9
    assert "welt_id" not in row
    fr = {"name": "X", "art": "Splittergruppe", "reichweite": "lokal",
          "staerke_wurf": 6, "regierung_name": "R", "staerke": "S",
          "staerke_beschreibung": "B", "seed": "s", "wuerfe": {}}
    frow = fraktion_zu_row(fr, heimatwelt_id=2, kampagne_id=5)
    assert frow["kampagne_id"] == 5 and frow["heimatwelt_id"] == 2
```

- [ ] **Step 2: Run, expect FAIL** — `python -m pytest tests/test_kampagne.py::test_zu_row_signaturen -v`.

- [ ] **Step 3: Implement nsc_zu_row** — `app/generators/nsc.py`, ersetze die Funktion:

```python
def nsc_zu_row(nsc: dict, kampagne_id: int, aufenthalt_welt_id: int | None) -> dict:
    """Mappt ein NSC-dict auf die Spalten der `nsc`-Tabelle (JSON serialisiert)."""
    import json
    return {
        "name": nsc["name"],
        "kampagne_id": kampagne_id,
        "aufenthalt_welt_id": aufenthalt_welt_id,
        "eigenschaften": json.dumps(nsc["eigenschaften"]),
        "skills": json.dumps(nsc["skills"]),
        "laufbahn": json.dumps(nsc.get("laufbahn")) if nsc.get("laufbahn") else None,
        "ausruestung": json.dumps(nsc.get("ausruestung") or []),
        "rolle": nsc.get("rolle"),
        "beschreibung": nsc.get("beschreibung"),
        "seed": nsc.get("seed"),
        "wuerfe": json.dumps(nsc.get("wuerfe") or {}),
    }
```

- [ ] **Step 4: Implement fraktion_zu_row** — `app/generators/faktionen.py`, Signatur erweitern:

```python
def fraktion_zu_row(fr: dict, heimatwelt_id: int, kampagne_id: int) -> dict:
    """Mappt ein Fraktions-dict auf die Spalten der `fraktion`-Tabelle."""
    import json
    return {
        "name": fr["name"],
        "kampagne_id": kampagne_id,
        "typ": fr["art"],
        "reichweite": fr["reichweite"],
        "heimatwelt_id": heimatwelt_id,
        "einfluss": fr["staerke_wurf"],
        "ziele": f"{fr['regierung_name']} ({fr['staerke']})",
        "notizen": fr["staerke_beschreibung"],
        "seed": fr["seed"],
        "wuerfe": json.dumps(fr["wuerfe"]),
    }
```

- [ ] **Step 5: Run, expect PASS**.

- [ ] **Step 6: Commit** — `git commit -am "feat(gen): nsc_zu_row/fraktion_zu_row mit kampagne_id"`

---

### Task A4: persist — speichere_sektor + Save-Funktionen mit kampagne_id

**Files:**
- Modify: `app/persist.py` (`speichere_sektor`, `liste_sektoren`, `speichere_nsc`, `speichere_auftrag`, `speichere_fraktion`, `baue_links`, `welt_kontext`)
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test**:

```python
def test_speichere_sektor_unter_kampagne(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    sid = persist.speichere_sektor(db, "SEED", "Sektor1", dichte="dicht", kampagne_id=kid)
    assert db.execute("SELECT kampagne_id FROM sektor WHERE id=?", (sid,)).fetchone()["kampagne_id"] == kid
    # Generierte Fraktionen tragen die Kampagne
    fr = db.execute("SELECT kampagne_id FROM fraktion LIMIT 1").fetchone()
    assert fr is None or fr["kampagne_id"] == kid
    assert persist.liste_sektoren(db, kid)[0]["id"] == sid
```

- [ ] **Step 2: Run, expect FAIL** (TypeError: unexpected kwarg kampagne_id).

- [ ] **Step 3: Implement** — `speichere_sektor` Signatur + INSERTs (ersetze relevante Zeilen):

```python
def speichere_sektor(db: sqlite3.Connection, seed: str, name: str,
                     dichte: str = "normal", zugehoerigkeit: str = "Im",
                     *, kampagne_id: int) -> int:
    cur = db.cursor()
    cur.execute("INSERT INTO sektor(kampagne_id, name, seed) VALUES(?, ?, ?)",
                (kampagne_id, name, seed))
    sektor_id = cur.lastrowid
    # ... subsektoren + welten unveraendert ...
    # Fraktions-INSERT: heimatwelt + kampagne_id
    for ss_index, welten in sektor_welten.items():
        for wlt in welten:
            for fr in erzeuge_fraktionen(wlt, seed):
                frow = fraktion_zu_row(fr, hex2id[wlt.hex], kampagne_id)
                spalten = ", ".join(frow.keys())
                platzhalter = ", ".join("?" * len(frow))
                cur.execute(f"INSERT INTO fraktion ({spalten}) VALUES ({platzhalter})",
                            list(frow.values()))
    # ... routen unveraendert ...
```

- [ ] **Step 4: liste_sektoren filtern** — Signatur `liste_sektoren(db, kampagne_id)`, SQL `... WHERE kampagne_id=? ORDER BY erstellt_am DESC`, Parameter ergänzen. Fraktions-Count-Subquery bleibt (joint über welt.sektor_id).

- [ ] **Step 5: speichere_nsc/auftrag/fraktion + baue_links anpassen**:

```python
def speichere_nsc(db, kampagne_id: int, aufenthalt_welt_id: int | None, nsc: dict) -> int:
    return _insert(db, "nsc", nsc_zu_row(nsc, kampagne_id, aufenthalt_welt_id))

def speichere_auftrag(db, row: dict) -> int:   # row enthält bereits kampagne_id
    return _insert(db, "auftrag", row)

def speichere_fraktion(db, kampagne_id: int, heimatwelt_id: int | None, felder: dict) -> int:
    row = {"name": felder.get("name") or "Unbenannte Fraktion",
           "kampagne_id": kampagne_id,
           "typ": felder.get("typ"),
           "reichweite": felder.get("reichweite") or "lokal",
           "heimatwelt_id": heimatwelt_id,
           "einfluss": felder.get("einfluss"),
           "ziele": felder.get("ziele"),
           "notizen": felder.get("notizen")}
    return _insert(db, "fraktion", row)
```
In `baue_links`: `... FROM nsc WHERE aufenthalt_welt_id=? ORDER BY id`.

- [ ] **Step 6: welt_kontext um kampagne_id erweitern** — SQL ergänzen `w.sektor_id`, join sektor für `se.kampagne_id AS kampagne_id`:

```python
def welt_kontext(db, welt_id: int) -> dict | None:
    r = db.execute(
        "SELECT w.id, w.sektor_id, w.hex, w.name, s.idx AS ss_index, se.kampagne_id "
        "FROM welt w LEFT JOIN subsektor s ON w.subsektor_id=s.id "
        "JOIN sektor se ON w.sektor_id=se.id WHERE w.id=?", (welt_id,)).fetchone()
    return dict(r) if r else None
```

- [ ] **Step 7: Run, expect PASS**.

- [ ] **Step 8: Commit** — `git commit -am "feat(persist): kampagne_id in speichere_sektor + Save-Funktionen, baue_links Rename"`

---

### Task A5: Kampagne-Blueprint + Templates (Liste = Home, Dashboard)

**Files:**
- Create: `app/blueprints/kampagne.py`
- Create: `app/templates/kampagne_liste.html`, `kampagne_dashboard.html`, `kampagne_form.html`
- Modify: `app/__init__.py` (Blueprint registrieren), `app/blueprints/main.py` (index → Kampagnen-Liste)
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test** (Routen):

```python
@pytest.fixture
def client(tmp_path):
    TestingConfig.DB_PATH = str(tmp_path / "test.db")
    app = create_app("testing")
    with app.test_client() as c:
        yield app, c

def test_kampagne_routen(client):
    app, c = client
    assert c.get("/").status_code == 200
    r = c.post("/kampagne/neu", data={"name": "Reft"})
    assert r.status_code == 302
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    assert c.get(f"/kampagne/{kid}").status_code == 200
    assert c.post(f"/kampagne/{kid}/loeschen").status_code == 302
```

- [ ] **Step 2: Run, expect FAIL** (404 auf /kampagne/neu).

- [ ] **Step 3: Implement Blueprint** — `app/blueprints/kampagne.py`:

```python
"""Kampagne-Blueprint: Liste (Startseite), Dashboard, anlegen/bearbeiten/loeschen."""
from __future__ import annotations
from flask import Blueprint, abort, redirect, render_template, request, url_for
from .. import db as dbmod
from .. import persist

bp = Blueprint("kampagne", __name__)


@bp.post("/kampagne/neu")
def kampagne_neu():
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, (request.form.get("name") or "").strip(),
                                    (request.form.get("notizen") or "").strip() or None)
    return redirect(url_for("kampagne.dashboard", kampagne_id=kid))


@bp.route("/kampagne/<int:kampagne_id>")
def dashboard(kampagne_id: int):
    db = dbmod.get_db()
    k = persist.lade_kampagne(db, kampagne_id)
    if not k:
        abort(404)
    return render_template(
        "kampagne_dashboard.html", kampagne=k,
        sektoren=persist.liste_sektoren(db, kampagne_id),
        nscs=persist.liste_nscs(db, kampagne_id),
        fraktionen=persist.liste_fraktionen(db, kampagne_id),
        auftraege=persist.liste_auftraege(db, kampagne_id),
        home_url=url_for("main.index"),
    )


@bp.post("/kampagne/<int:kampagne_id>/loeschen")
def kampagne_loeschen(kampagne_id: int):
    db = dbmod.get_db()
    if not persist.lade_kampagne(db, kampagne_id):
        abort(404)
    persist.loesche_kampagne(db, kampagne_id)
    return redirect(url_for("main.index"))
```

> Hinweis: `liste_nscs/liste_fraktionen/liste_auftraege` werden in Phase B (Task B1) ergänzt. Für Phase A im Dashboard zunächst leere Listen übergeben — ersetze die drei `persist.liste_*`-Aufrufe durch `[]` und vervollständige in B1. (Damit Task A5 isoliert grün ist.)

- [ ] **Step 4: main.index → Kampagnen-Liste** — `app/blueprints/main.py`:

```python
@bp.route("/")
def index():
    return render_template("kampagne_liste.html",
                           kampagnen=persist.liste_kampagnen(dbmod.get_db()))
```

- [ ] **Step 5: Templates** — `kampagne_liste.html` (analog `index.html`, Karten verlinken `kampagne.dashboard`, Anlege-Form POSTet `kampagne.kampagne_neu`); `kampagne_dashboard.html` (Sektor-Sektion mit Generier-Form POST `sektor.sektor_generieren` inkl. `<input type=hidden name=kampagne_id value=...>`, plus vier Listen-Platzhalter); `kampagne_form.html` minimal. Alle `{% extends "base.html" %}`, SPECTRUM-Klassen (`panel`, `sec-label`, `cards`, `card`, `btn`).

- [ ] **Step 6: Blueprint registrieren** — `app/__init__.py`: `from .blueprints.kampagne import bp as kampagne_bp` + `app.register_blueprint(kampagne_bp)`.

- [ ] **Step 7: Run, expect PASS**.

- [ ] **Step 8: Commit** — `git commit -am "feat(kampagne): Blueprint + Liste(Home)/Dashboard-Templates"`

---

### Task A6: Sektor-Generierung unter Kampagne + home_url→Dashboard

**Files:**
- Modify: `app/blueprints/sektor.py`
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test**:

```python
def test_sektor_unter_kampagne_generieren(client):
    app, c = client
    c.post("/kampagne/neu", data={"name": "K"})
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    r = c.post("/sektor/generieren", data={"name": "S", "seed": "X", "dichte": "dicht",
                                           "kampagne_id": str(kid)})
    assert r.status_code == 302
    with app.app_context():
        assert dbmod.get_db().execute("SELECT kampagne_id FROM sektor").fetchone()["kampagne_id"] == kid
```

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement** — `sektor_generieren`: `kampagne_id` aus Form lesen, validieren (Kampagne existiert sonst 404), an `speichere_sektor(..., kampagne_id=kid)` geben. `subsektor_ansicht`: `home_url` → `url_for("kampagne.dashboard", kampagne_id=sektor["kampagne_id"])` (sektor-row trägt jetzt kampagne_id; lade_sektor liefert sie via `SELECT *`). `sektor_loeschen`: nach Löschen zur Dashboard der Kampagne zurück (kampagne_id vor dem Löschen lesen).

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: Commit** — `git commit -am "feat(sektor): Generierung an Kampagne gebunden, Dashboard-Rücksprung"`

---

### Task A7: Bestehende Editoren auf kampagne_id umstellen

**Files:**
- Modify: `app/blueprints/nsc.py`, `app/blueprints/auftrag.py`, `app/blueprints/fraktion.py`, `app/blueprints/welt.py`
- Test: bestehende `tests/test_prep.py` (anpassen)

- [ ] **Step 1: test_prep-Helper anpassen** — `_sektor_mit_welt` erzeugt zuerst eine Kampagne und generiert den Sektor mit `kampagne_id`. Ersetze den ersten `client.post`:

```python
    client.post("/kampagne/neu", data={"name": "K"})
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    client.post("/sektor/generieren",
                data={"name": "T", "seed": "PREP-SEED", "dichte": "dicht", "kampagne_id": str(kid)})
```
Und die NSC-Lade-Asserts: `welt_id` → `aufenthalt_welt_id`.

- [ ] **Step 2: Run, expect FAIL** (NSC-Speichern bricht: nsc_zu_row braucht kampagne_id).

- [ ] **Step 3: nsc.py anpassen** — `nsc_neu`: kampagne_id aus `ctx["kampagne_id"]`, Aufruf `persist.speichere_nsc(db, ctx["kampagne_id"], welt_id, nsc)`. `nsc_bearbeiten`: für sektorlose NSCs `kampagne_id` direkt aus der nsc-Row (lade_nsc liefert sie). `sektor_fraktionen(db, sektor_id)` bleibt vorerst; Picker-Umbau in Phase C. `_NSC_EDIT` um `aufenthalt_welt_id` ergänzen (statt `welt_id`).

- [ ] **Step 4: auftrag.py anpassen** — `auftrag_neu`: `row["kampagne_id"] = ctx["kampagne_id"]`. `_AUFTRAG_EDIT` unverändert (kampagne_id nicht editierbar). `welt_id_des_auftrags` bleibt.

- [ ] **Step 5: fraktion.py anpassen** — `fraktion_neu`: `persist.speichere_fraktion(db, ctx["kampagne_id"], welt_id, _felder(request.form))`.

- [ ] **Step 6: welt.py anpassen** — `aktualisiere_welt`/`neuwuerfeln_welt`/`erzeuge_welt_in_hex` unberührt (kein kampagne_id nötig — Welt hängt am Sektor). Redirects bleiben Subsektor-Ansicht. Prüfen, dass `persist._WELT_KOMPONENTEN`-Import steht.

- [ ] **Step 7: Run, expect PASS** — `python -m pytest tests/test_prep.py -v`.

- [ ] **Step 8: Commit** — `git commit -am "refactor(blueprints): NSC/Auftrag/Fraktion an kampagne_id, aufenthalt_welt_id"`

---

### Task A8: Smoke-Tests + frische DB + Gesamtlauf

**Files:**
- Modify: `tests/test_smoke.py` (falls Sektor-Generierung ohne Kampagne)
- Delete (lokal): `traveller.db`

- [ ] **Step 1: test_smoke prüfen/anpassen** — jeder Test, der `/sektor/generieren` ohne Kampagne ruft, bekommt vorher `/kampagne/neu` + `kampagne_id`. Falls test_smoke nur `/` testet, ggf. nur Erwartung anpassen.

- [ ] **Step 2: Frische DB** — `rm -f traveller.db` (gitignored, wird neu erzeugt).

- [ ] **Step 3: Gesamtlauf** — `python -m pytest -q`. Expected: alle grün.

- [ ] **Step 4: Manueller Rauchtest** — `python run.py`, im Browser `/` → Kampagne anlegen → Sektor generieren → Subsektor-Ansicht lädt.

- [ ] **Step 5: Commit** — `git commit -am "test: Suite auf Kampagnen-Schema angepasst"`

---

# PHASE B — Eigenständige Editoren / Dashboard-Listen

Nach dieser Phase: Dashboard listet NSC/Fraktion/Auftrag der Kampagne; Standalone-Anlegen (Ort optional); Detail-Editoren erreichbar ohne Welt-Einstieg.

### Task B1: persist — Listen-Abfragen pro Kampagne

**Files:**
- Modify: `app/persist.py`
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test**:

```python
def test_listen_pro_kampagne(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    from app.generators.nsc import erzeuge_nsc
    persist.speichere_nsc(db, kid, None, erzeuge_nsc("S"))
    assert len(persist.liste_nscs(db, kid)) == 1
    assert persist.liste_fraktionen(db, kid) == []
    assert persist.liste_auftraege(db, kid) == []
```

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement**:

```python
def liste_nscs(db, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT n.id, n.name, n.rolle, n.status, n.aufenthalt_welt_id, w.name AS ort "
        "FROM nsc n LEFT JOIN welt w ON n.aufenthalt_welt_id=w.id "
        "WHERE n.kampagne_id=? ORDER BY n.name", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]


def liste_fraktionen(db, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT fr.id, fr.name, fr.typ, fr.reichweite, fr.einfluss, w.name AS heimat "
        "FROM fraktion fr LEFT JOIN welt w ON fr.heimatwelt_id=w.id "
        "WHERE fr.kampagne_id=? ORDER BY fr.name", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]


def liste_auftraege(db, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT a.id, a.titel, a.typ, a.status, w.name AS ort "
        "FROM auftrag a LEFT JOIN welt w ON a.welt_id=w.id "
        "WHERE a.kampagne_id=? ORDER BY a.status, a.titel", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: Dashboard verdrahten** — in `kampagne.py` die `[]`-Platzhalter (Task A5) durch echte `persist.liste_*`-Aufrufe ersetzen.

- [ ] **Step 6: Commit** — `git commit -am "feat(persist): Kampagnen-Listen für NSC/Fraktion/Auftrag + Dashboard verdrahtet"`

---

### Task B2: Standalone-Anlegen (Ort optional) + Dashboard-Listen-Templates

**Files:**
- Modify: `app/blueprints/nsc.py`, `app/blueprints/fraktion.py`, `app/blueprints/auftrag.py`
- Modify: `app/templates/kampagne_dashboard.html`
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test**:

```python
def test_nsc_standalone_anlegen(client):
    app, c = client
    c.post("/kampagne/neu", data={"name": "K"})
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    assert c.get(f"/kampagne/{kid}/nsc/neu").status_code == 200
    r = c.post(f"/kampagne/{kid}/nsc/neu",
               data={"aktion": "speichern", "name": "Jora", "rolle": "Kontakt"})
    assert r.status_code == 302
    with app.app_context():
        n = dbmod.get_db().execute("SELECT kampagne_id, aufenthalt_welt_id FROM nsc").fetchone()
    assert n["kampagne_id"] == kid and n["aufenthalt_welt_id"] is None
```

- [ ] **Step 2: Run, expect FAIL** (404).

- [ ] **Step 3: Neue Routen** — in `nsc.py` Route `GET/POST /kampagne/<int:kampagne_id>/nsc/neu` (analog `nsc_neu`, aber `welt_id=None`, `ctx` aus `lade_kampagne` mit Minimal-Feldern `{"kampagne_id": kid, "sektor_id": None, "ss_index": 0, "name": "—", "hex": "—"}`, Redirect → Dashboard). Gleiches Muster für `fraktion.py` (`/kampagne/<id>/fraktion/neu`, heimatwelt_id=None) und `auftrag.py` (`/kampagne/<id>/auftrag/neu`). Die `_render`-Helfer akzeptieren bereits ein `kontext`-dict — `zurueck_url` zeigt aufs Dashboard, wenn `sektor_id` None.

- [ ] **Step 4: Dashboard-Listen-Templates** — in `kampagne_dashboard.html` vier Abschnitte: je Liste eine Tabelle/Karten mit Edit-Link (`nsc.nsc_bearbeiten` etc.) + „+ Neu"-Button (→ `…/kampagne/<id>/<entity>/neu`).

- [ ] **Step 5: Run, expect PASS**.

- [ ] **Step 6: Commit** — `git commit -am "feat(editoren): Standalone-Anlegen (Ort optional) + Dashboard-Listen"`

---

# PHASE C — NSC-Orte + Fraktions-Picker + Hexkarte

### Task C1: persist — Orte über verknuepfung (Herkunft/wirkt_in)

**Files:**
- Modify: `app/persist.py`
- Test: `tests/test_orte.py` (neu, gleiche Fixtures wie test_kampagne)

- [ ] **Step 1: Failing test**:

```python
def test_nsc_orte_graph(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    from app.generators.nsc import erzeuge_nsc
    nid = persist.speichere_nsc(db, kid, None, erzeuge_nsc("S"))
    persist.setze_nsc_ort(db, nid, welt_id=42, relation="stammt_von")
    orte = persist.nsc_orte(db, nid)
    assert {"welt_id": 42, "relation": "stammt_von"} in orte
    # Welt-Query liefert NSCs mit dieser Herkunft
    treffer = persist.nscs_an_welt(db, 42)
    assert any(t["id"] == nid and t["relation"] == "stammt_von" for t in treffer)
```

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement** (`verknuepfung`-Helfer):

```python
_NSC_ORT_RELATIONEN = ("stammt_von", "wirkt_in", "versteckt_auf")


def setze_nsc_ort(db, nsc_id: int, welt_id: int, relation: str) -> None:
    if relation not in _NSC_ORT_RELATIONEN:
        return
    db.execute(
        "INSERT OR IGNORE INTO verknuepfung(von_typ, von_id, zu_typ, zu_id, relation) "
        "VALUES('nsc', ?, 'welt', ?, ?)", (nsc_id, welt_id, relation))
    db.commit()


def loesche_nsc_orte(db, nsc_id: int, relation: str | None = None) -> None:
    if relation:
        db.execute("DELETE FROM verknuepfung WHERE von_typ='nsc' AND von_id=? "
                   "AND zu_typ='welt' AND relation=?", (nsc_id, relation))
    else:
        db.execute("DELETE FROM verknuepfung WHERE von_typ='nsc' AND von_id=? AND zu_typ='welt'",
                   (nsc_id,))
    db.commit()


def nsc_orte(db, nsc_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT zu_id AS welt_id, relation FROM verknuepfung "
        "WHERE von_typ='nsc' AND von_id=? AND zu_typ='welt'", (nsc_id,)).fetchall()
    return [dict(r) for r in rows]


def nscs_an_welt(db, welt_id: int) -> list[dict]:
    """NSCs mit Bezug zu Welt W: Aufenthalt (relation='befindet_sich') + Graph-Relationen."""
    out = [{"id": r["id"], "name": r["name"], "rolle": r["rolle"], "relation": "befindet_sich"}
           for r in db.execute(
               "SELECT id, name, rolle FROM nsc WHERE aufenthalt_welt_id=?", (welt_id,)).fetchall()]
    for r in db.execute(
            "SELECT n.id, n.name, n.rolle, v.relation FROM verknuepfung v "
            "JOIN nsc n ON n.id=v.von_id "
            "WHERE v.von_typ='nsc' AND v.zu_typ='welt' AND v.zu_id=?", (welt_id,)).fetchall():
        out.append({"id": r["id"], "name": r["name"], "rolle": r["rolle"], "relation": r["relation"]})
    return out
```

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: Commit** — `git commit -am "feat(persist): NSC-Orte über verknuepfung-Graph"`

---

### Task C2: baue_links — Orte nach Relation gruppiert

**Files:**
- Modify: `app/persist.py` (`baue_links`)
- Test: `tests/test_orte.py`

- [ ] **Step 1: Failing test** — generiere Sektor, setze für einen NSC `aufenthalt_welt_id=W` und Herkunft `stammt_von=W2`; assert `baue_links` liefert für W einen NSC mit relation `befindet_sich`, für W2 relation `stammt_von`.

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement** — `baue_links` nutzt `nscs_an_welt(db, wid)` statt der direkten `aufenthalt_welt_id`-Query; gruppiert Ergebnis nach `relation` in `eintrag["nscs_nach_ort"] = {"befindet_sich": [...], "stammt_von": [...], "wirkt_in": [...]}` (leere Gruppen weglassen). `geheim`-Badge wie bisher pro NSC ermitteln. Bestehender `eintrag["nscs"]`-Schlüssel bleibt zusätzlich = Gruppe `befindet_sich` (Rückwärtskompatibilität der Card-JS bis C4).

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: Commit** — `git commit -am "feat(persist): baue_links gruppiert NSCs nach Orts-Relation"`

---

### Task C3: NSC-Formular — Orte-Felder (Aufenthalt + Herkunft) + Verdrahtung

**Files:**
- Modify: `app/blueprints/nsc.py`, `app/templates/nsc_form.html`
- Test: `tests/test_orte.py`

- [ ] **Step 1: Failing test** — POST auf `nsc_bearbeiten` mit `aufenthalt_welt_id=W` und `herkunft_welt_id=W2`; assert nsc-Row `aufenthalt_welt_id=W` und `nsc_orte` enthält `{welt_id:W2, relation:'stammt_von'}`.

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement** — `nsc_bearbeiten`/`nsc_neu` POST: `aufenthalt_welt_id` ins `felder`-dict (in `_NSC_EDIT`), Herkunft über `persist.loesche_nsc_orte(db, nid, "stammt_von")` + `setze_nsc_ort(...)` wenn gesetzt. Template `nsc_form.html`: zwei Welt-Auswahlen (Aufenthalt, Herkunft) — verwenden denselben Kaskaden-Picker wie Task C4 (Subsektor▸Hex), Wert = welt_id.

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: Commit** — `git commit -am "feat(nsc): Orte-Felder Aufenthalt/Herkunft im Editor"`

---

### Task C4: Fraktions-Picker (Kaskade + Suche)

**Files:**
- Modify: `app/persist.py` (`fraktionen_nach_welt_struktur`), `app/blueprints/nsc.py`, `app/templates/nsc_form.html`
- Test: `tests/test_orte.py`

- [ ] **Step 1: Failing test** (persist) — `fraktionen_struktur(db, kampagne_id)` liefert `[{ss_index, ss_name, welten:[{welt_id, hex, name, fraktionen:[{id,name,typ}]}]}]`, nur Welten mit Fraktionen.

- [ ] **Step 2: Run, expect FAIL**.

- [ ] **Step 3: Implement persist**:

```python
def fraktionen_struktur(db, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT s.idx AS ss_index, s.name AS ss_name, w.id AS welt_id, w.hex, w.name AS welt_name, "
        "       fr.id AS fr_id, fr.name AS fr_name, fr.typ AS fr_typ "
        "FROM fraktion fr JOIN welt w ON fr.heimatwelt_id=w.id "
        "JOIN subsektor s ON w.subsektor_id=s.id JOIN sektor se ON w.sektor_id=se.id "
        "WHERE se.kampagne_id=? ORDER BY s.idx, w.hex, fr.name", (kampagne_id,)).fetchall()
    aus: dict = {}
    for r in rows:
        ss = aus.setdefault(r["ss_index"], {"ss_index": r["ss_index"],
                                            "ss_name": r["ss_name"], "welten": {}})
        wlt = ss["welten"].setdefault(r["welt_id"], {"welt_id": r["welt_id"], "hex": r["hex"],
                                                     "name": r["welt_name"], "fraktionen": []})
        wlt["fraktionen"].append({"id": r["fr_id"], "name": r["fr_name"], "typ": r["fr_typ"]})
    return [{"ss_index": s["ss_index"], "ss_name": s["ss_name"],
             "welten": list(s["welten"].values())} for s in aus.values()]
```

- [ ] **Step 4: Blueprint** — `nsc_neu`/`nsc_bearbeiten`: statt `sektor_fraktionen` jetzt `persist.fraktionen_struktur(db, kampagne_id)` + flache Liste aller Kampagnen-Fraktionen (`persist.liste_fraktionen`) für das Suchfeld, beide ans Template.

- [ ] **Step 5: Template-Picker** — `nsc_form.html`: drei gekoppelte Selects (Subsektor→Hex→Fraktionen) als `<select>` + JS, das aus `STRUKTUR | tojson` die Optionen kaskadiert; daneben `<input>` Suchfeld, das die flache Fraktionsliste filtert. Gewählte Fraktionen als Chips (mit Rolle/geheim) in versteckten Feldern `fr_<id>`/`geheim_<id>`/`rolle_<id>` — kompatibel zu `_fraktionen_aus_form`. Lange Flachliste entfällt.

- [ ] **Step 6: Run, expect PASS** + manueller Klicktest.

- [ ] **Step 7: Commit** — `git commit -am "feat(nsc): Fraktions-Picker Kaskade+Suche statt Flachliste"`

---

### Task C5: Hexkarte — NSCs nach Orts-Relation anzeigen

**Files:**
- Modify: `app/templates/sektor/subsektor.html` (Card-JS)
- Test: manueller Klicktest + bestehende test_prep grün

- [ ] **Step 1: Card-JS erweitern** — die Detail-Overlay-Funktion liest `links[hex]` jetzt `nscs_nach_ort` (aus Task C2). Drei Abschnitte rendern: „Hier ansässig" (`befindet_sich`), „Stammt von hier" (`stammt_von`), „Wirkt hier" (`wirkt_in`) — nur nicht-leere. NSC-Namen verlinken auf `nsc_bearbeiten`. `geheim`-Badge erhalten.

- [ ] **Step 2: Run** — `python -m pytest -q` (alle grün), `python run.py`, Hex mit verorteten NSCs klicken → drei Gruppen sichtbar.

- [ ] **Step 3: Commit** — `git commit -am "feat(hexkarte): NSCs nach Orts-Relation gruppiert in der Detailkarte"`

---

# PHASE D — Tech-Schuld: Fraktions-Generator-Entdoppelung

### Task D1: Eindeutigere Fraktionsnamen

**Files:**
- Modify: `app/generators/faktionen.py` (`_fraktionsname` / `erzeuge_fraktionen`)
- Test: `tests/test_kampagne.py`

- [ ] **Step 1: Failing test**:

```python
def test_fraktionsnamen_eindeutig_pro_welt(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    persist.speichere_sektor(db, "DUP-SEED", "S", dichte="dicht", kampagne_id=kid)
    rows = db.execute("SELECT heimatwelt_id, name FROM fraktion").fetchall()
    proWelt: dict = {}
    for r in rows:
        proWelt.setdefault(r["heimatwelt_id"], []).append(r["name"])
    for namen in proWelt.values():
        assert len(namen) == len(set(namen)), "doppelte Fraktionsnamen an einer Welt"
```

- [ ] **Step 2: Run, expect FAIL** (Generator vergibt Namen mehrfach).

- [ ] **Step 3: Implement** — in `erzeuge_fraktionen` die je Welt erzeugten Namen in einem `set` sammeln; bei Kollision neu würfeln (max. N Versuche) oder einen deterministischen Suffix (`II`, `III`) anhängen. Determinismus bewahren (gleicher Seed → gleiche Namen) — Suffix-Variante ist deterministisch und einfacher.

- [ ] **Step 4: Run, expect PASS**.

- [ ] **Step 5: ROADMAP-Notiz** — Phase-D-Punkt in `ROADMAP.md` als erledigt markieren (falls dort gelistet).

- [ ] **Step 6: Commit** — `git commit -am "fix(gen): eindeutige Fraktionsnamen pro Welt"`

---

## Abschluss

- [ ] **Gesamtlauf** — `python -m pytest -q` alle grün.
- [ ] **Self-/Code-Review** — `/code-review` über den Branch-Diff.
- [ ] **Spec/ROADMAP aktualisieren** — Konzept-Phasen als umgesetzt markieren.
- [ ] **Branch abschließen** — `superpowers:finishing-a-development-branch` (Merge/PR nach Wunsch).
