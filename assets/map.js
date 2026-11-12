{% macro html(this, kwargs) %}
<script id="station-data" type="application/json">{{ this.entries | tojson }}</script>
{% endmacro %}
{% macro script(this, kwargs) %}
if (new URLSearchParams(location.search).has('embed')) document.body.classList.add('embedded');
const sensorMap = {{ this._parent.get_name() }};
const stationEntries = JSON.parse(document.getElementById('station-data').textContent);
const stationsById = new Map(stationEntries.map(entry => [entry.id, entry]));
const stationReferences = [
{% for entry in this.entries %}[{{ entry.marker }}, {{ entry.cluster }}],{% endfor %}
];
stationEntries.forEach((entry, index) => {
    entry.marker = stationReferences[index][0];
    entry.cluster = stationReferences[index][1];
    const element = entry.marker.getElement();
    if (element) element.dataset.stationId = entry.id;
});
const stationGroups = {
    piezometer: {{ this.groups.piezometer }}, river_sensor: {{ this.groups.river_sensor }}
};
const tools = L.control({position: 'topleft'});
tools.onAdd = function () {
    const container = L.DomUtil.create('div', 'station-tools');
    container.innerHTML = `
      <div class="search-card"><label for="station-search">Rechercher une station</label>
        <div class="search-field"><span aria-hidden="true">⌕</span>
          <input id="station-search" type="search" placeholder="Nom de station, ex. pzps3" autocomplete="off" aria-controls="station-results" aria-expanded="false">
        </div><div id="station-results" class="search-results" hidden></div>
      </div>
      <div class="csv-shortcuts" aria-label="Stations avec séries temporelles">
        <span>Séries disponibles</span>{% for entry in this.entries if entry.matched %}<button type="button" data-station-id="{{ entry.id }}">{{ entry.csv_id | e }}</button>{% endfor %}
      </div>
      <section class="map-overview map-summary"><p class="eyebrow">LE BASSIN DE L’ORGEVAL</p>
        <h1>Légende du réseau</h1><p class="overview-count"><strong>{{ this.entries | length }}</strong> stations géolocalisées · <strong>{{ this.entries | selectattr("matched") | list | length }}</strong> séries CSV</p>
        <p class="overview-help">Sélectionnez un point pour consulter sa fiche et les dernières mesures fournies. Les groupes s’ouvrent au clic.</p>
        <p class="legend-caption">Totaux des stations géolocalisées</p>
        <div class="map-legend"><span><i class="legend-dot piezometer"></i>Piézomètres <strong>{{ this.entries | selectattr("type", "equalto", "piezometer") | list | length }}</strong></span><span><i class="legend-dot river_sensor"></i>Rivière <strong>{{ this.entries | selectattr("type", "equalto", "river_sensor") | list | length }}</strong></span></div>
        <p class="cluster-explanation"><i aria-hidden="true">n</i>Dans un groupe : nombre de stations regroupées, pas le total par type.</p>
        <p class="csv-explanation">Cercle renforcé : série CSV fournie.</p>
        {% if this.missing_names %}<div class="missing-note"><strong>Sans coordonnées — non cartographiées</strong><p>{{ this.missing_names | e }}</p></div>{% endif %}
      </section>
      <aside id="station-panel" class="station-panel" aria-label="Fiche de la station" hidden>
        <button id="close-station" class="close-station" type="button" aria-label="Fermer la fiche">×</button>
        <div id="station-content" aria-live="polite"></div>
      </aside>`;
    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);
    return container;
};
tools.addTo(sensorMap);
const searchInput = document.getElementById('station-search');
const results = document.getElementById('station-results');
const panel = document.getElementById('station-panel');
const content = document.getElementById('station-content');
let selectedEntry;
let selectionRing;

