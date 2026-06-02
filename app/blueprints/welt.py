"""
Welt-/Sektor-Editor-Blueprint: Welt bearbeiten, neu wuerfeln, loeschen,
in leeren Hex setzen; Subsektor benennen.
Routen ohne url_prefix -> /welt/<id>/bearbeiten, /welt/<id>/neuwuerfeln, ...
"""
from __future__ import annotations

from flask import (Blueprint, abort, redirect, render_template, request, url_for)

from .. import db as dbmod
from .. import persist

bp = Blueprint("welt", __name__)

RAUMHAEFEN = ("A", "B", "C", "D", "E", "X")
TEMPERATUREN = ("Gefroren", "Kalt", "Gemäßigt", "Heiß", "Glühend")
ZONEN = ("gruen", "amber", "rot")
KOMPONENTEN = persist._WELT_KOMPONENTEN  # groesse..techlevel


def _ss_zu_index(hexcode: str) -> int:
    """Globaler Hex 'CCRR' -> Subsektor-Index 0..15 (4x4-Raster, 8x10 je Subsektor)."""
    spalte, zeile = int(hexcode[:2]), int(hexcode[2:])
    return ((zeile - 1) // 10) * 4 + ((spalte - 1) // 8)


# =====================================================================
#  Welt bearbeiten
# =====================================================================
@bp.route("/welt/<int:welt_id>/bearbeiten", methods=["GET", "POST"])
def welt_bearbeiten(welt_id: int):
    db = dbmod.get_db()
    welt = persist.lade_welt(db, welt_id)
    if not welt:
        abort(404)
    ctx = persist.welt_kontext(db, welt_id)

    if request.method == "POST":
        felder = {k: request.form.get(k) for k in KOMPONENTEN}
        felder["name"] = (request.form.get("name") or welt["name"]).strip() or welt["name"]
        felder["raumhafen"] = request.form.get("raumhafen") if request.form.get("raumhafen") in RAUMHAEFEN else welt["raumhafen"]
        felder["reisezone"] = request.form.get("reisezone") if request.form.get("reisezone") in ZONEN else welt["reisezone"]
        felder["temperatur"] = request.form.get("temperatur") if request.form.get("temperatur") in TEMPERATUREN else welt.get("temperatur")
        felder["zugehoerigkeit"] = (request.form.get("zugehoerigkeit") or "").strip() or None
        felder["gasriesen"] = "1" if request.form.get("gasriesen") else "0"
        felder["notizen"] = (request.form.get("notizen") or "").strip() or None
        persist.aktualisiere_welt(db, welt_id, felder)
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))

    return render_template(
        "welt_form.html", welt=welt, kontext=ctx,
        RAUMHAEFEN=RAUMHAEFEN, TEMPERATUREN=TEMPERATUREN, ZONEN=ZONEN, KOMPONENTEN=KOMPONENTEN,
        action=url_for("welt.welt_bearbeiten", welt_id=welt_id),
        home_url=url_for("main.index"),
        zurueck_url=url_for("sektor.subsektor_ansicht",
                            sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0),
    )


@bp.post("/welt/<int:welt_id>/neuwuerfeln")
def welt_neuwuerfeln(welt_id: int):
    db = dbmod.get_db()
    ctx = persist.welt_kontext(db, welt_id)
    if not ctx:
        abort(404)
    persist.neuwuerfeln_welt(db, welt_id)
    return redirect(url_for("sektor.subsektor_ansicht",
                            sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))


@bp.post("/welt/<int:welt_id>/loeschen")
def welt_loeschen(welt_id: int):
    db = dbmod.get_db()
    ctx = persist.welt_kontext(db, welt_id)
    if not ctx:
        abort(404)
    persist.loesche_welt(db, welt_id)
    return redirect(url_for("sektor.subsektor_ansicht",
                            sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))


# =====================================================================
#  Welt in leeren Hex setzen
# =====================================================================
@bp.route("/sektor/<int:sektor_id>/subsektor/<int:ss_index>/welt/neu", methods=["GET", "POST"])
def welt_neu(sektor_id: int, ss_index: int):
    db = dbmod.get_db()
    sektor = persist.lade_sektor(db, sektor_id)
    hexcode = (request.values.get("hex") or "").strip()
    gueltig = (sektor and 0 <= ss_index <= 15
               and len(hexcode) == 4 and hexcode.isdigit()
               and _ss_zu_index(hexcode) == ss_index)
    if not gueltig:
        abort(404)
    belegt = db.execute("SELECT id FROM welt WHERE sektor_id=? AND hex=?",
                        (sektor_id, hexcode)).fetchone()
    if belegt:
        # Schon belegt -> direkt zur Bearbeitung dieser Welt
        return redirect(url_for("welt.welt_bearbeiten", welt_id=belegt["id"]))

    if request.method == "POST":
        seed = (request.form.get("seed") or "").strip() or None
        neu_id = persist.erzeuge_welt_in_hex(db, sektor_id, ss_index, hexcode, seed)
        if not neu_id:
            abort(409)
        return redirect(url_for("welt.welt_bearbeiten", welt_id=neu_id))

    return render_template(
        "welt_neu.html", sektor=sektor, sektor_id=sektor_id, ss_index=ss_index,
        hexcode=hexcode, letter=chr(ord("A") + ss_index),
        home_url=url_for("main.index"),
        zurueck_url=url_for("sektor.subsektor_ansicht", sektor_id=sektor_id, ss_index=ss_index),
        action=url_for("welt.welt_neu", sektor_id=sektor_id, ss_index=ss_index, hex=hexcode),
    )


@bp.post("/sektor/<int:sektor_id>/subsektor/<int:ss_index>/benennen")
def subsektor_benennen(sektor_id: int, ss_index: int):
    db = dbmod.get_db()
    if not persist.lade_sektor(db, sektor_id) or not (0 <= ss_index <= 15):
        abort(404)
    persist.benenne_subsektor(db, sektor_id, ss_index, (request.form.get("name") or "").strip())
    return redirect(url_for("sektor.subsektor_ansicht", sektor_id=sektor_id, ss_index=ss_index))
