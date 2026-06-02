"""
Integrationstests fuer Phase C: NSC-Orte (Herkunft/Aufenthalt via
verknuepfung-Graph), Fraktions-Picker-Struktur, Hexkarte-Gruppierung.
Frische Wegwerf-DB pro Test.
"""
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


@pytest.fixture
def client(tmp_path):
    TestingConfig.DB_PATH = str(tmp_path / "test.db")
    app = create_app("testing")
    with app.test_client() as c:
        yield app, c


def _kampagne_mit_sektor(app):
    """(kampagne_id, welt_id_a, welt_id_b) — zwei bewohnte Welten."""
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    persist.speichere_sektor(db, "ORTE-SEED", "S", dichte="dicht", kampagne_id=kid)
    welten = db.execute(
        "SELECT id FROM welt WHERE sektor_id IN (SELECT id FROM sektor WHERE kampagne_id=?) "
        "ORDER BY id LIMIT 2", (kid,)).fetchall()
    return kid, welten[0]["id"], welten[1]["id"]


def test_nsc_orte_graph(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    from app.generators.nsc import erzeuge_nsc
    nid = persist.speichere_nsc(db, kid, None, erzeuge_nsc("S"))
    persist.setze_nsc_ort(db, nid, welt_id=42, relation="stammt_von")
    orte = persist.nsc_orte(db, nid)
    assert {"welt_id": 42, "relation": "stammt_von"} in orte
    treffer = persist.nscs_an_welt(db, 42)
    assert any(t["id"] == nid and t["relation"] == "stammt_von" for t in treffer)


def test_nscs_an_welt_aufenthalt_und_herkunft(app_ctx):
    app = app_ctx
    kid, wa, wb = _kampagne_mit_sektor(app)
    db = dbmod.get_db()
    from app.generators.nsc import erzeuge_nsc
    nid = persist.speichere_nsc(db, kid, wa, erzeuge_nsc("S"))   # Aufenthalt = wa
    persist.setze_nsc_ort(db, nid, welt_id=wb, relation="stammt_von")
    rel_a = {t["relation"] for t in persist.nscs_an_welt(db, wa) if t["id"] == nid}
    rel_b = {t["relation"] for t in persist.nscs_an_welt(db, wb) if t["id"] == nid}
    assert "befindet_sich" in rel_a
    assert "stammt_von" in rel_b


def test_nsc_orte_speichern_via_form(client):
    app, c = client
    c.post("/kampagne/neu", data={"name": "K"})
    with app.app_context():
        db = dbmod.get_db()
        kid = db.execute("SELECT id FROM kampagne").fetchone()["id"]
    c.post("/sektor/generieren", data={"name": "S", "seed": "FORM-SEED",
                                       "dichte": "dicht", "kampagne_id": str(kid)})
    with app.app_context():
        db = dbmod.get_db()
        welten = db.execute("SELECT id FROM welt ORDER BY id LIMIT 2").fetchall()
        wa, wb = welten[0]["id"], welten[1]["id"]
    # NSC standalone anlegen
    c.post(f"/kampagne/{kid}/nsc/neu", data={"aktion": "speichern", "name": "Wanderer"})
    with app.app_context():
        nid = dbmod.get_db().execute("SELECT id FROM nsc").fetchone()["id"]
    # Orte setzen: Aufenthalt = wa, Herkunft = wb
    c.post(f"/nsc/{nid}", data={"name": "Wanderer", "status": "lebendig",
                                "aufenthalt_welt_id": str(wa), "herkunft_welt_id": str(wb)})
    with app.app_context():
        db = dbmod.get_db()
        assert db.execute("SELECT aufenthalt_welt_id FROM nsc WHERE id=?",
                          (nid,)).fetchone()["aufenthalt_welt_id"] == wa
        orte = persist.nsc_orte(db, nid)
    assert {"welt_id": wb, "relation": "stammt_von"} in orte


def test_fraktionen_struktur(app_ctx):
    app = app_ctx
    kid, wa, wb = _kampagne_mit_sektor(app)
    db = dbmod.get_db()
    struktur = persist.fraktionen_struktur(db, kid)
    assert struktur, "Sektor sollte Fraktionen liefern"
    # nur Welten mit Fraktionen, jede Fraktion hat id/name
    for ss in struktur:
        assert "ss_index" in ss and isinstance(ss["welten"], list)
        for wlt in ss["welten"]:
            assert wlt["fraktionen"], "Welt ohne Fraktion darf nicht erscheinen"
            assert all("id" in f and "name" in f for f in wlt["fraktionen"])


def test_welten_struktur(app_ctx):
    app = app_ctx
    kid, wa, wb = _kampagne_mit_sektor(app)
    db = dbmod.get_db()
    struktur = persist.welten_struktur(db, kid)
    alle = [wlt["welt_id"] for ss in struktur for wlt in ss["welten"]]
    assert wa in alle and wb in alle


def test_baue_links_gruppiert_nach_ort(app_ctx):
    app = app_ctx
    kid, wa, wb = _kampagne_mit_sektor(app)
    db = dbmod.get_db()
    from app.generators.nsc import erzeuge_nsc
    nid = persist.speichere_nsc(db, kid, wa, erzeuge_nsc("S"))
    persist.setze_nsc_ort(db, nid, welt_id=wb, relation="stammt_von")
    welten = [persist.lade_welt(db, wa), persist.lade_welt(db, wb)]
    links = persist.baue_links(db, welten)
    hex_a, hex_b = welten[0]["hex"], welten[1]["hex"]
    assert any(n["id"] == nid for n in links[hex_a]["nscs_nach_ort"]["befindet_sich"])
    assert any(n["id"] == nid for n in links[hex_b]["nscs_nach_ort"]["stammt_von"])
