from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash

import config
from app import db

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
            date_installation = request.form["date_installation"]
            db.create_equipement(conn, nom, date_installation, site, date_debut=date_installation)
            flash(f"Équipement « {nom} » créé.")
            return redirect(url_for("dashboard"))
    return render_template("nouveau.html", sites=sites)


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


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
