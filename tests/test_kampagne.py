"""
Integrationstests fuer die Kampagnen-Schicht (Phase A/B).

Kampagne als Wurzel: CRUD, Sektor-Generierung unter Kampagne, Routen
(Liste=Home, Dashboard), Generator-Signaturen, eigenstaendiges Anlegen.
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


# ---------------------------------------------------------------------
#  persist: Kampagne
# ---------------------------------------------------------------------
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


def test_speichere_sektor_unter_kampagne(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    sid = persist.speichere_sektor(db, "SEED", "Sektor1", dichte="dicht", kampagne_id=kid)
    assert db.execute("SELECT kampagne_id FROM sektor WHERE id=?", (sid,)).fetchone()["kampagne_id"] == kid
    fr = db.execute("SELECT kampagne_id FROM fraktion LIMIT 1").fetchone()
    assert fr is None or fr["kampagne_id"] == kid
    assert persist.liste_sektoren(db, kid)[0]["id"] == sid


# ---------------------------------------------------------------------
#  Routen: Liste (Home), Dashboard, Generierung unter Kampagne
# ---------------------------------------------------------------------
def test_kampagne_routen(client):
    app, c = client
    assert c.get("/").status_code == 200
    r = c.post("/kampagne/neu", data={"name": "Reft"})
    assert r.status_code == 302
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    assert c.get(f"/kampagne/{kid}").status_code == 200
    assert c.post(f"/kampagne/{kid}/loeschen").status_code == 302


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


# ---------------------------------------------------------------------
#  Phase B: Listen + Standalone-Anlegen
# ---------------------------------------------------------------------
def test_listen_pro_kampagne(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    from app.generators.nsc import erzeuge_nsc
    persist.speichere_nsc(db, kid, None, erzeuge_nsc("S"))
    assert len(persist.liste_nscs(db, kid)) == 1
    assert persist.liste_fraktionen(db, kid) == []
    assert persist.liste_auftraege(db, kid) == []


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


def test_fraktionsnamen_eindeutig_pro_welt(app_ctx):
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(db, "K")
    persist.speichere_sektor(db, "DUP-SEED", "S", dichte="dicht", kampagne_id=kid)
    rows = db.execute("SELECT heimatwelt_id, name FROM fraktion").fetchall()
    pro_welt: dict = {}
    for r in rows:
        pro_welt.setdefault(r["heimatwelt_id"], []).append(r["name"])
    for namen in pro_welt.values():
        assert len(namen) == len(set(namen)), f"doppelte Fraktionsnamen: {namen}"


def test_fraktion_auftrag_standalone(client):
    app, c = client
    c.post("/kampagne/neu", data={"name": "K"})
    with app.app_context():
        kid = dbmod.get_db().execute("SELECT id FROM kampagne").fetchone()["id"]
    assert c.get(f"/kampagne/{kid}/fraktion/neu").status_code == 200
    assert c.post(f"/kampagne/{kid}/fraktion/neu",
                  data={"name": "Konzern X", "reichweite": "interstellar"}).status_code == 302
    assert c.get(f"/kampagne/{kid}/auftrag/neu").status_code == 200
    assert c.post(f"/kampagne/{kid}/auftrag/neu",
                  data={"aktion": "speichern", "titel": "Job", "status": "offen"}).status_code == 302
    with app.app_context():
        db = dbmod.get_db()
        assert db.execute("SELECT kampagne_id FROM fraktion").fetchone()["kampagne_id"] == kid
        a = db.execute("SELECT kampagne_id, welt_id FROM auftrag").fetchone()
        assert a["kampagne_id"] == kid and a["welt_id"] is None
