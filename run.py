from datetime import date

from flask import Flask, render_template, jsonify, send_from_directory

import config
from app import db, alertes, publication
from app.routes.equipements import equipements_bp
from app.routes.sites import sites_bp
from app.routes.parametres import parametres_bp

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "gmao-local-dev"

app.register_blueprint(equipements_bp)
app.register_blueprint(sites_bp)
app.register_blueprint(parametres_bp)


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
        site_ferme = bool(e["site_date_fermeture"])
        lignes.append({"e": e, "etat": etat, "couleur_fond": couleur_fond, "site_ferme": site_ferme})
    types = sorted({l["e"]["type"] for l in lignes if l["e"]["type"]})
    return render_template(
        "dashboard.html", lignes=lignes, sites=sites, couleurs=couleurs,
        uh_valeurs=db.UH_VALEURS, types=types,
    )


@app.route("/etiquettes/<path:filename>")
def etiquettes_file(filename):
    return send_from_directory(config.ETIQUETTES_DIR, filename)


@app.route("/aide")
def aide():
    return send_from_directory(config.BASE_DIR, "Aide.html")


@app.route("/guides")
def guides():
    return send_from_directory(config.BASE_DIR, "Guides.html")


@app.route("/api/statut-publication")
def api_statut_publication():
    return jsonify(publication.lire_statut() or {})


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
