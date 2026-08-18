// ============================================
// GMAO - Relais d'envoi de mail via Google Apps Script
// ============================================
// Le réseau SPCMO bloque les connexions SMTP sortantes (ports 587/465), mais
// laisse passer le trafic HTTPS classique (comme pour GitHub). Ce script
// s'exécute côté serveur Google (pas sur le réseau SPCMO) et utilise
// GmailApp.sendEmail() pour envoyer réellement le mail — le script Python
// scripts/verifier_alertes.py lui envoie juste une requête HTTPS (POST).
//
// Déploiement (à faire une seule fois, voir Aide.html > Paramétrage) :
//   1. script.google.com/home → Nouveau projet, coller ce code
//   2. Changer TOKEN_SECRET ci-dessous (valeur secrète de ton choix)
//   3. Déployer > Nouveau déploiement > type "Application Web"
//      - Exécuter en tant que : Moi (spcmo113466@gmail.com)
//      - Qui a accès : Tout le monde
//   4. Copier l'URL de déploiement obtenue et la coller dans GMAO > Paramètres
//      (avec le même TOKEN_SECRET)

const TOKEN_SECRET = 'CHANGE_MOI_AVEC_UNE_VALEUR_SECRETE';
const FROM_EMAIL = 'spcmo113466@gmail.com';

function doPost(e) {
  try {
    const donnees = JSON.parse(e.postData.contents);

    if (donnees.token !== TOKEN_SECRET) {
      return reponseJson({ ok: false, erreur: 'Token invalide' });
    }
    if (!donnees.destinataires || !donnees.destinataires.length) {
      return reponseJson({ ok: false, erreur: 'Aucun destinataire' });
    }

    GmailApp.sendEmail(
      donnees.destinataires.join(','),
      donnees.sujet,
      donnees.corps,
      { from: FROM_EMAIL, noReply: true }
    );

    return reponseJson({ ok: true });
  } catch (error) {
    return reponseJson({ ok: false, erreur: error.toString() });
  }
}

function reponseJson(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet))
    .setMimeType(ContentService.MimeType.JSON);
}
