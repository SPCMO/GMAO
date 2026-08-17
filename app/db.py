import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date

import config
from app import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipement (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL UNIQUE,
    date_installation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS affectation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipement_id TEXT NOT NULL REFERENCES equipement(id),
    site TEXT NOT NULL,
    date_debut TEXT NOT NULL,
    date_fin TEXT
);

CREATE INDEX IF NOT EXISTS idx_affectation_equipement ON affectation(equipement_id);
"""


def get_connection():
    conn = sqlite3.connect(settings.get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def new_equipement_id():
    return uuid.uuid4().hex[:12]


def create_equipement(conn, nom, date_installation, site, date_debut=None):
    eq_id = new_equipement_id()
    conn.execute(
        "INSERT INTO equipement (id, nom, date_installation) VALUES (?, ?, ?)",
        (eq_id, nom, date_installation),
    )
    conn.execute(
        "INSERT INTO affectation (equipement_id, site, date_debut, date_fin) VALUES (?, ?, ?, NULL)",
        (eq_id, site, date_debut or date_installation),
    )
    return eq_id


def changer_affectation(conn, equipement_id, nouveau_site, date_transfert):
    conn.execute(
        "UPDATE affectation SET date_fin = ? WHERE equipement_id = ? AND date_fin IS NULL",
        (date_transfert, equipement_id),
    )
    conn.execute(
        "INSERT INTO affectation (equipement_id, site, date_debut, date_fin) VALUES (?, ?, ?, NULL)",
        (equipement_id, nouveau_site, date_transfert),
    )


def list_equipements(conn):
    rows = conn.execute(
        """
        SELECT e.id, e.nom, e.date_installation,
               a.site AS site_actuel, a.date_debut AS affecte_depuis
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        ORDER BY e.nom
        """
    ).fetchall()
    return rows


def get_equipement(conn, equipement_id):
    return conn.execute(
        "SELECT * FROM equipement WHERE id = ?", (equipement_id,)
    ).fetchone()


def get_site_actuel(conn, equipement_id):
    return conn.execute(
        "SELECT * FROM affectation WHERE equipement_id = ? AND date_fin IS NULL",
        (equipement_id,),
    ).fetchone()


def get_historique(conn, equipement_id):
    return conn.execute(
        """
        SELECT * FROM affectation
        WHERE equipement_id = ?
        ORDER BY date_debut DESC
        """,
        (equipement_id,),
    ).fetchall()


def list_equipements_by_ids(conn, equipement_ids):
    if not equipement_ids:
        return []
    placeholders = ",".join("?" for _ in equipement_ids)
    rows = conn.execute(
        f"""
        SELECT e.id, e.nom, e.date_installation,
               a.site AS site_actuel, a.date_debut AS affecte_depuis
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        WHERE e.id IN ({placeholders})
        ORDER BY e.nom
        """,
        equipement_ids,
    ).fetchall()
    return rows


def list_sites(conn):
    rows = conn.execute(
        "SELECT DISTINCT site FROM affectation ORDER BY site"
    ).fetchall()
    return [r["site"] for r in rows]
