import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory

import config
from app import db, settings as app_settings
from app import qrcodes

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "gmao-local-dev"


@app.route("/")
def dashboard():
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        sites = db.list_sites(conn)
    return render_template("dashboard.html", equipements=equipements, sites=sites)


@app.route("/equipement/nouveau", methods=["GET", "POST"])
def nouveau_equipement():
    with db.db_session() as conn:
        sites = db.list_sites(conn)
        if request.method == "POST":
            nom = request.form["nom"].strip()
            site = request.form["site"].strip()
            if site == "__new__":
                site = request.form.get("nouveau_site_nom", "").strip()
            date_installation = request.form["date_installation"]
            db.create_equipement(
                conn, nom, date_installation, site, date_debut=date.today().isoformat()
            )
            flash(f"Équipement « {nom} » créé, affecté à « {site} » depuis aujourd'hui.")
            return redirect(url_for("dashboard"))
    return render_template("nouveau.html", sites=sites, aujourdhui=date.today().isoformat())


@app.route("/equipement/<equipement_id>")
def detail_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        historique = db.get_historique(conn, equipement_id)
    return render_template(
        "detail.html", equipement=equipement, site_actuel=site_actuel, historique=historique
    )


@app.route("/equipement/<equipement_id>/affecter", methods=["GET", "POST"])
def affecter_equipement(equipement_id):
    with db.db_session() as conn:
        equipement = db.get_equipement(conn, equipement_id)
        site_actuel = db.get_site_actuel(conn, equipement_id)
        sites = db.list_sites(conn)
        if request.method == "POST":
            nouveau_site = request.form["nouveau_site"].strip()
            date_transfert = request.form["date_transfert"]
            db.changer_affectation(conn, equipement_id, nouveau_site, date_transfert)
            flash(f"« {equipement['nom']} » réaffecté à {nouveau_site}.")
            return redirect(url_for("detail_equipement", equipement_id=equipement_id))
    return render_template(
        "affecter.html", equipement=equipement, site_actuel=site_actuel, sites=sites
    )


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
    return render_template("parametres.html", db_path=app_settings.get_db_path())


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
