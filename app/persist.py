"""
Persistenz-Schicht
==================

Verbindet die (reinen, seedbaren) Generatoren mit der Datenbank:
  * speichere_sektor()  -- generiert einen ganzen Sektor und schreibt
                           Welten, Fraktionen und Routen in die Tabellen.
  * lade_*()            -- liest die gespeicherten Daten zurueck und
                           HYDRIERT die JSON-Spalten (Strings -> Python),
                           damit die Renderer (hexmap/Templates) sie direkt
                           verwenden koennen.

Die Renderer lesen Welt-Objekte ODER dicts; hier liefern wir dicts.
"""
from __future__ import annotations
import json
import sqlite3

from .generators.sektor import (erzeuge_sektor, erzeuge_welt, welt_zu_row,
                                 baue_uwp, berechne_handelscodes)
from .generators.faktionen import erzeuge_fraktionen, fraktion_zu_row, _staerke
from .generators.routen import gen_alle_routen
from .generators.nsc import nsc_zu_row

# JSON-Spalten der welt-Tabelle, die beim Laden geparst werden muessen
_JSON_COLS = ("handelscodes", "basen", "raumhafen_details", "kultur",
              "sternendaten", "wuerfe")


def _eindeutiger_fraktionsname(basis: str, heimat: str, gesehen: set[str]) -> str:
    """Macht einen Fraktionsnamen kampagnenweit eindeutig: bei Kollision wird die
    Heimatwelt angehaengt — 'Allianz fuer Arbeit (Koux)' — bei weiterer Kollision
    durchnummeriert."""
    if basis not in gesehen:
        return basis
    kand = f"{basis} ({heimat})"
    if kand not in gesehen:
        return kand
    i = 2
    while f"{basis} ({heimat} {i})" in gesehen:
        i += 1
    return f"{basis} ({heimat} {i})"


# =====================================================================
#  Schreiben: ganzen Sektor generieren und speichern
# =====================================================================
def speichere_sektor(db: sqlite3.Connection, seed: str, name: str,
                     dichte: str = "normal", zugehoerigkeit: str = "Im",
                     *, kampagne_id: int) -> int:
    cur = db.cursor()
    cur.execute("INSERT INTO sektor(kampagne_id, name, seed) VALUES(?, ?, ?)",
                (kampagne_id, name, seed))
    sektor_id = cur.lastrowid

    # 16 Subsektoren (A..P)
    ss_id: dict[int, int] = {}
    for i in range(16):
        cur.execute("INSERT INTO subsektor(sektor_id, idx) VALUES(?, ?)", (sektor_id, i))
        ss_id[i] = cur.lastrowid

    # Alle Welten generieren und schreiben; hex -> welt_id merken
    sektor_welten = erzeuge_sektor(seed, dichte=dichte, zugehoerigkeit=zugehoerigkeit)
    hex2id: dict[str, int] = {}
    for ss_index, welten in sektor_welten.items():
        for wlt in welten:
            row = welt_zu_row(wlt, sektor_id, ss_id[ss_index])
            spalten = ", ".join(row.keys())
            platzhalter = ", ".join("?" * len(row))
            cur.execute(f"INSERT INTO welt ({spalten}) VALUES ({platzhalter})",
                        list(row.values()))
            hex2id[wlt.hex] = cur.lastrowid

    # Fraktionen pro Welt -> fraktion-Tabelle (heimatwelt_id = diese Welt).
    # Namen kampagnenweit eindeutig: bei Kollision Heimatwelt anhaengen.
    gesehen_namen = {r["name"] for r in db.execute(
        "SELECT name FROM fraktion WHERE kampagne_id=?", (kampagne_id,)).fetchall()}
    for ss_index, welten in sektor_welten.items():
        for wlt in welten:
            for fr in erzeuge_fraktionen(wlt, seed):
                fr["name"] = _eindeutiger_fraktionsname(fr["name"], wlt.name, gesehen_namen)
                gesehen_namen.add(fr["name"])
                frow = fraktion_zu_row(fr, hex2id[wlt.hex], kampagne_id)
                spalten = ", ".join(frow.keys())
                platzhalter = ", ".join("?" * len(frow))
                cur.execute(f"INSERT INTO fraktion ({spalten}) VALUES ({platzhalter})",
                            list(frow.values()))

    # Routen je Subsektor (ungerichtet, a<b; auto=1 = generiert)
    for ss_index, welten in sektor_welten.items():
        for r in gen_alle_routen(welten):
            a_id, b_id = hex2id[r["a"]], hex2id[r["b"]]
            lo, hi = sorted((a_id, b_id))
            cur.execute(
                "INSERT OR IGNORE INTO route(welt_a_id, welt_b_id, typ, jump_distanz, auto) "
                "VALUES (?, ?, ?, ?, 1)",
                (lo, hi, r["typ"], r.get("jump")),
            )

    db.commit()
    return sektor_id


