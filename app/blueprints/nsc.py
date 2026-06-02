"""
NSC-Blueprint: erzeugen, bearbeiten, loeschen, Fraktionen zuordnen.
Routen ohne url_prefix -> /welt/<id>/nsc/neu, /nsc/<id>, /nsc/<id>/loeschen.
"""
from __future__ import annotations
import random
import string

from flask import (Blueprint, abort, redirect, render_template, request, url_for)

from .. import db as dbmod
from .. import persist
from ..generators.nsc import erzeuge_nsc, profil_string, EIGENSCHAFTEN, ARCHETYPEN, ROLLEN

bp = Blueprint("nsc", __name__)


def _zufallsseed(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


# --- Formular <-> NSC-dict ------------------------------------------------
def _parse_eig(form) -> dict[str, int]:
    eig = {}
    for kuerzel, _ in EIGENSCHAFTEN:
        try:
            eig[kuerzel] = max(0, min(15, int(form.get(f"eig_{kuerzel}", 7))))
        except (TypeError, ValueError):
            eig[kuerzel] = 7
    return eig


def _parse_skills(text: str) -> dict[str, int]:
    """Eine Zeile je Skill: 'Pilot 2' oder 'Pilot: 2'."""
    skills: dict[str, int] = {}
    for zeile in (text or "").splitlines():
        zeile = zeile.strip().rstrip(":")
        if not zeile:
            continue
        teile = zeile.replace(":", " ").rsplit(None, 1)
        if len(teile) == 2 and teile[1].lstrip("-").isdigit():
            skills[teile[0].strip()] = max(0, int(teile[1]))   # Traveller-Skills sind >= 0
        else:
            skills[zeile] = 0
    return skills


def _parse_liste(text: str) -> list[str]:
    return [z.strip() for z in (text or "").replace(",", "\n").splitlines() if z.strip()]


def _nsc_aus_form(form) -> dict:
    """Rekonstruiert ein NSC-dict aus den Formularfeldern (fuer Re-Render + Speichern)."""
    eig = _parse_eig(form)
    return {
        "name": (form.get("name") or "Namenlos").strip() or "Namenlos",
        "archetyp": form.get("archetyp") or "",
        "rolle": form.get("rolle") if form.get("rolle") in ROLLEN else "Kontakt",
        "eigenschaften": eig,
        "profil": profil_string(eig),
        "skills": _parse_skills(form.get("skills", "")),
        "laufbahn": None,
        "ausruestung": _parse_liste(form.get("ausruestung", "")),
        "beschreibung": (form.get("beschreibung") or "").strip(),
        "notizen": (form.get("notizen") or "").strip(),
        "status": form.get("status") if form.get("status") in ("lebendig", "tot") else "lebendig",
        "seed": form.get("seed") or "",
        "wuerfe": {},
    }


def _fraktionen_aus_form(form, fraktionen: list[dict]) -> list[dict]:
    out = []
    for fr in fraktionen:
        if form.get(f"fr_{fr['id']}"):
            out.append({"fraktion_id": fr["id"],
                        "geheim": bool(form.get(f"geheim_{fr['id']}")),
                        "rolle": (form.get(f"rolle_{fr['id']}") or "").strip() or "Mitglied"})
    return out


def _zurueck_url(ctx) -> str:
    """Rücksprung-Ziel: Subsektor-Ansicht bei verortetem NSC, sonst Dashboard."""
    if ctx.get("sektor_id"):
        return url_for("sektor.subsektor_ansicht",
                       sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0)
    return url_for("kampagne.dashboard", kampagne_id=ctx["kampagne_id"])


def _render(welt_kontext, nsc, *, modus, action, fraktionen, nsc_fraktionen):
    return render_template(
        "nsc_form.html",
        modus=modus, action=action, nsc=nsc, kontext=welt_kontext,
        EIGENSCHAFTEN=EIGENSCHAFTEN, ARCHETYPEN=ARCHETYPEN, ROLLEN=ROLLEN,
        fraktionen=fraktionen, nsc_fraktionen=nsc_fraktionen,
        home_url=url_for("main.index"),
        zurueck_url=_zurueck_url(welt_kontext),
    )


# =====================================================================
#  Neu (kampagnenweit, Ort optional)
# =====================================================================
@bp.route("/kampagne/<int:kampagne_id>/nsc/neu", methods=["GET", "POST"])
def nsc_neu_kampagne(kampagne_id: int):
    db = dbmod.get_db()
    kamp = persist.lade_kampagne(db, kampagne_id)
    if not kamp:
        abort(404)
    ctx = {"sektor_id": None, "ss_index": 0, "name": kamp["name"], "hex": "—",
           "kampagne_id": kampagne_id}
    fraktionen = persist.liste_fraktionen(db, kampagne_id)

    if request.method == "POST" and request.form.get("aktion") == "speichern":
        nsc = _nsc_aus_form(request.form)
        nid = persist.speichere_nsc(db, kampagne_id, None, nsc)
        persist.aktualisiere_nsc(db, nid, {"status": nsc["status"], "notizen": nsc["notizen"]})
        persist.setze_nsc_fraktionen(db, nid, _fraktionen_aus_form(request.form, fraktionen))
        return redirect(url_for("kampagne.dashboard", kampagne_id=kampagne_id))

    if request.method == "POST":           # aktion == "generieren"
        archetyp = request.form.get("archetyp") or None
        rolle = request.form.get("rolle") or "Kontakt"
        seed = (request.form.get("seed") or "").strip() or _zufallsseed()
    else:
        archetyp, rolle, seed = None, "Kontakt", f"k{kampagne_id}|nsc|{_zufallsseed(4)}"
    nsc = erzeuge_nsc(seed, archetyp=archetyp, rolle=rolle)
    nsc["notizen"] = ""
    nsc["status"] = "lebendig"
    return _render(ctx, nsc, modus="neu",
                   action=url_for("nsc.nsc_neu_kampagne", kampagne_id=kampagne_id),
                   fraktionen=fraktionen, nsc_fraktionen={})


# =====================================================================
#  Neu (an einer Welt)
# =====================================================================
@bp.route("/welt/<int:welt_id>/nsc/neu", methods=["GET", "POST"])
def nsc_neu(welt_id: int):
    db = dbmod.get_db()
    ctx = persist.welt_kontext(db, welt_id)
    if not ctx:
        abort(404)
    fraktionen = persist.sektor_fraktionen(db, ctx["sektor_id"])

    if request.method == "POST" and request.form.get("aktion") == "speichern":
        nsc = _nsc_aus_form(request.form)
        nid = persist.speichere_nsc(db, ctx["kampagne_id"], welt_id, nsc)
        persist.aktualisiere_nsc(db, nid, {"status": nsc["status"], "notizen": nsc["notizen"]})
        persist.setze_nsc_fraktionen(db, nid, _fraktionen_aus_form(request.form, fraktionen))
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))

    # GET oder "Würfeln": neuen NSC generieren (Vorschlag, noch nicht gespeichert)
    if request.method == "POST":           # aktion == "generieren"
        archetyp = request.form.get("archetyp") or None
        rolle = request.form.get("rolle") or "Kontakt"
        seed = (request.form.get("seed") or "").strip() or _zufallsseed()
    else:
        archetyp, rolle, seed = None, "Kontakt", f"{welt_id}|nsc|{_zufallsseed(4)}"
    nsc = erzeuge_nsc(seed, archetyp=archetyp, rolle=rolle)
    nsc["notizen"] = ""
    nsc["status"] = "lebendig"

    return _render(ctx, nsc, modus="neu",
                   action=url_for("nsc.nsc_neu", welt_id=welt_id),
                   fraktionen=fraktionen, nsc_fraktionen={})


