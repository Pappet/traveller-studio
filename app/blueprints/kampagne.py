"""
Kampagne-Blueprint: Liste (Startseite via main.index), Dashboard, anlegen,
bearbeiten, loeschen. Die Kampagne ist die Wurzel — Sektoren/NSC/Fraktion/
Auftrag haengen darunter.
Routen: /kampagne/neu, /kampagne/<id>, /kampagne/<id>/bearbeiten, .../loeschen.
"""
from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, request, url_for

from .. import db as dbmod
from .. import persist

bp = Blueprint("kampagne", __name__)


@bp.post("/kampagne/neu")
def kampagne_neu():
    db = dbmod.get_db()
    kid = persist.erstelle_kampagne(
        db, (request.form.get("name") or "").strip(),
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


@bp.route("/kampagne/<int:kampagne_id>/bearbeiten", methods=["GET", "POST"])
def kampagne_bearbeiten(kampagne_id: int):
    db = dbmod.get_db()
    k = persist.lade_kampagne(db, kampagne_id)
    if not k:
        abort(404)
    if request.method == "POST":
        persist.aktualisiere_kampagne(db, kampagne_id, {
            "name": (request.form.get("name") or k["name"]).strip() or k["name"],
            "notizen": (request.form.get("notizen") or "").strip() or None,
        })
        return redirect(url_for("kampagne.dashboard", kampagne_id=kampagne_id))
    return render_template("kampagne_form.html", kampagne=k,
                           action=url_for("kampagne.kampagne_bearbeiten", kampagne_id=kampagne_id),
                           home_url=url_for("main.index"),
                           zurueck_url=url_for("kampagne.dashboard", kampagne_id=kampagne_id))


@bp.post("/kampagne/<int:kampagne_id>/loeschen")
def kampagne_loeschen(kampagne_id: int):
    db = dbmod.get_db()
    if not persist.lade_kampagne(db, kampagne_id):
        abort(404)
    persist.loesche_kampagne(db, kampagne_id)
    return redirect(url_for("main.index"))
