"""Envoi des mails d'alerte péremption matériel.

Le réseau SPCMO bloque les connexions SMTP sortantes (ports 587/465) mais laisse
passer le trafic HTTPS classique. Méthode privilégiée : un relais Google Apps
Script (voir apps_script/gmao_mail_relay.gs) qui envoie réellement le mail via
GmailApp côté serveur Google, contacté ici en HTTPS/POST. Le SMTP direct reste
disponible en repli, utile si l'appli tourne un jour sur un réseau qui ne
bloque pas ces ports.

Utilisé par le script autonome scripts/verifier_alertes.py (déclenché
quotidiennement par le Planificateur de tâches Windows).
"""
import json
import os
import smtplib
import time
import urllib.error
import urllib.request
from email.mime.text import MIMEText

import config
from app import settings


def _opener_relais():
    """Opener urllib avec un ProxyHandler explicite (proxy RIE en dur, voir config.PROXY_RIE).

    Sur le réseau SPCMO, la détection automatique de proxy de urlopen() s'est révélée
    peu fiable pour une requête POST via tunnel HTTPS (timeout constaté même variable
    d'environnement définie), alors qu'un ProxyHandler construit explicitement fonctionne
    à tous les coups — d'où ce contournement délibéré, en dur pour marcher aussi sur le
    poste des collègues sans configuration système préalable."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or config.PROXY_RIE
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def construire_message(equipement, etat):
    nom = equipement["nom"]
    peremption = etat["peremption"]
    jours = etat["jours_restants"]

    if jours is not None and jours < 0:
        delai = f"dépassée depuis {abs(jours)} jour(s)"
    elif jours is not None:
        delai = f"dans {jours} jour(s)"
    else:
        delai = "inconnu"

    sujet = f"[GMAO] Alerte péremption — {nom}"

    lignes = [
        f"L'équipement « {nom} » approche (ou a dépassé) sa date de péremption.",
        "",
        f"Date de péremption : {peremption.isoformat() if peremption else 'inconnue'}",
        f"Échéance : {delai}",
    ]
    if etat.get("deja_prolonge"):
        lignes.append("")
        lignes.append("Il s'agit d'une durée de vie déjà prolongée une première fois.")
    lignes.append("")
    lignes.append("— GMAO, envoi automatique quotidien")

    return sujet, "\n".join(lignes)


def _envoyer_via_apps_script(destinataires, sujet, corps):
    cfg = settings.get_apps_script_config()
    if not cfg["apps_script_url"]:
        return None  # pas configuré, on essaiera une autre méthode

    payload = json.dumps({
        "token": cfg["apps_script_token"],
        "destinataires": destinataires,
        "sujet": sujet,
        "corps": corps,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["apps_script_url"], data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    # Le proxy sortant du réseau SPCMO répond parfois avec un timeout de lecture isolé
    # (constaté : plusieurs tentatives identiques d'affilée aboutissent normalement la
    # plupart du temps) — quelques essais suffisent à absorber ces ratés ponctuels sans
    # faire échouer une vraie alerte pour un simple aléa réseau.
    derniere_erreur = "Erreur inconnue du relais Apps Script."
    for tentative in range(3):
        try:
            with _opener_relais().open(req, timeout=20) as resp:
                reponse = json.loads(resp.read().decode("utf-8"))
            if reponse.get("ok"):
                return True, None
            return False, reponse.get("erreur", "Erreur inconnue du relais Apps Script.")
        except urllib.error.URLError as e:
            derniere_erreur = f"Relais Apps Script injoignable : {e}"
        except Exception as e:
            derniere_erreur = str(e)
        if tentative < 2:
            time.sleep(2)
    return False, derniere_erreur


def _envoyer_via_smtp(destinataires, sujet, corps):
    cfg = settings.get_smtp_config()
    if not cfg["smtp_host"] or not cfg["smtp_user"] or not cfg["smtp_password"]:
        return False, "Configuration SMTP incomplète (voir Paramètres)."

    msg = MIMEText(corps, "plain", "utf-8")
    msg["Subject"] = sujet
    msg["From"] = cfg["smtp_user"]
    msg["To"] = ", ".join(destinataires)

    try:
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.sendmail(cfg["smtp_user"], destinataires, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def envoyer_mail(destinataires, sujet, corps):
    if not destinataires:
        return False, "Aucun destinataire."

    resultat = _envoyer_via_apps_script(destinataires, sujet, corps)
    if resultat is not None:
        return resultat

    return _envoyer_via_smtp(destinataires, sujet, corps)
