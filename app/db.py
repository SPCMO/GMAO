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

CREATE TABLE IF NOT EXISTS site (
    nom TEXT PRIMARY KEY,
    lat REAL,
    lon REAL
);

CREATE INDEX IF NOT EXISTS idx_affectation_equipement ON affectation(equipement_id);
"""


def get_connection():
    conn = sqlite3.connect(settings.get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    # equipement.lat/lon (version précédente) : conservées si présentes mais plus utilisées,
    # la localisation vit désormais sur le site (table site).
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(equipement)").fetchall()]
    if "lat" not in cols:
        conn.execute("ALTER TABLE equipement ADD COLUMN lat REAL")
    if "lon" not in cols:
        conn.execute("ALTER TABLE equipement ADD COLUMN lon REAL")

    # Backfill : un site déjà utilisé dans l'historique mais absent de la table site
    conn.execute(
        "INSERT OR IGNORE INTO site (nom) SELECT DISTINCT site FROM affectation"
    )


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()


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


def ensure_site(conn, nom):
    conn.execute("INSERT OR IGNORE INTO site (nom) VALUES (?)", (nom,))


def set_site_coordonnees(conn, nom, lat, lon):
    ensure_site(conn, nom)
    conn.execute("UPDATE site SET lat = ?, lon = ? WHERE nom = ?", (lat, lon, nom))


def get_site(conn, nom):
    return conn.execute("SELECT * FROM site WHERE nom = ?", (nom,)).fetchone()


def list_all_sites(conn):
    rows = conn.execute(
        """
        SELECT s.nom, s.lat, s.lon, COUNT(a.id) AS nb_equipements
        FROM site s
        LEFT JOIN affectation a ON a.site = s.nom AND a.date_fin IS NULL
        GROUP BY s.nom
        ORDER BY s.nom
        """
    ).fetchall()
    return rows


def create_equipement(conn, nom, date_installation, site, date_debut=None):
    ensure_site(conn, site)
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
    ensure_site(conn, nouveau_site)
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
               a.site AS site_actuel, a.date_debut AS affecte_depuis,
               s.lat AS site_lat, s.lon AS site_lon
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        LEFT JOIN site s ON s.nom = a.site
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
               a.site AS site_actuel, a.date_debut AS affecte_depuis,
               s.lat AS site_lat, s.lon AS site_lon
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        LEFT JOIN site s ON s.nom = a.site
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
