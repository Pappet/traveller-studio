from __future__ import annotations
from flask import Blueprint, render_template
from .. import db as dbmod
from .. import persist

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    kampagnen = persist.liste_kampagnen(dbmod.get_db())
    return render_template("kampagne_liste.html", kampagnen=kampagnen)
