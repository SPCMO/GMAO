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
    lon REAL,
    uh_gestion TEXT
);

CREATE TABLE IF NOT EXISTS raison_fermeture_option (
    nom TEXT PRIMARY KEY,
    ordre INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS type_equipement (
    nom TEXT PRIMARY KEY,
    ordre INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sous_type_equipement (
    type TEXT NOT NULL,
    nom TEXT NOT NULL,
    ordre INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (type, nom)
);

CREATE TABLE IF NOT EXISTS duree_vie_option (annees REAL PRIMARY KEY);
CREATE TABLE IF NOT EXISTS rappel_option (annees REAL PRIMARY KEY);
CREATE TABLE IF NOT EXISTS rallonge_option (annees REAL PRIMARY KEY);

CREATE TABLE IF NOT EXISTS uh_email (
    uh TEXT NOT NULL,
    email TEXT NOT NULL,
    PRIMARY KEY (uh, email)
);

CREATE TABLE IF NOT EXISTS couleur_config (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

CREATE TABLE IF NOT EXISTS tri_config (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

CREATE INDEX IF NOT EXISTS idx_affectation_equipement ON affectation(equipement_id);
"""

TYPES_SOUS_TYPES_PAR_DEFAUT = {
    "Centrale d'acquisition": ["AquaCJ", "LNS"],
    "Piézomètre": ["Paratronic", "Vega"],
    "Bulle à bulle": ["Limnair", "Nimbus", "OTT-CBS"],
    "Radar": ["Paratronic", "Vega", "Endress-Hauser", "TBRS"],
    "Modem": ["Radio", "IP"],
    "Batterie": ["40Ah", "80Ah"],
}
DUREES_VIE_PAR_DEFAUT = [1, 2, 5, 8, 10, 15]
RAPPELS_PAR_DEFAUT = [0.5, 1, 1.5, 2, 2.5, 3]
RALLONGES_PAR_DEFAUT = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5]
RAISONS_FERMETURE_PAR_DEFAUT = ["Abandon", "Déplacée"]
COULEURS_PAR_DEFAUT = {
    "uh_11": "#dbeafe",
    "uh_34": "#dcfce7",
    "uh_66": "#fef3c7",
    "maintenance": "#e5e7eb",
}

# Tri par défaut (jusqu'à 3 niveaux) appliqué au chargement de chaque liste, en plus de
# l'ordre déjà renvoyé par la requête SQL (qui sert de dernier niveau de tri implicite,
# grâce à la stabilité du tri JS — voir gmao-tri.js). "" pour l'accueil = on ne touche
# pas à l'ordre SQL existant (rétro-compatible avec le comportement historique).
TRI_PAR_DEFAUT = {
    "accueil": "",
    "sites": "statut,site",
    "equipements": "statut,type,equipement",
}
# Colonnes proposées dans Paramètres > Tri par défaut, par écran (valeur -> libellé).
TRI_COLONNES = {
    "accueil": [
        ("equipement", "Équipement"), ("type", "Type"), ("sous_type", "Sous-type"),
        ("site", "Site"), ("uh", "UH"), ("affecte_depuis", "Affecté depuis"),
        ("installation", "1ère mise en service"), ("statut", "Statut"),
        ("tps_restant", "Tps restant (j)"), ("duree_prolongee", "Durée de vie prolongée"),
    ],
    "sites": [
        ("site", "Site"), ("nb_equipements", "Équipements affectés"), ("uh", "UH"),
        ("maintenance", "Maintenance"), ("statut", "Statut"), ("localisation", "Localisation"),
    ],
    "equipements": [
        ("equipement", "Équipement"), ("type", "Type"), ("site", "Site actuel"),
        ("uh", "UH"), ("statut", "Statut"),
    ],
}


def get_connection():
    conn = sqlite3.connect(settings.get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_col_if_missing(conn, table, col, coltype):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def _migrate(conn):
    # equipement.lat/lon (version antérieure) : conservées si présentes mais plus utilisées,
    # la localisation vit désormais sur le site (table site).
    _add_col_if_missing(conn, "equipement", "lat", "REAL")
    _add_col_if_missing(conn, "equipement", "lon", "REAL")

    _add_col_if_missing(conn, "equipement", "date_creation", "TEXT")
    _add_col_if_missing(conn, "equipement", "type", "TEXT")
    _add_col_if_missing(conn, "equipement", "sous_type", "TEXT")
    _add_col_if_missing(conn, "equipement", "duree_vie_ans", "REAL")
    _add_col_if_missing(conn, "equipement", "duree_vie_effective_ans", "REAL")
    _add_col_if_missing(conn, "equipement", "rappel_ans", "REAL")
    _add_col_if_missing(conn, "equipement", "rallonge_ans", "REAL")
    _add_col_if_missing(conn, "equipement", "uh_gestion", "TEXT")
    _add_col_if_missing(conn, "equipement", "date_retrait", "TEXT")
    _add_col_if_missing(conn, "equipement", "raison_retrait", "TEXT")
    _add_col_if_missing(conn, "equipement", "alerte_envoyee_le", "TEXT")

    _add_col_if_missing(conn, "site", "maintenance", "INTEGER DEFAULT 0")
    _add_col_if_missing(conn, "site", "uh_gestion", "TEXT")
    _add_col_if_missing(conn, "site", "date_fermeture", "TEXT")
    _add_col_if_missing(conn, "site", "raison_fermeture", "TEXT")

    _add_col_if_missing(conn, "type_equipement", "ordre", "INTEGER NOT NULL DEFAULT 0")
    _add_col_if_missing(conn, "sous_type_equipement", "ordre", "INTEGER NOT NULL DEFAULT 0")

    # Backfill : un site déjà utilisé dans l'historique mais absent de la table site
    conn.execute(
        "INSERT OR IGNORE INTO site (nom) SELECT DISTINCT site FROM affectation"
    )

    # Backfill : l'UH de gestion vivait auparavant sur l'équipement (version antérieure).
    # Reprendre, pour chaque site sans UH encore renseignée, celle d'un équipement qui
    # y est actuellement affecté et qui en avait une.
    conn.execute(
        """
        UPDATE site SET uh_gestion = (
            SELECT e.uh_gestion
            FROM equipement e
            JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
            WHERE a.site = site.nom AND e.uh_gestion IS NOT NULL
            LIMIT 1
        )
        WHERE uh_gestion IS NULL
        """
    )

    for type_nom, sous_types in TYPES_SOUS_TYPES_PAR_DEFAUT.items():
        conn.execute("INSERT OR IGNORE INTO type_equipement (nom) VALUES (?)", (type_nom,))
        for st in sous_types:
            conn.execute(
                "INSERT OR IGNORE INTO sous_type_equipement (type, nom) VALUES (?, ?)",
                (type_nom, st),
            )
    for v in DUREES_VIE_PAR_DEFAUT:
        conn.execute("INSERT OR IGNORE INTO duree_vie_option (annees) VALUES (?)", (v,))
    for v in RAPPELS_PAR_DEFAUT:
        conn.execute("INSERT OR IGNORE INTO rappel_option (annees) VALUES (?)", (v,))
    for v in RALLONGES_PAR_DEFAUT:
        conn.execute("INSERT OR IGNORE INTO rallonge_option (annees) VALUES (?)", (v,))
    for cle, valeur in COULEURS_PAR_DEFAUT.items():
        conn.execute("INSERT OR IGNORE INTO couleur_config (cle, valeur) VALUES (?, ?)", (cle, valeur))
    for cle, valeur in TRI_PAR_DEFAUT.items():
        conn.execute("INSERT OR IGNORE INTO tri_config (cle, valeur) VALUES (?, ?)", (cle, valeur))
    for i, nom in enumerate(RAISONS_FERMETURE_PAR_DEFAUT, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO raison_fermeture_option (nom, ordre) VALUES (?, ?)", (nom, i)
        )

    # Backfill ordre (ordre=0 = jamais numéroté) : numérote une fois par ordre alphabétique,
    # devient un no-op dès que tout le monde a un ordre > 0. Les ajouts ultérieurs
    # (add_type/add_sous_type) assignent directement un ordre en fin de liste.
    a_numeroter = [r["nom"] for r in conn.execute(
        "SELECT nom FROM type_equipement WHERE ordre = 0 ORDER BY nom"
    ).fetchall()]
    for i, nom in enumerate(a_numeroter, start=1):
        conn.execute("UPDATE type_equipement SET ordre = ? WHERE nom = ?", (i, nom))

    for type_nom in [r["type"] for r in conn.execute("SELECT DISTINCT type FROM sous_type_equipement").fetchall()]:
        a_numeroter = [r["nom"] for r in conn.execute(
            "SELECT nom FROM sous_type_equipement WHERE type = ? AND ordre = 0 ORDER BY nom", (type_nom,)
        ).fetchall()]
        for i, nom in enumerate(a_numeroter, start=1):
            conn.execute(
                "UPDATE sous_type_equipement SET ordre = ? WHERE type = ? AND nom = ?", (i, type_nom, nom)
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


# ── Sites ─────────────────────────────────────────────────────────────────

def ensure_site(conn, nom):
    conn.execute("INSERT OR IGNORE INTO site (nom) VALUES (?)", (nom,))


def create_site(conn, nom, maintenance=False, lat=None, lon=None, uh_gestion=None):
    conn.execute(
        "INSERT OR IGNORE INTO site (nom, lat, lon, maintenance, uh_gestion) VALUES (?, ?, ?, ?, ?)",
        (nom, lat, lon, 1 if maintenance else 0, uh_gestion),
    )


def set_site_coordonnees(conn, nom, lat, lon):
    ensure_site(conn, nom)
    conn.execute("UPDATE site SET lat = ?, lon = ? WHERE nom = ?", (lat, lon, nom))


def set_site_maintenance(conn, nom, maintenance):
    conn.execute("UPDATE site SET maintenance = ? WHERE nom = ?", (1 if maintenance else 0, nom))


def update_site(conn, nom, maintenance, lat, lon, uh_gestion=None, date_fermeture=None, raison_fermeture=None):
    if not date_fermeture:
        raison_fermeture = None
    conn.execute(
        "UPDATE site SET lat = ?, lon = ?, maintenance = ?, uh_gestion = ?, "
        "date_fermeture = ?, raison_fermeture = ? WHERE nom = ?",
        (lat, lon, 1 if maintenance else 0, uh_gestion, date_fermeture, raison_fermeture, nom),
    )


def get_site(conn, nom):
    return conn.execute("SELECT * FROM site WHERE nom = ?", (nom,)).fetchone()


def delete_site(conn, nom):
    """Supprime un site uniquement si plus aucun équipement n'y est actuellement affecté
    (même définition que la colonne "Équipements actuellement affectés" de sites.html).
    Retourne True si supprimé, False sinon (l'appelant doit alors en informer l'utilisateur) ;
    l'historique des affectations passées vers ce site n'est pas touché."""
    nb_affectes = conn.execute(
        "SELECT COUNT(*) FROM affectation WHERE site = ? AND date_fin IS NULL", (nom,)
    ).fetchone()[0]
    if nb_affectes > 0:
        return False
    conn.execute("DELETE FROM site WHERE nom = ?", (nom,))
    return True


def list_all_sites(conn):
    rows = conn.execute(
        """
        SELECT s.nom, s.lat, s.lon, s.maintenance, s.uh_gestion,
               s.date_fermeture, s.raison_fermeture, COUNT(a.id) AS nb_equipements
        FROM site s
        LEFT JOIN affectation a ON a.site = s.nom AND a.date_fin IS NULL
        GROUP BY s.nom
        ORDER BY s.nom
        """
    ).fetchall()
    return rows


def list_sites(conn):
    """Tous les sites connus (table site), pas seulement ceux ayant déjà eu un équipement
    affecté : un site fraîchement créé via "+ Site" doit apparaître immédiatement dans les
    menus déroulants de création/réaffectation d'équipement."""
    rows = conn.execute("SELECT nom FROM site ORDER BY nom").fetchall()
    return [r["nom"] for r in rows]


# ── Équipements ──────────────────────────────────────────────────────────

_CHAMPS_EQUIPEMENT_OPTIONNELS = [
    "date_creation", "type", "sous_type",
    "duree_vie_ans", "rappel_ans", "rallonge_ans",
]


def create_equipement(conn, nom, date_installation, site, date_debut=None, **champs):
    ensure_site(conn, site)
    eq_id = new_equipement_id()
    valeurs = {c: champs.get(c) for c in _CHAMPS_EQUIPEMENT_OPTIONNELS}
    duree_vie = valeurs.get("duree_vie_ans")
    conn.execute(
        """
        INSERT INTO equipement
            (id, nom, date_installation, date_creation, type, sous_type,
             duree_vie_ans, duree_vie_effective_ans, rappel_ans, rallonge_ans)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eq_id, nom, date_installation, valeurs["date_creation"], valeurs["type"], valeurs["sous_type"],
            duree_vie, duree_vie, valeurs["rappel_ans"], valeurs["rallonge_ans"],
        ),
    )
    conn.execute(
        "INSERT INTO affectation (equipement_id, site, date_debut, date_fin) VALUES (?, ?, ?, NULL)",
        (eq_id, site, date_debut or date_installation),
    )
    return eq_id


def update_equipement(conn, equipement_id, **champs):
    """Met à jour les champs fournis (parmi nom, date_creation, date_installation, type,
    sous_type, duree_vie_ans, rappel_ans, rallonge_ans, date_retrait, raison_retrait).
    Ne touche pas à duree_vie_effective_ans ni alerte_envoyee_le (voir prolonger_equipement).
    L'UH de gestion se règle désormais au niveau du site (voir update_site)."""
    autorises = {
        "nom", "date_creation", "date_installation", "type", "sous_type",
        "duree_vie_ans", "rappel_ans", "rallonge_ans",
        "date_retrait", "raison_retrait",
    }
    a_mettre_a_jour = {k: v for k, v in champs.items() if k in autorises}
    if not a_mettre_a_jour:
        return
    colonnes = ", ".join(f"{k} = ?" for k in a_mettre_a_jour)
    valeurs = list(a_mettre_a_jour.values()) + [equipement_id]
    conn.execute(f"UPDATE equipement SET {colonnes} WHERE id = ?", valeurs)
    # Si la durée de vie de base change manuellement, resynchroniser la valeur effective
    # tant qu'aucune prolongation n'a eu lieu.
    if "duree_vie_ans" in a_mettre_a_jour:
        eq = get_equipement(conn, equipement_id)
        if eq and (eq["duree_vie_effective_ans"] is None or eq["duree_vie_effective_ans"] == eq["duree_vie_ans"]):
            conn.execute(
                "UPDATE equipement SET duree_vie_effective_ans = ? WHERE id = ?",
                (a_mettre_a_jour["duree_vie_ans"], equipement_id),
            )


def prolonger_equipement(conn, equipement_id):
    """Ajoute la rallonge à la durée de vie effective et réinitialise le suivi d'alerte."""
    eq = get_equipement(conn, equipement_id)
    if not eq or eq["rallonge_ans"] is None:
        return
    base = eq["duree_vie_effective_ans"] if eq["duree_vie_effective_ans"] is not None else (eq["duree_vie_ans"] or 0)
    nouvelle_duree = base + eq["rallonge_ans"]
    conn.execute(
        "UPDATE equipement SET duree_vie_effective_ans = ?, alerte_envoyee_le = NULL WHERE id = ?",
        (nouvelle_duree, equipement_id),
    )


def marquer_alerte_envoyee(conn, equipement_id, quand):
    conn.execute("UPDATE equipement SET alerte_envoyee_le = ? WHERE id = ?", (quand, equipement_id))


def peut_annuler_prolongation(eq):
    """Vrai si la durée de vie effective correspond exactement à une unique rallonge appliquée
    (base + rallonge) : au-delà d'une seule prolongation, l'historique n'est pas assez précis
    pour annuler sans ambiguïté, donc on ne propose pas le retour arrière."""
    if eq["duree_vie_ans"] is None or eq["duree_vie_effective_ans"] is None or eq["rallonge_ans"] is None:
        return False
    return abs(eq["duree_vie_effective_ans"] - (eq["duree_vie_ans"] + eq["rallonge_ans"])) < 1e-9


def annuler_prolongation(conn, equipement_id):
    """Ramène la durée de vie effective à sa valeur de base (voir peut_annuler_prolongation)."""
    eq = get_equipement(conn, equipement_id)
    if not eq or not peut_annuler_prolongation(eq):
        return False
    conn.execute(
        "UPDATE equipement SET duree_vie_effective_ans = ? WHERE id = ?",
        (eq["duree_vie_ans"], equipement_id),
    )
    return True


def delete_equipement(conn, equipement_id):
    """Supprime définitivement un équipement et tout son historique d'affectations
    (irréversible). Contrairement aux sites, pas de garde-fou métier ici : un équipement
    n'a pas de dépendants, seul son propre historique disparaît avec lui."""
    conn.execute("DELETE FROM affectation WHERE equipement_id = ?", (equipement_id,))
    conn.execute("DELETE FROM equipement WHERE id = ?", (equipement_id,))


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


_COLONNES_EQUIPEMENT_LISTE = """
    e.id, e.nom, e.date_installation, e.date_creation, e.type, e.sous_type,
    e.duree_vie_ans, e.duree_vie_effective_ans, e.rappel_ans, e.rallonge_ans,
    e.date_retrait, e.raison_retrait, e.alerte_envoyee_le,
    a.site AS site_actuel, a.date_debut AS affecte_depuis,
    s.lat AS site_lat, s.lon AS site_lon, s.maintenance AS site_maintenance, s.uh_gestion AS site_uh,
    s.date_fermeture AS site_date_fermeture, s.raison_fermeture AS site_raison_fermeture
"""


def list_equipements(conn):
    # Ordre par défaut de l'accueil et de la gestion des équipements : équipements retirés
    # relégués en fin de liste, puis groupés par UH / type / sous-type / nom (le tri manuel
    # par colonne, côté JS, prend le dessus au clic sur un en-tête).
    rows = conn.execute(
        f"""
        SELECT {_COLONNES_EQUIPEMENT_LISTE}
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        LEFT JOIN site s ON s.nom = a.site
        ORDER BY (e.date_retrait IS NOT NULL), s.uh_gestion, e.type, e.sous_type, e.nom
        """
    ).fetchall()
    return rows


def list_equipements_by_ids(conn, equipement_ids):
    if not equipement_ids:
        return []
    placeholders = ",".join("?" for _ in equipement_ids)
    rows = conn.execute(
        f"""
        SELECT {_COLONNES_EQUIPEMENT_LISTE}
        FROM equipement e
        LEFT JOIN affectation a ON a.equipement_id = e.id AND a.date_fin IS NULL
        LEFT JOIN site s ON s.nom = a.site
        WHERE e.id IN ({placeholders})
        ORDER BY e.nom
        """,
        equipement_ids,
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
        ORDER BY date_debut ASC
        """,
        (equipement_id,),
    ).fetchall()


# ── Listes de référence (types, sous-types, durées) ─────────────────────

def list_types(conn):
    return [r["nom"] for r in conn.execute("SELECT nom FROM type_equipement ORDER BY ordre").fetchall()]


def add_type(conn, nom):
    max_ordre = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM type_equipement").fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO type_equipement (nom, ordre) VALUES (?, ?)", (nom, max_ordre + 1))


def delete_type(conn, nom):
    conn.execute("DELETE FROM sous_type_equipement WHERE type = ?", (nom,))
    conn.execute("DELETE FROM type_equipement WHERE nom = ?", (nom,))


def deplacer_type(conn, nom, direction):
    """direction : -1 pour monter, +1 pour descendre."""
    rows = conn.execute("SELECT nom, ordre FROM type_equipement ORDER BY ordre").fetchall()
    noms = [r["nom"] for r in rows]
    if nom not in noms:
        return
    i = noms.index(nom)
    j = i + direction
    if j < 0 or j >= len(noms):
        return
    conn.execute("UPDATE type_equipement SET ordre = ? WHERE nom = ?", (rows[j]["ordre"], rows[i]["nom"]))
    conn.execute("UPDATE type_equipement SET ordre = ? WHERE nom = ?", (rows[i]["ordre"], rows[j]["nom"]))


def list_sous_types(conn, type_nom):
    return [
        r["nom"] for r in conn.execute(
            "SELECT nom FROM sous_type_equipement WHERE type = ? ORDER BY ordre", (type_nom,)
        ).fetchall()
    ]


def list_sous_types_tous(conn):
    """{type: [sous_types...]} pour tous les types, utilisé pour la cascade JS des formulaires."""
    resultat = {t: [] for t in list_types(conn)}
    for r in conn.execute("SELECT type, nom FROM sous_type_equipement ORDER BY type, ordre").fetchall():
        resultat.setdefault(r["type"], []).append(r["nom"])
    return resultat


def add_sous_type(conn, type_nom, nom):
    max_ordre = conn.execute(
        "SELECT COALESCE(MAX(ordre), 0) FROM sous_type_equipement WHERE type = ?", (type_nom,)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO sous_type_equipement (type, nom, ordre) VALUES (?, ?, ?)",
        (type_nom, nom, max_ordre + 1),
    )


def delete_sous_type(conn, type_nom, nom):
    conn.execute("DELETE FROM sous_type_equipement WHERE type = ? AND nom = ?", (type_nom, nom))


def deplacer_sous_type(conn, type_nom, nom, direction):
    """direction : -1 pour monter, +1 pour descendre."""
    rows = conn.execute(
        "SELECT nom, ordre FROM sous_type_equipement WHERE type = ? ORDER BY ordre", (type_nom,)
    ).fetchall()
    noms = [r["nom"] for r in rows]
    if nom not in noms:
        return
    i = noms.index(nom)
    j = i + direction
    if j < 0 or j >= len(noms):
        return
    conn.execute(
        "UPDATE sous_type_equipement SET ordre = ? WHERE type = ? AND nom = ?",
        (rows[j]["ordre"], type_nom, rows[i]["nom"]),
    )
    conn.execute(
        "UPDATE sous_type_equipement SET ordre = ? WHERE type = ? AND nom = ?",
        (rows[i]["ordre"], type_nom, rows[j]["nom"]),
    )


def _list_options(conn, table):
    return [r["annees"] for r in conn.execute(f"SELECT annees FROM {table} ORDER BY annees").fetchall()]


def _add_option(conn, table, annees):
    conn.execute(f"INSERT OR IGNORE INTO {table} (annees) VALUES (?)", (annees,))


def _delete_option(conn, table, annees):
    conn.execute(f"DELETE FROM {table} WHERE annees = ?", (annees,))


def list_durees_vie(conn):
    return _list_options(conn, "duree_vie_option")


def add_duree_vie(conn, annees):
    _add_option(conn, "duree_vie_option", annees)


def delete_duree_vie(conn, annees):
    _delete_option(conn, "duree_vie_option", annees)


def list_rappels(conn):
    return _list_options(conn, "rappel_option")


def add_rappel(conn, annees):
    _add_option(conn, "rappel_option", annees)


def delete_rappel(conn, annees):
    _delete_option(conn, "rappel_option", annees)


def list_rallonges(conn):
    return _list_options(conn, "rallonge_option")


def add_rallonge(conn, annees):
    _add_option(conn, "rallonge_option", annees)


def delete_rallonge(conn, annees):
    _delete_option(conn, "rallonge_option", annees)


# ── UH de gestion : emails de destination ───────────────────────────────

UH_VALEURS = ["11", "34", "66"]


def list_uh_emails(conn, uh):
    return [r["email"] for r in conn.execute(
        "SELECT email FROM uh_email WHERE uh = ? ORDER BY email", (uh,)
    ).fetchall()]


def list_uh_emails_tous(conn):
    resultat = {uh: [] for uh in UH_VALEURS}
    for r in conn.execute("SELECT uh, email FROM uh_email ORDER BY uh, email").fetchall():
        resultat.setdefault(r["uh"], []).append(r["email"])
    return resultat


def add_uh_email(conn, uh, email):
    conn.execute("INSERT OR IGNORE INTO uh_email (uh, email) VALUES (?, ?)", (uh, email))


def delete_uh_email(conn, uh, email):
    conn.execute("DELETE FROM uh_email WHERE uh = ? AND email = ?", (uh, email))


# ── Couleurs (UH / site de maintenance) ─────────────────────────────────

def list_couleurs(conn):
    return {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM couleur_config").fetchall()}


def set_couleur(conn, cle, valeur):
    conn.execute(
        "INSERT INTO couleur_config (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
        (cle, valeur),
    )


# ── Tri par défaut (accueil / sites / equipements) ──────────────────────

def get_tri_config(conn, cle):
    """Liste des colonnes (dans l'ordre de priorité) à appliquer par-dessus l'ordre SQL
    existant. [] si non configuré (= on garde l'ordre SQL tel quel, voir TRI_PAR_DEFAUT)."""
    r = conn.execute("SELECT valeur FROM tri_config WHERE cle = ?", (cle,)).fetchone()
    valeur = r["valeur"] if r else TRI_PAR_DEFAUT.get(cle, "")
    return [c for c in valeur.split(",") if c]


def set_tri_config(conn, cle, colonnes):
    valeur = ",".join(c for c in colonnes if c)
    conn.execute(
        "INSERT INTO tri_config (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
        (cle, valeur),
    )


# ── Raisons de fermeture de site ────────────────────────────────────────

def list_raisons_fermeture(conn):
    return [
        r["nom"] for r in conn.execute(
            "SELECT nom FROM raison_fermeture_option ORDER BY ordre"
        ).fetchall()
    ]


def add_raison_fermeture(conn, nom):
    max_ordre = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM raison_fermeture_option").fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO raison_fermeture_option (nom, ordre) VALUES (?, ?)", (nom, max_ordre + 1)
    )


def delete_raison_fermeture(conn, nom):
    conn.execute("DELETE FROM raison_fermeture_option WHERE nom = ?", (nom,))


def deplacer_raison_fermeture(conn, nom, direction):
    """direction : -1 pour monter, +1 pour descendre."""
    rows = conn.execute("SELECT nom, ordre FROM raison_fermeture_option ORDER BY ordre").fetchall()
    noms = [r["nom"] for r in rows]
    if nom not in noms:
        return
    i = noms.index(nom)
    j = i + direction
    if j < 0 or j >= len(noms):
        return
    conn.execute("UPDATE raison_fermeture_option SET ordre = ? WHERE nom = ?", (rows[j]["ordre"], rows[i]["nom"]))
    conn.execute("UPDATE raison_fermeture_option SET ordre = ? WHERE nom = ?", (rows[i]["ordre"], rows[j]["nom"]))
