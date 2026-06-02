"""
Traveller NSC-Generator  ·  Mongoose Traveller 2e (13Mann)
==========================================================

Erzeugt einen "schnellen NSC": sechs Eigenschaften (2W6) und ein Skill-Paket
nach Archetyp/Beruf, dazu eine leichte Laufbahn-Zusammenfassung (Karriere,
Begriffe, Rang). KEIN voller Term-fuer-Term-Lifepath -- die kompletten
Karrieretabellen stehen nicht im Repo; dieser Generator deckt den vom Roadmap
zuerst gewuenschten Fall ab ("schneller NSC, Eigenschaften 2W6, Skill-Paket
nach Rolle").

Deterministisch & seedbar wie alle Generatoren: gleicher Seed -> gleicher NSC.
Nur Standardbibliothek. Ausgabe = dict, dessen Schluessel zu den Spalten der
`nsc`-Tabelle passen (JSON-Felder werden in persist serialisiert).
"""

from __future__ import annotations
import random

from .sektor import w, clamp, to_ehex

# =====================================================================
#  Eigenschaften
# =====================================================================
# (Kuerzel, Anzeigename) in UPP-Reihenfolge.
EIGENSCHAFTEN = [
    ("STR", "Stärke"), ("GES", "Geschick"), ("KON", "Konstitution"),
    ("INT", "Intelligenz"), ("BIL", "Bildung"), ("SOZ", "Sozialstatus"),
]


def eigenschaft_dm(wert: int) -> int:
    """Eigenschafts-Modifikator nach MgT2 (-3 bei 0 … +3 ab 15)."""
    if wert <= 0:   return -3
    if wert <= 2:   return -2
    if wert <= 5:   return -1
    if wert <= 8:   return 0
    if wert <= 11:  return 1
    if wert <= 14:  return 2
    return 3


def profil_string(eig: dict[str, int]) -> str:
    """Eigenschaften als eHex-Lockup, z.B. '7A8C96' (Reihenfolge wie UPP)."""
    return "".join(to_ehex(eig[k]) for k, _ in EIGENSCHAFTEN)


