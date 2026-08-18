"""Régénère les fiches statiques publiques (docs/e/*.html) et les publie sur GitHub
(commit + push), en tâche de fond, à chaque modification d'un équipement qui a un
impact sur sa fiche publique (création, modification, changement d'affectation).

Le résultat (succès ou échec) est écrit dans data/publication_statut.json, lu par
le bandeau de l'appli (voir base.html) pour afficher un message de confirmation.

Le push vers GitHub peut échouer si le réseau SPCMO bloque les connexions sortantes
de git.exe (constaté par ailleurs pour les push manuels depuis ce poste — voir
Aide.html, onglet Paramétrage) : dans ce cas les fiches sont quand même à jour
localement et commitées, prêtes à partir dès qu'un push réussira (manuel ou lors
d'une prochaine modification).
"""
import json
import os
import subprocess
import threading
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

import config
from app import db

STATUT_PATH = os.path.join(config.BASE_DIR, "data", "publication_statut.json")

_verrou = threading.Lock()
_en_cours = False


def _ecrire_statut(ok, message):
    os.makedirs(os.path.dirname(STATUT_PATH), exist_ok=True)
    with open(STATUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"ok": ok, "message": message, "quand": datetime.now().isoformat(timespec="seconds")},
            f, ensure_ascii=False,
        )


def lire_statut():
    if not os.path.exists(STATUT_PATH):
        return None
    try:
        with open(STATUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _regenerer_fiches():
    env = Environment(loader=FileSystemLoader(os.path.join(config.BASE_DIR, "app", "templates")))
    template = env.get_template("fiche.html")
    os.makedirs(os.path.join(config.DOCS_DIR, "e"), exist_ok=True)
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        for e in equipements:
            equipement = db.get_equipement(conn, e["id"])
            site_actuel = db.get_site_actuel(conn, e["id"])
            historique = db.get_historique(conn, e["id"])
            html = template.render(equipement=equipement, site_actuel=site_actuel, historique=historique)
            out_path = os.path.join(config.DOCS_DIR, "e", f"{e['id']}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
        return len(equipements)


def _git(args):
    return subprocess.run(
        ["git"] + args, cwd=config.BASE_DIR, capture_output=True, text=True, timeout=30
    )


def _publier():
    try:
        count = _regenerer_fiches()
        statut = _git(["status", "--porcelain", "docs/"])
        if not statut.stdout.strip():
            _ecrire_statut(True, f"{count} fiche(s) déjà à jour, rien à republier.")
            return
        _git(["add", "docs/"])
        commit = _git(["commit", "-m", "Publication automatique des fiches (déclenchée par une modification GMAO)"])
        if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
            _ecrire_statut(False, f"Échec de l'enregistrement local : {commit.stderr.strip()[:200]}")
            return
        push = _git(["push"])
        if push.returncode != 0:
            _ecrire_statut(
                False,
                "Fiches à jour localement, mais l'envoi vers GitHub a échoué "
                f"(réseau ?) : {push.stderr.strip()[:200]}",
            )
            return
        _ecrire_statut(True, f"{count} fiche(s) publiée(s) sur GitHub Pages.")
    except Exception as e:
        _ecrire_statut(False, f"Erreur inattendue lors de la publication automatique : {e}")


def publier_en_tache_de_fond():
    """À appeler après toute modification d'équipement (création, modification,
    changement d'affectation). Ne fait rien si une publication est déjà en cours
    (la suivante, déclenchée par la prochaine modification, reprendra l'état à jour)."""
    global _en_cours
    with _verrou:
        if _en_cours:
            return
        _en_cours = True

    def _run():
        global _en_cours
        try:
            _publier()
        finally:
            with _verrou:
                _en_cours = False

    threading.Thread(target=_run, daemon=True).start()
