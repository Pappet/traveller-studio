"""
Persistenz-Schicht
==================

Verbindet die (reinen, seedbaren) Generatoren mit der Datenbank:
  * speichere_sektor()  -- generiert einen ganzen Sektor und schreibt
                           Welten, Fraktionen und Routen in die Tabellen.
  * lade_*()            -- liest die gespeicherten Daten zurueck und
                           HYDRIERT die JSON-Spalten (Strings -> Python),
                           damit die Renderer (hexmap/detailkarte) sie direkt
                           verwenden koennen.

Die Renderer lesen Welt-Objekte ODER dicts; hier liefern wir dicts.
"""
from __future__ import annotations
import json
import sqlite3

from sektor_generator import erzeuge_sektor, welt_zu_row
from faktionen import erzeuge_fraktionen, fraktion_zu_row, _staerke
from routes import gen_alle_routen

# JSON-Spalten der welt-Tabelle, die beim Laden geparst werden muessen
_JSON_COLS = ("handelscodes", "basen", "raumhafen_details", "kultur",
              "sternendaten", "wuerfe")


# =====================================================================
#  Schreiben: ganzen Sektor generieren und speichern
# =====================================================================
def speichere_sektor(db: sqlite3.Connection, seed: str, name: str,
                     dichte: str = "normal", zugehoerigkeit: str = "Im") -> int:
    cur = db.cursor()
    cur.execute("INSERT INTO sektor(name, seed) VALUES(?, ?)", (name, seed))
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

    # Fraktionen pro Welt -> fraktion-Tabelle (heimatwelt_id = diese Welt)
    for ss_index, welten in sektor_welten.items():
        for wlt in welten:
            for fr in erzeuge_fraktionen(wlt, seed):
                frow = fraktion_zu_row(fr, hex2id[wlt.hex])
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


def liste_sektoren(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT id, name, seed FROM sektor ORDER BY erstellt_am DESC").fetchall()
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
    """hex -> {nscs, auftraege, fraktionen} fuer die Detailkarte."""
    links: dict = {}
    for w in welt_dicts:
        wid, hexc = w["id"], w["hex"]
        eintrag: dict = {}

        nscs = db.execute(
            "SELECT id, name, rolle, status FROM nsc WHERE welt_id=?", (wid,)).fetchall()
        if nscs:
            liste = []
            for n in nscs:
                geheim = db.execute(
                    "SELECT 1 FROM nsc_fraktion WHERE nsc_id=? AND geheim=1 LIMIT 1",
                    (n["id"],)).fetchone() is not None
                liste.append({"name": n["name"], "rolle": n["rolle"],
                              "status": n["status"], "geheim": geheim})
            eintrag["nscs"] = liste

        auf = db.execute(
            "SELECT titel, status FROM auftrag WHERE welt_id=?", (wid,)).fetchall()
        if auf:
            eintrag["auftraege"] = [dict(a) for a in auf]

        fra = db.execute(
            "SELECT name, typ, einfluss FROM fraktion WHERE heimatwelt_id=?", (wid,)).fetchall()
        if fra:
            eintrag["fraktionen"] = [
                {"name": f["name"], "typ": f["typ"],
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


def subsektoren_mit_welten(db: sqlite3.Connection, sektor_id: int) -> set[int]:
    rows = db.execute(
        "SELECT DISTINCT s.idx FROM subsektor s JOIN welt w ON w.subsektor_id=s.id "
        "WHERE s.sektor_id=?", (sektor_id,)).fetchall()
    return {r["idx"] for r in rows}


# =====================================================================
#  Subsektor-Navigation (A..P) -- als HTML-Schnipsel fuer render_app
# =====================================================================
def baue_nav(sektor_id: int, aktiv_idx: int, vorhanden: set[int]) -> str:
    pills = []
    for i in range(16):
        letter = chr(65 + i)
        if i == aktiv_idx:
            pills.append(f'<a class="nav-pill on" href="/sektor/{sektor_id}/subsektor/{i}">{letter}</a>')
        elif i in vorhanden:
            pills.append(f'<a class="nav-pill" href="/sektor/{sektor_id}/subsektor/{i}">{letter}</a>')
        else:
            pills.append(f'<span class="nav-pill leer">{letter}</span>')
    style = """<style>
      .subnav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 24px 0;}
      .nav-pill{display:grid;place-items:center;min-width:30px;height:28px;padding:0 9px;
        border-radius:9999px;font-family:var(--font-mono);font-size:.72rem;text-decoration:none;
        color:var(--on-variant);border:1px solid rgba(65,74,52,.4);
        transition:background 120ms var(--ease),color 120ms var(--ease);}
      .nav-pill:hover{color:var(--on-surface);background:var(--container-high);}
      .nav-pill.on{background:var(--primary);color:var(--on-primary);border-color:transparent;font-weight:600;}
      .nav-pill.leer{opacity:.3;pointer-events:none;}
    </style>"""
    return style + '<div class="subnav">' + "".join(pills) + "</div>"


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
