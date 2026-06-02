"""
Fraktions-Blueprint: bearbeiten, manuell anlegen, loeschen.
Routen ohne url_prefix -> /fraktion/<id>, /welt/<id>/fraktion/neu.
"""
from __future__ import annotations

from flask import (Blueprint, abort, redirect, render_template, request, url_for)

from .. import db as dbmod
from .. import persist
from ..generators.faktionen import _staerke

bp = Blueprint("fraktion", __name__)
_REICHWEITE = ("lokal", "interstellar")


def _opt_int(v, lo=None, hi=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _render(ctx, fraktion, *, modus, action, mitglieder):
    staerke = _staerke(fraktion["einfluss"])[0] if fraktion.get("einfluss") is not None else None
    return render_template(
        "fraktion_form.html",
        modus=modus, action=action, fraktion=fraktion, kontext=ctx,
        mitglieder=mitglieder, REICHWEITE=_REICHWEITE, staerke=staerke,
        home_url=url_for("main.index"),
        zurueck_url=url_for("sektor.subsektor_ansicht",
                            sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0),
    )


def _felder(form) -> dict:
    return {
        "name": (form.get("name") or "Unbenannte Fraktion").strip() or "Unbenannte Fraktion",
        "typ": (form.get("typ") or "").strip() or None,
        "reichweite": form.get("reichweite") if form.get("reichweite") in _REICHWEITE else "lokal",
        "einfluss": _opt_int(form.get("einfluss"), 1, 12),
        "ziele": (form.get("ziele") or "").strip() or None,
        "notizen": (form.get("notizen") or "").strip() or None,
    }


# =====================================================================
#  Neu (an einer Heimatwelt)
# =====================================================================
@bp.route("/welt/<int:welt_id>/fraktion/neu", methods=["GET", "POST"])
def fraktion_neu(welt_id: int):
    db = dbmod.get_db()
    ctx = persist.welt_kontext(db, welt_id)
    if not ctx:
        abort(404)
    if request.method == "POST":
        persist.speichere_fraktion(db, ctx["kampagne_id"], welt_id, _felder(request.form))
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))
    leer = {"name": "", "typ": "", "reichweite": "lokal", "einfluss": None,
            "ziele": "", "notizen": ""}
    return _render(ctx, leer, modus="neu",
                   action=url_for("fraktion.fraktion_neu", welt_id=welt_id), mitglieder=[])


# =====================================================================
#  Bearbeiten
# =====================================================================
@bp.route("/fraktion/<int:fraktion_id>", methods=["GET", "POST"])
def fraktion_bearbeiten(fraktion_id: int):
    db = dbmod.get_db()
    fr = persist.lade_fraktion(db, fraktion_id)
    if not fr:
        abort(404)
    ctx = persist.welt_kontext(db, fr["heimatwelt_id"]) if fr["heimatwelt_id"] else None
    if not ctx:
        ctx = {"sektor_id": None, "ss_index": 0, "name": "—"}

    if request.method == "POST":
        persist.aktualisiere_fraktion(db, fraktion_id, _felder(request.form))
        ziel = (url_for("sektor.subsektor_ansicht", sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0)
                if ctx["sektor_id"] else url_for("main.index"))
        return redirect(ziel)

    return _render(ctx, fr, modus="bearbeiten",
                   action=url_for("fraktion.fraktion_bearbeiten", fraktion_id=fraktion_id),
                   mitglieder=persist.fraktion_mitglieder(db, fraktion_id))


@bp.post("/fraktion/<int:fraktion_id>/loeschen")
def fraktion_loeschen(fraktion_id: int):
    db = dbmod.get_db()
    fr = persist.lade_fraktion(db, fraktion_id)
    if not fr:
        abort(404)
    ctx = persist.welt_kontext(db, fr["heimatwelt_id"]) if fr["heimatwelt_id"] else None
    persist.loesche_fraktion(db, fraktion_id)
    if ctx:
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))
    return redirect(url_for("main.index"))