function closeStation() {
    panel.hidden = true;
    sensorMap.getContainer().classList.remove('details-open');
    sensorMap.closePopup();
    if (selectedEntry && selectedEntry.marker.getElement()) selectedEntry.marker.getElement().classList.remove('is-selected');
    if (selectionRing) {sensorMap.removeLayer(selectionRing);selectionRing = undefined;}
    selectedEntry = undefined;
}
function showDetails(entry) {
    if (selectedEntry && selectedEntry.marker.getElement()) selectedEntry.marker.getElement().classList.remove('is-selected');
    selectedEntry = entry;
    if (selectionRing) sensorMap.removeLayer(selectionRing);
    selectionRing = L.circleMarker(entry.coordinate, {
        renderer:L.svg(),pane:'markerPane',radius:17,weight:2,color:'#d6a72d',
        fillColor:'#eac24c',fillOpacity:0.12,interactive:false,className:'selection-ring'
    }).addTo(sensorMap);
    content.innerHTML = entry.html;
    if (document.body.classList.contains('embedded')) {
        const link = content.querySelector('.chart-link');
        if (link) link.target = '_top';
    }
    panel.hidden = false;
    panel.scrollTop = 0;
    sensorMap.getContainer().classList.add('details-open');
    if (window.innerWidth < 700) sensorMap.getContainer().classList.remove('legend-requested');
    if (entry.marker.getElement()) entry.marker.getElement().classList.add('is-selected');
    if (window.innerWidth < 700) {
        entry.marker.closePopup();
        sensorMap.setView(entry.coordinate, sensorMap.getZoom(), {animate:false});
        sensorMap.panBy([0, sensorMap.getSize().y * 0.24], {animate:false});
    }
}
function selectStation(stationId) {
    const entry = stationsById.get(Number(stationId));
    if (!entry) return;
    sensorMap.addLayer(stationGroups[entry.type]);
    results.hidden = true;
    searchInput.setAttribute('aria-expanded', 'false');
    searchInput.value = entry.name;
    // Already-visible markers keep their local context; search zoom stays bounded.
    const visible = entry.marker.getElement();
    if (!visible || !sensorMap.getBounds().contains(entry.coordinate)) {
        sensorMap.setView(entry.coordinate, Math.min(15, Math.max(sensorMap.getZoom(), 14)), {animate:false});
    } else if (sensorMap.getZoom() > 16) {
        sensorMap.setView(entry.coordinate, 16, {animate:false});
    }
    if (entry.matched) {
        if (sensorMap.getZoom() < 14) sensorMap.setView(entry.coordinate, 14, {animate:false});
        showDetails(entry);
    } else if (entry.marker.getElement()) {
        showDetails(entry);
    } else {
        // Spiderfy a remaining local cluster instead of zooming away the context.
        sensorMap.setView(entry.coordinate, 15, {animate:false});
        const parent = entry.cluster.getVisibleParent(entry.marker);
        if (parent && parent.spiderfy) parent.spiderfy();
        showDetails(entry);
    }
}
stationEntries.forEach(entry => {
    entry.marker.on('click', () => selectStation(entry.id));
    entry.marker.on('add', () => {
        const element = entry.marker.getElement();
        if (element) element.dataset.stationId = entry.id;
        if (selectedEntry === entry && element) element.classList.add('is-selected');
    });
});
document.querySelectorAll('.csv-shortcuts button').forEach(button => {
    button.onclick = () => selectStation(Number(button.dataset.stationId));
});
document.getElementById('close-station').onclick = closeStation;
sensorMap.on('overlayremove', event => {
    if (selectedEntry && event.layer === stationGroups[selectedEntry.type]) closeStation();
});
sensorMap.on('click', () => {results.hidden = true;searchInput.setAttribute('aria-expanded','false');});
searchInput.addEventListener('input', () => {
    const query = searchInput.value.trim().toLocaleLowerCase('fr');
    results.replaceChildren();
    if (!query) {results.hidden = true; searchInput.setAttribute('aria-expanded', 'false'); return;}
    const matches = stationEntries.filter(entry => [entry.name, entry.csv_id, String(entry.id)].some(value => value && value.toLocaleLowerCase('fr').includes(query)))
        .sort((a,b) => Number(b.name.toLocaleLowerCase('fr') === query) - Number(a.name.toLocaleLowerCase('fr') === query) || a.name.localeCompare(b.name, 'fr'));
    if (!matches.length) {
        const note = document.createElement('p');note.textContent = 'Aucune station trouvée.';results.appendChild(note);
    }
    matches.slice(0, 12).forEach(entry => {
        const button = document.createElement('button');button.type = 'button';button.className = 'search-result';
        const name = document.createElement('strong');name.textContent = entry.name;
        const detail = document.createElement('span');detail.textContent = (entry.type === 'piezometer' ? 'Piézomètre' : 'Station en rivière') + (entry.matched ? ' · Série disponible' : ' · Fiche station');
        button.append(name, detail);button.onclick = () => selectStation(entry.id);results.appendChild(button);
    });
    results.hidden = false; searchInput.setAttribute('aria-expanded', 'true');
});
searchInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') {results.hidden = true;searchInput.setAttribute('aria-expanded', 'false');}
    if (event.key === 'Enter') {const first = results.querySelector('button');if (first) {event.preventDefault();first.click();}}
    if (event.key === 'ArrowDown') {const first = results.querySelector('button');if (first) {event.preventDefault();first.focus();}}
});

