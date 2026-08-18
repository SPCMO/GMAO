// Défaut : centre approximatif du secteur SPCMO (Aude / Carcassonne)
var GMAO_CENTRE_DEFAUT = [43.05, 2.35];
var GMAO_ZOOM_DEFAUT = 9;

/**
 * Fonds de carte disponibles (plan OpenStreetMap + vue satellite Esri, gratuits, sans clé).
 * Retourne un objet {libellé: couche} à passer à L.control.layers, la première couche
 * de l'objet n'est pas ajoutée automatiquement : appeler .addTo(map) sur la couche par défaut.
 */
function creerFondsDeCarte() {
  var plan = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19
  });
  var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics',
    maxZoom: 19
  });
  return { "Plan": plan, "Satellite": satellite };
}

/** Ajoute le sélecteur de fond de carte + l'échelle dynamique (bas gauche).
 * collapsed:false : le sélecteur Plan/Satellite reste déplié en permanence
 * (replié, on ne devine pas qu'il est cliquable) — taille réduite en CSS. */
function ajouterControlesCommuns(map, fonds) {
  fonds["Plan"].addTo(map);
  L.control.layers(fonds, null, { position: 'topright', collapsed: false }).addTo(map);
  L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map);
}

/**
 * Mini-carte de pointage (formulaires nouvel équipement / modifier coordonnées).
 * Clic sur la carte OU saisie manuelle des champs -> se synchronisent l'un l'autre.
 */
function initMiniCarte(mapId, latInputId, lonInputId) {
  var latInput = document.getElementById(latInputId);
  var lonInput = document.getElementById(lonInputId);
  var hasCoords = latInput.value !== "" && lonInput.value !== "";
  var startLat = hasCoords ? parseFloat(latInput.value) : GMAO_CENTRE_DEFAUT[0];
  var startLon = hasCoords ? parseFloat(lonInput.value) : GMAO_CENTRE_DEFAUT[1];

  var map = L.map(mapId).setView([startLat, startLon], hasCoords ? 15 : GMAO_ZOOM_DEFAUT);
  ajouterControlesCommuns(map, creerFondsDeCarte());

  var marker = null;
  function setMarker(lat, lon) {
    if (marker) {
      marker.setLatLng([lat, lon]);
    } else {
      marker = L.marker([lat, lon], { draggable: true }).addTo(map);
      marker.on('dragend', function () {
        var pos = marker.getLatLng();
        latInput.value = pos.lat.toFixed(6);
        lonInput.value = pos.lng.toFixed(6);
      });
    }
  }

  if (hasCoords) {
    setMarker(startLat, startLon);
  }

  map.on('click', function (e) {
    latInput.value = e.latlng.lat.toFixed(6);
    lonInput.value = e.latlng.lng.toFixed(6);
    setMarker(e.latlng.lat, e.latlng.lng);
  });

  function syncDepuisChamps() {
    var lat = parseFloat(latInput.value);
    var lon = parseFloat(lonInput.value);
    if (!isNaN(lat) && !isNaN(lon)) {
      setMarker(lat, lon);
      map.setView([lat, lon], 15);
    }
  }
  latInput.addEventListener('change', syncDepuisChamps);
  lonInput.addEventListener('change', syncDepuisChamps);

  // Certains conteneurs sont masqués au chargement (ex: formulaire nouveau site) -
  // Leaflet a besoin d'un recalcul de taille une fois le conteneur visible.
  setTimeout(function () { map.invalidateSize(); }, 200);

  return map;
}

/**
 * Carte du dashboard : place une pastille colorée par SITE géolocalisé (pas par
 * équipement — plusieurs équipements peuvent partager un même site/marqueur) et notifie
 * onBoundsChange(bounds|null) à chaque déplacement/zoom (null si zoom arrière-plan par
 * défaut, pour ne pas filtrer). Couleur : voir la priorité calculée côté serveur
 * (run.py) — fermé > maintenance > sans équipement affecté (gris foncé) > UH > défaut.
 */
var GMAO_COULEUR_PASTILLE_DEFAUT = '#3388ff';

function creerPastille(couleur, maintenance) {
  var fond = couleur || GMAO_COULEUR_PASTILLE_DEFAUT;
  var contenu = maintenance ? '🔧' : '';
  return L.divIcon({
    className: 'gmao-pastille',
    html: '<div style="width:20px;height:20px;border-radius:50%;background:' + fond +
      ';border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.5);display:flex;' +
      'align-items:center;justify-content:center;font-size:10px;line-height:1;">' + contenu + '</div>',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

/** Site fermé : pastille blanche à croix rouge, semi-transparente (prioritaire sur tout le reste). */
function creerPastilleFermee() {
  return L.divIcon({
    className: 'gmao-pastille',
    html: '<div style="width:20px;height:20px;border-radius:50%;background:#fff;' +
      'border:2px solid #dc2626;box-shadow:0 1px 3px rgba(0,0,0,.5);display:flex;' +
      'align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#dc2626;' +
      'line-height:1;opacity:.55;">&#10005;</div>',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

/** Contenu de la bulle d'un site : son nom, son statut, puis la liste cliquable des
 * équipements qui y sont actuellement affectés (ou un message si aucun). */
function construirePopupSite(s) {
  var html = '<b>' + s.nom + '</b>';
  if (s.ferme) {
    html += ' <span style="color:#dc2626;">(site fermé)</span>';
  } else if (s.maintenance) {
    html += ' <span style="color:#4b5563;">(site de maintenance)</span>';
  }
  if (s.equipements && s.equipements.length) {
    html += '<ul style="margin:.4rem 0 0; padding-left:1.1rem;">';
    s.equipements.forEach(function (e) {
      html += '<li><a href="/equipement/' + e.id + '" style="color:#14314f; text-decoration:underline;">' + e.nom + '</a></li>';
    });
    html += '</ul>';
  } else {
    html += '<div style="color:#6b7280; font-size:.85rem; margin-top:.3rem;">Aucun équipement affecté</div>';
  }
  return html;
}

function initDashboardCarte(mapId, sitesCarte, onBoundsChange) {
  var map = L.map(mapId).setView(GMAO_CENTRE_DEFAUT, GMAO_ZOOM_DEFAUT);
  ajouterControlesCommuns(map, creerFondsDeCarte());

  var group = L.featureGroup();
  var marqueursFermes = [];
  sitesCarte.forEach(function (s) {
    if (s.lat !== null && s.lon !== null) {
      var icon = s.ferme ? creerPastilleFermee() : creerPastille(s.couleur, s.maintenance);
      var marker = L.marker([s.lat, s.lon], { icon: icon }).addTo(group).bindPopup(construirePopupSite(s));
      if (s.ferme) marqueursFermes.push(marker);
    }
  });
  group.addTo(map);
  map.gmaoMarqueursFermes = marqueursFermes;

  if (group.getLayers().length > 0) {
    map.fitBounds(group.getBounds().pad(0.2));
  }

  var filtreActif = false;
  map.on('moveend zoomend', function () {
    filtreActif = true;
    onBoundsChange(map.getBounds());
  });

  return map;
}

/** Affiche/masque les sites fermés sur la carte du dashboard (checkbox dédiée) —
 * seule la suppression complète d'un site (Gestionnaire des sites) le retire
 * définitivement de la carte, ceci n'est qu'un allègement visuel temporaire. */
function toggleSitesFermes(map, masquer) {
  (map.gmaoMarqueursFermes || []).forEach(function (marker) {
    if (masquer) {
      map.removeLayer(marker);
    } else if (!map.hasLayer(marker)) {
      marker.addTo(map);
    }
  });
}
