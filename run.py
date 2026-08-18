import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory

import config
from app import db, settings as app_settings, alertes
from app import qrcodes

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "gmao-local-dev"


def _parse_coord(valeur):
    valeur = (valeur or "").strip()
    return float(valeur) if valeur else None


def _parse_float(valeur):
    valeur = (valeur or "").strip()
    return float(valeur) if valeur else None


def _equipement_form_fields(form):
    return {
        "date_creation": form.get("date_creation") or None,
        "type": form.get("type") or None,
        "sous_type": form.get("sous_type") or None,
        "duree_vie_ans": _parse_float(form.get("duree_vie_ans")),
        "rappel_ans": _parse_float(form.get("rappel_ans")),
        "rallonge_ans": _parse_float(form.get("rallonge_ans")),
    }


def _listes_reference(conn):
    return {
        "types": db.list_types(conn),
        "sous_types_json": db.list_sous_types_tous(conn),
        "durees_vie": db.list_durees_vie(conn),
        "rappels": db.list_rappels(conn),
        "rallonges": db.list_rallonges(conn),
        "uh_valeurs": db.UH_VALEURS,
    }


@app.route("/")
def dashboard():
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        sites = db.list_sites(conn)
        couleurs = db.list_couleurs(conn)
    aujourdhui = date.today()
    lignes = []
    for e in equipements:
        etat = alertes.etat_alerte(e, aujourdhui)
        if e["site_maintenance"]:
            couleur_fond = couleurs.get("maintenance")
        elif e["site_uh"] in db.UH_VALEURS:
            couleur_fond = couleurs.get(f"uh_{e['site_uh']}")
        else:
            couleur_fond = None
        lignes.append({"e": e, "etat": etat, "couleur_fond": couleur_fond})
    types = sorted({l["e"]["type"] for l in lignes if l["e"]["type"]})
    return render_template(
        "dashboard.html", lignes=lignes, sites=sites, couleurs=couleurs,
        uh_valeurs=db.UH_VALEURS, types=types,
    )


@app.route("/equipements")
def gestion_equipements():
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
    aujourdhui = date.today()
    lignes = [{"e": e, "etat": alertes.etat_alerte(e, aujourdhui)} for e in equipements]
    return render_template("equipements.html", lignes=lignes)


@app.route("/equipement/nouveau", methods=["GET", "POST"])
def nouveau_equipement():
    with db.db_session() as conn:
        sites = db.list_sites(conn)
        listes = _listes_reference(conn)
        if request.method == "POST":
            nom = request.form["nom"].strip()
            site = request.form["site"].strip()
            nouveau_site = site == "__new__"
            if nouveau_site:
                site = request.form.get("nouveau_site_nom", "").strip()
            date_installation = request.form["date_installation"]
            champs = _equipement_form_fields(request.form)
            db.create_equipement(
                conn, nom, date_installation, site,
                date_debut=date.today().isoformat(), **champs
            )
            if nouveau_site:
                lat = _parse_coord(request.form.get("lat"))
                lon = _parse_coord(request.form.get("lon"))
                uh = request.form.get("uh_gestion") or None
                db.update_site(conn, site, maintenance=False, lat=lat, lon=lon, uh_gestion=uh)
            flash(f"Équipement « {nom} » créé, affecté à « {site} » depuis aujourd'hui.")
            return redirect(url_for("gestion_equipements"))
    return render_template(
        "nouveau.html", sites=sites, aujourdhui=date.today().isoformat(), **listes
    )


@app.route("/equipement/<equipement_id>")
def detail_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        historique = db.get_historique(conn, equipement_id)
        site_geo = db.get_site(conn, site_actuel["site"]) if site_actuel else None
    _, _, pdf_path = qrcodes.generate([equipement_id])
    return render_template(
        "detail.html", equipement=equipement, site_actuel=site_actuel,
        historique=historique, site_geo=site_geo, pdf_filename=os.path.basename(pdf_path),
    )


