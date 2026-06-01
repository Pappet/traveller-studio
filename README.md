# Traveller Studio

Lokales Spielleiter-Werkzeug für **Mongoose Traveller 2e** (13Mann-Ausgabe).
Generiert Sektoren regelbasiert, speichert sie in SQLite und zeigt eine
anklickbare Hexkarte mit Detailkarte – im SPECTRUM-Look.

## Start

```bash
pip install flask
python app.py
```

Dann im Browser: **http://127.0.0.1:5000**

> Hinweis: Die Oberfläche lädt die Schriften (Manrope / Space Grotesk /
> JetBrains Mono) von Google Fonts. Ohne Internet fällt sie auf System­schriften
> zurück – Layout und Farben bleiben identisch.

## Bedienung

1. **Übersicht** – Name, optionalen Seed und Dichte angeben → *Generieren*.
   (Gleicher Seed ⇒ exakt gleicher Sektor. Leerer Seed ⇒ zufällig.)
2. **Subsektor-Ansicht** – Hexkarte mit Welten, Basen, Gasriesen, Reisezonen
   und Kommunikations-/Handelsrouten. Oben A–P zum Umschalten der Subsektoren.
3. **Welt anklicken** → Detailkarte mit dekodierter UWP, Temperatur,
   Raumhafen-Details, Kultur, Handelscodes und den verknüpften
   NSCs / Aufträgen / Fraktionen.
4. **UWP-Export** – Subsektor als lesbares Textlisting (oben rechts).

## Was generiert wird

Pro bewohnter Welt: vollständige UWP (Größe, Atmosphäre, Temperatur,
Hydrographie, Bevölkerung, Regierung, Justizgrad, Tech-Level), Handelscodes,
alle sechs Basentypen, Gasriese, Reisezone, Raumhafen-Details (Treibstoff,
Anlegekosten, Werft), eine kulturelle Eigenheit (W66) und **1W3 Fraktionen**
mit Mini-Regierung, Stärke und Einstufung (Splittergruppe / Opposition).
Dazu Routen zwischen nahen, wichtigen bzw. komplementären Welten.

## Aufbau

```
app.py             Flask-Routen (Übersicht, Generieren, Ansicht, Export, Löschen)
db.py              SQLite-Verbindung pro Request (+ Auto-Init des Schemas)
persist.py         Generierung → DB schreiben; DB → laden & JSON hydrieren
schema.sql         Datenmodell (Sektor/Welt/NSC/Fraktion/Auftrag/Route/…)

sektor_generator.py  Regelbasierte Welt-/Sektorgenerierung (seedbar)
faktionen.py         Fraktionsgenerator
routes.py            Hexdistanz + Routen-Heuristik
hexmap.py            SVG-Hexkarte
detailkarte.py       Interaktive Seite (Karte + Detail-Overlay-Card)

templates/         base.html, index.html (Übersicht)
static/            spectrum.css (Tokens + Komponenten der Übersicht)
traveller.db       SQLite-Datei (wird beim ersten Start angelegt)
```

Die Datei `traveller.db` enthält bereits einen **Demo-Sektor** („Testsektor").
Über *Löschen* auf der Übersicht entfernbar.

## Hinweise & Grenzen (v0.1)

- Routen werden je Subsektor erzeugt (keine subsektorübergreifenden Linien)
  und sind eine bewusste **Heuristik** – das Regelwerk definiert keinen harten
  Routen-Algorithmus.
- Handelscodes werden intern als kanonische (englische) Codes geführt
  (Kompatibilität zu Traveller Map / fertigen Sektordateien); die Detailkarte
  zeigt die deutschen Namen.
- NSCs und Aufträge werden noch nicht generiert; die Detailkarte zeigt sie
  bereits an, sobald sie in der DB stehen. Ein Editor dafür ist der nächste
  sinnvolle Schritt.
- Stellen, die gegen das Buch abgeglichen werden sollten, sind im Code mit
  `# PRUEFEN` markiert (v. a. Temperatur-Atmosphären-WM).
```
