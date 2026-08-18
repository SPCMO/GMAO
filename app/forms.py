"""Fonctions de parsing des formulaires, partagées entre les blueprints de routes
(app/routes/equipements.py, sites.py, parametres.py)."""
from app import db


def parse_coord(valeur):
    valeur = (valeur or "").strip()
    return float(valeur) if valeur else None


def parse_float(valeur):
    valeur = (valeur or "").strip()
    return float(valeur) if valeur else None


def equipement_form_fields(form):
    return {
        "date_creation": form.get("date_creation") or None,
        "type": form.get("type") or None,
        "sous_type": form.get("sous_type") or None,
        "duree_vie_ans": parse_float(form.get("duree_vie_ans")),
        "rappel_ans": parse_float(form.get("rappel_ans")),
        "rallonge_ans": parse_float(form.get("rallonge_ans")),
    }


def listes_reference(conn):
    return {
        "types": db.list_types(conn),
        "sous_types_json": db.list_sous_types_tous(conn),
        "durees_vie": db.list_durees_vie(conn),
        "rappels": db.list_rappels(conn),
        "rallonges": db.list_rallonges(conn),
        "uh_valeurs": db.UH_VALEURS,
    }
