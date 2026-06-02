"""
Traveller Fraktionen  ·  Generator (Grundregelwerk: "Rivalen, Fraktionen …")
=============================================================================

Erzeugt pro BEWOHNTER Welt 1W3 Fraktionen (mit WM), jede mit eigener
Mini-Regierung, Staerke und Art. Diese Fraktionen sind eigenstaendige
Entitaeten -> sie fuellen die `fraktion`-Tabelle (heimatwelt_id = diese Welt).

Regel (Buch):
  * Anzahl: 1W3, WM +1 wenn Regierung 0 oder 7, WM -1 wenn Regierung >= 10.
  * Jede Fraktion erhaelt ueber die Regierungstabelle eine Mini-Regierung.
  * Ist sie der Hauptregierung aehnlich -> Splittergruppe; ist sie radikal
    anders -> Rebellengruppe/Bewegung.
  * Staerke: 2W6 auf der Fraktionsstaerketabelle.

Deterministisch & seedbar: Sub-Seed aus master_seed|hex|fraktionen.
Nur Standardbibliothek.
"""

from __future__ import annotations
import random
from .sektor import REGIERUNG_NAMEN, w, clamp

# Fraktionsstaerketabelle (2W6): (obergrenze, kurz, beschreibung)
STAERKE = [
    (3,  "Obskur",        "wenige haben von ihnen gehört, keine Unterstützung"),
    (5,  "Randgruppe",    "wenig Unterstützung"),
    (7,  "Klein",         "einige Unterstützung"),
    (9,  "Bemerkenswert", "bedeutende Unterstützung, sehr bekannt"),
    (11, "Bedeutend",     "fast so einflussreich wie die Regierung"),
    (12, "Überwältigend", "mächtiger als die Regierung"),
]

def _staerke(roll: int) -> tuple[str, str]:
    for hi, kurz, lang in STAERKE:
        if roll <= hi:
            return kurz, lang
    return STAERKE[-1][1], STAERKE[-1][2]


# --- Fraktionsnamen (deterministisch) ------------------------------------
_ADJ = ["Freie", "Vereinigte", "Wahre", "Rote", "Schwarze", "Erste", "Heilige",
        "Geeinte", "Stille", "Eiserne", "Neue", "Alte"]
_NOMEN = ["Front", "Bewegung", "Liga", "Allianz", "Bruderschaft", "Partei",
          "Koalition", "Fraktion", "Garde", "Versammlung", "Union", "Zirkel"]
_SACHE = ["Reform", "Freiheit", "Tradition", "Einheit", "Erneuerung", "Ordnung",
          "Heimat", "Zukunft", "Wahrheit", "Gerechtigkeit", "Arbeit", "Sterne"]

def _fraktionsname(rng: random.Random) -> str:
    form = rng.randint(0, 2)
    if form == 0:
        return f"{rng.choice(_ADJ)} {rng.choice(_NOMEN)}"
    if form == 1:
        return f"{rng.choice(_NOMEN)} für {rng.choice(_SACHE)}"
    return f"{rng.choice(_SACHE)}s{rng.choice(['front', 'bewegung', 'partei'])}"


def _g(obj, key):
    return getattr(obj, key) if hasattr(obj, key) else obj[key]


# =====================================================================
#  Hauptfunktion
# =====================================================================
def erzeuge_fraktionen(welt, master_seed: str) -> list[dict]:
    """Liste von Fraktions-dicts fuer eine Welt (leer wenn unbewohnt)."""
    bev = _g(welt, "bevoelkerung")
    if bev == 0:
        return []

    reg = _g(welt, "regierung")
    hexc = _g(welt, "hex")
    rng = random.Random(f"{master_seed}|{hexc}|fraktionen")

    # Anzahl: 1W3 + WM
    dm = (1 if reg in (0, 7) else 0) + (-1 if reg >= 10 else 0)
    anzahl = max(0, w(rng, n=1, sides=3) + dm)

    fraktionen: list[dict] = []
    for _ in range(anzahl):
        rolls: dict = {}

        # Mini-Regierung ueber die Regierungstabelle (2W6-7 + Bevoelkerung)
        rr = w(rng); rolls["regierung"] = rr
        fr_reg = clamp(rr - 7 + bev, 0, 13)

        # Aehnlich (Splittergruppe) vs. radikal anders (Opposition)
        art = "Splittergruppe" if abs(fr_reg - reg) <= 1 else "Oppositionsbewegung"

        # Staerke: 2W6
        sr = w(rng); rolls["staerke"] = sr
        st_kurz, st_lang = _staerke(sr)

        fraktionen.append({
            "name": _fraktionsname(rng),
            "regierung": fr_reg,
            "regierung_name": REGIERUNG_NAMEN.get(fr_reg, "Sonstige"),
            "art": art,
            "staerke_wurf": sr,
            "staerke": st_kurz,
            "staerke_beschreibung": st_lang,
            "reichweite": "lokal",
            "seed": f"{master_seed}|{hexc}|fraktionen",
            "wuerfe": rolls,
        })
    return fraktionen


def fraktion_zu_row(fr: dict, heimatwelt_id: int, kampagne_id: int) -> dict:
    """Mappt ein Fraktions-dict auf die Spalten der `fraktion`-Tabelle."""
    import json
    return {
        "name": fr["name"],
        "kampagne_id": kampagne_id,
        "typ": fr["art"],                       # Splittergruppe / Oppositionsbewegung
        "reichweite": fr["reichweite"],
        "heimatwelt_id": heimatwelt_id,
        "einfluss": fr["staerke_wurf"],         # 2-12
        "ziele": f"{fr['regierung_name']} ({fr['staerke']})",
        "notizen": fr["staerke_beschreibung"],
        "seed": fr["seed"],
        "wuerfe": json.dumps(fr["wuerfe"]),
    }


# =====================================================================
#  Demo
# =====================================================================
if __name__ == "__main__":
    from app.generators.sektor import erzeuge_subsektor
    SEED = "Demo-Sektor-2026"
    welten = erzeuge_subsektor(SEED, 0)
    gesamt = 0
    for wlt in welten[:12]:
        frs = erzeuge_fraktionen(wlt, SEED)
        gesamt += len(frs)
        if frs:
            print(f"\n{wlt.hex} {wlt.name}  (Reg {wlt.regierung} {REGIERUNG_NAMEN[wlt.regierung]})")
            for f in frs:
                print(f"   • {f['name']:<28} {f['art']:<18} "
                      f"{f['regierung_name']:<26} Stärke: {f['staerke']}")
    print(f"\n(erste 12 Welten: {gesamt} Fraktionen)")
