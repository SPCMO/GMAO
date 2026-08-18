"""Routes liées au cycle de vie d'un équipement : liste de gestion, création, fiche
détail, modification, réaffectation, prolongation/annulation, étiquette QR/PDF."""
import os
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import alertes, db, publication, qrcodes
from app.forms import parse_coord, equipement_form_fields, listes_reference

equipements_bp = Blueprint("equipements", __name__)

# Correspondance nom de colonne (Paramètres > Tri par défaut) -> index de cellule dans
# la ligne du tableau (voir equipements.html, même ordre que le tableau th-triable).
COLONNE_INDEX_EQUIPEMENTS = {"equipement": 0, "type": 1, "site": 2, "uh": 3, "statut": 4}


@equipements_bp.route("/equipements")
def gestion_equipements():
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        tri_defaut = [
            [COLONNE_INDEX_EQUIPEMENTS[c], 1]
            for c in db.get_tri_config(conn, "equipements") if c in COLONNE_INDEX_EQUIPEMENTS
        ]
    aujourdhui = date.today()
    lignes = [{"e": e, "etat": alertes.etat_alerte(e, aujourdhui)} for e in equipements]
    return render_template("equipements.html", lignes=lignes, tri_defaut=tri_defaut)


@equipements_bp.route("/equipement/nouveau", methods=["GET", "POST"])
def nouveau_equipement():
    with db.db_session() as conn:
        sites = db.list_sites(conn)
        listes = listes_reference(conn)
        if request.method == "POST":
            nom = request.form["nom"].strip()
            site = request.form["site"].strip()
            nouveau_site = site == "__new__"
            if nouveau_site:
                site = request.form.get("nouveau_site_nom", "").strip()
            date_installation = request.form["date_installation"]
            champs = equipement_form_fields(request.form)
            db.create_equipement(
                conn, nom, date_installation, site,
                date_debut=date.today().isoformat(), **champs
            )
            if nouveau_site:
                # Un nouveau site créé à la volée depuis ce formulaire n'a pas encore de
                # localisation/UH tant qu'on ne les saisit pas ici (voir nouveau.html).
                lat = parse_coord(request.form.get("lat"))
                lon = parse_coord(request.form.get("lon"))
                uh = request.form.get("uh_gestion") or None
                db.update_site(conn, site, maintenance=False, lat=lat, lon=lon, uh_gestion=uh)
            publication.publier_en_tache_de_fond()
            flash(f"Équipement « {nom} » créé, affecté à « {site} » depuis aujourd'hui.")
            return redirect(url_for("equipements.gestion_equipements"))
    return render_template(
        "nouveau.html", sites=sites, aujourdhui=date.today().isoformat(), **listes
    )


@equipements_bp.route("/equipement/<equipement_id>")
def detail_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        historique = db.get_historique(conn, equipement_id)
        site_geo = db.get_site(conn, site_actuel["site"]) if site_actuel else None
    # Réutilise l'étiquette déjà générée si elle existe (voir qrcodes.generate) : cette route
    # est appelée à chaque consultation de la fiche, pas seulement à la création.
    _, _, pdf_path = qrcodes.generate([equipement_id])
    peut_annuler = db.peut_annuler_prolongation(equipement)
    return render_template(
        "detail.html", equipement=equipement, site_actuel=site_actuel,
        historique=historique, site_geo=site_geo, pdf_filename=os.path.basename(pdf_path),
        peut_annuler=peut_annuler,
    )


