"""
Auftrags-Blueprint: Patron-Aufhaenger erzeugen, bearbeiten, Statuswechsel, loeschen.
Routen ohne url_prefix -> /welt/<id>/auftrag/neu, /auftrag/<id>, /auftrag/<id>/status.
"""
from __future__ import annotations
import random
import string

from flask import (Blueprint, abort, redirect, render_template, request, url_for)

from .. import db as dbmod
from .. import persist
from ..generators.auftrag import (erzeuge_auftrag, auftrag_zu_row, ZIEL_KAT)

bp = Blueprint("auftrag", __name__)
_STATUS = ("offen", "aktiv", "abgeschlossen", "gescheitert")


def _zufallsseed(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _opt_int(v):
    try:
        return int(v) if v not in (None, "", "0") else None
    except (TypeError, ValueError):
        return None


def _render(ctx, auftrag, *, modus, action, nscs, fraktionen):
    return render_template(
        "auftrag_form.html",
        modus=modus, action=action, auftrag=auftrag, kontext=ctx,
        nscs=nscs, fraktionen=fraktionen, ZIEL_KAT=ZIEL_KAT, STATUS=_STATUS,
        home_url=url_for("main.index"),
        zurueck_url=url_for("sektor.subsektor_ansicht",
                            sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0),
    )


# =====================================================================
#  Neu
# =====================================================================
@bp.route("/welt/<int:welt_id>/auftrag/neu", methods=["GET", "POST"])
def auftrag_neu(welt_id: int):
    db = dbmod.get_db()
    ctx = persist.welt_kontext(db, welt_id)
    if not ctx:
        abort(404)
    nscs = persist.welt_nscs(db, welt_id)
    fraktionen = persist.sektor_fraktionen(db, ctx["sektor_id"])

    if request.method == "POST" and request.form.get("aktion") == "speichern":
        row = {
            "titel": (request.form.get("titel") or "Auftrag").strip() or "Auftrag",
            "typ": request.form.get("typ") or None,
            "belohnung": (request.form.get("belohnung") or "").strip() or None,
            "komplikation": (request.form.get("komplikation") or "").strip() or None,
            "wendung": (request.form.get("wendung") or "").strip() or None,
            "notizen": (request.form.get("notizen") or "").strip() or None,
            "status": request.form.get("status") if request.form.get("status") in _STATUS else "offen",
            "kampagne_id": ctx["kampagne_id"],
            "welt_id": welt_id,
            "patron_nsc_id": _opt_int(request.form.get("patron_nsc_id")),
            "fraktion_id": _opt_int(request.form.get("fraktion_id")),
        }
        persist.speichere_auftrag(db, row)
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))

    # GET oder "Würfeln": frischen Aufhaenger generieren (noch nicht gespeichert)
    seed = ((request.form.get("seed") or "").strip() or f"{welt_id}|auftrag|{_zufallsseed(4)}"
            if request.method == "POST" else f"{welt_id}|auftrag|{_zufallsseed(4)}")
    a = erzeuge_auftrag(seed)
    auftrag = {
        "titel": a["titel"], "typ": a["typ"], "belohnung": a["belohnung"],
        "komplikation": a["komplikation"], "wendung": a["wendung"],
        "notizen": f"Auftraggeber: {a['auftraggeber']}\n{a['beschreibung']}",
        "status": "offen", "patron_nsc_id": None, "fraktion_id": None,
    }
    return _render(ctx, auftrag, modus="neu",
                   action=url_for("auftrag.auftrag_neu", welt_id=welt_id),
                   nscs=nscs, fraktionen=fraktionen)


# =====================================================================
#  Bearbeiten
# =====================================================================
@bp.route("/auftrag/<int:auftrag_id>", methods=["GET", "POST"])
def auftrag_bearbeiten(auftrag_id: int):
    db = dbmod.get_db()
    auf = persist.lade_auftrag(db, auftrag_id)
    if not auf:
        abort(404)
    ctx = persist.welt_kontext(db, auf["welt_id"]) if auf["welt_id"] else None
    if not ctx:
        ctx = {"sektor_id": None, "ss_index": 0, "name": "—"}
    nscs = persist.welt_nscs(db, auf["welt_id"]) if auf["welt_id"] else []
    fraktionen = persist.sektor_fraktionen(db, ctx["sektor_id"]) if ctx["sektor_id"] else []

    if request.method == "POST":
        felder = {
            "titel": (request.form.get("titel") or auf["titel"]).strip(),
            "typ": request.form.get("typ") or None,
            "belohnung": (request.form.get("belohnung") or "").strip() or None,
            "komplikation": (request.form.get("komplikation") or "").strip() or None,
            "wendung": (request.form.get("wendung") or "").strip() or None,
            "notizen": (request.form.get("notizen") or "").strip() or None,
            "status": request.form.get("status") if request.form.get("status") in _STATUS else auf["status"],
            "patron_nsc_id": _opt_int(request.form.get("patron_nsc_id")),
            "fraktion_id": _opt_int(request.form.get("fraktion_id")),
        }
        persist.aktualisiere_auftrag(db, auftrag_id, felder)
        ziel = (url_for("sektor.subsektor_ansicht", sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0)
                if ctx["sektor_id"] else url_for("main.index"))
        return redirect(ziel)

    return _render(ctx, auf, modus="bearbeiten",
                   action=url_for("auftrag.auftrag_bearbeiten", auftrag_id=auftrag_id),
                   nscs=nscs, fraktionen=fraktionen)


# =====================================================================
#  Statuswechsel (z.B. direkt aus der Detailkarte)
# =====================================================================
@bp.post("/auftrag/<int:auftrag_id>/status")
def auftrag_status(auftrag_id: int):
    db = dbmod.get_db()
    welt_id = persist.welt_id_des_auftrags(db, auftrag_id)
    if welt_id is None and persist.lade_auftrag(db, auftrag_id) is None:
        abort(404)
    persist.setze_auftrag_status(db, auftrag_id, request.form.get("status", ""))
    ctx = persist.welt_kontext(db, welt_id) if welt_id else None
    if ctx:
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))
    return redirect(url_for("main.index"))


@bp.post("/auftrag/<int:auftrag_id>/loeschen")
def auftrag_loeschen(auftrag_id: int):
    db = dbmod.get_db()
    welt_id = persist.welt_id_des_auftrags(db, auftrag_id)
    if welt_id is None and persist.lade_auftrag(db, auftrag_id) is None:
        abort(404)
    persist.loesche_auftrag(db, auftrag_id)
    ctx = persist.welt_kontext(db, welt_id) if welt_id else None
    if ctx:
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))
    return redirect(url_for("main.index"))
