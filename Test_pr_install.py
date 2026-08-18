# -*- coding: utf-8 -*-
"""
Test_pr_install.py — Vérification de l'environnement Python pour l'outil GMAO.

Usage :  python Test_pr_install.py
         (ou double-clic via Test_pr_install.bat)
"""

import sys
import subprocess
import importlib
import importlib.metadata
import os
import io
import urllib.request


def _version_of(pip_name, import_name, mod):
    dist_name = (pip_name or import_name).split("[")[0]
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return getattr(mod, "__version__", "?")

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Constantes ─────────────────────────────────────────────────────────────
MIN_PYTHON = (3, 9)

# (nom_import, nom_pip, version_minimale_optionnelle)
REQUIRED = [
    ("sqlite3",   None,          None),          # stdlib
    ("flask",     "flask",       None),
    ("qrcode",    "qrcode[pil]", None),
    ("PIL",       "pillow",      None),
    ("openpyxl",  "openpyxl",    None),
    ("reportlab", "reportlab",   None),
    ("dateutil",  "python-dateutil", None),
]

OPTIONAL = []

SEP2 = "=" * 60


def titre(txt):
    print(f"\n{SEP2}")
    print(f"  {txt}")
    print(SEP2)


def ok(msg):    print(f"  [OK]   {msg}")
def warn(msg):  print(f"  [!!]   {msg}")
def err(msg):   print(f"  [ERR]  {msg}")


# ── 1. Version Python ───────────────────────────────────────────────────────
def check_python():
    titre("1 / Vérification Python")
    v = sys.version_info
    vstr = f"{v.major}.{v.minor}.{v.micro}"
    print(f"  Version détectée : Python {vstr}")

    if (v.major, v.minor) < MIN_PYTHON:
        err(f"Python {vstr} trop ancien. Version minimale requise : {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")
        err("Installez une version récente depuis https://www.python.org et relancez Test_pr_install.bat.")
        return False
    ok(f"Python {vstr} — compatible.")
    return True


# ── 2. Packages requis ──────────────────────────────────────────────────────
def check_packages(package_list, label="Requis"):
    titre(f"2 / Vérification des packages {label}")
    manquants = []
    for import_name, pip_name, ver_min in package_list:
        try:
            mod = importlib.import_module(import_name)
            ver = _version_of(pip_name, import_name, mod)
            ok(f"{import_name:<12} v{ver}")
        except ImportError:
            if pip_name:
                err(f"{import_name:<12} NON INSTALLÉ  (pip install {pip_name})")
                manquants.append((pip_name, ver_min))
            else:
                err(f"{import_name:<12} NON DISPONIBLE (module stdlib manquant — réinstaller Python)")
    return manquants


# ── 3. Fichiers projet ──────────────────────────────────────────────────────
def check_project_files():
    titre("3 / Vérification des fichiers du projet")
    base = os.path.dirname(os.path.abspath(__file__))
    attendus = [
        "run.py",
        "config.py",
        "requirements.txt",
        "Aide.html",
        os.path.join("app", "db.py"),
        os.path.join("app", "settings.py"),
        os.path.join("app", "qrcodes.py"),
        os.path.join("app", "templates", "base.html"),
        os.path.join("scripts", "generate_site.py"),
        os.path.join("scripts", "generate_qrcodes.py"),
    ]
    manquants = []
    for f in attendus:
        path = os.path.join(base, f)
        if os.path.isfile(path):
            ok(f"{f}")
        else:
            err(f"{f}  — MANQUANT")
            manquants.append(f)

    data_dir = os.path.join(base, "data")
    if not os.path.isdir(data_dir):
        warn("Le dossier 'data/' n'existe pas encore — il sera créé automatiquement au premier lancement.")
    else:
        ok("data/  (dossier présent)")

    return manquants


