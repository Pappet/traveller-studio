# Kampagnen-zentrierte Architektur — Konzept

**Datum:** 2026-06-02
**Status:** Konzept (Zielarchitektur, noch keine Implementierungsreihenfolge fixiert)
**Auslöser:** Fraktions-Zuordnung im NSC-Formular ist eine endlose Flachliste
aller Sektor-Fraktionen. Daraus erwuchs die größere Frage: NSC-Orte (Herkunft
vs. Aufenthalt), eigenständige Editoren, und ob das Werkzeug **kampagnen-zentriert**
werden soll.

## Ziel

`Kampagne` wird die Wurzel des Datenmodells. Sektoren, NSCs, Fraktionen und
Aufträge gehören zu einer Kampagne. Die Kampagne wird der zentrale Container,
durch den der Spielleiter navigiert. NSCs lassen sich eigenständig anlegen
(losgelöst vom Welt-Einstieg) und Orten zuweisen — mit Unterscheidung von
**Herkunft** und **aktuellem Aufenthalt**. Die Hexkarte zeigt beim Hex-Klick,
welche NSCs dort verortet sind.

## Leitprinzipien (bestehend, gelten weiter)

- Generatoren bleiben rein & seedbar. Kampagnen-Logik berührt sie nicht.
- **Backbone = echte Fremdschlüssel, weiche Querverweise = Graph** (`verknuepfung`).
  Orte eines NSC sind teils Backbone (Aufenthalt), teils Graph (Herkunft/„wirkt in").
- Abfragbares → eigene Spalte, Variables/Abgeleitetes → JSON.
- SPECTRUM-Look durchgängig.

---

## 1. Datenmodell

### Neue Tabelle
```sql
CREATE TABLE kampagne (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    notizen     TEXT,
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Geänderte Fremdschlüssel (Backbone)
- `sektor.kampagne_id` → `NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE`.
  Sektor gehört zu **genau einer** Kampagne (1 Kampagne : n Sektoren).
- `nsc.kampagne_id` → `NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE`.
  **Direkt** — damit ein unverorteter/schiffsgebundener NSC trotzdem in der
  Kampagne sichtbar bleibt, nicht nur transitiv über Welt→Sektor.
- `fraktion.kampagne_id` und `auftrag.kampagne_id` → analog `NOT NULL … CASCADE`
  (Symmetrie: auch ortsfreie Fraktionen/Aufträge gehören sichtbar zur Kampagne).
- `nsc.welt_id` → **umbenannt** `aufenthalt_welt_id`
  (`REFERENCES welt(id) ON DELETE SET NULL`). Bedeutung: *aktueller Aufenthalt*.
  Treibt die Standard-Anzeige auf der Hexkarte.

**Lösch-Verhalten:** Kampagne löschen → kaskadiert auf Sektoren (→ Welten →
NSCs/Aufträge) und direkt auf NSCs/Fraktionen/Aufträge der Kampagne. Welt löschen
(z. B. Sektor neu generieren) → `aufenthalt_welt_id` wird NULL, NSC überlebt in
der Kampagne.

### Orte über den Graph (`verknuepfung`, kein Schemawechsel nötig)
- Herkunft: `von_typ='nsc', zu_typ='welt', relation='stammt_von'`.
- Weitere Relationen: `'wirkt_in'`, `'versteckt_auf'`, ggf. `'befindet_sich_auf'`
  (Schiff/Station als eigener Typ später).
- `verknuepfung` ist bewusst ohne FK (Dangling möglich, per App-Logik aufräumen).

### Keine Migration
DB enthält nur Testdaten → `schema.sql` ändern, `traveller.db` löschen, frisch
generieren. Kein Migrationscode.

---

## 2. Navigation & Editor-Topologie

- **Startseite (`/`)** = Kampagnen-Liste: anlegen, auswählen, löschen.
  Die heutige Sektor-Übersicht rutscht unter die Kampagne.
- **Kampagnen-Dashboard (`/kampagne/<id>`)** = Hub mit vier Listen:
  **Sektoren · NSCs · Fraktionen · Aufträge**. Jede Zeile editierbar/anklickbar.
- **Eigenständige Editoren:** NSC/Fraktion/Auftrag erreichbar aus dem Dashboard,
  nicht mehr nur über eine Welt. Ort-Zuweisung wird **optional**.

**Zwei gültige Einstiegswege:**
1. *Von der Karte:* Hex klicken → „+ NSC hier" (setzt `aufenthalt_welt_id` vor).
2. *Aus dem Dashboard:* „+ NSC" (kampagnenweit, Ort optional, per Picker nachreichbar).

**Kampagnen-Kontext** wird über die FKs aufgelöst und durchgereicht. Alle
Editoren-Listen (Fraktions-Picker, NSC-Auswahl, Patron-Auswahl) **filtern immer
auf die aktive Kampagne** — das allein schrumpft viele Listen.

### NSC-Editor (entschieden: Dashboard-Liste + Detail)
- Dashboard hat eine NSC-Liste (alle NSCs der Kampagne, filter-/suchbar).
- Klick → Detail-Editor. Ort-Zuweisung (Aufenthalt + Herkunft) ist ein Feld
  im Editor (optional, per Picker, s. Abschnitt 3).
- Karten-Einstieg bleibt zusätzlich erhalten.

---

## 3. Fraktions-Picker (ursprünglicher Schmerzpunkt)

Heute flache Liste **aller** Sektor-Fraktionen → endlos. Dreifach entschärft:

1. **Scope = Kampagne** statt Sektor.
2. **Kaskade** als Standard-Pfad: `Subsektor ▸ Hex/Welt ▸ Fraktionen dort`
   (`fraktion.heimatwelt_id = gewählte Welt`). Nur Welten mit Fraktionen erscheinen.
3. **Suchfeld** daneben: filtert **alle** Kampagnen-Fraktionen (fängt interstellare
   / ortsferne, die an keinem Hex hängen).

**Gewählte Fraktionen als Chips oben**, bleiben sichtbar während des Browsens.
Pro Zuordnung wie bisher: `Rolle` + `geheim`-Flag.

---

## 4. Hexkarte

Hex-Klick zeigt heute nur NSCs mit `welt_id = W`. Neu nach Relation gruppiert:
- **„Hier ansässig"** — `aufenthalt_welt_id = W`.
- **„Stammt von hier"** — `verknuepfung relation='stammt_von'`.
- **„Wirkt hier"** — `relation='wirkt_in'`.

Je Relation ein Abschnitt/Badge in der Detailkarte. Ein NSC darf mehrfach
auftauchen (stammt von hier + wohnt woanders) — gewollt, macht Orts-Bezüge sichtbar.

Query „wer ist an Welt W?": Vereinigung aus `aufenthalt_welt_id = W` und
`verknuepfung WHERE von_typ='nsc' AND zu_typ='welt' AND zu_id = W`.

---

## 5. Vorgeschlagene Build-Reihenfolge (Decomposition)

Zu groß für eine einzelne Implementierung — in unabhängig lieferbare Phasen geteilt.
Jede Phase bekommt später ihren eigenen Plan.

- **Phase A — Kampagne-Wurzel + Datenmodell.** `schema.sql` (kampagne-Tabelle,
  `kampagne_id`-FKs, `welt_id`→`aufenthalt_welt_id`-Rename), persist-Schicht
  angepasst, Kampagnen-CRUD + Kampagnen-Liste als Startseite, Dashboard-Gerüst,
  Sektor-Generierung an eine Kampagne gehängt. DB frisch. **Fundament für alles.**
- **Phase B — Eigenständige Editoren / Dashboard-Listen.** NSC/Fraktion/Auftrag
  als kampagnenweite Listen + Standalone-Anlegen (Ort optional) + Detail-Editoren.
  Karten-Einstieg weiter funktionsfähig.
- **Phase C — NSC-Orte + Fraktions-Picker + Hexkarte.** `verknuepfung`-basierte
  Orte (Herkunft/wirkt), Kaskaden+Such-Picker, Multi-Relations-Anzeige auf der Karte.
- **Phase D (Tech-Schuld, optional).** Fraktions-Generator: generische Namen werden
  mehrfach vergeben („Allianz für Arbeit" 3×) — Entdoppelung / variantenreichere Namen.
  Eigener ROADMAP-Punkt; verschärft heute die Listen-Redundanz.

**Quick-Win-Option:** Die reine **Kaskade im Fraktions-Picker** (Subsektor▸Hex▸
Fraktion) braucht keine Kampagnen — sie nutzt nur den heutigen Sektor-Kontext.
Falls schnelle Linderung gewünscht, kann dieser Teil aus Phase C vorgezogen und
vor Phase A gebaut werden.

---

## Offene Punkte / bewusst ausgeklammert (YAGNI)

- Schiffe/Stationen als eigener Ort-Typ (`befindet_sich_auf`) — erst, wenn gebraucht.
- Sektor-übergreifende Routen-Darstellung (bestehende v0.1-Grenze, unberührt).
- Fraktions-Generator-Qualität (Phase D, separat).
