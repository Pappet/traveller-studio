"""
Traveller Auftrags-/Patron-Generator  ·  Mongoose Traveller 2e (13Mann)
=======================================================================

Erzeugt einen Abenteuer-Aufhänger aus 6×6-Tabellen: WER beauftragt (Auftraggeber),
WAS soll getan werden (Ziel), WAS geht schief (Komplikation), die unerwartete
WENDUNG und die BELOHNUNG. Jede Tabelle wird mit zwei W6 angesprochen
(Zeile = Kategorie, Spalte = konkrete Ausprägung) -> 36 Einträge je Tabelle.

Das Grundregelwerk verweist beim Thema Patron auf eigene Tabellen; die hier
hinterlegten sind eine kohärente, eigenständige Sammlung im selben Geist
(bewusst Heuristik/Flavour, keine wörtliche Buchregel).

Deterministisch & seedbar. Nur Standardbibliothek. Ausgabe = dict, dessen
Schlüssel zu den Spalten der `auftrag`-Tabelle passen (über auftrag_zu_row).
"""

from __future__ import annotations
import random
import json

from .sektor import w


def _zelle(rng: random.Random, tabelle: list[list[str]]) -> tuple[str, int, int]:
    """Wirft Zeile+Spalte (je 1W6) und liest den Eintrag."""
    zeile = rng.randint(0, 5)
    spalte = rng.randint(0, 5)
    return tabelle[zeile][spalte], zeile + 1, spalte + 1


# =====================================================================
#  6×6-Tabellen  (Zeile = Kategorie, Spalte = Ausprägung)
# =====================================================================
AUFTRAGGEBER_KAT = ["Regierung", "Konzern", "Unterwelt", "Privatperson", "Adel/Militär", "Mysteriös"]
AUFTRAGGEBER = [
    ["ein lokaler Gouverneur", "die Zollbehörde", "ein Geheimdienst", "ein Diplomat", "ein Steuerfahnder", "die planetare Marine"],
    ["ein Handelshaus", "ein Bergbaukonzern", "eine Reederei", "ein Pharmakonzern", "ein Medienkonzern", "ein Werftbetreiber"],
    ["ein Schmugglerring", "ein Pirat", "ein Hehler", "ein Bandenboss", "ein Auftragskiller", "ein Schwarzmarkthändler"],
    ["ein reicher Exzentriker", "eine verzweifelte Familie", "ein Forscher", "ein pensionierter Soldat", "eine Künstlerin", "eine Pilgerin"],
    ["eine Adelsfamilie", "ein Söldnerkommandant", "ein abtrünniger Offizier", "ein Ritter", "eine Baronin", "eine Veteranengilde"],
    ["ein verschleierter Mittelsmann", "der Vertreter einer KI", "ein religiöser Orden", "ein fremdartiger Gesandter", "ein anonymer Auftraggeber", "ein Geheimbund"],
]

ZIEL_KAT = ["Transport", "Bergung", "Schutz", "Beschaffung", "Ermittlung", "Beseitigung"]
ZIEL = [
    ["Fracht liefern", "einen Passagier eskortieren", "einen Gefangenen überstellen", "Daten schmuggeln", "Hilfsgüter bringen", "ein Artefakt transportieren"],
    ["ein verschollenes Schiff finden", "eine Person aufspüren", "ein Artefakt bergen", "ein Wrack plündern", "Beweise sichern", "einen Schatz heben"],
    ["eine Person beschützen", "einen Konvoi sichern", "eine Anlage verteidigen", "einen Zeugen bewachen", "eine Sabotage verhindern", "eine Räumung decken"],
    ["einen Prototyp stehlen", "Dokumente entwenden", "eine Probe sammeln", "eine Geisel befreien", "eine Warenlieferung abfangen", "eine Quelle anzapfen"],
    ["ein Verschwinden aufklären", "einen Spion enttarnen", "Korruption beweisen", "ein Phänomen untersuchen", "einen Mord aufklären", "ein Leck finden"],
    ["ein Ziel ausschalten", "eine Anlage sabotieren", "eine Bedrohung neutralisieren", "Beweise vernichten", "einen Rivalen verdrängen", "einen Aufstand niederschlagen"],
]

KOMPLIKATION_KAT = ["Gegenspieler", "Behörde", "Technik", "Soziales", "Umwelt", "Zeitdruck"]
KOMPLIKATION = [
    ["ein Konkurrenzteam", "ein Kopfgeldjäger", "ein korrupter Beamter", "eine Rivalenfraktion", "ein eifersüchtiger Ex-Partner", "ein Doppelagent"],
    ["eine Zollkontrolle", "eine Reisesperre", "eine Quarantäne", "ein Embargo", "eine laufende Fahndung", "ein Lizenzentzug"],
    ["ein Schiffsschaden", "Treibstoffmangel", "ein Navigationsfehler", "ein Kommunikationsausfall", "defekte Ausrüstung", "eine Sprungverzögerung"],
    ["der Auftraggeber lügt", "das Ziel ist unschuldig", "Verrat im Team", "eine Erpressung", "eine falsche Identität", "ein moralisches Dilemma"],
    ["Sturm und Strahlung", "feindliche Fauna", "unwirtliches Gelände", "eine Seuche", "eine Naturkatastrophe", "ein Piratenrevier"],
    ["eine knappe Frist", "ein Wettlauf gegen Rivalen", "ein ablaufendes Ultimatum", "eine kollabierende Lage", "verderbende Beweise", "eine Geisel in akuter Gefahr"],
]

