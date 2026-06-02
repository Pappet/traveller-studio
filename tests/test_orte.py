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
