"""Vérifie les péremptions de matériel et envoie un mail par équipement en alerte
non encore notifié. À exécuter une fois par jour (Planificateur de tâches Windows, 7h00).

Usage : venv/Scripts/python.exe scripts/verifier_alertes.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import alertes, db, mail


def main():
    db.init_db()
    aujourdhui = date.today()
    envoyes, echecs = 0, 0

    with db.db_session() as conn:
        emails_par_uh = db.list_uh_emails_tous(conn)
        a_notifier = alertes.equipements_en_alerte(conn, db, aujourdhui)

        if not a_notifier:
            print(f"[{aujourdhui.isoformat()}] Aucune nouvelle alerte.")
            return

        for eq, etat in a_notifier:
            destinataires = emails_par_uh.get(eq["site_uh"] or "", [])
            if not destinataires:
                print(f"  [!!] {eq['nom']} : alerte active mais aucun destinataire pour l'UH « {eq['site_uh']} » (site {eq['site_actuel']}) — mail non envoyé, non marqué comme traité.")
                continue

            sujet, corps = mail.construire_message(eq, etat)
            ok, erreur = mail.envoyer_mail(destinataires, sujet, corps)
            if ok:
                db.marquer_alerte_envoyee(conn, eq["id"], aujourdhui.isoformat())
                print(f"  [OK] {eq['nom']} -> {', '.join(destinataires)}")
                envoyes += 1
            else:
                print(f"  [ERR] {eq['nom']} : {erreur}")
                echecs += 1

    print(f"[{aujourdhui.isoformat()}] {envoyes} mail(s) envoyé(s), {echecs} échec(s).")


if __name__ == "__main__":
    main()
