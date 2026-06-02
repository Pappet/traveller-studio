from __future__ import annotations
import random
import string

from flask import Blueprint, abort, redirect, render_template, request, url_for, Response

from .. import db as dbmod
from .. import persist
from ..rendering.hexmap import render_svg, _g

bp = Blueprint("sektor", __name__, url_prefix="/sektor")

_FELDER = [
    "name", "uwp", "raumhafen", "groesse", "atmosphaere", "hydrographie",
    "bevoelkerung", "regierung", "gesetz", "techlevel",
    "handelscodes", "basen", "reisezone", "gasriesen", "zugehoerigkeit",
    "temperatur", "raumhafen_details", "kultur",
]


def _zufallsseed(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _welt_dict(w) -> dict:
    d = {k: _g(w, k) for k in _FELDER}
    d["id"] = _g(w, "id")
    return d


@bp.post("/generieren")
def sektor_generieren():
    name = (request.form.get("name") or "Unbenannt").strip() or "Unbenannt"
    seed = (request.form.get("seed") or "").strip() or _zufallsseed()
    dichte = request.form.get("dichte") or "normal"
    if dichte not in ("normal", "dicht", "duenn", "rift"):
        dichte = "normal"
    sektor_id = persist.speichere_sektor(dbmod.get_db(), seed, name, dichte)
    return redirect(url_for("sektor.subsektor_ansicht", sektor_id=sektor_id, ss_index=0))


@bp.route("/<int:sektor_id>/subsektor/<int:ss_index>")
def subsektor_ansicht(sektor_id: int, ss_index: int):
    db = dbmod.get_db()
    sektor = persist.lade_sektor(db, sektor_id)
    if not sektor or not (0 <= ss_index <= 15):
        abort(404)
    welten = persist.lade_subsektor_welten(db, sektor_id, ss_index)
    links = persist.baue_links(db, welten)
    routen = persist.lade_routen(db, sektor_id)
    vorhanden = persist.subsektoren_mit_welten(db, sektor_id)

    svg = render_svg(welten, ss_index, routen=routen)
    letter = chr(ord("A") + ss_index)
    welten_data = {_g(w, "hex"): _welt_dict(w) for w in welten}

    return render_template(
        "sektor/subsektor.html",
        svg=svg,
        sektor_name=sektor["name"].upper(),
        sektor_id=sektor_id,
        letter=letter,
        ss_index=ss_index,
        ss_name=persist.subsektor_name(db, sektor_id, ss_index) or "",
        n=len(welten),
        n_amber=sum(1 for w in welten if _g(w, "reisezone") == "amber"),
        n_rot=sum(1 for w in welten if _g(w, "reisezone") == "rot"),
        welten_data=welten_data,
        links=links,
        vorhanden=vorhanden,
        home_url=url_for("main.index"),
        export_url=url_for("sektor.export_uwp", sektor_id=sektor_id, ss_index=ss_index),
        rename_url=url_for("welt.subsektor_benennen", sektor_id=sektor_id, ss_index=ss_index),
        welt_neu_base=url_for("welt.welt_neu", sektor_id=sektor_id, ss_index=ss_index),
    )


@bp.route("/<int:sektor_id>/subsektor/<int:ss_index>/export.txt")
def export_uwp(sektor_id: int, ss_index: int):
    db = dbmod.get_db()
    if not persist.lade_sektor(db, sektor_id):
        abort(404)
    txt = persist.export_uwp(db, sektor_id, ss_index)
    return Response(txt, mimetype="text/plain; charset=utf-8")


@bp.post("/<int:sektor_id>/loeschen")
def sektor_loeschen(sektor_id: int):
    db = dbmod.get_db()
    db.execute("DELETE FROM sektor WHERE id=?", (sektor_id,))
    db.commit()
    return redirect(url_for("main.index"))
