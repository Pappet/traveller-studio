# Traveller Studio — Roadmap
Lokales Spielleiter-Werkzeug für **Mongoose Traveller 2e** (13Mann).
Stand dieses Dokuments: Ende der ersten Aufbauphase (Generatoren + Karte +
Detailkarte + Flask/SQLite-Persistenz laufen).

---

## Leitprinzipien (gelten für alles Folgende)

Diese Entscheidungen sind das Fundament — neue Features sollen sie respektieren:

1. **Generatoren sind reine, seedbare Funktionen.** Gleicher Seed ⇒ gleiches
   Ergebnis. Jede Welt hat einen eigenen Sub-Seed (`master_seed|hex`), damit
   Einzel-Neuwürfe die Nachbarn nicht verschieben. Mechanik ist deterministisch;
   Flavour (Namen, Beschreibungen) darf später optional an ein lokales LLM gehen.
2. **Prep ↔ Tisch ist keine Datengrenze, sondern zwei Sichten auf denselben
   Bestand.** Generierte Entität = gespeicherte DB-Zeile mit stabiler ID.
3. **Abfragbares → eigene Spalte, Variables/Abgeleitetes → JSON.**
4. **Entwurf bleibt außerhalb der DB** — erst „Behalten“ schreibt eine Zeile.
5. **Backbone = echte Fremdschlüssel, weiche Querverweise = Graph**
   (`verknuepfung`-Tabelle, polymorph).
6. **SPECTRUM-Look** durchgängig (dunkle Fläche, Farbe nur für Bedeutung,
   Mono-Lockups für Daten, Nicht-Farb-Signale wie Strichelung).

---

## Kampagnen-zentrierte Architektur (✅ umgesetzt)

`Kampagne` ist jetzt die Wurzel (1 Kampagne : n Sektoren); NSC/Fraktion/Auftrag
tragen direkt `kampagne_id`. Startseite = Kampagnen-Liste, darunter ein
Kampagnen-Dashboard (Sektoren/NSC/Fraktion/Auftrag) mit eigenständigen Editoren.
NSC-Orte unterscheiden **Aufenthalt** (`nsc.aufenthalt_welt_id`, treibt die Karte)
und **Herkunft** (`verknuepfung`-Graph, `relation='stammt_von'`); die Detailkarte
gruppiert NSCs nach „hier ansässig / stammt von hier / wirkt hier". Der
Fraktions-Picker ist eine Kaskade (Subsektor▸Hex▸Fraktion) plus Suche statt
Flachliste. Konzept + Plan unter `docs/superpowers/`.

---

## Was steht (✅ implementiert)

### Datenmodell (`schema.sql`)
- Backbone `sektor → subsektor → welt`, dazu `nsc`, `fraktion`, `auftrag`.
- `nsc_fraktion` als n:m **mit `geheim`-Flag** (Doppelagenten).
- `route` (ungerichtet via `welt_a_id < welt_b_id`, `auto`-Flag trennt
  generierte von handgezeichneten Routen).
- `verknuepfung` (polymorpher Graph für alles Weiche).
- `welt` führt UWP-Komponenten als Einzelspalten + JSON-Felder
  (`handelscodes`, `basen`, `raumhafen_details`, `kultur`, `sternendaten`).

### Generatoren
- **Sektor/Welt** (`app/generators/sektor.py`): vollständige UWP nach MgT2-Regeln,
  gegen das 13Mann-Buch abgeglichen. Temperatur (inkl. Hydro-WM), alle 6
  Basentypen, Gasriese, Reisezone, Raumhafen-Details (Treibstoff, Anlegekosten,
  Werft), kulturelle Eigenheit (W66).
- **Fraktionen** (`app/generators/faktionen.py`): 1W3 pro bewohnter Welt, Mini-Regierung,
  Stärke, Einstufung Splittergruppe/Opposition.
- **Routen** (`app/generators/routen.py`): getestete Hexdistanz + Heuristik für
  Kommunikations- und Handelsrouten.

### Darstellung
- **Hexkarte** (`app/rendering/hexmap.py`): SVG, korrekter Subsektor-Versatz, Routen-Layer,
  Basen/Gasriese/Zonen, SPECTRUM-getönt.
- **Detailkarte** (`app/templates/sektor/subsektor.html`): anklickbare Hexe → bodenverankerte
  Overlay-Card mit dekodierter UWP, Temperatur, Raumhafen-Details, Kultur,
  Handelscodes und den verknüpften NSCs/Aufträgen/Fraktionen.

### App (`app/__init__.py`, `app/blueprints/`, `app/db.py`, `app/persist.py`)
- Flask + SQLite, als `app/`-Package mit `create_app()`-Factory und Blueprints
  (`main`, `sektor`). Übersicht, Sektor generieren, Subsektor-Ansicht aus DB,
  A–P-Navigation, UWP-Export, Sektor löschen.
- `app/persist.py` schreibt Generator-Output in die Tabellen und hydriert beim
  Laden die JSON-Spalten zurück.

---

## Prep-Werkzeuge

### 1. NSC-Editor & -Generator  ✅ *erledigt*
- **Generator** (`app/generators/nsc.py`): schneller NSC (Eigenschaften 2W6,
  Skill-Paket nach Archetyp, leichte Laufbahn). Seedbar, mit `wuerfe`.
- **Speichern**: `persist.speichere_nsc()` über die `nsc`-Tabelle.
- **Verknüpfen**: NSC ↔ Welt (FK), NSC ↔ Fraktion über `nsc_fraktion`
  inkl. `geheim`-Flag → rotes Badge in der Card.
