"""Routes de gestion des sites : liste, création, modification (localisation,
UH de gestion, statut maintenance, statut de fermeture)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db, publication
from app.forms import parse_coord

sites_bp = Blueprint("sites", __name__)

# Correspondance nom de colonne (Paramètres > Tri par défaut) -> index de cellule dans
# la ligne du tableau (voir sites.html, même ordre que le tableau th-triable).
COLONNE_INDEX_SITES = {
    "site": 0, "nb_equipements": 1, "uh": 2, "maintenance": 3, "statut": 4, "localisation": 5,
}


@sites_bp.route("/sites")
def gestion_sites():
    with db.db_session() as conn:
        sites = db.list_all_sites(conn)
        tri_defaut = [
            [COLONNE_INDEX_SITES[c], 1]
            for c in db.get_tri_config(conn, "sites") if c in COLONNE_INDEX_SITES
        ]
    return render_template("sites.html", sites=sites, tri_defaut=tri_defaut)


@sites_bp.route("/sites/nouveau", methods=["GET", "POST"])
def nouveau_site():
    if request.method == "POST":
        nom = request.form["nom"].strip()
        maintenance = request.form.get("maintenance") == "on"
        lat = parse_coord(request.form.get("lat"))
        lon = parse_coord(request.form.get("lon"))
        uh = request.form.get("uh_gestion") or None
        with db.db_session() as conn:
            db.create_site(conn, nom, maintenance=maintenance, lat=lat, lon=lon, uh_gestion=uh)
        publication.publier_en_tache_de_fond()
        flash(f"Site « {nom} » créé.")
        return redirect(url_for("sites.gestion_sites"))
    return render_template("nouveau_site.html", uh_valeurs=db.UH_VALEURS)


@sites_bp.route("/sites/<nom>/supprimer", methods=["POST"])
def supprimer_site(nom):
    with db.db_session() as conn:
        supprime = db.delete_site(conn, nom)
    if supprime:
        flash(f"Site « {nom} » supprimé.")
    else:
        flash(f"Impossible de supprimer « {nom} » : au moins un équipement y est encore affecté.")
    return redirect(url_for("sites.gestion_sites"))


@sites_bp.route("/sites/<nom>/modifier", methods=["GET", "POST"])
def modifier_site(nom):
    with db.db_session() as conn:
        if request.method == "POST":
            lat = parse_coord(request.form.get("lat"))
            lon = parse_coord(request.form.get("lon"))
            maintenance = request.form.get("maintenance") == "on"
            uh = request.form.get("uh_gestion") or None
            date_fermeture = request.form.get("date_fermeture", "").strip() or None
            raison_fermeture = request.form.get("raison_fermeture", "").strip()
            if raison_fermeture == "__libre__":
                raison_fermeture = request.form.get("raison_fermeture_libre", "").strip()
            # Pas de raison sans date de fermeture (garde-fou serveur, en plus du JS ;
            # update_site() applique aussi cette règle de son côté).
            raison_fermeture = (raison_fermeture or None) if date_fermeture else None
            db.update_site(
                conn, nom, maintenance, lat, lon, uh_gestion=uh,
                date_fermeture=date_fermeture, raison_fermeture=raison_fermeture,
            )
            flash(f"Site « {nom} » mis à jour.")
            return redirect(url_for("sites.gestion_sites"))
        site = db.get_site(conn, nom)
        raisons_fermeture = db.list_raisons_fermeture(conn)
    return render_template(
        "modifier_site.html", site=site, uh_valeurs=db.UH_VALEURS, raisons_fermeture=raisons_fermeture
    )