# =====================================================================
#  Archetypen (Beruf -> Skill-Paket).  Skill-Namen deutsch (13Mann).
#  merkmal_dm: kleine Eigenschafts-WM, die den Beruf praegen (vor Clamp).
# =====================================================================
ARCHETYPEN: dict[str, dict] = {
    "haendler": {
        "label": "Händler",
        "skills": {"Vermittler": 2, "Überreden": 1, "Verwaltung": 1, "Steward": 1},
        "merkmal_dm": {"SOZ": 1},
        "ausruestung": ["Handcomputer", "feine Kleidung"],
        "karriere": "Kaufmann",
    },
    "pilot": {
        "label": "Pilot",
        "skills": {"Pilot": 2, "Astrogation": 1, "Geschütze": 1, "Vakuumanzug": 1},
        "merkmal_dm": {"GES": 1},
        "ausruestung": ["Vakuumanzug", "Bordfunk"],
        "karriere": "Raumfahrer",
    },
    "soeldner": {
        "label": "Söldner",
        "skills": {"Schusswaffen": 2, "Nahkampf": 1, "Taktik": 1, "Athletik": 1},
        "merkmal_dm": {"STR": 1, "KON": 1},
        "ausruestung": ["Autopistole", "Schutzweste"],
        "karriere": "Militär",
    },
    "techniker": {
        "label": "Techniker",
        "skills": {"Maschinist": 2, "Mechaniker": 1, "Elektronik": 1},
        "merkmal_dm": {"INT": 1},
        "ausruestung": ["Werkzeugsatz", "Diagnoserechner"],
        "karriere": "Ingenieur",
    },
    "beamter": {
        "label": "Beamter",
        "skills": {"Verwaltung": 2, "Diplomatie": 1, "Rechtskunde": 1},
        "merkmal_dm": {"BIL": 1},
        "ausruestung": ["Datapad", "Dienstausweis"],
        "karriere": "Verwaltung",
    },
    "krimineller": {
        "label": "Krimineller",
        "skills": {"Szenekenntnis": 2, "Täuschung": 1, "Tarnung": 1, "Nahkampf": 1},
        "merkmal_dm": {"GES": 1},
        "ausruestung": ["Klappmesser", "gefälschte Papiere"],
        "karriere": "Schurke",
    },
    "wissenschaftler": {
        "label": "Wissenschaftler",
        "skills": {"Wissenschaft": 2, "Ermitteln": 1, "Elektronik": 1},
        "merkmal_dm": {"BIL": 1, "INT": 1},
        "ausruestung": ["Feldlabor", "Datapad"],
        "karriere": "Gelehrter",
    },
    "mediziner": {
        "label": "Mediziner",
        "skills": {"Medizin": 2, "Wissenschaft": 1, "Diplomatie": 1},
        "merkmal_dm": {"BIL": 1},
        "ausruestung": ["Medikit", "Diagnoserechner"],
        "karriere": "Mediziner",
    },
    "adliger": {
        "label": "Adliger",
        "skills": {"Diplomatie": 2, "Führung": 1, "Verwaltung": 1},
        "merkmal_dm": {"SOZ": 2},
        "ausruestung": ["feine Kleidung", "Siegelring"],
        "karriere": "Adel",
    },
    "spaeher": {
        "label": "Späher",
        "skills": {"Pilot": 1, "Astrogation": 1, "Aufklärung": 1, "Überleben": 1, "Vakuumanzug": 1},
        "merkmal_dm": {"KON": 1},
        "ausruestung": ["Vakuumanzug", "Überlebenspaket"],
        "karriere": "Forscher",
    },
    "streuner": {
        "label": "Streuner",
        "skills": {"Athletik": 1, "Szenekenntnis": 1, "Überleben": 1, "Nahkampf": 1},
        "merkmal_dm": {},
        "ausruestung": ["abgetragene Kleidung"],
        "karriere": "Drifter",
    },
}

# Narrative Rolle am Tisch (unabhaengig vom Beruf).
ROLLEN = ["Patron", "Kontakt", "Verbündeter", "Rivale", "Antagonist", "Neutral"]

# Rangbezeichnungen je Karriere (Index = Rang 0..3+); generisch gehalten.
_RAENGE = {
    "Militär":   ["Rekrut", "Unteroffizier", "Leutnant", "Hauptmann"],
    "Raumfahrer": ["Raumflieger", "Maat", "Fähnrich", "Kommandant"],
    "Kaufmann":  ["Anwärter", "Händler", "Erster Maat", "Kapitän"],
    "Verwaltung": ["Sachbearbeiter", "Referent", "Abteilungsleiter", "Direktor"],
    "Adel":      ["Ritter", "Baron", "Marquis", "Graf"],
}


# =====================================================================
#  Namen (deterministisch, Vor- + Nachname)
# =====================================================================
_VORNAMEN = ["Jora", "Kael", "Mira", "Doran", "Sela", "Tavan",
             "Rhia", "Veck", "Lio", "Nara", "Corin", "Esa", "Bran", "Tessa",
             "Halden", "Ysa", "Marn", "Pell", "Ravi", "Sten"]
_NACHNAMEN = ["Voss", "Karr", "Delan", "Mott", "Sarn", "Othic", "Brel", "Vane",
              "Korr", "Less", "Dane", "Pryce", "Holt", "Marek", "Renn", "Skol",
              "Tarn", "Wex", "Lund", "Garro"]


def gen_nsc_name(rng: random.Random) -> str:
    return f"{rng.choice(_VORNAMEN)} {rng.choice(_NACHNAMEN)}"


