"""
Traveller Studio  ·  Flask-App
==============================

Lokales Referee-Werkzeug. Generiert Sektoren regelbasiert (Mongoose
Traveller 2e / 13Mann), speichert sie in SQLite und rendert die Hexkarte
samt anklickbarer Detailkarte aus der Datenbank.

Start:  pip install flask  &&  python app.py   ->  http://127.0.0.1:5000
"""
from __future__ import annotations
import os
import random
import string

from flask import (Flask, request, redirect, url_for, render_template,
                   Response, abort)

import db as dbmod
import persist
from detailkarte import render_app


def _zufallsseed(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = os.path.join(app.root_path, "traveller.db")
    app.teardown_appcontext(dbmod.close_db)

    with app.app_context():
        dbmod.init_db_if_needed()

    # --- Uebersicht: Sektorenliste + Generierungsformular --------------
    @app.route("/")
    def index():
        sektoren = persist.liste_sektoren(dbmod.get_db())
        return render_template("index.html", sektoren=sektoren)

    # --- Sektor generieren ---------------------------------------------
    @app.post("/sektor/generieren")
    def sektor_generieren():
        name = (request.form.get("name") or "Unbenannt").strip() or "Unbenannt"
        seed = (request.form.get("seed") or "").strip() or _zufallsseed()
        dichte = request.form.get("dichte") or "normal"
        if dichte not in ("normal", "dicht", "duenn", "rift"):
            dichte = "normal"
        sektor_id = persist.speichere_sektor(dbmod.get_db(), seed, name, dichte)
        return redirect(url_for("subsektor_ansicht", sektor_id=sektor_id, ss_index=0))

    # --- Subsektor-Ansicht (Hexkarte + Detailkarte aus DB) -------------
    @app.route("/sektor/<int:sektor_id>/subsektor/<int:ss_index>")
    def subsektor_ansicht(sektor_id: int, ss_index: int):
        db = dbmod.get_db()
        sektor = persist.lade_sektor(db, sektor_id)
        if not sektor or not (0 <= ss_index <= 15):
            abort(404)
        welten = persist.lade_subsektor_welten(db, sektor_id, ss_index)
        links = persist.baue_links(db, welten)
        routen = persist.lade_routen(db, sektor_id)
        nav = persist.baue_nav(sektor_id, ss_index,
                               persist.subsektoren_mit_welten(db, sektor_id))
        return render_app(
            welten, ss_index,
            sektor_name=sektor["name"].upper(),
            links=links, routen=routen, nav_html=nav,
            home_url=url_for("index"),
            export_url=url_for("export_uwp", sektor_id=sektor_id, ss_index=ss_index),
        )

    # --- UWP-Export eines Subsektors -----------------------------------
    @app.route("/sektor/<int:sektor_id>/subsektor/<int:ss_index>/export.txt")
    def export_uwp(sektor_id: int, ss_index: int):
        db = dbmod.get_db()
        if not persist.lade_sektor(db, sektor_id):
            abort(404)
        txt = persist.export_uwp(db, sektor_id, ss_index)
        return Response(txt, mimetype="text/plain; charset=utf-8")

    # --- Sektor loeschen (kaskadiert) ----------------------------------
    @app.post("/sektor/<int:sektor_id>/loeschen")
    def sektor_loeschen(sektor_id: int):
        db = dbmod.get_db()
        db.execute("DELETE FROM sektor WHERE id=?", (sektor_id,))
        db.commit()
        return redirect(url_for("index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