@app.route("/equipement/<equipement_id>/modifier", methods=["GET", "POST"])
def modifier_equipement(equipement_id):
    with db.db_session() as conn:
        listes = _listes_reference(conn)
        if request.method == "POST":
            champs = _equipement_form_fields(request.form)
            champs["nom"] = request.form["nom"].strip()
            champs["date_installation"] = request.form["date_installation"]
            date_retrait = request.form.get("date_retrait", "").strip()
            champs["date_retrait"] = date_retrait or None
            raison = request.form.get("raison_retrait", "").strip()
            if raison == "__libre__":
                raison = request.form.get("raison_retrait_libre", "").strip()
            champs["raison_retrait"] = raison or None
            db.update_equipement(conn, equipement_id, **champs)
            flash(f"Équipement « {champs['nom']} » mis à jour.")
            return redirect(url_for("detail_equipement", equipement_id=equipement_id))
        equipement = db.get_equipement(conn, equipement_id)
    depuis_alerte = request.args.get("depuis_alerte") == "1"
    return render_template(
        "modifier_equipement.html", equipement=equipement,
        depuis_alerte=depuis_alerte, **listes
    )


@app.route("/equipement/<equipement_id>/prolonger", methods=["POST"])
def prolonger_equipement(equipement_id):
    with db.db_session() as conn:
        db.prolonger_equipement(conn, equipement_id)
        equipement = db.get_equipement(conn, equipement_id)
    flash(f"« {equipement['nom']} » prolongé de {equipement['rallonge_ans']} an(s).")
    return redirect(url_for("modifier_equipement", equipement_id=equipement_id))


@app.route("/equipement/<equipement_id>/affecter", methods=["GET", "POST"])
def affecter_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        sites = db.list_sites(conn)
        if request.method == "POST":
            nouveau_site = request.form["nouveau_site"].strip()
            est_nouveau_site = nouveau_site == "__new__"
            if est_nouveau_site:
                nouveau_site = request.form.get("nouveau_site_nom", "").strip()
            date_transfert = request.form["date_transfert"]
            db.changer_affectation(conn, equipement_id, nouveau_site, date_transfert)
            if est_nouveau_site:
                lat = _parse_coord(request.form.get("lat"))
                lon = _parse_coord(request.form.get("lon"))
                uh = request.form.get("uh_gestion") or None
                db.update_site(conn, nouveau_site, maintenance=False, lat=lat, lon=lon, uh_gestion=uh)
            flash(f"« {equipement['nom']} » réaffecté à {nouveau_site}.")
            return redirect(url_for("detail_equipement", equipement_id=equipement_id))
    return render_template(
        "affecter.html", equipement=equipement, site_actuel=site_actuel,
        sites=sites, aujourdhui=date.today().isoformat(), uh_valeurs=db.UH_VALEURS,
    )


@app.route("/sites")
def gestion_sites():
    with db.db_session() as conn:
        sites = db.list_all_sites(conn)
    return render_template("sites.html", sites=sites)


@app.route("/sites/nouveau", methods=["GET", "POST"])
def nouveau_site():
    if request.method == "POST":
        nom = request.form["nom"].strip()
        maintenance = request.form.get("maintenance") == "on"
        lat = _parse_coord(request.form.get("lat"))
        lon = _parse_coord(request.form.get("lon"))
        uh = request.form.get("uh_gestion") or None
        with db.db_session() as conn:
            db.create_site(conn, nom, maintenance=maintenance, lat=lat, lon=lon, uh_gestion=uh)
        flash(f"Site « {nom} » créé.")
        return redirect(url_for("gestion_sites"))
    return render_template("nouveau_site.html", uh_valeurs=db.UH_VALEURS)


@app.route("/sites/<nom>/modifier", methods=["GET", "POST"])
def modifier_site(nom):
    with db.db_session() as conn:
        if request.method == "POST":
            lat = _parse_coord(request.form.get("lat"))
            lon = _parse_coord(request.form.get("lon"))
            maintenance = request.form.get("maintenance") == "on"
            uh = request.form.get("uh_gestion") or None
            db.update_site(conn, nom, maintenance, lat, lon, uh_gestion=uh)
            flash(f"Site « {nom} » mis à jour.")
            return redirect(url_for("gestion_sites"))
        site = db.get_site(conn, nom)
    return render_template("modifier_site.html", site=site, uh_valeurs=db.UH_VALEURS)


