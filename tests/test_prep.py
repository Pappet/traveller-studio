"""
Integrationstests fuer die Prep-Werkzeuge (NSC / Auftrag / Fraktion / Welt-Editor).

Decken die neuen Routen end-to-end ab: Formular-GET (Template rendert),
Generieren, Speichern (Redirect + DB-Zeile), Bearbeiten, Statuswechsel, Loeschen
sowie die Welt-Editor-Funktionen (Felder ueberschreiben, neu wuerfeln, Welt in
leeren Hex setzen, Subsektor benennen). Frische Wegwerf-DB pro Test.
"""
from __future__ import annotations
import pytest

from app import create_app
from app.config import TestingConfig
from app import db as dbmod


@pytest.fixture
def app_client(tmp_path):
    TestingConfig.DB_PATH = str(tmp_path / "test.db")
    app = create_app("testing")
    with app.test_client() as c:
        yield app, c


def _sektor_mit_welt(app, client):
    """Erzeugt einen dichten Sektor und liefert (sektor_id, welt_id, hex, leerer_hex) in Subsektor 0."""
    client.post("/sektor/generieren", data={"name": "T", "seed": "PREP-SEED", "dichte": "dicht"})
    with app.app_context():
        db = dbmod.get_db()
        sid = db.execute("SELECT id FROM sektor").fetchone()["id"]
        w = db.execute(
            "SELECT w.id, w.hex FROM welt w JOIN subsektor s ON w.subsektor_id=s.id "
            "WHERE s.sektor_id=? AND s.idx=0 AND w.bevoelkerung>0 LIMIT 1", (sid,)).fetchone()
        belegt = {r["hex"] for r in db.execute(
            "SELECT hex FROM welt WHERE sektor_id=?", (sid,)).fetchall()}
        leer = next(f"{c:02d}{r:02d}" for c in range(1, 9) for r in range(1, 11)
                    if f"{c:02d}{r:02d}" not in belegt)
        return sid, w["id"], w["hex"], leer


def _q(app, sql, params=()):
    """Einzelabfrage in EIGENEM App-Context (niemals client-Calls darin schachteln!)."""
    with app.app_context():
        return dbmod.get_db().execute(sql, params).fetchone()


# ---------------------------------------------------------------------
#  NSC
# ---------------------------------------------------------------------
def test_nsc_form_get(app_client):
    app, client = app_client
    _, wid, _, _ = _sektor_mit_welt(app, client)
    r = client.get(f"/welt/{wid}/nsc/neu")
    assert r.status_code == 200
    assert "Neuer NSC".encode() in r.data


def test_nsc_generieren_rerendert(app_client):
    app, client = app_client
    _, wid, _, _ = _sektor_mit_welt(app, client)
    r = client.post(f"/welt/{wid}/nsc/neu", data={"aktion": "generieren", "archetyp": "pilot"})
    assert r.status_code == 200
    assert b"PROFIL" in r.data


def test_nsc_speichern_und_laden(app_client):
    app, client = app_client
    _, wid, _, _ = _sektor_mit_welt(app, client)
    daten = {"aktion": "speichern", "name": "Testkontakt", "rolle": "Patron",
             "skills": "Pilot 2\nAstrogation 1", "ausruestung": "Vakuumanzug",
             "beschreibung": "x", "notizen": "Notiz", "status": "lebendig",
             "eig_STR": 7, "eig_GES": 9, "eig_KON": 8, "eig_INT": 10, "eig_BIL": 6, "eig_SOZ": 5}
    assert client.post(f"/welt/{wid}/nsc/neu", data=daten).status_code == 302
    import json
    n = _q(app, "SELECT * FROM nsc WHERE welt_id=?", (wid,))
    assert n["name"] == "Testkontakt" and n["rolle"] == "Patron"
    assert json.loads(n["eigenschaften"])["GES"] == 9
    assert json.loads(n["skills"])["Pilot"] == 2
    nid = n["id"]
    assert client.get(f"/nsc/{nid}").status_code == 200                 # Bearbeiten-GET rendert
    client.post(f"/nsc/{nid}", data={"name": "Neu", "rolle": "Rivale", "status": "tot"})
    assert _q(app, "SELECT name FROM nsc WHERE id=?", (nid,))["name"] == "Neu"
    client.post(f"/nsc/{nid}/loeschen")
    assert _q(app, "SELECT 1 FROM nsc WHERE id=?", (nid,)) is None


