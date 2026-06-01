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
- **Sektor/Welt** (`sektor_generator.py`): vollständige UWP nach MgT2-Regeln,
  gegen das 13Mann-Buch abgeglichen. Temperatur (inkl. Hydro-WM), alle 6
  Basentypen, Gasriese, Reisezone, Raumhafen-Details (Treibstoff, Anlegekosten,
  Werft), kulturelle Eigenheit (W66).
- **Fraktionen** (`faktionen.py`): 1W3 pro bewohnter Welt, Mini-Regierung,
  Stärke, Einstufung Splittergruppe/Opposition.
- **Routen** (`routes.py`): getestete Hexdistanz + Heuristik für
  Kommunikations- und Handelsrouten.

### Darstellung
- **Hexkarte** (`hexmap.py`): SVG, korrekter Subsektor-Versatz, Routen-Layer,
  Basen/Gasriese/Zonen, SPECTRUM-getönt.
- **Detailkarte** (`detailkarte.py`): anklickbare Hexe → bodenverankerte
  Overlay-Card mit dekodierter UWP, Temperatur, Raumhafen-Details, Kultur,
  Handelscodes und den verknüpften NSCs/Aufträgen/Fraktionen.

### App (`app.py`, `db.py`, `persist.py`)
- Flask + SQLite. Übersicht, Sektor generieren, Subsektor-Ansicht aus DB,
  A–P-Navigation, UWP-Export, Sektor löschen.
- `persist.py` schreibt Generator-Output in die Tabellen und hydriert beim
  Laden die JSON-Spalten zurück.

---

## Was noch fehlt (Prep-Werkzeuge)

### 1. NSC-Editor & -Generator  ⭐ nächster Schritt
**Warum zuerst:** Die Detailkarte zeigt NSCs bereits an, sobald sie in der DB
stehen — es fehlt nur das Anlegen. Das ist der kürzeste Weg, den Prep↔Tisch-
Kreis wirklich zu schließen.

- **Generator** (`nsc_generator.py`, neu): schneller NSC (Eigenschaften 2W6,
  Skill-Paket nach Rolle) und/oder voller Lifepath. Seedbar, mit `wuerfe`.
- **Speichern**: `persist.speichere_nsc()`; nutzt vorhandene `nsc`-Tabelle.
- **Verknüpfen**: NSC ↔ Welt (FK), NSC ↔ Fraktion über `nsc_fraktion`
  inkl. `geheim`-Checkbox → erscheint als rotes Badge in der Card.
- **UI**: Routen `GET/POST /welt/<id>/nsc/neu`, `GET/POST /nsc/<id>`
  (Bearbeiten, inkl. dem Freitext-`notizen`-Feld, das am Tisch wächst).
  Neues Template `nsc_form.html`.
- **Card-Hook**: in `detailkarte.py` einen „+ NSC“-Knoten im NSCs-Abschnitt.

### 2. Auftrags-/Patron-Generator
- **Generator** (`auftrag_generator.py`, neu): die 6×6-Patron-Tabellen
  (Auftraggeber, Ziel, Komplikation, Wendung, Belohnung).
- **Speichern**: `auftrag`-Tabelle steht schon; `patron_nsc_id`, `welt_id`,
  `fraktion_id` als FKs setzen → Auftrag wird zum Knoten, der NSC/Welt/Fraktion
  zusammenzieht.
- **UI**: `/welt/<id>/auftrag/neu`, Statuswechsel
  (offen→aktiv→abgeschlossen/gescheitert) direkt aus der Card.

### 3. Fraktionen editierbar machen
- Aktuell nur generiert/angezeigt. Fehlt: bearbeiten (Ziele, Einfluss, Notizen),
  manuell anlegen, NSCs zuordnen. Routen `/fraktion/<id>`.
- Optional: sektorweite Fraktionen (`reichweite='interstellar'`,
  Einflusssphäre über `verknuepfung` statt nur `heimatwelt_id`).

### 4. Sektor-/Welt-Editor (Überschreiben von Würfen)
- Einzelne Welt **neu würfeln** (Sub-Seed neu) oder Felder von Hand
  überschreiben — Welt umbenennen, Reisezone auf „rot“ setzen, UWP-Ziffer ändern.
- Subsektoren benennen (`subsektor.name` existiert, wird noch nicht genutzt).
- Welt von Hand in leeren Hex setzen.

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

- **Doppelte SPECTRUM-Tokens**: einmal in `static/spectrum.css` (Übersicht),
  einmal inline in `detailkarte.py` (Subsektor-Ansicht). Sollte in *eine*
  CSS-Datei zusammengeführt werden, sobald die Subsektor-Ansicht ein echtes
  Jinja-Template wird (statt einem großen Python-String).
- **Subsektor-Ansicht → Jinja-Template**: `detailkarte.render_app` baut HTML als
  String. Für Wartbarkeit perspektivisch in `templates/subsektor.html` + ein
  schlankes SVG-Fragment überführen.
- **Routen subsektorübergreifend**: aktuell nur innerhalb eines Subsektors
  gezeichnet. Grenzüberschreitende Routen brauchen Rendering über
  Subsektor-Kanten hinweg (oder eine Sektor-Gesamtansicht).
- **Handelscodes**: intern kanonisch (englisch), Anzeige deutsch. Falls strikt
  Buch-Codes gewünscht — Mapping `CODE_DE` in `sektor_generator.py` umlegen.
- **Tests**: bisher nur die Hexdistanz hat einen Selbsttest. Generatoren
  könnten Smoke-Tests (Verteilungen plausibel, JSON serialisierbar) gebrauchen.

---

## Vorgeschlagene Reihenfolge

1. **NSC-Editor & -Generator** (1) — schließt den Prep↔Tisch-Kreis sichtbar.
2. **Auftrags-Generator** (2) — macht Welten zu Abenteuer-Ausgangspunkten.
3. **Würfler** (6) — kleiner, sofort am Tisch nützlicher Gewinn.
4. **Reiseplaner** (7) + **Handelsrechner** (8) — bauen auf vorhandener Logik
   (Distanz, Trade-Codes) auf und ergeben zusammen den „Schiff-unterwegs“-Loop.
5. Danach: Fraktions-/Welt-Editoren (3, 4), Sternendaten (5), Begegnungen (9),
   Kampagnen-Tooling (10).

Parallel laufend: technische Schuld abbauen, sobald ein Bereich ohnehin
angefasst wird (z. B. CSS zusammenführen, wenn die Subsektor-Ansicht zum
Template wird).