# =====================================================================
#  Bearbeiten
# =====================================================================
@bp.route("/nsc/<int:nsc_id>", methods=["GET", "POST"])
def nsc_bearbeiten(nsc_id: int):
    db = dbmod.get_db()
    nsc_row = persist.lade_nsc(db, nsc_id)
    if not nsc_row:
        abort(404)
    welt_id = nsc_row["aufenthalt_welt_id"]
    ctx = persist.welt_kontext(db, welt_id) if welt_id else None
    sektor_id = ctx["sektor_id"] if ctx else None
    fraktionen = persist.sektor_fraktionen(db, sektor_id) if sektor_id else []

    if request.method == "POST":
        felder = {
            "name": (request.form.get("name") or nsc_row["name"]).strip(),
            "rolle": request.form.get("rolle") if request.form.get("rolle") in ROLLEN else nsc_row["rolle"],
            "beschreibung": (request.form.get("beschreibung") or "").strip(),
            "notizen": (request.form.get("notizen") or "").strip(),
            "status": request.form.get("status") if request.form.get("status") in ("lebendig", "tot") else "lebendig",
        }
        persist.aktualisiere_nsc(db, nsc_id, felder)
        persist.setze_nsc_fraktionen(db, nsc_id, _fraktionen_aus_form(request.form, fraktionen))
        ziel = _zurueck_url(ctx) if ctx else url_for("kampagne.dashboard", kampagne_id=nsc_row["kampagne_id"])
        return redirect(ziel)

    # Anzeige-dict aufbereiten
    nsc_row.setdefault("eigenschaften", {})
    nsc_row["profil"] = profil_string(nsc_row["eigenschaften"]) if nsc_row.get("eigenschaften") else ""
    nsc_row.setdefault("archetyp", "")
    if not ctx:
        # NSC ohne Welt -> Kampagnen-Kontext fuer das Template
        ctx = {"sektor_id": None, "ss_index": 0, "name": "—", "hex": "—",
               "kampagne_id": nsc_row["kampagne_id"]}
    return _render(ctx, nsc_row, modus="bearbeiten",
                   action=url_for("nsc.nsc_bearbeiten", nsc_id=nsc_id),
                   fraktionen=fraktionen,
                   nsc_fraktionen=persist.lade_nsc_fraktionen(db, nsc_id))


@bp.post("/nsc/<int:nsc_id>/loeschen")
def nsc_loeschen(nsc_id: int):
    db = dbmod.get_db()
    nsc_row = persist.lade_nsc(db, nsc_id)
    if not nsc_row:
        abort(404)
    ctx = persist.welt_kontext(db, nsc_row["aufenthalt_welt_id"]) if nsc_row["aufenthalt_welt_id"] else None
    kampagne_id = nsc_row["kampagne_id"]
    persist.loesche_nsc(db, nsc_id)
    if ctx:
        return redirect(url_for("sektor.subsektor_ansicht",
                                sektor_id=ctx["sektor_id"], ss_index=ctx["ss_index"] or 0))
    return redirect(url_for("kampagne.dashboard", kampagne_id=kampagne_id))
