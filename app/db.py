"""
Datenbank-Schicht (SQLite)
==========================

Eine Verbindung pro Request via Flask `g`. WICHTIG: PRAGMA foreign_keys = ON
muss pro Verbindung gesetzt werden -- sonst ignoriert SQLite die FKs still.
"""
from __future__ import annotations
import sqlite3
from flask import g, current_app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        con = sqlite3.connect(current_app.config["DB_PATH"])
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        g.db = con
    return g.db


def close_db(e=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db_if_needed() -> None:
    """Legt das Schema an, falls die Tabelle `kampagne` noch nicht existiert."""
    con = sqlite3.connect(current_app.config["DB_PATH"])
    con.execute("PRAGMA foreign_keys = ON")
    vorhanden = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kampagne'"
    ).fetchone()
    if not vorhanden:
        with current_app.open_resource("schema.sql") as f:
            con.executescript(f.read().decode("utf-8"))
        con.commit()
    con.close()
