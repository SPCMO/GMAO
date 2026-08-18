"""Calcul des péremptions et alertes matériel.

Péremption = date de 1ère mise en service + durée de vie effective (ans).
Alerte = péremption - rappel (ans) <= aujourd'hui, tant que l'équipement n'est
pas retiré et qu'une durée de vie est renseignée.

Utilisé à la fois par l'appli Flask (icône ⚠️ sur le dashboard) et par le
script autonome d'envoi de mail (scripts/verifier_alertes.py).
"""
from datetime import date

from dateutil.relativedelta import relativedelta


def _ans_vers_relativedelta(annees):
    mois_totaux = round(annees * 12)
    return relativedelta(months=mois_totaux)


def date_peremption(equipement):
    """Retourne la date de péremption (date) ou None si non calculable."""
    duree = equipement["duree_vie_effective_ans"] or equipement["duree_vie_ans"]
    date_service = equipement["date_installation"]
    if not duree or not date_service:
        return None
    d = date.fromisoformat(date_service) if isinstance(date_service, str) else date_service
    return d + _ans_vers_relativedelta(duree)


def date_alerte(equipement):
    """Retourne la date à partir de laquelle l'alerte doit se déclencher, ou None."""
    peremption = date_peremption(equipement)
    rappel = equipement["rappel_ans"]
    if peremption is None or not rappel:
        return None
    return peremption - _ans_vers_relativedelta(rappel)


def etat_alerte(equipement, aujourdhui=None):
    """Retourne un dict décrivant l'état d'alerte de cet équipement.

    {
      'active': bool,              # alerte à afficher/envoyer
      'peremption': date|None,
      'jours_restants': int|None,  # peut être négatif si déjà périmé
      'deja_prolonge': bool,
    }
    """
    aujourdhui = aujourdhui or date.today()
    if equipement["date_retrait"]:
        return {"active": False, "peremption": None, "jours_restants": None, "deja_prolonge": False}

    peremption = date_peremption(equipement)
    seuil = date_alerte(equipement)
    deja_prolonge = bool(
        equipement["duree_vie_effective_ans"] and equipement["duree_vie_ans"]
        and equipement["duree_vie_effective_ans"] > equipement["duree_vie_ans"]
    )
    if peremption is None or seuil is None:
        return {"active": False, "peremption": peremption, "jours_restants": None, "deja_prolonge": deja_prolonge}

    active = aujourdhui >= seuil
    jours_restants = (peremption - aujourdhui).days
    return {
        "active": active,
        "peremption": peremption,
        "jours_restants": jours_restants,
        "deja_prolonge": deja_prolonge,
    }


def equipements_en_alerte(conn, db_module, aujourdhui=None):
    """Retourne [(equipement_row, etat_alerte_dict), ...] pour les équipements en alerte active
    et pas encore notifiés (alerte_envoyee_le vide)."""
    resultat = []
    for eq in db_module.list_equipements(conn):
        etat = etat_alerte(eq, aujourdhui)
        if etat["active"] and not eq["alerte_envoyee_le"]:
            resultat.append((eq, etat))
    return resultat