WENDUNG_KAT = ["Identität", "Verrat", "Wahrheit", "Drittpartei", "Eskalation", "Moral"]
WENDUNG = [
    ["der Auftraggeber ist nicht, wer er vorgibt", "das Ziel ist ein alter Verbündeter", "ein Totgeglaubter lebt", "ein Doppelgänger ist im Spiel", "eine verborgene Verwandtschaft", "eine KI tarnt sich als Mensch"],
    ["der Auftraggeber will die Gruppe loswerden", "die Bezahlung ist eine Falle", "ein NSC wechselt die Seite", "die Ware ist nur ein Köder", "der Verbündete ist ein Spion", "die Belohnung ist selbst gestohlen"],
    ["die Mission ist illegal", "das Ziel ist Opfer, nicht Täter", "ein unsichtbarer Drahtzieher zieht die Fäden", "die Fracht ist hochgefährlich", "alles war nur ein Test", "die Wahrheit ist brisanter als gedacht"],
    ["eine dritte Fraktion mischt sich ein", "das Imperium beobachtet alles", "Piraten haben dieselbe Beute im Visier", "ein Konzern zieht im Hintergrund die Fäden", "die Lokalen leisten Widerstand", "ein Rivale kommt zuvor"],
    ["die Sache ist viel größer als angenommen", "Kollateralschaden droht", "ein Krieg hängt daran", "eine Seuche breitet sich aus", "die Beweise belasten Mächtige", "ein zweites Ziel taucht auf"],
    ["die Belohnung ist Blutgeld", "Unschuldige geraten zwischen die Fronten", "der „Bösewicht“ hat gute Gründe", "die Gruppe wird benutzt", "Schweigen wird teuer erkauft", "Gewissen steht gegen Profit"],
]

BELOHNUNG_KAT = ["Bargeld", "Ausrüstung", "Schiff", "Information", "Beziehung", "Status"]
BELOHNUNG = [
    ["Cr. 5.000", "Cr. 10.000", "Cr. 25.000", "Cr. 50.000", "Cr. 100.000", "Cr. 250.000"],
    ["eine Waffenkiste", "Schutzanzüge", "ein Medikit-Vorrat", "ein Werkzeugsatz", "eine Drohne", "ein Bodenfahrzeug"],
    ["freier Treibstoff", "freie Reparatur", "ein Frachtanteil", "Liegeplatzrechte", "ein Schiffsmodul", "ein lukrativer Frachtkontrakt"],
    ["eine seltene Sternenkarte", "kompromittierende Daten", "Forschungsdaten", "eine geheime Schmugglerroute", "ein Codeschlüssel", "der Standort eines Wracks"],
    ["ein wertvoller Kontakt", "ein dauerhafter Verbündeter", "ein Gefallen der Regierung", "eine Mitgliedschaft", "Fürsprache beim Adel", "der Schutz einer Fraktion"],
    ["Landrechte", "ein Adelstitel", "eine begehrte Lizenz", "eine Amnestie", "eine Auszeichnung", "Aufnahme in eine Gilde"],
]


# =====================================================================
#  Hauptfunktion
# =====================================================================
def erzeuge_auftrag(seed: str) -> dict:
    """Erzeugt einen Auftrag/Patron-Aufhänger als dict."""
    rng = random.Random(seed)
    rolls: dict = {}

    auftraggeber, az, asp = _zelle(rng, AUFTRAGGEBER)
    rolls["auftraggeber"] = [az, asp]
    ziel, zz, zsp = _zelle(rng, ZIEL)
    rolls["ziel"] = [zz, zsp]
    komplikation, kz, ksp = _zelle(rng, KOMPLIKATION)
    rolls["komplikation"] = [kz, ksp]
    wendung, wz, wsp = _zelle(rng, WENDUNG)
    rolls["wendung"] = [wz, wsp]
    belohnung, bz, bsp = _zelle(rng, BELOHNUNG)
    rolls["belohnung"] = [bz, bsp]

    typ = ZIEL_KAT[zz - 1]
    titel = ziel[0].upper() + ziel[1:]                      # "Fracht liefern" -> "Fracht liefern"
    beschreibung = (f"Auftrag: {ziel}. Auftraggeber ist {auftraggeber}. "
                    f"Im Weg steht {komplikation} — und {wendung}.")

    return {
        "titel": titel,
        "typ": typ,
        "auftraggeber": auftraggeber,
        "ziel": ziel,
        "komplikation": komplikation.capitalize(),
        "wendung": wendung.capitalize(),
        "belohnung": belohnung,
        "beschreibung": beschreibung,
        "seed": seed,
        "wuerfe": rolls,
    }


def auftrag_zu_row(auf: dict, *, welt_id: int | None = None,
                   patron_nsc_id: int | None = None,
                   fraktion_id: int | None = None) -> dict:
    """Mappt ein Auftrags-dict auf die Spalten der `auftrag`-Tabelle."""
    return {
        "titel": auf["titel"],
        "typ": auf["typ"],
        "belohnung": auf["belohnung"],
        "komplikation": auf["komplikation"],
        "wendung": auf["wendung"],
        "welt_id": welt_id,
        "patron_nsc_id": patron_nsc_id,
        "fraktion_id": fraktion_id,
        "notizen": f"Auftraggeber: {auf['auftraggeber']}\n{auf['beschreibung']}",
        "seed": auf["seed"],
        "wuerfe": json.dumps(auf["wuerfe"]),
    }


# =====================================================================
#  Demo
# =====================================================================
if __name__ == "__main__":
    for i in range(6):
        a = erzeuge_auftrag(f"Demo-Auftrag|{i}")
        print(f"[{a['typ']}] {a['titel']}  →  Belohnung: {a['belohnung']}")
        print(f"   {a['beschreibung']}\n")