L.control.zoom({position:'bottomright',zoomInTitle:'Zoom avant',zoomOutTitle:'Zoom arrière'}).addTo(sensorMap);
L.control.scale({position:'bottomleft',metric:true,imperial:false}).addTo(sensorMap);
const reset = L.control({position:'bottomright'});
reset.onAdd = () => {
    const button = L.DomUtil.create('button','map-reset');button.type = 'button';button.textContent = 'Vue du bassin';
    button.title = 'Rétablir la vue du bassin';
    L.DomEvent.disableClickPropagation(button);
    button.onclick = () => {closeStation();searchInput.value='';results.hidden=true;sensorMap.fitBounds({{ this.bounds | tojson }},{padding:[24,24]});};
    return button;
};
reset.addTo(sensorMap);
let compactControls;
function adaptControls() {
    const compact = sensorMap.getContainer().clientWidth < 700;
    if (compact === compactControls) return;
    compactControls = compact;
    const container = document.querySelector('.leaflet-control-layers');
    const toggle = container.querySelector('.leaflet-control-layers-toggle');
    toggle.title = 'Couches et types de stations';toggle.setAttribute('aria-label','Couches et types de stations');
    container.classList.toggle('leaflet-control-layers-expanded', !compact);
}
adaptControls();
sensorMap.on('resize', adaptControls);
const layersButton = document.getElementById('toggle-map-layers');
const legendButton = document.getElementById('toggle-map-legend');
const overview = document.querySelector('.map-overview');
const layerControl = document.querySelector('.leaflet-control-layers');
layersButton.onclick = () => {
    if (window.innerWidth < 700 && selectedEntry) closeStation();
    layerControl.classList.toggle('leaflet-control-layers-expanded');
    layersButton.setAttribute('aria-expanded', String(layerControl.classList.contains('leaflet-control-layers-expanded')));
};
legendButton.onclick = () => {
    const visible = getComputedStyle(overview).display !== 'none' && !overview.hidden;
    if (window.innerWidth < 700 && selectedEntry) closeStation();
    overview.hidden = visible;
    sensorMap.getContainer().classList.toggle('legend-requested', !visible);
    legendButton.setAttribute('aria-expanded', String(!visible));
};
document.getElementById('reset-map-view').onclick = () => document.querySelector('.map-reset').click();
function adaptStationLabels() {
    sensorMap.getContainer().classList.toggle('station-labels-visible', sensorMap.getZoom() >= 14);
}
adaptStationLabels();
sensorMap.on('zoomend', adaptStationLabels);
sensorMap.on('popupopen', () => {
    const close = sensorMap.getContainer().querySelector('.leaflet-popup-close-button');
    if (close) {close.title = 'Fermer l’aperçu';close.setAttribute('aria-label','Fermer l’aperçu');}
});
if (window.ResizeObserver) new ResizeObserver(() => sensorMap.invalidateSize({pan:false})).observe(sensorMap.getContainer());
const status = L.control({position:'bottomleft'});
status.onAdd = function () {
    this.message = L.DomUtil.create('div','tile-status');this.message.setAttribute('role','status');this.message.hidden = true;
    return this.message;
};
status.addTo(sensorMap);
document.querySelector('.station-tools').appendChild(status.message);
const background = {{ this.tile_layer.get_name() }};
const failedTiles = new Set();
function updateTileStatus() {
    // Ignore failures from discarded tiles after a pan, zoom, or source reload.
    const current = new Set(Object.values(background._tiles || {}).filter(tile => tile.current).map(tile => tile.el));
    failedTiles.forEach(tile => {if (!current.has(tile)) failedTiles.delete(tile);});
    status.message.hidden = failedTiles.size === 0;
}
background.on('tileerror', event => {
    failedTiles.add(event.tile);
    status.message.textContent = 'Le fond de carte est momentanément indisponible. Les stations et leurs fiches restent consultables.';
    updateTileStatus();
});
background.on('tileload', event => {failedTiles.delete(event.tile);updateTileStatus();});
background.on('tileunload', event => {failedTiles.delete(event.tile);updateTileStatus();});
background.on('load', updateTileStatus);
window.stationUI = {entries:stationEntries, groups:stationGroups, select:value => {const entry = stationsById.get(Number(value)) || stationEntries.find(item => item.name === value || item.csv_id === value);if (entry) selectStation(entry.id);}, close:closeStation, get highlight(){return selectionRing;}, get selected(){return selectedEntry?.name;}};
{% endmacro %}
