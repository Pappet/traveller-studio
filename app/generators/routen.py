"""
Traveller Routen  ·  Hexdistanz + Routen-Generierung
=====================================================

Modelliert Verbindungen zwischen Welten und rendert sie spaeter als Linien.

WICHTIG zur Regellage: Das Weltenerschaffungs-Kapitel des Grundregelwerks
definiert KEINEN rigorosen Wuerfel-Algorithmus fuer Routen -- es verweist auf
das Handelssystem (S.~180). Routen sind in Traveller weitgehend SL-Konvention
(Xboat-/Kommunikationsnetz, Handelsstrassen). Die Generatoren hier sind daher
bewusst HEURISTIKEN, keine Buchregel:

  * Kommunikationsrouten verbinden "wichtige" Welten (Marinebasis, Scoutbasis,
    Raumhafen A/B, hohe Bevoelkerung) innerhalb einer Sprungreichweite.
  * Handelsrouten verbinden Welten mit KOMPLEMENTAEREN Handelscodes
    (z.B. Agrar <-> Industrie/Hohe Bev.) innerhalb einer Sprungreichweite.

Beide liefern ungerichtete Kanten als dicts:
    {"a": "0101", "b": "0203", "typ": "kommunikation"|"handel", "jump": <int>}

Hexdistanz: 1 Hex = 1 Parsek. Layout = gerade Spalten (02,04,...) um ein halbes
Hex nach UNTEN versetzt (wie in hexmap.py). Die Distanz ist unten getestet.
Nur Standardbibliothek.
"""

from __future__ import annotations


# =====================================================================
#  Hexdistanz (Parsek)  -- Cube-Koordinaten, gerade Spalten nach unten
# =====================================================================
def _to_cube(col: int, row: int) -> tuple[int, int, int]:
    # "even-q": gerade Spalten nach unten versetzt (= unser Render-Layout).
    x = col
    z = row - (col + (col & 1)) // 2
    return x, -x - z, z


def hex_distance(hex_a: str, hex_b: str) -> int:
    """Distanz in Parsek zwischen zwei 4-stelligen Hexcodes ('CCRR')."""
    ax, ay, az = _to_cube(int(hex_a[:2]), int(hex_a[2:]))
    bx, by, bz = _to_cube(int(hex_b[:2]), int(hex_b[2:]))
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


# =====================================================================
#  Welt-Zugriff (Welt-Objekt ODER dict)
# =====================================================================
def _g(w, key):
    return getattr(w, key) if hasattr(w, key) else w[key]


# =====================================================================
#  Kommunikationsrouten (Xboat-aehnlich): wichtige Welten verbinden
# =====================================================================
def _wichtigkeit(w) -> int:
    basen = set(_g(w, "basen") or [])
    score = 0
    if "Marine" in basen:               score += 2
    if "Scout" in basen:                score += 1
    if _g(w, "raumhafen") in ("A", "B"): score += 1
    if _g(w, "bevoelkerung") >= 9:       score += 2   # Hohe Bevoelkerung
    return score


def gen_kommunikationsrouten(welten, max_jump: int = 2, schwelle: int = 2) -> list[dict]:
    """Verbindet Welten mit Wichtigkeit >= schwelle, die <= max_jump entfernt sind."""
    wichtig = [w for w in welten if _wichtigkeit(w) >= schwelle]
    kanten = []
    for i, a in enumerate(wichtig):
        for b in wichtig[i + 1:]:
            d = hex_distance(_g(a, "hex"), _g(b, "hex"))
            if 1 <= d <= max_jump:
                kanten.append({"a": _g(a, "hex"), "b": _g(b, "hex"),
                               "typ": "kommunikation", "jump": d})
    return kanten


# =====================================================================
#  Handelsrouten: komplementaere Handelscodes in Sprungreichweite
# =====================================================================
# Ungerichtete Anziehung: wenn A einen Code hat und B einen aus der Menge,
# entsteht eine Handelsbeziehung. (Kanonische englische Codes, vgl. Generator.)
KOMPLEMENTE = {
    "Ag": {"Hi", "In", "Na"},   # Agrar versorgt Hohe Bev. / Industrie / Nicht-Agrar
    "Na": {"Ag"},
    "In": {"Ag", "Ni", "As"},   # Industrie braucht Nahrung / Rohstoffe
    "Ni": {"In"},
    "As": {"In"},
    "Ht": {"Lt"},               # Hightech -> Lowtech
    "Lt": {"Ht"},
    "Hi": {"Lo"},               # Hohe Bev. <-> Geringe Bev.
    "Lo": {"Hi"},
    "Ri": {"Hi", "In"},         # Reiche Welt zieht Handel an
}


def _zieht_handel(codes_a: set, codes_b: set) -> bool:
    for c in codes_a:
        if KOMPLEMENTE.get(c, set()) & codes_b:
            return True
    return False


def gen_handelsrouten(welten, max_jump: int = 2) -> list[dict]:
    kanten = []
    for i, a in enumerate(welten):
        ca = set(_g(a, "handelscodes") or [])
        if not ca:
            continue
        for b in welten[i + 1:]:
            cb = set(_g(b, "handelscodes") or [])
            if not cb:
                continue
            if _zieht_handel(ca, cb) or _zieht_handel(cb, ca):
                d = hex_distance(_g(a, "hex"), _g(b, "hex"))
                if 1 <= d <= max_jump:
                    kanten.append({"a": _g(a, "hex"), "b": _g(b, "hex"),
                                   "typ": "handel", "jump": d})
    return kanten


def gen_alle_routen(welten, jump_komm: int = 2, jump_handel: int = 2) -> list[dict]:
    """Bequemer Sammelaufruf -> beide Routentypen in einer Liste."""
    return (gen_kommunikationsrouten(welten, max_jump=jump_komm)
            + gen_handelsrouten(welten, max_jump=jump_handel))


# =====================================================================
#  Selbsttest der Hexdistanz (gegen bekannte Traveller-Distanzen)
# =====================================================================
if __name__ == "__main__":
    faelle = [
        ("0101", "0101", 0),
        ("0101", "0102", 1),   # gleiche Spalte, eine Zeile
        ("0101", "0201", 1),   # rechter unterer Nachbar (gerade Spalte versetzt)
        ("0101", "0202", 2),
        ("0102", "0201", 1),   # rechter oberer Nachbar
        ("0101", "0103", 2),   # gleiche Spalte
        ("0101", "0301", 2),   # zwei Spalten, gleiche Zeile
        ("0101", "0401", 3),
        ("0101", "0110", 9),
    ]
    ok = True
    for a, b, soll in faelle:
        ist = hex_distance(a, b)
        flag = "OK " if ist == soll else "!! "
        if ist != soll:
            ok = False
        print(f"  {flag}d({a},{b}) = {ist}  (erwartet {soll})")
    print("\nAlle Distanzen korrekt." if ok else "\nFEHLER in der Distanzfunktion!")

    from sektor_generator import erzeuge_subsektor
    w = erzeuge_subsektor("Demo-Sektor-2026", 0)
    k = gen_kommunikationsrouten(w)
    h = gen_handelsrouten(w)
    print(f"\nDemo-Subsektor: {len(k)} Kommunikations- und {len(h)} Handelsrouten.")
