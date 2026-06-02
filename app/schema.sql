-- =====================================================================
--  Traveller Referee-Werkzeug  ·  Datenmodell (SQLite)
--  Mongoose Traveller 2e (13Mann-Ausgabe)
-- ---------------------------------------------------------------------
--  Grundprinzipien:
--   * Backbone (Sektor -> Subsektor -> Welt -> NSC/Auftrag) = echte FKs
--   * Weiche Querverweise = generische Tabelle `verknuepfung` (Graph)
--   * Abfragbares -> eigene Spalte ; Variables/Abgeleitetes -> JSON (TEXT)
--   * Jede generierte Entitaet traegt `seed` + `wuerfe` (Reproduzierbar.)
--   * Entwurf bleibt AUSSERHALB der DB; erst "Behalten" schreibt eine Zeile
--   * `status` ist der Spiel-Lebenszyklus, NICHT Entwurf/fixiert
-- =====================================================================

PRAGMA foreign_keys = ON;   -- pro Verbindung setzen, sonst werden FKs ignoriert!

-- =====================================================================
--  WURZEL
-- =====================================================================

CREATE TABLE kampagne (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    notizen     TEXT,
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =====================================================================
--  BACKBONE
-- =====================================================================

CREATE TABLE sektor (
    id          INTEGER PRIMARY KEY,
    kampagne_id INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    notizen     TEXT,
    seed        TEXT,                       -- Generator-Seed (reproduzierbar)
    wuerfe      TEXT,                       -- JSON: rohe Wuerfelergebnisse
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE subsektor (
    id          INTEGER PRIMARY KEY,
    sektor_id   INTEGER NOT NULL REFERENCES sektor(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL CHECK (idx BETWEEN 0 AND 15),  -- A..P = 0..15
    name        TEXT,
    notizen     TEXT,
    UNIQUE (sektor_id, idx)
);

CREATE TABLE welt (
    id           INTEGER PRIMARY KEY,
    sektor_id    INTEGER NOT NULL REFERENCES sektor(id)    ON DELETE CASCADE,
    subsektor_id INTEGER          REFERENCES subsektor(id) ON DELETE SET NULL,
    hex          TEXT NOT NULL CHECK (hex GLOB '[0-9][0-9][0-9][0-9]'), -- "0101"
    name         TEXT NOT NULL,

    -- UWP-Komponenten einzeln & abfragbar -------------------------------
    -- Raumhafen ist kategorisch (Buchstabe), daher TEXT.
    raumhafen    TEXT    CHECK (raumhafen IN ('A','B','C','D','E','X')),
    -- Rest numerisch gespeichert, beim Anzeigen als eHex rendern.
    -- Obergrenzen bewusst grosszuegig (Gesetz > F moeglich, Alien-Welten).
    groesse      INTEGER CHECK (groesse      >= 0),
    atmosphaere  INTEGER CHECK (atmosphaere  >= 0),
    hydrographie INTEGER CHECK (hydrographie >= 0),
    bevoelkerung INTEGER CHECK (bevoelkerung >= 0),   -- bis C (=12) und mehr
    regierung    INTEGER CHECK (regierung    >= 0),
    gesetz       INTEGER CHECK (gesetz       >= 0),   -- kann ueber F hinaus
    techlevel    INTEGER CHECK (techlevel    >= 0),

    uwp          TEXT,        -- gerenderter String fuers Display, z.B. "A788899-C"
    handelscodes TEXT,        -- JSON-Array, z.B. ["Ag","Ni"]
    basen        TEXT,        -- JSON-Array, z.B. ["Navy","Scout"]
    reisezone    TEXT CHECK (reisezone IN ('gruen','amber','rot')) DEFAULT 'gruen',
    gasriesen    INTEGER NOT NULL DEFAULT 0 CHECK (gasriesen IN (0,1)),
    zugehoerigkeit TEXT,      -- Allegiance, z.B. "Im" / "Va" / "As"
    temperatur   TEXT,        -- Band: Gefroren/Kalt/Gemaessigt/Heiss/Gluehend
    raumhafen_details TEXT,   -- JSON: Treibstoff, Anlegekosten, Werft, Reparatur
    kultur       TEXT,        -- JSON: {code, name, beschreibung} (W66, nur bewohnt)
    sternendaten TEXT,        -- JSON: Sterne, Nebenkoerper, Raumhafen-Details
    notizen      TEXT,

    seed         TEXT,
    wuerfe       TEXT,        -- JSON
    erstellt_am  TEXT NOT NULL DEFAULT (datetime('now')),
    aktualisiert_am TEXT,
    UNIQUE (sektor_id, hex)
);

-- =====================================================================
--  AKTEURE
-- =====================================================================

-- Fraktion ist KEIN Kind der Welt: kann mehrere Welten umspannen.
CREATE TABLE fraktion (
    id           INTEGER PRIMARY KEY,
    kampagne_id  INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    typ          TEXT,                       -- Regierung, Konzern, Kult, ...
    reichweite   TEXT CHECK (reichweite IN ('lokal','interstellar')),
    heimatwelt_id INTEGER REFERENCES welt(id) ON DELETE SET NULL,
    einfluss     INTEGER,                    -- frei skalierbar
    ziele        TEXT,
    notizen      TEXT,
    seed         TEXT,
    wuerfe       TEXT,
    erstellt_am  TEXT NOT NULL DEFAULT (datetime('now')),
    aktualisiert_am TEXT
);

CREATE TABLE nsc (
    id           INTEGER PRIMARY KEY,
    kampagne_id  INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    aufenthalt_welt_id INTEGER REFERENCES welt(id) ON DELETE SET NULL, -- aktueller Aufenthalt; NULL = schiffsgebunden/unverortet

    eigenschaften TEXT,       -- JSON: {"STR":7,"GES":9,...} (auch Alien-Werte)
    skills        TEXT,       -- JSON: {"Pilot":2,"Diplomatie":1,...}
    laufbahn      TEXT,       -- JSON: Lifepath-Verlauf (Terms, Karrieren, Events)
    ausruestung   TEXT,       -- JSON-Array
    rolle         TEXT,       -- "Patron", "Kontakt", "Antagonist", ...
    beschreibung  TEXT,
    notizen       TEXT,       -- waechst am Tisch ("hat Spieler beim Schmuggel erwischt")

    -- Spiel-Lebenszyklus
    status        TEXT NOT NULL DEFAULT 'lebendig'
                  CHECK (status IN ('lebendig','tot')),
    getroffen     INTEGER NOT NULL DEFAULT 0 CHECK (getroffen IN (0,1)),

    seed          TEXT,
    wuerfe        TEXT,       -- JSON: rohe Lifepath-Wuerfe
    erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
    aktualisiert_am TEXT
);

-- NSC <-> Fraktion : n:m, mit Rolle und geheim-Flag (Doppelagenten!)
CREATE TABLE nsc_fraktion (
    id          INTEGER PRIMARY KEY,
    nsc_id      INTEGER NOT NULL REFERENCES nsc(id)      ON DELETE CASCADE,
    fraktion_id INTEGER NOT NULL REFERENCES fraktion(id) ON DELETE CASCADE,
    rolle       TEXT,                        -- "Mitglied","Agent","Anfuehrer",...
    geheim      INTEGER NOT NULL DEFAULT 0 CHECK (geheim IN (0,1)),
    notiz       TEXT,
    UNIQUE (nsc_id, fraktion_id)
);

-- =====================================================================
--  AUFTRAG  (der Knoten, der NSC <-> Welt <-> Fraktion zusammenzieht)
-- =====================================================================

CREATE TABLE auftrag (
    id            INTEGER PRIMARY KEY,
    kampagne_id   INTEGER NOT NULL REFERENCES kampagne(id) ON DELETE CASCADE,
    titel         TEXT NOT NULL,
    patron_nsc_id INTEGER REFERENCES nsc(id)      ON DELETE SET NULL,
    welt_id       INTEGER REFERENCES welt(id)     ON DELETE SET NULL,
    fraktion_id   INTEGER REFERENCES fraktion(id) ON DELETE SET NULL,
    typ           TEXT,
    belohnung     TEXT,
    komplikation  TEXT,
    wendung       TEXT,
    status        TEXT NOT NULL DEFAULT 'offen'
                  CHECK (status IN ('offen','aktiv','abgeschlossen','gescheitert')),
    notizen       TEXT,
    seed          TEXT,
    wuerfe        TEXT,
    erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
    aktualisiert_am TEXT
);

-- =====================================================================
--  ROUTE  (Verbindungen zwischen Welten: Kommunikation / Handel)
--  Ungerichtet: CHECK (welt_a_id < welt_b_id) erzwingt kanonische
--  Reihenfolge -> keine Doppelkanten. `auto` trennt generierte von
--  handgezeichneten Routen, damit ein "Routen neu generieren" die
--  manuell gesetzten nicht ueberschreibt (Entwurf/fixiert-Gedanke).
-- =====================================================================

CREATE TABLE route (
    id           INTEGER PRIMARY KEY,
    welt_a_id    INTEGER NOT NULL REFERENCES welt(id) ON DELETE CASCADE,
    welt_b_id    INTEGER NOT NULL REFERENCES welt(id) ON DELETE CASCADE,
    typ          TEXT NOT NULL CHECK (typ IN ('kommunikation','handel')),
    jump_distanz INTEGER,
    auto         INTEGER NOT NULL DEFAULT 0 CHECK (auto IN (0,1)),
    notiz        TEXT,
    erstellt_am  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (welt_a_id < welt_b_id),
    UNIQUE (welt_a_id, welt_b_id, typ)
);

-- =====================================================================
--  POLYMORPHE VERKNUEPFUNG  (weiche Querverweise / Graph)
--  ACHTUNG: bewusst OHNE FK-Constraints (polymorph). Dangling-Links
--  moeglich -> bei Bedarf per App-Logik oder Trigger aufraeumen.
-- =====================================================================

CREATE TABLE verknuepfung (
    id          INTEGER PRIMARY KEY,
    von_typ     TEXT NOT NULL,   -- 'nsc','welt','fraktion','auftrag','sektor',...
    von_id      INTEGER NOT NULL,
    zu_typ      TEXT NOT NULL,
    zu_id       INTEGER NOT NULL,
    relation    TEXT,            -- "kennt","verfeindet","versteckt_auf","Rivale",...
    notiz       TEXT,
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (von_typ, von_id, zu_typ, zu_id, relation)
);

-- =====================================================================
--  INDIZES
-- =====================================================================

CREATE INDEX idx_sektor_kampagne    ON sektor(kampagne_id);
CREATE INDEX idx_subsektor_sektor   ON subsektor(sektor_id);
CREATE INDEX idx_welt_sektor        ON welt(sektor_id);
CREATE INDEX idx_welt_subsektor     ON welt(subsektor_id);
CREATE INDEX idx_nsc_kampagne       ON nsc(kampagne_id);
CREATE INDEX idx_nsc_aufenthalt     ON nsc(aufenthalt_welt_id);
CREATE INDEX idx_fraktion_kampagne  ON fraktion(kampagne_id);
CREATE INDEX idx_auftrag_kampagne   ON auftrag(kampagne_id);
CREATE INDEX idx_nf_nsc             ON nsc_fraktion(nsc_id);
CREATE INDEX idx_nf_fraktion        ON nsc_fraktion(fraktion_id);
CREATE INDEX idx_auftrag_patron     ON auftrag(patron_nsc_id);
CREATE INDEX idx_auftrag_welt       ON auftrag(welt_id);
CREATE INDEX idx_auftrag_fraktion   ON auftrag(fraktion_id);
CREATE INDEX idx_route_a             ON route(welt_a_id);
CREATE INDEX idx_route_b             ON route(welt_b_id);
CREATE INDEX idx_vk_von             ON verknuepfung(von_typ, von_id);
CREATE INDEX idx_vk_zu              ON verknuepfung(zu_typ,  zu_id);

-- =====================================================================
--  TRIGGER: aktualisiert_am pflegen (nur die haeufig editierten Tabellen)
-- =====================================================================

CREATE TRIGGER trg_welt_update     AFTER UPDATE ON welt
BEGIN UPDATE welt     SET aktualisiert_am = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_nsc_update      AFTER UPDATE ON nsc
BEGIN UPDATE nsc      SET aktualisiert_am = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_fraktion_update AFTER UPDATE ON fraktion
BEGIN UPDATE fraktion SET aktualisiert_am = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_auftrag_update  AFTER UPDATE ON auftrag
BEGIN UPDATE auftrag  SET aktualisiert_am = datetime('now') WHERE id = NEW.id; END;
