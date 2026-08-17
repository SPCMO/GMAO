// Défaut : centre approximatif du secteur SPCMO (Aude / Carcassonne)
var GMAO_CENTRE_DEFAUT = [43.05, 2.35];
var GMAO_ZOOM_DEFAUT = 9;

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
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19
  }).addTo(map);

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
 * Carte du dashboard : place un marqueur par équipement géolocalisé et notifie
 * onBoundsChange(bounds|null) à chaque déplacement/zoom (null si zoom arrière-plan par défaut, pour ne pas filtrer).
 */
function initDashboardCarte(mapId, equipements, onBoundsChange) {
  var map = L.map(mapId).setView(GMAO_CENTRE_DEFAUT, GMAO_ZOOM_DEFAUT);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19
  }).addTo(map);

  var group = L.featureGroup();
  equipements.forEach(function (e) {
    if (e.lat !== null && e.lon !== null) {
      L.marker([e.lat, e.lon]).addTo(group).bindPopup(e.nom);
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