def test_nsc_fraktion_geheim(app_client):
    app, client = app_client
    sid, wid, _, _ = _sektor_mit_welt(app, client)
    with app.app_context():
        db = dbmod.get_db()
        fr = db.execute("SELECT fr.id FROM fraktion fr JOIN welt w ON fr.heimatwelt_id=w.id "
                        "WHERE w.sektor_id=? LIMIT 1", (sid,)).fetchone()
        assert fr, "Sektor sollte Fraktionen haben"
        frid = fr["id"]
    client.post(f"/welt/{wid}/nsc/neu", data={
        "aktion": "speichern", "name": "Spion", "rolle": "Kontakt",
        "eig_STR": 7, "eig_GES": 7, "eig_KON": 7, "eig_INT": 7, "eig_BIL": 7, "eig_SOZ": 7,
        f"fr_{frid}": "on", f"geheim_{frid}": "on", f"rolle_{frid}": "Agent"})
    with app.app_context():
        db = dbmod.get_db()
        nf = db.execute("SELECT geheim FROM nsc_fraktion WHERE fraktion_id=?", (frid,)).fetchone()
        assert nf and nf["geheim"] == 1


# ---------------------------------------------------------------------
#  Auftrag
# ---------------------------------------------------------------------
def test_auftrag_flow(app_client):
    app, client = app_client
    _, wid, _, _ = _sektor_mit_welt(app, client)
    assert client.get(f"/welt/{wid}/auftrag/neu").status_code == 200
    assert client.post(f"/welt/{wid}/auftrag/neu", data={"aktion": "generieren"}).status_code == 200
    r = client.post(f"/welt/{wid}/auftrag/neu", data={
        "aktion": "speichern", "titel": "Testauftrag", "typ": "Transport",
        "belohnung": "Cr. 10.000", "status": "offen"})
    assert r.status_code == 302
    a = _q(app, "SELECT * FROM auftrag WHERE welt_id=?", (wid,))
    assert a["titel"] == "Testauftrag"
    aid = a["id"]
    client.post(f"/auftrag/{aid}/status", data={"status": "aktiv"})
    assert _q(app, "SELECT status FROM auftrag WHERE id=?", (aid,))["status"] == "aktiv"
    client.post(f"/auftrag/{aid}/status", data={"status": "quatsch"})    # ungueltig -> ignoriert
    assert _q(app, "SELECT status FROM auftrag WHERE id=?", (aid,))["status"] == "aktiv"
    assert client.get(f"/auftrag/{aid}").status_code == 200
    client.post(f"/auftrag/{aid}/loeschen")
    assert _q(app, "SELECT 1 FROM auftrag WHERE id=?", (aid,)) is None


# ---------------------------------------------------------------------
#  Fraktion
# ---------------------------------------------------------------------
def test_fraktion_flow(app_client):
    app, client = app_client
    sid, wid, _, _ = _sektor_mit_welt(app, client)
    assert client.get(f"/welt/{wid}/fraktion/neu").status_code == 200
    # Eindeutiger Name -> keine Kollision mit auto-generierten Fraktionsnamen.
    r = client.post(f"/welt/{wid}/fraktion/neu", data={
        "name": "ZZZ Sondertruppe", "typ": "Konzern", "reichweite": "interstellar", "einfluss": "9"})
    assert r.status_code == 302
    fr = _q(app, "SELECT * FROM fraktion WHERE name='ZZZ Sondertruppe'")
    assert fr and fr["reichweite"] == "interstellar" and fr["einfluss"] == 9
    fid = fr["id"]
    assert client.get(f"/fraktion/{fid}").status_code == 200
    client.post(f"/fraktion/{fid}", data={"name": "ZZZ Umbenannt", "reichweite": "lokal", "einfluss": "5"})
    assert _q(app, "SELECT name FROM fraktion WHERE id=?", (fid,))["name"] == "ZZZ Umbenannt"
    client.post(f"/fraktion/{fid}/loeschen")
    assert _q(app, "SELECT 1 FROM fraktion WHERE id=?", (fid,)) is None