# =====================================================================
#  Hauptfunktion
# =====================================================================
def erzeuge_nsc(seed: str, *, archetyp: str | None = None,
                rolle: str = "Kontakt") -> dict:
    """Erzeugt einen schnellen NSC als dict (passend zur `nsc`-Tabelle)."""
    rng = random.Random(seed)
    rolls: dict = {}

    if archetyp not in ARCHETYPEN:
        archetyp = rng.choice(list(ARCHETYPEN.keys()))
    arch = ARCHETYPEN[archetyp]
    if rolle not in ROLLEN:
        rolle = "Kontakt"

    # --- Eigenschaften: 2W6 je, + berufstypische WM -------------------
    eig: dict[str, int] = {}
    rolls["eigenschaften"] = {}
    for kuerzel, _ in EIGENSCHAFTEN:
        r = w(rng)
        rolls["eigenschaften"][kuerzel] = r
        eig[kuerzel] = clamp(r + arch["merkmal_dm"].get(kuerzel, 0), 1, 15)

    # --- Skill-Paket: Basis aus dem Archetyp, + 1 Bonusrang -----------
    skills = dict(arch["skills"])
    bonus = rng.choice(list(skills.keys()))
    skills[bonus] = skills[bonus] + 1
    rolls["bonus_skill"] = bonus

    # --- Leichte Laufbahn (Karriere / Begriffe / Rang) ----------------
    begriffe = w(rng, n=1, sides=3)              # 1W3 Begriffe (Terms)
    rang = clamp(w(rng, n=1, sides=3) - 1, 0, begriffe)
    rolls["begriffe"] = begriffe
    rolls["rang"] = rang
    karriere = arch["karriere"]
    rang_namen = _RAENGE.get(karriere)
    rang_name = rang_namen[min(rang, len(rang_namen) - 1)] if rang_namen else None
    alter = 18 + begriffe * 4
    laufbahn = {
        "karriere": karriere, "begriffe": begriffe, "rang": rang,
        "rang_name": rang_name, "alter": alter,
    }

    name = gen_nsc_name(rng)
    rang_txt = f"{rang_name}, " if rang_name else ""
    beschreibung = (f"{arch['label']} · {rang_txt}{begriffe} Begriff(e) als "
                    f"{karriere} · ca. {alter} Jahre")

    return {
        "name": name,
        "archetyp": archetyp,
        "rolle": rolle,
        "eigenschaften": eig,
        "profil": profil_string(eig),
        "skills": skills,
        "laufbahn": laufbahn,
        "ausruestung": list(arch["ausruestung"]),
        "beschreibung": beschreibung,
        "seed": seed,
        "wuerfe": rolls,
    }


def nsc_zu_row(nsc: dict, welt_id: int | None) -> dict:
    """Mappt ein NSC-dict auf die Spalten der `nsc`-Tabelle (JSON serialisiert)."""
    import json
    return {
        "name": nsc["name"],
        "welt_id": welt_id,
        "eigenschaften": json.dumps(nsc["eigenschaften"]),
        "skills": json.dumps(nsc["skills"]),
        "laufbahn": json.dumps(nsc.get("laufbahn")) if nsc.get("laufbahn") else None,
        "ausruestung": json.dumps(nsc.get("ausruestung") or []),
        "rolle": nsc.get("rolle"),
        "beschreibung": nsc.get("beschreibung"),
        "seed": nsc.get("seed"),
        "wuerfe": json.dumps(nsc.get("wuerfe") or {}),
    }


# =====================================================================
#  Demo
# =====================================================================
if __name__ == "__main__":
    for i in range(6):
        n = erzeuge_nsc(f"Demo-NSC|{i}")
        eig = "  ".join(f"{k} {n['eigenschaften'][k]:>2}" for k, _ in EIGENSCHAFTEN)
        print(f"{n['name']:<16} [{n['profil']}]  {n['beschreibung']}")
        print(f"   {eig}")
        print(f"   Skills: " + ", ".join(f"{s} {l}" for s, l in n["skills"].items()))