@equipements_bp.route("/equipement/<equipement_id>/modifier", methods=["GET", "POST"])
def modifier_equipement(equipement_id):
    with db.db_session() as conn:
        listes = listes_reference(conn)
        if request.method == "POST":
            champs = equipement_form_fields(request.form)
            champs["nom"] = request.form["nom"].strip()
            champs["date_installation"] = request.form["date_installation"]
            date_retrait = request.form.get("date_retrait", "").strip()
            champs["date_retrait"] = date_retrait or None
            raison = request.form.get("raison_retrait", "").strip()
            if raison == "__libre__":
                raison = request.form.get("raison_retrait_libre", "").strip()
            # Pas de raison sans date de retrait définitif (garde-fou serveur, en plus du JS).
            champs["raison_retrait"] = (raison or None) if champs["date_retrait"] else None
            db.update_equipement(conn, equipement_id, **champs)
            publication.publier_en_tache_de_fond()
            flash(f"Équipement « {champs['nom']} » mis à jour.")
            return redirect(url_for("equipements.detail_equipement", equipement_id=equipement_id))
        equipement = db.get_equipement(conn, equipement_id)
    depuis_alerte = request.args.get("depuis_alerte") == "1"
    return render_template(
        "modifier_equipement.html", equipement=equipement,
        depuis_alerte=depuis_alerte, **listes
    )


@equipements_bp.route("/equipement/<equipement_id>/supprimer", methods=["POST"])
def supprimer_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        nom = equipement["nom"] if equipement else equipement_id
        db.delete_equipement(conn, equipement_id)
    flash(f"Équipement « {nom} » supprimé définitivement.")
    return redirect(url_for("equipements.gestion_equipements"))


@equipements_bp.route("/equipement/<equipement_id>/prolonger", methods=["POST"])
def prolonger_equipement(equipement_id):
    with db.db_session() as conn:
        db.prolonger_equipement(conn, equipement_id)
        equipement = db.get_equipement(conn, equipement_id)
    flash(f"« {equipement['nom']} » prolongé de {equipement['rallonge_ans']} an(s).")
    return redirect(url_for("equipements.modifier_equipement", equipement_id=equipement_id))


@equipements_bp.route("/equipement/<equipement_id>/annuler-prolongation", methods=["POST"])
def annuler_prolongation_equipement(equipement_id):
    with db.db_session() as conn:
        annule = db.annuler_prolongation(conn, equipement_id)
        equipement = db.get_equipement(conn, equipement_id)
    if annule:
        flash(f"Prolongation de « {equipement['nom']} » annulée.")
    else:
        flash("Rien à annuler (aucune prolongation simple en cours).")
    return redirect(url_for("equipements.detail_equipement", equipement_id=equipement_id))


@equipements_bp.route("/equipement/<equipement_id>/regenerer-etiquette", methods=["POST"])
def regenerer_etiquette(equipement_id):
    qrcodes.generate([equipement_id], force=True)
    flash("Étiquette (QR code / PDF) régénérée.")
    return redirect(url_for("equipements.detail_equipement", equipement_id=equipement_id))


@equipements_bp.route("/equipement/<equipement_id>/affecter", methods=["GET", "POST"])
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
                lat = parse_coord(request.form.get("lat"))
                lon = parse_coord(request.form.get("lon"))
                uh = request.form.get("uh_gestion") or None
                db.update_site(conn, nouveau_site, maintenance=False, lat=lat, lon=lon, uh_gestion=uh)
            publication.publier_en_tache_de_fond()
            flash(f"« {equipement['nom']} » réaffecté à {nouveau_site}.")
            return redirect(url_for("equipements.detail_equipement", equipement_id=equipement_id))
    return render_template(
        "affecter.html", equipement=equipement, site_actuel=site_actuel,
        sites=sites, aujourdhui=date.today().isoformat(), uh_valeurs=db.UH_VALEURS,
    )


@equipements_bp.route("/equipement/<equipement_id>/fiche")
def fiche_publique(equipement_id):
    """Aperçu local de la fiche publique (même rendu que la page statique générée)."""
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        historique = db.get_historique(conn, equipement_id)
    return render_template(
        "fiche.html", equipement=equipement, site_actuel=site_actuel, historique=historique
    )


@equipements_bp.route("/qrcodes/generer", methods=["POST"])
def generer_qrcodes_selection():
    ids = request.form.getlist("ids")
    if not ids:
        flash("Aucun équipement sélectionné.")
        return redirect(url_for("dashboard"))
    count, sheet_path, pdf_path = qrcodes.generate(ids)
    return redirect(url_for("etiquettes_file", filename=os.path.basename(sheet_path)))
