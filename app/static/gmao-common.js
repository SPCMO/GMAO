/** Remplit dynamiquement le select sous-type en fonction du type choisi. */
function initCascadeType(typeSelectId, sousTypeSelectId, sousTypesParType, sousTypeActuel) {
  var typeSelect = document.getElementById(typeSelectId);
  var sousTypeSelect = document.getElementById(sousTypeSelectId);
  function remplir() {
    var options = sousTypesParType[typeSelect.value] || [];
    var valeurASelectionner = sousTypeSelect.dataset.premierRemplissage === '1' ? sousTypeActuel : null;
    sousTypeSelect.innerHTML = '<option value="">—</option>';
    options.forEach(function (o) {
      var opt = document.createElement('option');
      opt.value = o;
      opt.textContent = o;
      if (o === valeurASelectionner) opt.selected = true;
      sousTypeSelect.appendChild(opt);
    });
    sousTypeSelect.dataset.premierRemplissage = '0';
  }
  sousTypeSelect.dataset.premierRemplissage = '1';
  typeSelect.addEventListener('change', remplir);
  if (typeSelect.value) remplir();
}

/** Empêche de valider si la date de 1ère mise en service précède la date de création. */
function validerDateCreationMiseService(creationId, miseServiceId) {
  var creation = document.getElementById(creationId);
  var miseService = document.getElementById(miseServiceId);
  function verifier() {
    if (creation.value && miseService.value && miseService.value < creation.value) {
      miseService.setCustomValidity("La date de 1ère mise en service doit être postérieure ou égale à la date de création.");
    } else {
      miseService.setCustomValidity("");
    }
  }
  creation.addEventListener('change', verifier);
  miseService.addEventListener('change', verifier);
}

/** Bascule le champ de saisie libre pour "Raison du retrait" quand l'option correspondante est choisie. */
function toggleRaisonLibre(selectId, champLibreId) {
  var sel = document.getElementById(selectId);
  var champ = document.getElementById(champLibreId);
  function maj() {
    champ.style.display = sel.value === '__libre__' ? 'block' : 'none';
  }
  sel.addEventListener('change', maj);
  maj();
}

/** Empêche de choisir une raison (retrait équipement / fermeture site) tant que la date associée est vide. */
function validerRaisonNecessiteDate(dateId, raisonSelectId, raisonLibreId) {
  var dateChamp = document.getElementById(dateId);
  var raisonSelect = document.getElementById(raisonSelectId);
  var raisonLibre = raisonLibreId ? document.getElementById(raisonLibreId) : null;
  function verifier() {
    var raisonRenseignee = raisonSelect.value || (raisonLibre && raisonLibre.value.trim());
    if (!dateChamp.value && raisonRenseignee) {
      raisonSelect.setCustomValidity("Renseignez d'abord la date avant de choisir une raison.");
    } else {
      raisonSelect.setCustomValidity("");
    }
  }
  dateChamp.addEventListener('change', verifier);
  raisonSelect.addEventListener('change', verifier);
  if (raisonLibre) raisonLibre.addEventListener('input', verifier);
  verifier();
}