# ---------------------------------------------------------------------
#  Welt-/Sektor-Editor
# ---------------------------------------------------------------------
def test_welt_bearbeiten_recompute(app_client):
    app, client = app_client
    _, wid, _, _ = _sektor_mit_welt(app, client)
    assert client.get(f"/welt/{wid}/bearbeiten").status_code == 200
    with app.app_context():
        db = dbmod.get_db()
        alt = dict(db.execute("SELECT * FROM welt WHERE id=?", (wid,)).fetchone())
    daten = {k: alt[k] for k in ("groesse", "atmosphaere", "hydrographie",
             "bevoelkerung", "regierung", "gesetz", "techlevel")}
    daten.update({"name": "Editwelt", "raumhafen": alt["raumhafen"] or "C",
                  "atmosphaere": 12, "reisezone": "rot", "temperatur": "Heiß"})
    r = client.post(f"/welt/{wid}/bearbeiten", data=daten)
    assert r.status_code == 302
    with app.app_context():
        db = dbmod.get_db()
        neu = db.execute("SELECT * FROM welt WHERE id=?", (wid,)).fetchone()
        assert neu["name"] == "Editwelt" and neu["reisezone"] == "rot"
        assert neu["uwp"][2] == "C"            # Atmosphaere-Stelle = eHex(12) = 'C'


def test_welt_neuwuerfeln(app_client):
    app, client = app_client
    _, wid, hexc, _ = _sektor_mit_welt(app, client)
    with app.app_context():
        db = dbmod.get_db()
        alt = db.execute("SELECT seed FROM welt WHERE id=?", (wid,)).fetchone()["seed"]
    assert client.post(f"/welt/{wid}/neuwuerfeln").status_code == 302
    with app.app_context():
        db = dbmod.get_db()
        row = db.execute("SELECT seed, hex FROM welt WHERE id=?", (wid,)).fetchone()
        assert row["seed"] != alt and row["hex"] == hexc


def test_welt_in_leeren_hex(app_client):
    app, client = app_client
    sid, _, _, leer = _sektor_mit_welt(app, client)
    assert client.get(f"/sektor/{sid}/subsektor/0/welt/neu?hex={leer}").status_code == 200
    r = client.post(f"/sektor/{sid}/subsektor/0/welt/neu?hex={leer}", data={})
    assert r.status_code == 302 and "/bearbeiten" in r.headers["Location"]
    with app.app_context():
        db = dbmod.get_db()
        assert db.execute("SELECT 1 FROM welt WHERE sektor_id=? AND hex=?", (sid, leer)).fetchone()


def test_welt_neu_ungueltiger_hex_404(app_client):
    app, client = app_client
    sid, _, _, _ = _sektor_mit_welt(app, client)
    # Hex aus Subsektor 1 (Spalte 9+) passt nicht zu ss_index 0
    assert client.get(f"/sektor/{sid}/subsektor/0/welt/neu?hex=0911").status_code == 404


def test_welt_loeschen(app_client):
    app, client = app_client
    sid, wid, _, _ = _sektor_mit_welt(app, client)
    assert client.post(f"/welt/{wid}/loeschen").status_code == 302
    with app.app_context():
        db = dbmod.get_db()
        assert db.execute("SELECT 1 FROM welt WHERE id=?", (wid,)).fetchone() is None


def test_subsektor_benennen(app_client):
    app, client = app_client
    sid, _, _, _ = _sektor_mit_welt(app, client)
    assert client.post(f"/sektor/{sid}/subsektor/0/benennen", data={"name": "Kernregion"}).status_code == 302
    with app.app_context():
        db = dbmod.get_db()
        assert db.execute("SELECT name FROM subsektor WHERE sektor_id=? AND idx=0",
                          (sid,)).fetchone()["name"] == "Kernregion"


def test_subsektor_view_enthaelt_welt_ids(app_client):
    app, client = app_client
    sid, wid, _, _ = _sektor_mit_welt(app, client)
    r = client.get(f"/sektor/{sid}/subsektor/0")
    assert r.status_code == 200
    assert b"WELT_NEU_BASE" in r.data and f'"id": {wid}'.encode() in r.data