- **UI**: `GET/POST /welt/<id>/nsc/neu`, `GET/POST /nsc/<id>`, Freitext-`notizen`,
  Template `app/templates/nsc_form.html`, „+ NSC“-Knoten in der Detailkarte.

### 2. Auftrags-/Patron-Generator  ✅ *erledigt*
- **Generator** (`app/generators/auftrag.py`): 6×6-Tabellen
  (Auftraggeber, Ziel, Komplikation, Wendung, Belohnung).
- **Speichern**: `auftrag`-Tabelle mit `patron_nsc_id`, `welt_id`, `fraktion_id`
  als FKs → Auftrag zieht NSC/Welt/Fraktion zusammen.
- **UI**: `/welt/<id>/auftrag/neu`, Statuswechsel
  (offen→aktiv→abgeschlossen/gescheitert) aus der Card.

### 3. Fraktionen editierbar machen  ✅ *erledigt*
- Bearbeiten (Ziele, Einfluss, Notizen), manuell anlegen, Mitgliederliste,
  Routen `/welt/<id>/fraktion/neu`, `/fraktion/<id>`. `reichweite` (lokal/
  interstellar) wählbar.
- Offen: sektorweite Einflusssphäre über `verknuepfung` statt nur `heimatwelt_id`.

### 4. Sektor-/Welt-Editor (Überschreiben von Würfen)  ✅ *erledigt*
- Welt **neu würfeln** (neuer Sub-Seed) oder Felder von Hand überschreiben
  (uwp + Handelscodes werden neu berechnet, Reisezone als manueller Override).
- Subsektoren benennen, Welt von Hand in leeren Hex setzen.

### 5. Generatoren-Restpunkte aus dem Regelwerk
- **Temperatur-Atmosphären-WM** final gegen das Buch prüfen (Code: `# PRUEFEN`).
- **Sternendaten** (Sterntyp, Nebenkörper) — Feld `sternendaten` ist vorbereitet,
  Generator fehlt.
- **Raumhafen-Details** um Anlegekosten-Varianten / Servicelevel erweitern.

---

## Was noch fehlt (Spieltisch-Werkzeuge)

### 6. Würfler mit Task-System
- 2W6 + Eigenschaft + Skill gegen Schwierigkeit, **Effect = Wurf − 8**
  automatisch. Boon/Bane (3W6 bestes/schlechtestes Paar).
- Klein, eigenständig; kann als JS-Komponente in die Subsektor-Ansicht oder
  als eigene Seite.

### 7. Reise-/Sprungplaner
- Route über die Hexkarte, Distanz in Parsec (`routes.hex_distance` steht
  schon), Treibstoff (10 % Rumpf pro Parsec), 1 Woche pro Sprung.
- Baut direkt auf der vorhandenen Distanz- und Routenlogik auf.

### 8. Handelsrechner
- Kauf-/Verkaufs-DMs aus Trade-Codes, Spekulationsfracht, Passagiere/Fracht,
  Makler-Probe. Nutzt `welt.handelscodes` + Raumhafen-Details.
- **Killer-Feature** für Traveller, hoch automatisierbar.

### 9. Begegnungen
- Tier-/Patron-/Gerüchte-Tabellen je Welt/Gelände; Sprungraum-Begegnungen.

### 10. Kampagnen-Persistenz / Session-Tooling
- Session-Logbuch, Imperialer Kalender/Zeitleiste.
- **Brücke zum `llm_wiki`**: Session-Notizen ↔ Wiki-Einträge.
- Spielerfiguren-Verwaltung (volle Charakterbögen).

---

## Technische Schuld / Aufräumen

- ~~**Doppelte SPECTRUM-Tokens**~~ *(erledigt)*: in eine `app/static/spectrum.css`
  zusammengeführt; die Subsektor-Ansicht ist jetzt ein echtes Jinja-Template.
- ~~**Subsektor-Ansicht → Jinja-Template**~~ *(erledigt)*: jetzt
  `app/templates/sektor/subsektor.html` + SVG-Fragment statt Python-String.
- **Routen subsektorübergreifend**: aktuell nur innerhalb eines Subsektors
  gezeichnet. Grenzüberschreitende Routen brauchen Rendering über
  Subsektor-Kanten hinweg (oder eine Sektor-Gesamtansicht).
- **Handelscodes**: intern kanonisch (englisch), Anzeige deutsch. Falls strikt
  Buch-Codes gewünscht — Mapping `CODE_DE` in `app/generators/sektor.py` umlegen.
- **Tests**: Smoke-Tests für die Kern-Routen vorhanden (`tests/`, via
  `TestingConfig`). Die Generatoren könnten zusätzlich eigene Smoke-Tests
  (Verteilungen plausibel, JSON serialisierbar) gebrauchen.

---

## Vorgeschlagene Reihenfolge

1. ~~NSC-Editor (1), Auftrags-Generator (2), Fraktions- & Welt-Editor (3, 4)~~
   *(erledigt — Prep↔Tisch-Kreis geschlossen)*.
2. **Würfler** (6) — kleiner, sofort am Tisch nützlicher Gewinn.
3. **Reiseplaner** (7) + **Handelsrechner** (8) — bauen auf vorhandener Logik
   (Distanz, Trade-Codes) auf und ergeben zusammen den „Schiff-unterwegs“-Loop.
4. Danach: Sternendaten (5), Begegnungen (9), Kampagnen-Tooling (10).

Parallel laufend: technische Schuld abbauen, sobald ein Bereich ohnehin
angefasst wird (z. B. CSS zusammenführen, wenn die Subsektor-Ansicht zum
Template wird).
