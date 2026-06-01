"""
Traveller Sektor-Generator  ·  Mongoose Traveller 2e (13Mann)
=============================================================

Deterministisch & seedbar: gleicher Seed -> gleicher Sektor.
Jeder Hex hat einen EIGENEN, aus dem Master-Seed abgeleiteten Sub-Seed.
Dadurch ist jede Welt unabhaengig reproduzierbar -> man kann eine einzelne
Welt neu wuerfeln, ohne dass sich die anderen verschieben.

Nur Standardbibliothek. Ausgabe = dicts, deren Schluessel den Spalten in
`welt` aus traveller_schema.sql entsprechen (direkt einfuegbar).

Regelquelle: Traveller SRD (MgT2 Core). Wo der 13Mann-Grundregelwerk-Wert
abweichen koennte, ist es mit  # PRUEFEN  markiert. Alle Regeltabellen sind
bewusst als Daten oben im Modul gehalten -> leicht gegen das Buch anpassbar.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field

# =====================================================================
#  eHex (erweitertes Hex: 0-9, dann A-Z ohne I und O) -> Werte 0..33
# =====================================================================
EHEX = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"

def to_ehex(v: int) -> str:
    return EHEX[v] if 0 <= v < len(EHEX) else "?"

def from_ehex(c: str) -> int:
    return EHEX.index(c.upper())

# =====================================================================
#  Wuerfel
# =====================================================================
def w(rng: random.Random, n: int = 2, sides: int = 6) -> int:
    return sum(rng.randint(1, sides) for _ in range(n))

def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))

# =====================================================================
#  Regeldaten  (gegen das Grundregelwerk pruefbar)
# =====================================================================

# Hexbesetzung: Welt vorhanden bei (1W6 + DM) >= 4
DICHTE_DM = {"normal": 0, "dicht": 1, "duenn": -1, "rift": -2}

# Raumhafen (Standard-Imperium: glatter 2W6-Wurf)
def raumhafen_aus_wurf(r: int) -> str:
    if r <= 2:  return "X"
    if r <= 4:  return "E"
    if r <= 6:  return "D"
    if r <= 8:  return "C"
    if r <= 10: return "B"
    return "A"

# Tech-Level-DMs (1W6 + Summe der DMs)
TL_DM_RAUMHAFEN = {"A": 6, "B": 4, "C": 2, "D": 0, "E": 0, "X": -4}
TL_DM_GROESSE   = {0: 2, 1: 2, 2: 1, 3: 1, 4: 1}
TL_DM_ATMO      = {0: 1, 1: 1, 2: 1, 3: 1, 10: 1, 11: 1, 12: 1, 13: 1, 14: 1, 15: 1}
TL_DM_HYDRO     = {0: 1, 9: 1, 10: 2}
TL_DM_BEV       = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 9: 1, 10: 2, 11: 3, 12: 4}
TL_DM_REG     = {0: 1, 5: 1, 7: 2, 10: -2, 11: -2, 12: -2, 13: -2, 14: -2, 15: -2}

# Basen: alle 6 Typen aus dem 13Mann-Grundregelwerk (Raumhafentabelle S.~248).
# Format: code -> {raumhafenklasse: mindestwurf_2W6}. Fehlt eine Klasse,
# ist dieser Basentyp dort unmoeglich.
BASEN_REGELN = {
    "Marine":    {"A": 8,  "B": 8},
    "Scout":     {"A": 10, "B": 8,  "C": 8,  "D": 7},
    "Forschung": {"A": 8,  "B": 10, "C": 10},
    "TAS":       {"A": 4,  "B": 6,  "C": 10},
    "Konsulat":  {"A": 6,  "B": 8,  "C": 10},
    "Piraten":   {"B": 12, "C": 10, "D": 12, "E": 12},
}

# Handelscodes als Praedikate ueber die UWP-Werte.
# # PRUEFEN: einzelne Grenzen (v.a. Ga/De/In) variieren je nach Druck.
def _trade_codes() -> list[tuple[str, callable]]:
    return [
        ("Ag", lambda x: x["atmo"] in range(4, 10) and x["hydro"] in range(4, 9) and x["bev"] in range(5, 8)),
        ("As", lambda x: x["groesse"] == 0 and x["atmo"] == 0 and x["hydro"] == 0),
        ("Ba", lambda x: x["bev"] == 0 and x["reg"] == 0 and x["gesetz"] == 0),
        ("De", lambda x: x["atmo"] >= 2 and x["hydro"] == 0),
        ("Fl", lambda x: x["atmo"] >= 10 and x["hydro"] >= 1),
        ("Ga", lambda x: x["groesse"] >= 5 and x["atmo"] in range(4, 10) and x["hydro"] in range(4, 9)),
        ("Hi", lambda x: x["bev"] >= 9),
        ("Ht", lambda x: x["tl"] >= 12),
        ("Ic", lambda x: x["atmo"] in (0, 1) and x["hydro"] >= 1),
        ("In", lambda x: x["atmo"] in (0, 1, 2, 4, 7, 9) and x["bev"] >= 9),
        ("Lo", lambda x: x["bev"] in range(1, 4)),
        ("Lt", lambda x: x["tl"] <= 5),
        ("Na", lambda x: x["atmo"] in range(0, 4) and x["hydro"] in range(0, 4) and x["bev"] >= 6),
        ("Ni", lambda x: x["bev"] in range(4, 7)),
        ("Po", lambda x: x["atmo"] in range(2, 6) and x["hydro"] in range(0, 4)),
        ("Ri", lambda x: x["atmo"] in (6, 8) and x["bev"] in range(6, 9)),
        ("Wa", lambda x: x["hydro"] == 10),
        ("Va", lambda x: x["atmo"] == 0),
    ]

TRADE_CODES = _trade_codes()

# ENTSCHEIDUNG Codenamen: Der Generator nutzt intern die KANONISCHEN
# (englischen) Codes Hi/Ht/Ba/De/Fl/Ic/Lo/Po/Ri -- damit bleibt das Tool
# kompatibel zu Traveller Map und fertigen Sektordateien (z.B. Spinwaerts-Marken).
# Das 13Mann-Buch druckt teils ABWEICHENDE deutsche Codes; Mapping hier:
#   Buch Di = Hi (Hohe Bev.)   |  Buch Hi = Ht (Hightech)   <- ACHTUNG: vertauscht!
#   Buch Od = Ba | Wue = De | Li = Fl | Ei = Ic | Due = Lo | Ar = Po | Re = Ri
# Anzeige-Namen (Deutsch) liegen in der UI (detailkarte.py -> TRADE).
# Wer strikt die Buch-Codes will, mappt hier 1:1 um -- Einzeiler.
CODE_DE = {"Ba": "Od", "De": "Wü", "Fl": "Li", "Ga": "Ga", "Hi": "Di", "Ht": "Hi",
           "Ic": "Ei", "Lo": "Dü", "Lt": "Lo", "Po": "Ar", "Ri": "Re"}

# Regierungstabelle (Grundregelwerk). Wird auch vom Fraktionsgenerator genutzt.
REGIERUNG_NAMEN = {
    0: "Keine", 1: "Firma/Konzern", 2: "Partizipierende Demokratie",
    3: "Selbsterhaltende Oligarchie", 4: "Repräsentative Demokratie",
    5: "Feudaltechnokratie", 6: "Gefangene Regierung", 7: "Balkanisierung",
    8: "Staatsdienst-Bürokratie", 9: "Unpersönliche Bürokratie",
    10: "Charismatischer Diktator", 11: "Uncharismatischer Führer",
    12: "Charismatische Oligarchie", 13: "Religiöse Diktatur",
    14: "Sonstige", 15: "Sonstige",
}

# --- Temperatur: 2W6 + Atmosphaeren-WM -> Band ---------------------------
# Das Buch nennt nur die Hydro-WM (Heiss -2 / Gluehend -6); die Atmo-WM und
# Baender sind die kanonischen MgT2-Werte, hier ergaenzt.  # PRUEFEN
TEMP_DM_ATMO = {0: 0, 1: 0, 2: -2, 3: -2, 4: -1, 5: -1, 14: -1,
                6: 0, 7: 0, 8: 1, 9: 1, 10: 2, 13: 2, 15: 2, 11: 6, 12: 6}

def temperatur_band(wert: int) -> str:
    if wert <= 2:  return "Gefroren"
    if wert <= 4:  return "Kalt"
    if wert <= 9:  return "Gemäßigt"
    if wert <= 11: return "Heiß"
    return "Glühend"

# --- Raumhafen-Details (Raumhafentabelle S.~249) -------------------------
# anlegekosten = 1W6 * kosten_faktor (einmal pro Hafen gewuerfelt).
RAUMHAFEN_DETAILS = {
    "A": {"treibstoff": "raffiniert",   "kosten_faktor": 1000, "werft": "alle Schiffe",   "reparatur": "voll"},
    "B": {"treibstoff": "raffiniert",   "kosten_faktor": 500,  "werft": "Raumfahrzeuge",  "reparatur": "voll"},
    "C": {"treibstoff": "unraffiniert", "kosten_faktor": 100,  "werft": "Kleinfahrzeuge", "reparatur": "voll"},
    "D": {"treibstoff": "unraffiniert", "kosten_faktor": 10,   "werft": None,             "reparatur": "beschränkt"},
    "E": {"treibstoff": None,           "kosten_faktor": 0,    "werft": None,             "reparatur": None},
    "X": {"treibstoff": None,           "kosten_faktor": 0,    "werft": None,             "reparatur": None},
}

# --- Kulturelle Eigenheiten (W66-Tabelle, Grundregelwerk) ----------------
KULTUR_W66 = {
    "11": ("Sexistisch", "Ein Geschlecht wird als dem anderen unterlegen betrachtet."),
    "12": ("Religiös", "Die Kultur wird stark von einer Religion oder einem Glaubenssystem geprägt."),
    "13": ("Künstlerisch", "Kunst und Kultur werden hoch geschätzt; ästhetisches Design hat hohen Stellenwert."),
    "14": ("Ritualisiert", "Soziale Interaktion und Handel sind äußerst formalisiert. Höflichkeit ist sehr wichtig."),
    "15": ("Konservativ", "Die Kultur widersetzt sich Veränderungen und Einflüssen von außen."),
    "16": ("Xenophobisch", "Misstrauen gegenüber Außenseitern; Außenweltler erfahren erhebliche Vorurteile."),
    "21": ("Tabu", "Ein bestimmtes Thema ist verboten; wer es erwähnt, wird ausgegrenzt."),
    "22": ("Irreführend", "Betrug und Mehrdeutigkeit gelten als akzeptabel; Ehrlichkeit als Schwäche."),
    "23": ("Liberal", "Veränderungen und Einflüsse von außen sind willkommen; neue Ideen werden begrüßt."),
    "24": ("Ehrenhaft", "Ein Ehrenwort gilt alles; Lügen sind selten und werden verachtet."),
    "25": ("Beeinflusst", "Die Kultur wird stark von einer Nachbarwelt geprägt."),
    "26": ("Fusion", "Eine Vermischung zweier eigenständiger Kulturen (zweimal würfeln)."),
    "31": ("Barbarisch", "Physische Stärke und Kampfkraft werden hoch geschätzt; Sport ist blutig."),
    "32": ("Überbleibsel", "Rest einer einst großen Zivilisation, die sich an vergangenen Ruhm klammert."),
    "33": ("Degeneriert", "Die Kultur zerfällt; Proteste sind alltäglich, die Sozialordnung bröckelt."),
    "34": ("Progressiv", "Die Kultur breitet sich aus, ist sehr lebendig; Handel und Wissenschaft blühen."),
    "35": ("Genesend", "Ein jüngeres Trauma (Seuche, Krieg, Despotie) hat Narben hinterlassen."),
    "36": ("Nexus", "Mitglieder vieler Kulturen und Spezies treffen sich hier."),
    "41": ("Touristenattraktion", "Ein Aspekt der Kultur zieht Besucher aus dem ganzen Raum an."),
    "42": ("Gewalttätig", "Konflikte sind häufig: Duelle, Schlägereien, Gerichtskämpfe."),
    "43": ("Friedlich", "Körperliche Konflikte fast nie; Diplomatie ist extrem wichtig."),
    "44": ("Obsessiv", "Alle sind von einer Substanz, Person oder Sache besessen."),
    "45": ("Mode", "Schöne Kleidung und Schmuck sind von großer Bedeutung."),
    "46": ("Im Krieg", "Die Kultur ist im Krieg oder wird von Rebellen/Terroristen erschüttert."),
    "51": ("Brauch: Außenweltler", "Weltraumreisende haben eine einzigartige Stellung in Mythos/Glaube."),
    "52": ("Brauch: Raumhafen", "Der Raumhafen ist mehr als Handelszentrum (Tempel, kontrovers …)."),
    "53": ("Brauch: Medien", "Nachrichten und Telekommunikation sind auffallend merkwürdig."),
    "54": ("Brauch: Technologie", "Seltsame Interaktion mit Technik (Roboterrechte, Telekomverbot …)."),
    "55": ("Brauch: Lebenszyklus", "Vorgeschriebenes Höchstalter, Klone, ungewöhnliche Familienformen."),
    "56": ("Brauch: Sozialstatus", "Besonderes Kastensystem; Fehlverhalten wird bestraft."),
    "61": ("Brauch: Handel", "Seltsame Wirtschaftsbräuche behindern den Handel im Raumhafen."),
    "62": ("Brauch: Adel", "Seltsame Bräuche für Hochgestellte (goldene Käfige, Exil …)."),
    "63": ("Brauch: Sex", "Ungewöhnliche Einstellung zu Fortpflanzung und Geschlechtsverkehr."),
    "64": ("Brauch: Essen", "Essen und Trinken haben einen besonderen, ritualisierten Platz."),
    "65": ("Brauch: Reisen", "Reisende werden besonders behandelt (gefeiert oder beargwöhnt)."),
    "66": ("Brauch: Verschwörung", "Etwas Merkwürdiges geht vor; die Regierung wird untergraben."),
}

# =====================================================================
#  Namensgenerator (deterministisch; spaeter optional durch LLM ersetzbar)
# =====================================================================
_SIL_A = ["Va", "Re", "Ko", "Mi", "Tar", "Bel", "Dra", "Cor", "Zan", "Lor",
          "Ar", "Sol", "Vel", "Nor", "Kha", "Pa", "Tre", "Gus", "Mar", "Or"]
_SIL_B = ["la", "ron", "ka", "dor", "nis", "tha", "rim", "vos", "len", "gar",
          "mir", "tas", "wen", "dul", "ra", "shan", "tek", "lon", "via", "ux"]

def gen_name(rng: random.Random) -> str:
    name = rng.choice(_SIL_A) + rng.choice(_SIL_B)
    if rng.random() < 0.3:
        name += " " + rng.choice(["Prime", "II", "Major", "Minor", "IV"])
    return name

# =====================================================================
#  Eine Welt erzeugen
# =====================================================================
@dataclass
class Welt:
    hex: str
    name: str
    raumhafen: str
    groesse: int
    atmosphaere: int
    hydrographie: int
    bevoelkerung: int
    regierung: int
    gesetz: int
    techlevel: int
    uwp: str
    handelscodes: list[str]
    basen: list[str]
    reisezone: str
    gasriesen: bool
    zugehoerigkeit: str | None
    temperatur: str | None
    raumhafen_details: dict | None
    kultur: dict | None
    sternendaten: dict | None
    seed: str
    wuerfe: dict


def erzeuge_welt(seed: str, hexcode: str, *, zugehoerigkeit: str | None = "Im") -> Welt:
    rng = random.Random(seed)
    rolls: dict = {}

    # --- Groesse: 2W6-2 ------------------------------------------------
    r = w(rng); rolls["groesse"] = r
    groesse = clamp(r - 2, 0, 10)

    # --- Atmosphaere: 2W6-7 + Groesse ----------------------------------
    r = w(rng); rolls["atmo"] = r
    atmo = clamp(r - 7 + groesse, 0, 15)

    # --- Temperatur: 2W6 + Atmosphaeren-WM -> Band ---------------------
    r = w(rng); rolls["temp"] = r
    temperatur = temperatur_band(r + TEMP_DM_ATMO.get(atmo, 0))

    # --- Hydrographie: 2W6-7 + Groesse, mit DMs ------------------------
    r = w(rng); rolls["hydro"] = r
    if groesse <= 1:
        hydro = 0                                   # zu klein fuer Wasser
    else:
        h = r - 7 + groesse
        if atmo in (0, 1, 10, 11, 12):
            h -= 4
        # Temperatur-WM auf Hydrographie -- nur wenn die Atmosphaere Wasser
        # nicht sicher haelt (Buch: "nicht D, oder eine Art F").  # PRUEFEN
        if atmo not in (13, 15):
            if temperatur == "Heiß":
                h -= 2
            elif temperatur == "Glühend":
                h -= 6
        hydro = clamp(h, 0, 10)

    # --- Bevoelkerung: 2W6-2 -------------------------------------------
    r = w(rng); rolls["bev"] = r
    bev = clamp(r - 2, 0, 10)

    # --- Regierung / Gesetz (0 wenn unbewohnt) -------------------------
    if bev == 0:
        reg = gesetz = 0
        rolls["reg"] = rolls["gesetz"] = None
    else:
        r = w(rng); rolls["reg"] = r
        reg = clamp(r - 7 + bev, 0, 15)
        r = w(rng); rolls["gesetz"] = r
        gesetz = clamp(r - 7 + reg, 0, 18)          # Gesetz kann ueber F hinaus

    # --- Raumhafen: 2W6 ------------------------------------------------
    r = w(rng); rolls["raumhafen"] = r
    raumhafen = raumhafen_aus_wurf(r)

    # --- Tech-Level: 1W6 + DMs (0 wenn unbewohnt) ----------------------
    if bev == 0:
        tl = 0
        rolls["tl"] = None
    else:
        r = w(rng, n=1); rolls["tl"] = r
        dm = (TL_DM_RAUMHAFEN.get(raumhafen, 0)
              + TL_DM_GROESSE.get(groesse, 0)
              + TL_DM_ATMO.get(atmo, 0)
              + TL_DM_HYDRO.get(hydro, 0)
              + TL_DM_BEV.get(bev, 0)
              + TL_DM_REG.get(reg, 0))
        tl = clamp(r + dm, 0, 33)

    # --- Gasriese: vorhanden wenn 2W6 <= 9 -----------------------------
    r = w(rng); rolls["gasriese"] = r
    gasriesen = r <= 9

    # --- Basen ---------------------------------------------------------
    basen: list[str] = []
    rolls["basen"] = {}
    for code, schwellen in BASEN_REGELN.items():
        schwelle = schwellen.get(raumhafen)
        if schwelle is not None:
            br = w(rng); rolls["basen"][code] = br
            if br >= schwelle:
                basen.append(code)

    # --- Raumhafen-Details (Treibstoff, Anlegekosten, Werft) -----------
    raumhafen_details = dict(RAUMHAFEN_DETAILS[raumhafen])
    if raumhafen_details["kosten_faktor"]:
        br = w(rng, n=1); rolls["anlegekosten"] = br
        raumhafen_details["anlegekosten"] = br * raumhafen_details["kosten_faktor"]
    else:
        rolls["anlegekosten"] = None
        raumhafen_details["anlegekosten"] = 0

    # --- Kulturelle Eigenheit: W66 (nur bewohnte Welten) ---------------
    if bev >= 1:
        code66 = f"{rng.randint(1, 6)}{rng.randint(1, 6)}"
        rolls["kultur"] = code66
        kname, kbesch = KULTUR_W66[code66]
        kultur = {"code": code66, "name": kname, "beschreibung": kbesch}
    else:
        rolls["kultur"] = None
        kultur = None

    # --- Werte fuer Trade-Codes buendeln -------------------------------
    werte = dict(groesse=groesse, atmo=atmo, hydro=hydro, bev=bev,
                 reg=reg, gesetz=gesetz, tl=tl)
    handelscodes = [code for code, pred in TRADE_CODES if pred(werte)]

    # --- Reisezone: Amber-Kandidat? ------------------------------------
    amber = (atmo >= 10) or (reg in (0, 7, 10)) or (gesetz == 0) or (gesetz >= 9)
    reisezone = "amber" if amber else "gruen"

    # --- UWP-String ----------------------------------------------------
    uwp = (raumhafen
           + to_ehex(groesse) + to_ehex(atmo) + to_ehex(hydro)
           + to_ehex(bev) + to_ehex(reg) + to_ehex(gesetz)
           + "-" + to_ehex(tl))

    name = gen_name(rng)

    return Welt(
        hex=hexcode, name=name, raumhafen=raumhafen,
        groesse=groesse, atmosphaere=atmo, hydrographie=hydro,
        bevoelkerung=bev, regierung=reg, gesetz=gesetz, techlevel=tl,
        uwp=uwp, handelscodes=handelscodes, basen=basen,
        reisezone=reisezone, gasriesen=gasriesen,
        zugehoerigkeit=zugehoerigkeit,
        temperatur=temperatur,
        raumhafen_details=raumhafen_details,
        kultur=kultur,
        sternendaten=None,                # Erweiterungspunkt (Sterne/Nebenkoerper)
        seed=seed, wuerfe=rolls,
    )

# =====================================================================
#  Subsektor (8 Spalten x 10 Zeilen) und Sektor (4x4 Subsektoren)
# =====================================================================
def hex_code(ss_index: int, lokal_spalte: int, lokal_zeile: int) -> str:
    """Globale 4-stellige Hexnummer im Sektor (Spalten 01-32, Zeilen 01-40)."""
    ss_spalte = ss_index % 4
    ss_zeile = ss_index // 4
    spalte = ss_spalte * 8 + lokal_spalte
    zeile = ss_zeile * 10 + lokal_zeile
    return f"{spalte:02d}{zeile:02d}"


def erzeuge_subsektor(master_seed: str, ss_index: int, *,
                      dichte: str = "normal",
                      zugehoerigkeit: str | None = "Im") -> list[Welt]:
    welten: list[Welt] = []
    dm = DICHTE_DM[dichte]
    for spalte in range(1, 9):
        for zeile in range(1, 11):
            hc = hex_code(ss_index, spalte, zeile)
            seed = f"{master_seed}|{hc}"
            occ = random.Random(seed + "|occ")
            if w(occ, n=1) + dm >= 4:               # Hexbesetzung
                welten.append(erzeuge_welt(seed, hc, zugehoerigkeit=zugehoerigkeit))
    return welten


def erzeuge_sektor(master_seed: str, *, dichte: str = "normal",
                   zugehoerigkeit: str | None = "Im") -> dict[int, list[Welt]]:
    """Liefert {subsektor_index: [Welt, ...]} fuer alle 16 Subsektoren (A-P)."""
    return {i: erzeuge_subsektor(master_seed, i, dichte=dichte,
                                 zugehoerigkeit=zugehoerigkeit)
            for i in range(16)}

# =====================================================================
#  Bruecke zum DB-Schema:  Welt -> dict mit Spaltennamen aus `welt`
# =====================================================================
import json

def welt_zu_row(wlt: Welt, sektor_id: int, subsektor_id: int | None) -> dict:
    """JSON-Felder werden serialisiert; passt 1:1 auf die Spalten in `welt`."""
    return {
        "sektor_id": sektor_id,
        "subsektor_id": subsektor_id,
        "hex": wlt.hex,
        "name": wlt.name,
        "raumhafen": wlt.raumhafen,
        "groesse": wlt.groesse,
        "atmosphaere": wlt.atmosphaere,
        "hydrographie": wlt.hydrographie,
        "bevoelkerung": wlt.bevoelkerung,
        "regierung": wlt.regierung,
        "gesetz": wlt.gesetz,
        "techlevel": wlt.techlevel,
        "uwp": wlt.uwp,
        "handelscodes": json.dumps(wlt.handelscodes),
        "basen": json.dumps(wlt.basen),
        "reisezone": wlt.reisezone,
        "gasriesen": int(wlt.gasriesen),
        "zugehoerigkeit": wlt.zugehoerigkeit,
        "temperatur": wlt.temperatur,
        "raumhafen_details": json.dumps(wlt.raumhafen_details) if wlt.raumhafen_details else None,
        "kultur": json.dumps(wlt.kultur) if wlt.kultur else None,
        "sternendaten": json.dumps(wlt.sternendaten) if wlt.sternendaten else None,
        "seed": wlt.seed,
        "wuerfe": json.dumps(wlt.wuerfe),
    }

# =====================================================================
#  Demo / schnelle Sichtpruefung
# =====================================================================
def print_subsektor(welten: list[Welt]) -> None:
    print(f"{'Hex':<6}{'Name':<16}{'UWP':<11}{'Basen':<14}"
          f"{'Zone':<7}{'GR':<4}Handelscodes")
    print("-" * 78)
    for x in sorted(welten, key=lambda v: v.hex):
        print(f"{x.hex:<6}{x.name:<16}{x.uwp:<11}"
              f"{','.join(x.basen):<14}{x.reisezone:<7}"
              f"{'J' if x.gasriesen else '-':<4}{' '.join(x.handelscodes)}")
    print(f"\n{len(welten)} Welten von 80 Hexen.")


if __name__ == "__main__":
    # Beispiel: ein Subsektor mit normaler Dichte.
    # Tipp: Reft Sektor ist ein Rift -> dichte="rift".
    SEED = "Demo-Sektor-2026"
    welten = erzeuge_subsektor(SEED, ss_index=0, dichte="normal")
    print_subsektor(welten)