@app.route("/equipement/<equipement_id>/fiche")
def fiche_publique(equipement_id):
    """Aperçu local de la fiche publique (même rendu que la page statique générée)."""
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        historique = db.get_historique(conn, equipement_id)
    return render_template(
        "fiche.html", equipement=equipement, site_actuel=site_actuel, historique=historique
    )


@app.route("/parametres", methods=["GET", "POST"])
def parametres():
    if request.method == "POST":
        nouveau_chemin = request.form["db_path"].strip()
        app_settings.set_db_path(nouveau_chemin)
        flash("Emplacement de la base enregistré.")
        return redirect(url_for("parametres"))
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
        )
    return render_template("parametres.html", **contexte)


@app.route("/parametres/smtp", methods=["POST"])
def parametres_smtp():
    app_settings.set_smtp_config(
        request.form["smtp_host"].strip(),
        int(request.form["smtp_port"]),
        request.form["smtp_user"].strip(),
        request.form.get("smtp_password", "").strip(),
    )
    flash("Configuration mail enregistrée.")
    return redirect(url_for("parametres"))


@app.route("/parametres/relais-mail", methods=["POST"])
def parametres_relais_mail():
    app_settings.set_apps_script_config(
        request.form["apps_script_url"].strip(),
        request.form.get("apps_script_token", "").strip(),
    )
    flash("Relais mail (Apps Script) enregistré.")
    return redirect(url_for("parametres"))


@app.route("/parametres/relais-mail/tester", methods=["POST"])
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
    return redirect(url_for("parametres"))


@app.route("/parametres/types/ajouter", methods=["POST"])
def parametres_types_ajouter():
    nom = request.form["nom"].strip()
    if nom:
        with db.db_session() as conn:
            db.add_type(conn, nom)
        flash(f"Type « {nom} » ajouté.")
    return redirect(url_for("parametres"))


@app.route("/parametres/types/supprimer", methods=["POST"])
def parametres_types_supprimer():
    nom = request.form["nom"]
    with db.db_session() as conn:
        db.delete_type(conn, nom)
    flash(f"Type « {nom} » supprimé.")
    return redirect(url_for("parametres"))


@app.route("/parametres/types/monter", methods=["POST"])
def parametres_types_monter():
    with db.db_session() as conn:
        db.deplacer_type(conn, request.form["nom"], -1)
    return redirect(url_for("parametres"))


@app.route("/parametres/types/descendre", methods=["POST"])
def parametres_types_descendre():
    with db.db_session() as conn:
        db.deplacer_type(conn, request.form["nom"], 1)
    return redirect(url_for("parametres"))


@app.route("/parametres/sous-types/ajouter", methods=["POST"])
def parametres_sous_types_ajouter():
    type_nom = request.form["type"].strip()
    nom = request.form["nom"].strip()
    if type_nom and nom:
        with db.db_session() as conn:
            db.add_sous_type(conn, type_nom, nom)
        flash(f"Sous-type « {nom} » ajouté à « {type_nom} ».")
    return redirect(url_for("parametres"))


@app.route("/parametres/sous-types/supprimer", methods=["POST"])
def parametres_sous_types_supprimer():
    type_nom = request.form["type"]
    nom = request.form["nom"]
    with db.db_session() as conn:
        db.delete_sous_type(conn, type_nom, nom)
    flash(f"Sous-type « {nom} » supprimé.")
    return redirect(url_for("parametres"))


@app.route("/parametres/sous-types/monter", methods=["POST"])
def parametres_sous_types_monter():
    with db.db_session() as conn:
        db.deplacer_sous_type(conn, request.form["type"], request.form["nom"], -1)
    return redirect(url_for("parametres"))


