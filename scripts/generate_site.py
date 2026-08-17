"""Génère les fiches HTML statiques (une par équipement) à publier en ligne.

Usage: venv/Scripts/python.exe scripts/generate_site.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jinja2 import Environment, FileSystemLoader

import config
from app import db

INDEX_HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>GMAO — Matériel hydrométrique</title></head>
<body style="font-family:system-ui;padding:2rem;color:#374151;">
<p>Cette page ne liste pas les équipements. Scannez le QR code apposé sur le matériel pour accéder à sa fiche.</p>
</body></html>
"""


def main():
    env = Environment(loader=FileSystemLoader(os.path.join(config.BASE_DIR, "app", "templates")))
    template = env.get_template("fiche.html")

    os.makedirs(os.path.join(config.DOCS_DIR, "e"), exist_ok=True)

    with db.db_session() as conn:
        equipements = db.list_equipements(conn)
        count = 0
        for e in equipements:
            equipement = db.get_equipement(conn, e["id"])
            site_actuel = db.get_site_actuel(conn, e["id"])
            historique = db.get_historique(conn, e["id"])
            html = template.render(equipement=equipement, site_actuel=site_actuel, historique=historique)
            out_path = os.path.join(config.DOCS_DIR, "e", f"{e['id']}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            count += 1

    with open(os.path.join(config.DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_HTML)

    print(f"{count} fiche(s) générée(s) dans {os.path.join(config.DOCS_DIR, 'e')}")


if __name__ == "__main__":
    main()
