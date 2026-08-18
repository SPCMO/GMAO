import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "gmao.db")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
ETIQUETTES_DIR = os.path.join(BASE_DIR, "etiquettes")

# URL de base des fiches publiées (QR codes). A ajuster une fois l'hébergement choisi.
FICHE_BASE_URL = "https://spcmo.github.io/GMAO/e"

# Proxy sortant obligatoire sur le réseau SPCMO/RIE pour toute connexion internet (voir
# Aide.html > Paramétrage) : contrairement au navigateur, git/curl/urllib ne le détectent
# pas automatiquement. Utilisé par app/mail.py (relais Apps Script) et app/publication.py
# (git push), en dur ici pour que ça fonctionne aussi sur le poste des collègues sans
# configuration préalable. Une variable d'environnement HTTPS_PROXY, si définie, reste
# prioritaire (utile si un poste n'est pas sur ce réseau).
PROXY_RIE = "http://pfrie-std.proxy.e2.rie.gouv.fr:8080"
