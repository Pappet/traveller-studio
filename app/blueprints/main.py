from __future__ import annotations
from flask import Blueprint, render_template
from .. import db as dbmod
from .. import persist

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    sektoren = persist.liste_sektoren(dbmod.get_db())
    return render_template("index.html", sektoren=sektoren)
