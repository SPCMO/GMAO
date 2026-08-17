import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "gmao.db")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
ETIQUETTES_DIR = os.path.join(BASE_DIR, "etiquettes")

# URL de base des fiches publiées (QR codes). A ajuster une fois l'hébergement choisi.
FICHE_BASE_URL = "https://spcmo.github.io/GMAO/e"