# ── 4. Détection du proxy ───────────────────────────────────────────────────
def detecter_proxy():
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    try:
        proxies = urllib.request.getproxies()
        for key in ("https", "http"):
            if key in proxies and proxies[key]:
                return proxies[key]
    except Exception:
        pass
    return ""


# ── 5. Proposition d'installation ──────────────────────────────────────────
def proposer_installation(manquants_requis, manquants_optionnels):
    if not manquants_requis and not manquants_optionnels:
        return

    titre("4 / Installation des packages manquants")

    tous = []
    if manquants_requis:
        print(f"\n  Packages REQUIS manquants ({len(manquants_requis)}) :")
        for pip_name, ver_min in manquants_requis:
            spec = f"{pip_name}>={ver_min}" if ver_min else pip_name
            print(f"    - {spec}")
            tous.append(spec)

    if manquants_optionnels:
        print(f"\n  Packages OPTIONNELS manquants ({len(manquants_optionnels)}) :")
        for pip_name, ver_min in manquants_optionnels:
            spec = f"{pip_name}>={ver_min}" if ver_min else pip_name
            print(f"    - {spec}")

    if not tous:
        print("\n  Seuls des packages optionnels manquent. Rien à installer pour le fonctionnement de base.")
        return

    proxy_auto = detecter_proxy()
    if proxy_auto:
        print(f"\n  Proxy détecté automatiquement : {proxy_auto}")
        rep_proxy = input("  Utiliser ce proxy pour l'installation ? [O/n] : ").strip().lower()
        proxy = proxy_auto if rep_proxy in ("", "o", "oui", "y", "yes") else ""
        if not proxy:
            proxy = input("  Entrez l'adresse du proxy, ou laisser vide : ").strip()
    else:
        print("\n  Aucun proxy système détecté.")
        proxy = input("  Entrez l'adresse du proxy si nécessaire, ou Entrée pour ignorer : ").strip()

    print()
    reponse = input("  Voulez-vous installer les packages manquants maintenant ? [O/n] : ").strip().lower()
    if reponse in ("", "o", "oui", "y", "yes"):
        print()
        for spec in tous:
            cmd = [sys.executable, "-m", "pip", "install"]
            if proxy:
                cmd += ["--proxy", proxy]
            cmd.append(spec)
            print(f"  >> {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=False)
            if result.returncode == 0:
                ok(f"{spec} installé.")
            else:
                proxy_hint = f" --proxy {proxy}" if proxy else ""
                err(f"Échec de l'installation de {spec}. Lancez manuellement : pip install{proxy_hint} {spec}")
    else:
        print("\n  Installation annulée. Lancez manuellement :")
        proxy_hint = f" --proxy {proxy}" if proxy else ""
        for spec in tous:
            print(f"    pip install{proxy_hint} {spec}")


# ── 6. Bilan ────────────────────────────────────────────────────────────────
def bilan(py_ok, manquants_req, manquants_fich):
    titre("BILAN")
    if py_ok and not manquants_req and not manquants_fich:
        print("  [OK] Tout est en ordre - l'outil peut etre lance.")
        print()
        print("  Double-cliquez sur  Lancer_GMAO.bat")
    else:
        print("  [!!] Des problemes ont ete detectes :")
        if not py_ok:
            err("Version Python incompatible.")
        for f in manquants_fich:
            err(f"Fichier manquant : {f}")
        if manquants_req:
            err("Des packages requis ne sont pas installés.")
    print()


if __name__ == "__main__":
    print()
    print(SEP2)
    print("  TEST D'INSTALLATION - GMAO Materiel hydrometrique")
    print(SEP2)

    py_ok      = check_python()
    manq_req   = check_packages(REQUIRED, "requis")
    manq_opt   = check_packages(OPTIONAL, "optionnels")
    manq_fich  = check_project_files()

    proposer_installation(manq_req, manq_opt)
    manq_req_final = check_packages(REQUIRED, "requis (après install)")
    bilan(py_ok, manq_req_final, manq_fich)

    input("  Appuyez sur Entrée pour fermer...")
