from datetime import date

from flask import Flask, render_template, jsonify, send_from_directory

import config
from app import db, alertes, publication, sante
from app.routes.equipements import equipements_bp
from app.routes.sites import sites_bp
from app.routes.parametres import parametres_bp

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "gmao-local-dev"

app.register_blueprint(equipements_bp)
app.register_blueprint(sites_bp)
app.register_blueprint(parametres_bp)

# Correspondance nom de colonne (Paramètres > Tri par défaut) -> index réel de la
# cellule dans la ligne du tableau accueil (voir dashboard.html, même ordre que le
# tableau th-triable) ; utilisée pour traduire db.get_tri_config() en tri JS initial.
COLONNE_INDEX_ACCUEIL = {
    "equipement": 1, "type": 2, "sous_type": 3, "site": 4, "uh": 5,
    "affecte_depuis": 6, "installation": 7, "statut": 8, "tps_restant": 9, "duree_prolongee": 10,
}


def _style_site(couleurs, opacites, uh, maintenance, ferme, vide=False):
    """Couleur + opacité (%) d'un site selon son statut — même priorité utilisée pour la
    carte et pour le fond des lignes du tableau accueil : fermé > maintenance > sans
    équipement affecté (carte uniquement) > UH configurée > sans UH. Couleurs/opacités
    réglables dans Paramètres > Couleurs (voir db.COULEURS_PAR_DEFAUT)."""
    if ferme:
        cle = "ferme"
    elif maintenance:
        cle = "maintenance"
    elif vide:
        cle = "site_vide"
    elif uh in db.UH_VALEURS:
        cle = f"uh_{uh}"
    else:
        cle = "sans_uh"
    return couleurs.get(cle), opacites.get(cle, 100)


@app.route("/")
def dashboard():
    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        sites = db.list_sites(conn)
        couleurs = db.list_couleurs(conn)
        opacites = db.list_opacites(conn)
        sites_geo = db.list_all_sites(conn)
        tri_defaut_accueil = [
            [COLONNE_INDEX_ACCUEIL[c], 1]
            for c in db.get_tri_config(conn, "accueil") if c in COLONNE_INDEX_ACCUEIL
        ]
    aujourdhui = date.today()
    lignes = []
    equip_par_site = {}
    for e in equipements:
        etat = alertes.etat_alerte(e, aujourdhui)
        # Jours restants avant péremption, indépendamment du rappel (calculé même si le
        # rappel n'est pas configuré, contrairement à etat["jours_restants"]).
        peremption = alertes.date_peremption(e)
        jours_restants_vie = (peremption - aujourdhui).days if peremption and not e["date_retrait"] else None
        couleur_fond, opacite_fond = _style_site(
            couleurs, opacites, e["site_uh"], e["site_maintenance"], e["site_date_fermeture"]
        )
        site_ferme = bool(e["site_date_fermeture"])
        lignes.append({
            "e": e, "etat": etat, "couleur_fond": couleur_fond, "opacite_fond": opacite_fond,
            "site_ferme": site_ferme, "jours_restants_vie": jours_restants_vie,
        })
        if e["site_actuel"] and not e["date_retrait"]:
            equip_par_site.setdefault(e["site_actuel"], []).append({"id": e["id"], "nom": e["nom"]})
    types = sorted({l["e"]["type"] for l in lignes if l["e"]["type"]})

    # Carte : un marqueur par site (pas par équipement), coloré selon la même priorité
    # que le fond des lignes du tableau (voir _style_site) — fermé > maintenance > sans
    # équipement affecté (spécifique à la carte) > UH > sans UH configurée.
    sites_carte = []
    for s in sites_geo:
        if s["lat"] is None or s["lon"] is None:
            continue
        equip_ici = equip_par_site.get(s["nom"], [])
        couleur, opacite = _style_site(
            couleurs, opacites, s["uh_gestion"], s["maintenance"], s["date_fermeture"], vide=not equip_ici
        )
        sites_carte.append({
            "nom": s["nom"], "lat": s["lat"], "lon": s["lon"], "couleur": couleur, "opacite": opacite,
            "maintenance": bool(s["maintenance"]), "ferme": bool(s["date_fermeture"]),
            "equipements": equip_ici,
        })

    return render_template(
        "dashboard.html", lignes=lignes, sites=sites, couleurs=couleurs, opacites=opacites,
        uh_valeurs=db.UH_VALEURS, types=types, sites_carte=sites_carte,
        tri_defaut_accueil=tri_defaut_accueil,
    )


@app.route("/etiquettes/<path:filename>")
def etiquettes_file(filename):
    return send_from_directory(config.ETIQUETTES_DIR, filename)


@app.route("/aide")
def aide():
    return send_from_directory(config.BASE_DIR, "Aide.html")


@app.route("/api/statut-publication")
def api_statut_publication():
    return jsonify(publication.lire_statut() or {})


@app.route("/api/statut-connexion")
def api_statut_connexion():
    return jsonify(sante.verifier_connexion())


@app.route("/api/forcer-synchro", methods=["POST"])
def api_forcer_synchro():
    # Vérification base synchrone (rapide) + publication GitHub en tâche de fond
    # (peut prendre plusieurs secondes) : le bandeau reste utilisable pendant ce temps.
    connexion = sante.verifier_connexion()
    publication.publier_en_tache_de_fond()
    return jsonify({"connexion": connexion})


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
