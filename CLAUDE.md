# GMAO — Traçabilité du matériel hydrométrique (SPCMO)

## Objectif

Outil interne au Service de Prévision des Crues Méditerranée Ouest (SPCMO) pour
tracer le matériel hydrométrique (capteurs, centrales d'acquisition...) : sites
d'affectation, historique des changements, cycle de vie (durée de vie / rappel /
rallonge avant péremption), et consultation terrain via QR code.

## Stack technique

- **Python 3.9+** (testé avec 3.14.5), **Flask** (Blueprints), **Jinja2** (dépendance
  transitive de Flask — non listée dans `requirements.txt` mais utilisée directement
  par `app/publication.py` et `scripts/generate_site.py`)
- **SQLite** via `sqlite3` de la stdlib, sans ORM — requêtes SQL inline dans `app/db.py`,
  `conn.row_factory = sqlite3.Row`
- Front-end **HTML/CSS/JS vanilla** (pas de framework JS, pas d'étape de build) +
  **Leaflet.js** vendorisé localement (`app/static/leaflet/`) pour la cartographie
- `qrcode` + `Pillow` + `ReportLab` (génération QR codes et PDF d'étiquettes),
  `openpyxl` (import Excel ponctuel), `python-dateutil`

## Architecture

- `run.py` — point d'entrée Flask, route `/` (dashboard), enregistrement des Blueprints
- `app/db.py` — toute la couche données (schéma, requêtes, migrations légères via
  `_add_col_if_missing`)
- `app/routes/{equipements,sites,parametres}.py` — Blueprints (routes découpées depuis
  un `run.py` monolithique initial)
- `app/{alertes,mail,publication,sante,settings,qrcodes,forms}.py` — modules métier
  (péremption, envoi mail, publication GitHub Pages, statut de connexion, réglages
  propres au poste, génération QR/PDF, helpers de formulaires)
- `app/templates/` — Jinja2, tous héritent de `base.html` (blocks `extra_head` /
  `content` / `extra_scripts`)
- `app/static/gmao-common.js`, `app/static/leaflet/gmao-map.js` — JS partagé entre
  templates (tri de tableaux, cascades de champs, carte)
- `scripts/` — tâches autonomes : `verifier_alertes.py` (planifiée quotidiennement,
  Planificateur de tâches Windows), `generate_site.py` / `generate_qrcodes.py`
  (génération statique), `import_excel.py` (import ponctuel)
- `docs/` — fiches HTML statiques publiques, servies par **GitHub Pages**
  (`https://spcmo.github.io/GMAO/e/<id>.html`), régénérées et poussées automatiquement
  par `app/publication.py`
- `apps_script/gmao_mail_relay.gs` — relais Google Apps Script (contournement du
  blocage SMTP du réseau SPCMO)

## Conventions de code observées

- **Noms de fonctions/variables et commentaires en français** dans tout le code Python
  (`list_equipements`, `changer_affectation`, `verifier_chevauchement`...)
- Commentaires/docstrings expliquent souvent le **pourquoi** métier, pas juste le quoi
  (ex. pourquoi tel ordre de priorité de couleur, pourquoi telle contrainte de date)
- Chaque module métier commence par une **docstring de module** résumant son rôle
- Terminologie UI et code alignées (les libellés des templates reprennent le
  vocabulaire des fonctions `db.py`)

## Points d'attention récurrents

- **Proxy réseau RIE/SPCMO obligatoire** pour toute connexion sortante (git, mail,
  pip) : ni `git`, ni `curl`, ni `urllib`/`pip` ne le détectent automatiquement
  (contrairement au navigateur). Adresse en dur dans `config.PROXY_RIE`, utilisée par
  `app/mail.py` et `app/publication.py`.
- **`settings.json` et `data/gmao.db` sont propres à chaque poste**, exclus du dépôt
  (`.gitignore`) — ne jamais les committer ni écraser la base réseau partagée.
- La base SQLite peut être **locale ou partagée sur le réseau SPCMO** (chemin UNC,
  usage multi-postes simultané) — réglable via `⚙️ Paramètres` dans l'appli.
- **L'URL d'un QR code ne doit jamais changer** une fois l'étiquette imprimée et collée
  sur le matériel — elle est basée sur l'identifiant technique de l'équipement, pas sur
  son nom ni ses données (qui, eux, changent).
- Toute modification impactant une fiche publique doit déclencher
  `publication.publier_en_tache_de_fond()` (régénère les fiches `docs/e/*.html` +
  commit + push GitHub en tâche de fond).
- **3 destinations à tenir synchronisées** après une modification de code : poste
  local, copie sur le réseau SPCMO, dépôt GitHub.
- Vocabulaire métier : **UH** (Unité Hydrographique de gestion — valeurs actuelles
  11/34/66, `db.UH_VALEURS`), **durée de vie / rappel / rallonge** (cycle de
  péremption du matériel), **affectation** (association équipement ↔ site dans le
  temps, avec historique).
- Le remote `origin` est authentifié via un **token d'accès personnel GitHub**
  (scope Contents) intégré à l'URL du remote — à régénérer depuis GitHub si expiré
  (voir `Aide.html`, section Paramétrage).

## Commandes utiles

```bash
# Lancer l'appli en local
venv\Scripts\python.exe run.py          # ou double-clic Lancer_GMAO.bat

# Vérifier/installer l'environnement (Python + dépendances)
Test_pr_install.bat                      # ou venv\Scripts\python.exe Test_pr_install.py

# Vérifier la syntaxe d'un fichier Python modifié
python -m py_compile <fichier.py>

# Vérification manuelle des alertes de péremption (normalement planifiée à 7h)
venv\Scripts\python.exe scripts\verifier_alertes.py

# Régénérer le site statique / les QR codes de tous les équipements
venv\Scripts\python.exe scripts\generate_site.py
venv\Scripts\python.exe scripts\generate_qrcodes.py
```