@app.route("/parametres/sous-types/descendre", methods=["POST"])
def parametres_sous_types_descendre():
    with db.db_session() as conn:
        db.deplacer_sous_type(conn, request.form["type"], request.form["nom"], 1)
    return redirect(url_for("parametres"))


def _route_options(nom_liste, ajouter_fn, supprimer_fn):
    def ajouter():
        annees = _parse_float(request.form.get("annees"))
        if annees is not None:
            with db.db_session() as conn:
                ajouter_fn(conn, annees)
            flash(f"Valeur {annees} ajoutée.")
        return redirect(url_for("parametres"))

    def supprimer():
        annees = _parse_float(request.form.get("annees"))
        with db.db_session() as conn:
            supprimer_fn(conn, annees)
        flash(f"Valeur {annees} supprimée.")
        return redirect(url_for("parametres"))

    return ajouter, supprimer


_durees_ajouter, _durees_supprimer = _route_options("durees_vie", db.add_duree_vie, db.delete_duree_vie)
app.add_url_rule("/parametres/durees-vie/ajouter", "parametres_durees_ajouter", _durees_ajouter, methods=["POST"])
app.add_url_rule("/parametres/durees-vie/supprimer", "parametres_durees_supprimer", _durees_supprimer, methods=["POST"])

_rappels_ajouter, _rappels_supprimer = _route_options("rappels", db.add_rappel, db.delete_rappel)
app.add_url_rule("/parametres/rappels/ajouter", "parametres_rappels_ajouter", _rappels_ajouter, methods=["POST"])
app.add_url_rule("/parametres/rappels/supprimer", "parametres_rappels_supprimer", _rappels_supprimer, methods=["POST"])

_rallonges_ajouter, _rallonges_supprimer = _route_options("rallonges", db.add_rallonge, db.delete_rallonge)
app.add_url_rule("/parametres/rallonges/ajouter", "parametres_rallonges_ajouter", _rallonges_ajouter, methods=["POST"])
app.add_url_rule("/parametres/rallonges/supprimer", "parametres_rallonges_supprimer", _rallonges_supprimer, methods=["POST"])


@app.route("/parametres/uh-emails/ajouter", methods=["POST"])
def parametres_uh_emails_ajouter():
    uh = request.form["uh"].strip()
    email = request.form["email"].strip()
    if uh and email:
        with db.db_session() as conn:
            db.add_uh_email(conn, uh, email)
        flash(f"Adresse ajoutée pour l'UH {uh}.")
    return redirect(url_for("parametres"))


@app.route("/parametres/uh-emails/supprimer", methods=["POST"])
def parametres_uh_emails_supprimer():
    uh = request.form["uh"]
    email = request.form["email"]
    with db.db_session() as conn:
        db.delete_uh_email(conn, uh, email)
    flash(f"Adresse supprimée pour l'UH {uh}.")
    return redirect(url_for("parametres"))


@app.route("/parametres/couleurs", methods=["POST"])
def parametres_couleurs():
    with db.db_session() as conn:
        for cle in ("uh_11", "uh_34", "uh_66", "maintenance"):
            valeur = request.form.get(cle, "").strip()
            if valeur:
                db.set_couleur(conn, cle, valeur)
    flash("Couleurs enregistrées.")
    return redirect(url_for("parametres"))


@app.route("/qrcodes/generer", methods=["POST"])
def generer_qrcodes_selection():
    ids = request.form.getlist("ids")
    if not ids:
        flash("Aucun équipement sélectionné.")
        return redirect(url_for("dashboard"))
    count, sheet_path, pdf_path = qrcodes.generate(ids)
    return redirect(url_for("etiquettes_file", filename=os.path.basename(sheet_path)))


@app.route("/etiquettes/<path:filename>")
def etiquettes_file(filename):
    return send_from_directory(config.ETIQUETTES_DIR, filename)


@app.route("/aide")
def aide():
    return send_from_directory(config.BASE_DIR, "Aide.html")


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
