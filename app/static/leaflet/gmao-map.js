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

/** Ajoute le sélecteur de fond de carte + l'échelle dynamique (bas gauche). */
function ajouterControlesCommuns(map, fonds) {
  fonds["Plan"].addTo(map);
  L.control.layers(fonds, null, { position: 'topright' }).addTo(map);
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
 * Carte du dashboard : place une pastille colorée par équipement géolocalisé (couleur du
 * site : UH de gestion ou maintenance, voir Paramètres) et notifie onBoundsChange(bounds|null)
 * à chaque déplacement/zoom (null si zoom arrière-plan par défaut, pour ne pas filtrer).
 */
var GMAO_COULEUR_PASTILLE_DEFAUT = '#3388ff';

function creerPastille(couleur) {
  return L.divIcon({
    className: 'gmao-pastille',
    html: '<div style="width:20px;height:20px;border-radius:50%;background:' + couleur +
      ';border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.5);"></div>',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

/** Site fermé : pastille blanche à croix rouge (prioritaire sur la couleur UH/maintenance). */
function creerPastilleFermee() {
  return L.divIcon({
    className: 'gmao-pastille',
    html: '<div style="width:20px;height:20px;border-radius:50%;background:#fff;' +
      'border:2px solid #dc2626;box-shadow:0 1px 3px rgba(0,0,0,.5);display:flex;' +
      'align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#dc2626;line-height:1;">&#10005;</div>',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

function initDashboardCarte(mapId, equipements, onBoundsChange) {
  var map = L.map(mapId).setView(GMAO_CENTRE_DEFAUT, GMAO_ZOOM_DEFAUT);
  ajouterControlesCommuns(map, creerFondsDeCarte());

  var group = L.featureGroup();
  equipements.forEach(function (e) {
    if (e.lat !== null && e.lon !== null) {
      var icon = e.ferme ? creerPastilleFermee() : creerPastille(e.couleur || GMAO_COULEUR_PASTILLE_DEFAUT);
      var libelle = e.nom + (e.ferme ? ' (site fermé)' : (e.maintenance ? ' (site de maintenance)' : ''));
      L.marker([e.lat, e.lon], { icon: icon }).addTo(group).bindPopup(libelle);
    }
  });
  group.addTo(map);

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
