"""Vérification de l'état de connexion à la base, affichée dans le bandeau de l'appli
à côté du statut de publication GitHub (voir app/publication.py). Une requête triviale
est retentée à chaque affichage d'une page (voir base.html) ; l'horodatage de la
dernière réussite est conservé même en cas d'échec de la tentative en cours, pour
savoir depuis quand la base est injoignable plutôt que de simplement perdre l'info."""
import json
import os
from datetime import datetime

import config
from app import db

STATUT_PATH = os.path.join(config.BASE_DIR, "data", "connexion_statut.json")


def verifier_connexion():
    ancien = lire_statut() or {}
    maintenant = datetime.now().isoformat(timespec="seconds")
    try:
        with db.db_session() as conn:
            conn.execute("SELECT 1")
        statut = {"ok": True, "quand": maintenant, "derniere_reussite": maintenant, "erreur": None}
    except Exception as e:
        statut = {
            "ok": False, "quand": maintenant,
            "derniere_reussite": ancien.get("derniere_reussite"),
            "erreur": str(e),
        }
    _ecrire_statut(statut)
    return statut


def _ecrire_statut(statut):
    os.makedirs(os.path.dirname(STATUT_PATH), exist_ok=True)
    with open(STATUT_PATH, "w", encoding="utf-8") as f:
        json.dump(statut, f, ensure_ascii=False)


def lire_statut():
    if not os.path.exists(STATUT_PATH):
        return None
    try:
        with open(STATUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
