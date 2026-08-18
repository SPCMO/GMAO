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
import smtplib
import urllib.error
import urllib.request
from email.mime.text import MIMEText

from app import settings


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
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            reponse = json.loads(resp.read().decode("utf-8"))
        if reponse.get("ok"):
            return True, None
        return False, reponse.get("erreur", "Erreur inconnue du relais Apps Script.")
    except urllib.error.URLError as e:
        return False, f"Relais Apps Script injoignable : {e}"
    except Exception as e:
        return False, str(e)


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
