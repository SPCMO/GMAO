"""Routes de la page Paramètres : chemin de la base, SMTP, relais mail Apps Script,
listes de référence (types/sous-types, durées de vie/rappel/rallonge, emails par UH,
raisons de fermeture de site) et couleurs de fond (UH / maintenance)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db, settings as app_settings
from app.forms import parse_float

parametres_bp = Blueprint("parametres", __name__)


@parametres_bp.route("/parametres", methods=["GET", "POST"])
def parametres():
    if request.method == "POST":
        nouveau_chemin = request.form["db_path"].strip()
        app_settings.set_db_path(nouveau_chemin)
        flash("Emplacement de la base enregistré.")
        return redirect(url_for("parametres.parametres"))
    with db.db_session() as conn:
        contexte = dict(
            db_path=app_settings.get_db_path(),
            smtp=app_settings.get_smtp_config(),
            apps_script=app_settings.get_apps_script_config(),
            types=db.list_types(conn),
            sous_types_json=db.list_sous_types_tous(conn),
            durees_vie=db.list_durees_vie(conn),
            rappels=db.list_rappels(conn),
            rallonges=db.list_rallonges(conn),
            uh_valeurs=db.UH_VALEURS,
            uh_emails=db.list_uh_emails_tous(conn),
            couleurs=db.list_couleurs(conn),
            raisons_fermeture=db.list_raisons_fermeture(conn),
            tri_colonnes=db.TRI_COLONNES,
            tri_actuel={
                cle: (db.get_tri_config(conn, cle) + ["", "", ""])[:3]
                for cle in db.TRI_COLONNES
            },
        )
    return render_template("parametres.html", **contexte)


@parametres_bp.route("/parametres/smtp", methods=["POST"])
def parametres_smtp():
    app_settings.set_smtp_config(
        request.form["smtp_host"].strip(),
        int(request.form["smtp_port"]),
        request.form["smtp_user"].strip(),
        request.form.get("smtp_password", "").strip(),
    )
    flash("Configuration mail enregistrée.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/relais-mail", methods=["POST"])
def parametres_relais_mail():
    app_settings.set_apps_script_config(
        request.form["apps_script_url"].strip(),
        request.form.get("apps_script_token", "").strip(),
    )
    flash("Relais mail (Apps Script) enregistré.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/relais-mail/tester", methods=["POST"])
def parametres_relais_mail_tester():
    destinataire = request.form["destinataire_test"].strip()
    from app import mail
    ok, erreur = mail.envoyer_mail(
        [destinataire], "[GMAO] Mail de test",
        "Ceci est un mail de test envoyé depuis GMAO (Paramètres > Relais mail).",
    )
    if ok:
        flash(f"Mail de test envoyé à {destinataire}.")
    else:
        flash(f"Échec de l'envoi du mail de test : {erreur}")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/types/ajouter", methods=["POST"])
def parametres_types_ajouter():
    nom = request.form["nom"].strip()
    if nom:
        with db.db_session() as conn:
            db.add_type(conn, nom)
        flash(f"Type « {nom} » ajouté.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/types/supprimer", methods=["POST"])
def parametres_types_supprimer():
    nom = request.form["nom"]
    with db.db_session() as conn:
        db.delete_type(conn, nom)
    flash(f"Type « {nom} » supprimé.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/types/monter", methods=["POST"])
def parametres_types_monter():
    with db.db_session() as conn:
        db.deplacer_type(conn, request.form["nom"], -1)
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/types/descendre", methods=["POST"])
def parametres_types_descendre():
    with db.db_session() as conn:
        db.deplacer_type(conn, request.form["nom"], 1)
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/sous-types/ajouter", methods=["POST"])
def parametres_sous_types_ajouter():
    type_nom = request.form["type"].strip()
    nom = request.form["nom"].strip()
    if type_nom and nom:
        with db.db_session() as conn:
            db.add_sous_type(conn, type_nom, nom)
        flash(f"Sous-type « {nom} » ajouté à « {type_nom} ».")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/sous-types/supprimer", methods=["POST"])
def parametres_sous_types_supprimer():
    type_nom = request.form["type"]
    nom = request.form["nom"]
    with db.db_session() as conn:
        db.delete_sous_type(conn, type_nom, nom)
    flash(f"Sous-type « {nom} » supprimé.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/sous-types/monter", methods=["POST"])
def parametres_sous_types_monter():
    with db.db_session() as conn:
        db.deplacer_sous_type(conn, request.form["type"], request.form["nom"], -1)
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/sous-types/descendre", methods=["POST"])
def parametres_sous_types_descendre():
    with db.db_session() as conn:
        db.deplacer_sous_type(conn, request.form["type"], request.form["nom"], 1)
    return redirect(url_for("parametres.parametres"))


def _route_options(ajouter_fn, supprimer_fn):
    """Fabrique une paire de vues ajouter/supprimer pour une liste de référence numérique
    (durée de vie, rappel, rallonge partagent exactement le même comportement)."""
    def ajouter():
        annees = parse_float(request.form.get("annees"))
        if annees is not None:
            with db.db_session() as conn:
                ajouter_fn(conn, annees)
            flash(f"Valeur {annees} ajoutée.")
        return redirect(url_for("parametres.parametres"))

    def supprimer():
        annees = parse_float(request.form.get("annees"))
        with db.db_session() as conn:
            supprimer_fn(conn, annees)
        flash(f"Valeur {annees} supprimée.")
        return redirect(url_for("parametres.parametres"))

    return ajouter, supprimer


_durees_ajouter, _durees_supprimer = _route_options(db.add_duree_vie, db.delete_duree_vie)
parametres_bp.add_url_rule("/parametres/durees-vie/ajouter", "parametres_durees_ajouter", _durees_ajouter, methods=["POST"])
parametres_bp.add_url_rule("/parametres/durees-vie/supprimer", "parametres_durees_supprimer", _durees_supprimer, methods=["POST"])

_rappels_ajouter, _rappels_supprimer = _route_options(db.add_rappel, db.delete_rappel)
parametres_bp.add_url_rule("/parametres/rappels/ajouter", "parametres_rappels_ajouter", _rappels_ajouter, methods=["POST"])
parametres_bp.add_url_rule("/parametres/rappels/supprimer", "parametres_rappels_supprimer", _rappels_supprimer, methods=["POST"])

_rallonges_ajouter, _rallonges_supprimer = _route_options(db.add_rallonge, db.delete_rallonge)
parametres_bp.add_url_rule("/parametres/rallonges/ajouter", "parametres_rallonges_ajouter", _rallonges_ajouter, methods=["POST"])
parametres_bp.add_url_rule("/parametres/rallonges/supprimer", "parametres_rallonges_supprimer", _rallonges_supprimer, methods=["POST"])


@parametres_bp.route("/parametres/uh-emails/ajouter", methods=["POST"])
def parametres_uh_emails_ajouter():
    uh = request.form["uh"].strip()
    email = request.form["email"].strip()
    if uh and email:
        with db.db_session() as conn:
            db.add_uh_email(conn, uh, email)
        flash(f"Adresse ajoutée pour l'UH {uh}.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/uh-emails/supprimer", methods=["POST"])
def parametres_uh_emails_supprimer():
    uh = request.form["uh"]
    email = request.form["email"]
    with db.db_session() as conn:
        db.delete_uh_email(conn, uh, email)
    flash(f"Adresse supprimée pour l'UH {uh}.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/raisons-fermeture/ajouter", methods=["POST"])
def parametres_raisons_fermeture_ajouter():
    nom = request.form["nom"].strip()
    if nom:
        with db.db_session() as conn:
            db.add_raison_fermeture(conn, nom)
        flash(f"Raison de fermeture « {nom} » ajoutée.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/raisons-fermeture/supprimer", methods=["POST"])
def parametres_raisons_fermeture_supprimer():
    nom = request.form["nom"]
    with db.db_session() as conn:
        db.delete_raison_fermeture(conn, nom)
    flash(f"Raison de fermeture « {nom} » supprimée.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/raisons-fermeture/monter", methods=["POST"])
def parametres_raisons_fermeture_monter():
    with db.db_session() as conn:
        db.deplacer_raison_fermeture(conn, request.form["nom"], -1)
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/raisons-fermeture/descendre", methods=["POST"])
def parametres_raisons_fermeture_descendre():
    with db.db_session() as conn:
        db.deplacer_raison_fermeture(conn, request.form["nom"], 1)
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/couleurs", methods=["POST"])
def parametres_couleurs():
    with db.db_session() as conn:
        for cle in ("uh_11", "uh_34", "uh_66", "maintenance"):
            valeur = request.form.get(cle, "").strip()
            if valeur:
                db.set_couleur(conn, cle, valeur)
    flash("Couleurs enregistrées.")
    return redirect(url_for("parametres.parametres"))


@parametres_bp.route("/parametres/tri/<cle>", methods=["POST"])
def parametres_tri(cle):
    if cle not in db.TRI_COLONNES:
        flash("Liste de tri inconnue.")
        return redirect(url_for("parametres.parametres"))
    colonnes = [request.form.get(f"niveau{i}", "").strip() for i in (1, 2, 3)]
    with db.db_session() as conn:
        db.set_tri_config(conn, cle, colonnes)
    flash("Tri par défaut enregistré.")
    return redirect(url_for("parametres.parametres"))