# =====================================================================
#  Lesen
# =====================================================================
def _hydrate(row: sqlite3.Row) -> dict:
    """welt-Zeile -> dict mit geparsten JSON-Spalten."""
    d = dict(row)
    for c in _JSON_COLS:
        if c in d:
            if d[c]:
                try:
                    d[c] = json.loads(d[c])
                except (ValueError, TypeError):
                    pass
            else:
                d[c] = [] if c in ("handelscodes", "basen") else None
    return d


def liste_sektoren(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    rows = db.execute("SELECT id, name, seed FROM sektor WHERE kampagne_id=? "
                      "ORDER BY erstellt_am DESC", (kampagne_id,)).fetchall()
    out = []
    for s in rows:
        welten = db.execute("SELECT COUNT(*) c FROM welt WHERE sektor_id=?",
                            (s["id"],)).fetchone()["c"]
        frak = db.execute(
            "SELECT COUNT(*) c FROM fraktion fr JOIN welt w ON fr.heimatwelt_id=w.id "
            "WHERE w.sektor_id=?", (s["id"],)).fetchone()["c"]
        out.append({"id": s["id"], "name": s["name"], "seed": s["seed"],
                    "welten": welten, "fraktionen": frak})
    return out


def lade_sektor(db: sqlite3.Connection, sektor_id: int) -> dict | None:
    r = db.execute("SELECT * FROM sektor WHERE id=?", (sektor_id,)).fetchone()
    return dict(r) if r else None


def lade_subsektor_welten(db: sqlite3.Connection, sektor_id: int, ss_index: int) -> list[dict]:
    rows = db.execute(
        "SELECT w.* FROM welt w JOIN subsektor s ON w.subsektor_id=s.id "
        "WHERE s.sektor_id=? AND s.idx=?", (sektor_id, ss_index)).fetchall()
    return [_hydrate(r) for r in rows]


def baue_links(db: sqlite3.Connection, welt_dicts: list[dict]) -> dict:
    """hex -> {nscs, nscs_nach_ort, auftraege, fraktionen} fuer die Detailkarte.

    NSCs werden nach Orts-Relation gruppiert (befindet_sich/stammt_von/wirkt_in/
    versteckt_auf). `nscs` bleibt als Alias der befindet_sich-Gruppe erhalten.
    """
    links: dict = {}
    for w in welt_dicts:
        wid, hexc = w["id"], w["hex"]
        eintrag: dict = {}

        gruppen: dict[str, list] = {}
        for t in nscs_an_welt(db, wid):
            geheim = db.execute(
                "SELECT 1 FROM nsc_fraktion WHERE nsc_id=? AND geheim=1 LIMIT 1",
                (t["id"],)).fetchone() is not None
            gruppen.setdefault(t["relation"], []).append(
                {"id": t["id"], "name": t["name"], "rolle": t["rolle"],
                 "status": t["status"], "geheim": geheim})
        if gruppen:
            eintrag["nscs_nach_ort"] = gruppen
            if gruppen.get("befindet_sich"):
                eintrag["nscs"] = gruppen["befindet_sich"]

        auf = db.execute(
            "SELECT id, titel, typ, status FROM auftrag WHERE welt_id=? ORDER BY id", (wid,)).fetchall()
        if auf:
            eintrag["auftraege"] = [dict(a) for a in auf]

        fra = db.execute(
            "SELECT id, name, typ, einfluss FROM fraktion WHERE heimatwelt_id=? ORDER BY id", (wid,)).fetchall()
        if fra:
            eintrag["fraktionen"] = [
                {"id": f["id"], "name": f["name"], "typ": f["typ"],
                 "staerke": _staerke(f["einfluss"])[0] if f["einfluss"] is not None else ""}
                for f in fra
            ]

        if eintrag:
            links[hexc] = eintrag
    return links


def lade_routen(db: sqlite3.Connection, sektor_id: int) -> list[dict]:
    """Routen des Sektors als hex-Paare (Renderer filtert auf den Subsektor)."""
    id2hex = {r["id"]: r["hex"] for r in db.execute(
        "SELECT id, hex FROM welt WHERE sektor_id=?", (sektor_id,)).fetchall()}
    rows = db.execute(
        "SELECT r.welt_a_id, r.welt_b_id, r.typ, r.jump_distanz FROM route r "
        "JOIN welt w ON r.welt_a_id=w.id WHERE w.sektor_id=?", (sektor_id,)).fetchall()
    out = []
    for r in rows:
        a, b = id2hex.get(r["welt_a_id"]), id2hex.get(r["welt_b_id"])
        if a and b:
            out.append({"a": a, "b": b, "typ": r["typ"], "jump": r["jump_distanz"]})
    return out


def subsektor_name(db: sqlite3.Connection, sektor_id: int, ss_index: int) -> str | None:
    r = db.execute("SELECT name FROM subsektor WHERE sektor_id=? AND idx=?",
                   (sektor_id, ss_index)).fetchone()
    return r["name"] if r else None


def subsektoren_mit_welten(db: sqlite3.Connection, sektor_id: int) -> set[int]:
    rows = db.execute(
        "SELECT DISTINCT s.idx FROM subsektor s JOIN welt w ON w.subsektor_id=s.id "
        "WHERE s.sektor_id=?", (sektor_id,)).fetchall()
    return {r["idx"] for r in rows}


# =====================================================================
#  UWP-Export (lesbares Subsektor-Listing; KEIN striktes .sec-Format)
# =====================================================================
def export_uwp(db: sqlite3.Connection, sektor_id: int, ss_index: int) -> str:
    welten = sorted(lade_subsektor_welten(db, sektor_id, ss_index), key=lambda w: w["hex"])
    sektor = lade_sektor(db, sektor_id)
    kopf = (f'# Sektor "{sektor["name"]}" — Subsektor {chr(65 + ss_index)}  (Seed {sektor["seed"]})\n'
            f'# Hex  Name               UWP         B  Z GG  Handelscodes\n')
    zeilen = []
    for w in welten:
        basen = "".join(b[0] for b in (w.get("basen") or []))
        codes = " ".join(w.get("handelscodes") or [])
        zone = {"amber": "A", "rot": "R"}.get(w.get("reisezone"), " ")
        gg = "G" if w.get("gasriesen") else " "
        zeilen.append(f'{w["hex"]}  {w["name"][:18]:<18} {w["uwp"]:<11} {basen:<2} {zone} {gg}  {codes}')
    return kopf + "\n".join(zeilen) + "\n"


# =====================================================================
#  Editier-Schicht (Prep-Werkzeuge)
#  -------------------------------------------------------------------
#  Gemeinsames Muster: kleine, fokussierte DB-Funktionen. SQL bleibt hier
#  (nicht in den Blueprints), Generatoren bleiben rein. Spalten werden gegen
#  Whitelists geschrieben (kein dynamisches SQL aus User-Schluesseln).
# =====================================================================
def _insert(db: sqlite3.Connection, tabelle: str, row: dict) -> int:
    spalten = ", ".join(row.keys())
    platzhalter = ", ".join("?" * len(row))
    cur = db.execute(f"INSERT INTO {tabelle} ({spalten}) VALUES ({platzhalter})",
                     list(row.values()))
    db.commit()
    return cur.lastrowid


def _update(db: sqlite3.Connection, tabelle: str, row_id: int,
            felder: dict, erlaubt: set[str]) -> None:
    setz = {k: v for k, v in felder.items() if k in erlaubt}
    if not setz:
        return
    zuweisung = ", ".join(f"{k}=?" for k in setz)
    db.execute(f"UPDATE {tabelle} SET {zuweisung} WHERE id=?",
               list(setz.values()) + [row_id])
    db.commit()


# ---------------------------------------------------------------------
#  Kampagne (Wurzel)
# ---------------------------------------------------------------------
_KAMPAGNE_EDIT = {"name", "notizen"}


def erstelle_kampagne(db: sqlite3.Connection, name: str, notizen: str | None = None) -> int:
    return _insert(db, "kampagne", {"name": name or "Unbenannte Kampagne",
                                    "notizen": notizen})


def lade_kampagne(db: sqlite3.Connection, kampagne_id: int) -> dict | None:
    r = db.execute("SELECT * FROM kampagne WHERE id=?", (kampagne_id,)).fetchone()
    return dict(r) if r else None


def liste_kampagnen(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT id, name, notizen FROM kampagne ORDER BY erstellt_am DESC").fetchall()
    out = []
    for k in rows:
        sek = db.execute("SELECT COUNT(*) c FROM sektor WHERE kampagne_id=?",
                         (k["id"],)).fetchone()["c"]
        nsc = db.execute("SELECT COUNT(*) c FROM nsc WHERE kampagne_id=?",
                         (k["id"],)).fetchone()["c"]
        out.append({"id": k["id"], "name": k["name"], "notizen": k["notizen"],
                    "sektoren": sek, "nscs": nsc})
    return out


def aktualisiere_kampagne(db: sqlite3.Connection, kampagne_id: int, felder: dict) -> None:
    _update(db, "kampagne", kampagne_id, felder, _KAMPAGNE_EDIT)


def loesche_kampagne(db: sqlite3.Connection, kampagne_id: int) -> None:
    db.execute("DELETE FROM kampagne WHERE id=?", (kampagne_id,))
    db.commit()


# ---------------------------------------------------------------------
#  Kampagnen-Listen (Dashboard)
# ---------------------------------------------------------------------
def liste_nscs(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT n.id, n.name, n.rolle, n.status, n.aufenthalt_welt_id, w.name AS ort "
        "FROM nsc n LEFT JOIN welt w ON n.aufenthalt_welt_id=w.id "
        "WHERE n.kampagne_id=? ORDER BY n.name", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]


def liste_fraktionen(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT fr.id, fr.name, fr.typ, fr.reichweite, fr.einfluss, w.name AS heimat "
        "FROM fraktion fr LEFT JOIN welt w ON fr.heimatwelt_id=w.id "
        "WHERE fr.kampagne_id=? ORDER BY fr.name", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]


def liste_auftraege(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT a.id, a.titel, a.typ, a.status, w.name AS ort "
        "FROM auftrag a LEFT JOIN welt w ON a.welt_id=w.id "
        "WHERE a.kampagne_id=? ORDER BY a.status, a.titel", (kampagne_id,)).fetchall()
    return [dict(r) for r in rows]


def welt_kontext(db: sqlite3.Connection, welt_id: int) -> dict | None:
    """Liefert {welt_id, sektor_id, ss_index, hex, name, kampagne_id} fuer Redirects/Forms."""
    r = db.execute(
        "SELECT w.id, w.sektor_id, w.hex, w.name, s.idx AS ss_index, se.kampagne_id "
        "FROM welt w LEFT JOIN subsektor s ON w.subsektor_id=s.id "
        "JOIN sektor se ON w.sektor_id=se.id WHERE w.id=?",
        (welt_id,)).fetchone()
    return dict(r) if r else None


def lade_welt(db: sqlite3.Connection, welt_id: int) -> dict | None:
    r = db.execute("SELECT * FROM welt WHERE id=?", (welt_id,)).fetchone()
    return _hydrate(r) if r else None


def welt_nscs(db: sqlite3.Connection, welt_id: int) -> list[dict]:
    """NSCs einer Welt (fuer Patron-Auswahl im Auftrags-Formular)."""
    rows = db.execute("SELECT id, name, rolle FROM nsc WHERE aufenthalt_welt_id=? ORDER BY name",
                      (welt_id,)).fetchall()
    return [dict(r) for r in rows]


def sektor_fraktionen(db: sqlite3.Connection, sektor_id: int) -> list[dict]:
    """Alle Fraktionen eines Sektors (fuer NSC-Zuordnung + Card)."""
    rows = db.execute(
        "SELECT fr.id, fr.name, fr.typ FROM fraktion fr "
        "JOIN welt w ON fr.heimatwelt_id=w.id WHERE w.sektor_id=? ORDER BY fr.name",
        (sektor_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
#  NSC
# ---------------------------------------------------------------------
_NSC_JSON = ("eigenschaften", "skills", "laufbahn", "ausruestung", "wuerfe")
_NSC_EDIT = {"name", "rolle", "beschreibung", "notizen", "status", "getroffen", "aufenthalt_welt_id"}


def _hydrate_nsc(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in _NSC_JSON:
        if d.get(c):
            try:
                d[c] = json.loads(d[c])
            except (ValueError, TypeError):
                pass
    return d


def speichere_nsc(db: sqlite3.Connection, kampagne_id: int,
                  aufenthalt_welt_id: int | None, nsc: dict) -> int:
    """Schreibt ein NSC-dict (aus erzeuge_nsc oder Formular) in die nsc-Tabelle."""
    return _insert(db, "nsc", nsc_zu_row(nsc, kampagne_id, aufenthalt_welt_id))


def lade_nsc(db: sqlite3.Connection, nsc_id: int) -> dict | None:
    r = db.execute("SELECT * FROM nsc WHERE id=?", (nsc_id,)).fetchone()
    return _hydrate_nsc(r) if r else None


def aktualisiere_nsc(db: sqlite3.Connection, nsc_id: int, felder: dict) -> None:
    _update(db, "nsc", nsc_id, felder, _NSC_EDIT)


def loesche_nsc(db: sqlite3.Connection, nsc_id: int) -> None:
    db.execute("DELETE FROM nsc WHERE id=?", (nsc_id,))
    db.commit()


def lade_nsc_fraktionen(db: sqlite3.Connection, nsc_id: int) -> dict[int, dict]:
    """fraktion_id -> {geheim, rolle} fuer die aktuellen Zuordnungen eines NSC."""
    rows = db.execute(
        "SELECT fraktion_id, geheim, rolle FROM nsc_fraktion WHERE nsc_id=?",
        (nsc_id,)).fetchall()
    return {r["fraktion_id"]: {"geheim": r["geheim"], "rolle": r["rolle"]} for r in rows}


def setze_nsc_fraktionen(db: sqlite3.Connection, nsc_id: int,
                         eintraege: list[dict]) -> None:
    """Ersetzt die Fraktions-Zuordnungen eines NSC (eintraege: {fraktion_id, geheim, rolle})."""
    db.execute("DELETE FROM nsc_fraktion WHERE nsc_id=?", (nsc_id,))
    for e in eintraege:
        db.execute(
            "INSERT OR IGNORE INTO nsc_fraktion(nsc_id, fraktion_id, geheim, rolle) "
            "VALUES (?, ?, ?, ?)",
            (nsc_id, e["fraktion_id"], 1 if e.get("geheim") else 0, e.get("rolle")))
    db.commit()


# ---------------------------------------------------------------------
#  NSC-Orte (Herkunft/wirkt_in via verknuepfung-Graph)
#  -------------------------------------------------------------------
#  Aufenthalt = Backbone-FK nsc.aufenthalt_welt_id (label 'befindet_sich').
#  Herkunft & Sonstiges = weiche Querverweise im Graph.
# ---------------------------------------------------------------------
_NSC_ORT_RELATIONEN = ("stammt_von", "wirkt_in", "versteckt_auf")


def setze_nsc_ort(db: sqlite3.Connection, nsc_id: int, welt_id: int, relation: str) -> None:
    if relation not in _NSC_ORT_RELATIONEN:
        return
    db.execute(
        "INSERT OR IGNORE INTO verknuepfung(von_typ, von_id, zu_typ, zu_id, relation) "
        "VALUES('nsc', ?, 'welt', ?, ?)", (nsc_id, welt_id, relation))
    db.commit()


def loesche_nsc_orte(db: sqlite3.Connection, nsc_id: int, relation: str | None = None) -> None:
    if relation:
        db.execute("DELETE FROM verknuepfung WHERE von_typ='nsc' AND von_id=? "
                   "AND zu_typ='welt' AND relation=?", (nsc_id, relation))
    else:
        db.execute("DELETE FROM verknuepfung WHERE von_typ='nsc' AND von_id=? AND zu_typ='welt'",
                   (nsc_id,))
    db.commit()


def nsc_orte(db: sqlite3.Connection, nsc_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT zu_id AS welt_id, relation FROM verknuepfung "
        "WHERE von_typ='nsc' AND von_id=? AND zu_typ='welt'", (nsc_id,)).fetchall()
    return [dict(r) for r in rows]


def fraktionen_struktur(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    """Fraktionen der Kampagne als Kaskade [{ss_index, ss_name, welten:[{welt_id,
    hex, name, fraktionen:[{id, name, typ}]}]}] — nur Welten mit Fraktionen."""
    rows = db.execute(
        "SELECT s.idx AS ss_index, s.name AS ss_name, w.id AS welt_id, w.hex, "
        "       w.name AS welt_name, fr.id AS fr_id, fr.name AS fr_name, fr.typ AS fr_typ "
        "FROM fraktion fr JOIN welt w ON fr.heimatwelt_id=w.id "
        "JOIN subsektor s ON w.subsektor_id=s.id JOIN sektor se ON w.sektor_id=se.id "
        "WHERE se.kampagne_id=? ORDER BY s.idx, w.hex, fr.name", (kampagne_id,)).fetchall()
    aus: dict = {}
    for r in rows:
        ss = aus.setdefault(r["ss_index"], {"ss_index": r["ss_index"],
                                            "ss_name": r["ss_name"], "welten": {}})
        wlt = ss["welten"].setdefault(r["welt_id"], {"welt_id": r["welt_id"], "hex": r["hex"],
                                                     "name": r["welt_name"], "fraktionen": []})
        wlt["fraktionen"].append({"id": r["fr_id"], "name": r["fr_name"], "typ": r["fr_typ"]})
    return [{"ss_index": s["ss_index"], "ss_name": s["ss_name"],
             "welten": list(s["welten"].values())} for s in aus.values()]


def welten_struktur(db: sqlite3.Connection, kampagne_id: int) -> list[dict]:
    """Alle Welten der Kampagne als Kaskade [{ss_index, ss_name, welten:[{welt_id,
    hex, name}]}] — fuer den Orts-Picker (Aufenthalt/Herkunft)."""
    rows = db.execute(
        "SELECT s.idx AS ss_index, s.name AS ss_name, w.id AS welt_id, w.hex, w.name AS welt_name "
        "FROM welt w JOIN subsektor s ON w.subsektor_id=s.id JOIN sektor se ON w.sektor_id=se.id "
        "WHERE se.kampagne_id=? ORDER BY s.idx, w.hex", (kampagne_id,)).fetchall()
    aus: dict = {}
    for r in rows:
        ss = aus.setdefault(r["ss_index"], {"ss_index": r["ss_index"],
                                            "ss_name": r["ss_name"], "welten": []})
        ss["welten"].append({"welt_id": r["welt_id"], "hex": r["hex"], "name": r["welt_name"]})
    return list(aus.values())


def nscs_an_welt(db: sqlite3.Connection, welt_id: int) -> list[dict]:
    """NSCs mit Bezug zu Welt W: Aufenthalt (relation='befindet_sich') + Graph-Relationen."""
    out = [{"id": r["id"], "name": r["name"], "rolle": r["rolle"],
            "status": r["status"], "relation": "befindet_sich"}
           for r in db.execute(
               "SELECT id, name, rolle, status FROM nsc WHERE aufenthalt_welt_id=?", (welt_id,)).fetchall()]
    for r in db.execute(
            "SELECT n.id, n.name, n.rolle, n.status, v.relation FROM verknuepfung v "
            "JOIN nsc n ON n.id=v.von_id "
            "WHERE v.von_typ='nsc' AND v.zu_typ='welt' AND v.zu_id=?", (welt_id,)).fetchall():
        out.append({"id": r["id"], "name": r["name"], "rolle": r["rolle"],
                    "status": r["status"], "relation": r["relation"]})
    return out


# ---------------------------------------------------------------------
#  Auftrag
# ---------------------------------------------------------------------
_AUFTRAG_EDIT = {"titel", "typ", "belohnung", "komplikation", "wendung",
                 "notizen", "status", "patron_nsc_id", "welt_id", "fraktion_id"}
_AUFTRAG_STATUS = {"offen", "aktiv", "abgeschlossen", "gescheitert"}


def speichere_auftrag(db: sqlite3.Connection, row: dict) -> int:
    return _insert(db, "auftrag", row)


def lade_auftrag(db: sqlite3.Connection, auftrag_id: int) -> dict | None:
    r = db.execute("SELECT * FROM auftrag WHERE id=?", (auftrag_id,)).fetchone()
    return dict(r) if r else None


def aktualisiere_auftrag(db: sqlite3.Connection, auftrag_id: int, felder: dict) -> None:
    _update(db, "auftrag", auftrag_id, felder, _AUFTRAG_EDIT)


def setze_auftrag_status(db: sqlite3.Connection, auftrag_id: int, status: str) -> bool:
    if status not in _AUFTRAG_STATUS:
        return False
    db.execute("UPDATE auftrag SET status=? WHERE id=?", (status, auftrag_id))
    db.commit()
    return True


def loesche_auftrag(db: sqlite3.Connection, auftrag_id: int) -> None:
    db.execute("DELETE FROM auftrag WHERE id=?", (auftrag_id,))
    db.commit()


def welt_id_des_auftrags(db: sqlite3.Connection, auftrag_id: int) -> int | None:
    r = db.execute("SELECT welt_id FROM auftrag WHERE id=?", (auftrag_id,)).fetchone()
    return r["welt_id"] if r else None


# ---------------------------------------------------------------------
#  Fraktion
# ---------------------------------------------------------------------
_FRAKTION_EDIT = {"name", "typ", "reichweite", "einfluss", "ziele", "notizen", "heimatwelt_id"}


def lade_fraktion(db: sqlite3.Connection, fraktion_id: int) -> dict | None:
    r = db.execute("SELECT * FROM fraktion WHERE id=?", (fraktion_id,)).fetchone()
    return dict(r) if r else None


def aktualisiere_fraktion(db: sqlite3.Connection, fraktion_id: int, felder: dict) -> None:
    _update(db, "fraktion", fraktion_id, felder, _FRAKTION_EDIT)


def speichere_fraktion(db: sqlite3.Connection, kampagne_id: int,
                       heimatwelt_id: int | None, felder: dict) -> int:
    row = {"name": felder.get("name") or "Unbenannte Fraktion",
           "kampagne_id": kampagne_id,
           "typ": felder.get("typ"),
           "reichweite": felder.get("reichweite") or "lokal",
           "heimatwelt_id": heimatwelt_id,
           "einfluss": felder.get("einfluss"),
           "ziele": felder.get("ziele"),
           "notizen": felder.get("notizen")}
    return _insert(db, "fraktion", row)


def loesche_fraktion(db: sqlite3.Connection, fraktion_id: int) -> None:
    db.execute("DELETE FROM fraktion WHERE id=?", (fraktion_id,))
    db.commit()


def fraktion_mitglieder(db: sqlite3.Connection, fraktion_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT n.id, n.name, n.rolle, nf.geheim FROM nsc n "
        "JOIN nsc_fraktion nf ON nf.nsc_id=n.id WHERE nf.fraktion_id=? ORDER BY n.name",
        (fraktion_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
#  Welt-/Sektor-Editor
# ---------------------------------------------------------------------
# Direkt setzbare (nicht-abgeleitete) Spalten. uwp/handelscodes/reisezone werden
# aus den Komponenten neu berechnet, NICHT direkt geschrieben.
_WELT_KOMPONENTEN = ("groesse", "atmosphaere", "hydrographie", "bevoelkerung",
                     "regierung", "gesetz", "techlevel")
_WELT_DIREKT = {"name", "raumhafen", "zugehoerigkeit", "temperatur", "notizen"}


def aktualisiere_welt(db: sqlite3.Connection, welt_id: int, felder: dict) -> None:
    """Schreibt editierte Welt-Felder; uwp + Handelscodes werden neu berechnet.

    Reisezone ist eine MANUELLE Override-Spalte (Roadmap: „Reisezone auf rot
    setzen") und wird daher direkt aus `felder['reisezone']` uebernommen.
    """
    aktuell = db.execute("SELECT * FROM welt WHERE id=?", (welt_id,)).fetchone()
    if not aktuell:
        return
    aktuell = dict(aktuell)

    komp = {}
    for k in _WELT_KOMPONENTEN:
        v = felder.get(k, aktuell[k])
        try:
            komp[k] = max(0, int(v))            # leere/ungueltige Eingabe -> alter Wert
        except (TypeError, ValueError):
            komp[k] = aktuell[k] or 0

    setz = {k: felder[k] for k in _WELT_DIREKT if k in felder}
    if "gasriesen" in felder:
        setz["gasriesen"] = 1 if str(felder["gasriesen"]) in ("1", "true", "on") else 0
    if felder.get("reisezone") in ("gruen", "amber", "rot"):
        setz["reisezone"] = felder["reisezone"]
    setz.update(komp)

    raumhafen = setz.get("raumhafen", aktuell["raumhafen"]) or "X"
    setz["uwp"] = baue_uwp(raumhafen, komp["groesse"], komp["atmosphaere"],
                           komp["hydrographie"], komp["bevoelkerung"],
                           komp["regierung"], komp["gesetz"], komp["techlevel"])
    setz["handelscodes"] = json.dumps(berechne_handelscodes(
        komp["groesse"], komp["atmosphaere"], komp["hydrographie"],
        komp["bevoelkerung"], komp["regierung"], komp["gesetz"], komp["techlevel"]))

    erlaubt = _WELT_DIREKT | set(_WELT_KOMPONENTEN) | {"uwp", "handelscodes", "reisezone", "gasriesen"}
    _update(db, "welt", welt_id, setz, erlaubt)


def neuwuerfeln_welt(db: sqlite3.Connection, welt_id: int) -> None:
    """Wuerfelt eine Welt mit NEUEM Sub-Seed neu (Nachbarn bleiben unberuehrt).

    Die welt-id und der Hex bleiben erhalten; bestehende NSCs/Auftraege/Fraktionen
    bleiben verknuepft (sie haengen an der id). Die UWP-Felder werden ersetzt.
    """
    ctx = db.execute("SELECT hex, seed, sektor_id, subsektor_id, zugehoerigkeit "
                     "FROM welt WHERE id=?", (welt_id,)).fetchone()
    if not ctx:
        return
    import secrets
    basis = ctx["seed"] or f"manuell|{ctx['hex']}"
    neuer_seed = f"{basis}|r{secrets.token_hex(3)}"
    wlt = erzeuge_welt(neuer_seed, ctx["hex"], zugehoerigkeit=ctx["zugehoerigkeit"])
    row = welt_zu_row(wlt, ctx["sektor_id"], ctx["subsektor_id"])
    row.pop("hex", None)                                # Hex nicht aendern
    zuweisung = ", ".join(f"{k}=?" for k in row)
    db.execute(f"UPDATE welt SET {zuweisung} WHERE id=?", list(row.values()) + [welt_id])
    db.commit()


def erzeuge_welt_in_hex(db: sqlite3.Connection, sektor_id: int, ss_index: int,
                        hexcode: str, seed: str | None = None) -> int | None:
    """Setzt eine generierte Welt in einen (leeren) Hex. None, wenn Hex belegt."""
    belegt = db.execute("SELECT 1 FROM welt WHERE sektor_id=? AND hex=?",
                        (sektor_id, hexcode)).fetchone()
    if belegt:
        return None
    sub = db.execute("SELECT id FROM subsektor WHERE sektor_id=? AND idx=?",
                     (sektor_id, ss_index)).fetchone()
    if not sub:
        return None
    sektor = db.execute("SELECT seed FROM sektor WHERE id=?", (sektor_id,)).fetchone()
    welt_seed = seed or f"{(sektor['seed'] if sektor else 'manuell')}|{hexcode}"
    wlt = erzeuge_welt(welt_seed, hexcode)
    return _insert(db, "welt", welt_zu_row(wlt, sektor_id, sub["id"]))


def loesche_welt(db: sqlite3.Connection, welt_id: int) -> None:
    db.execute("DELETE FROM welt WHERE id=?", (welt_id,))
    db.commit()


def benenne_subsektor(db: sqlite3.Connection, sektor_id: int, ss_index: int,
                      name: str) -> None:
    db.execute("UPDATE subsektor SET name=? WHERE sektor_id=? AND idx=?",
               (name or None, sektor_id, ss_index))
    db.commit()
