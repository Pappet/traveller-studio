"""
Smoke-Tests fuer die App-Factory.

Decken die vier Kern-Routen ab (Uebersicht, Generieren, Subsektor-Ansicht,
UWP-Export) sowie 404-Verhalten. Nutzt die TestingConfig mit einer
frischen Wegwerf-DB pro Test (tmp_path).
"""
from __future__ import annotations
import pytest

from app import create_app
from app.config import TestingConfig


@pytest.fixture
def client(tmp_path):
    # Frische, isolierte DB pro Test -- vor create_app() setzen, da die
    # Factory das Schema beim Start anlegt.
    TestingConfig.DB_PATH = str(tmp_path / "test.db")
    app = create_app("testing")
    with app.test_client() as c:
        yield c


def test_index(client):
    assert client.get("/").status_code == 200


def test_generieren_redirect(client):
    resp = client.post("/sektor/generieren", data={"name": "Test", "dichte": "normal"})
    assert resp.status_code == 302
    assert "/sektor/1/subsektor/0" in resp.headers["Location"]


def test_subsektor_ansicht(client):
    client.post("/sektor/generieren", data={"name": "Test"})
    assert client.get("/sektor/1/subsektor/0").status_code == 200


def test_export_uwp(client):
    client.post("/sektor/generieren", data={"name": "Test"})
    resp = client.get("/sektor/1/subsektor/0/export.txt")
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"


def test_unbekannter_sektor_404(client):
    assert client.get("/sektor/999/subsektor/0").status_code == 404


def test_ungueltiger_ss_index_404(client):
    client.post("/sektor/generieren", data={"name": "Test"})
    assert client.get("/sektor/1/subsektor/99").status_code == 404
