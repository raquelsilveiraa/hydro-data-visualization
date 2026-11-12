"""Build the French station map from source geometries and verified CSV summaries."""
from html import escape
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from branca.element import Element, MacroElement
from folium.plugins import MarkerCluster
from jinja2 import Template

from presentation import INSTRUMENT_LABELS, MEASUREMENTS, format_count, format_number

CSV_GIS_IDS = {"pzps1": 1, "pzps3": 4, "pzps4": 8}
GIS_CSV_IDS = {value: key for key, value in CSV_GIS_IDS.items()}

ASSETS = Path(__file__).resolve().parent / "assets"
PIEZO_COLORS = {"piezometer": "#1269a5", "river_sensor": "#15866d"}
IGN_TILES = (
    "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
    "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png"
    "&TILEMATRIXSET=PM_0_19&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
)
GIS_LABELS = {
    "ID_SENSOR": "Identifiant", "LIBELLE": "Nom de la station", "INSTITUTIO": "Organisme",
    "LIEU_DIT": "Lieu-dit", "COMMENTAIR": "Commentaire", "NATURE": "Nature",
    "STATION_GR": "Groupe de stations", "STATION_01": "Station de rattachement",
    "TYPE_CAPTE": "Type de capteur", "PROF_DEB_C": "Début de crépine",
    "PROF_FIN_C": "Fin de crépine", "PERMEABILI": "Perméabilité", "TRANSMITIV": "Transmissivité",
    "PROPRIETAI": "Propriétaire", "MAITRE_OEU": "Maître d’œuvre", "TYPE_INSTR": "Instrument",
    "NOM_COMPLE": "Nom complet", "GROUD_ELEV": "Altitude du sol", "HEAD_ELEVA": "Altitude de référence",
    "BOTTOM_ELE": "Altitude du fond", "SENSOR_DEP": "Profondeur du capteur", "CABLE_LENG": "Longueur du câble",
}


def sensor_popup(row, details):
    """Render one station sheet using the verified stable GIS identifier."""
    name = str(row["LIBELLE"])
    instrument = INSTRUMENT_LABELS[row["TYPE_INSTR"]]
    content = [f'<section class="sensor-details" data-station="{escape(name, quote=True)}">',
               f'<div class="station-kind">{escape(instrument)}</div><h2>{escape(name)}</h2>',
               f'<p class="coordinates">Latitude {format_number(row.geometry.y, 6)}° · '
               f'Longitude {format_number(row.geometry.x, 6)}°<br><span>Coordonnées WGS84</span></p>']
    csv_id = GIS_CSV_IDS.get(int(row["ID_SENSOR"]))
    summary = details.get(csv_id)
    if summary is None:
        content.append('<div class="empty-series"><strong>Fiche de station</strong><p>Aucune série temporelle n’a été fournie pour cette station.</p></div>')
    else:
        content.append('<h3>Dernières mesures disponibles</h3><div class="latest-readings">')
        for column, (label, unit, _) in MEASUREMENTS.items():
            values = summary["measurements"].get(column)
            content.append(f'<article class="reading"><span>{label}</span>')
            if values is not None and values["last"] is not None:
                content.append(f'<strong>{format_number(values["last"])} <small>{unit}</small></strong>'
                               f'<time>{escape(values["last_date"])}</time>')
            else:
                content.append('<strong class="unavailable">Non disponible</strong><span class="reading-note">Aucune mesure valide fournie</span>')
            content.append('</article>')
        content.append('</div>')
        content.append(f'<a class="chart-link" href="{escape(csv_id, quote=True)}.html">Consulter les séries temporelles <span aria-hidden="true">↗</span></a>')
        content.extend([
            '<div class="series-period"><h3>Période observée</h3>',
            f'<p>{escape(summary["start"])} — {escape(summary["end"])}</p>',
            f'<p>{format_count(summary["rows"])} observations originales · {summary["months"]} mois valides pour la tendance</p></div>',
            '<div class="trend-card"><span>Tendance thermique observée</span>',
            f'<strong>{format_number(summary["trend"])} °C/décennie</strong>',
        ])
        for key, label, unit in (("ci", "Demi-largeur de l’intervalle à 95 %", " °C/décennie"),
                                 ("p_value", "Valeur p", "")):
            value = summary.get(key)
            if value is not None and np.isfinite(value):
                formatted = f"{value:.2e}".replace(".", ",") if key == "p_value" and 0 < value < 0.001 else format_number(value)
                content.append(f'<p>{label} : {formatted}{unit}</p>')
        content.append('<p>Estimation sur les observations, sans prévision.</p></div>')
        content.append('<details><summary>Qualité et statistiques des séries</summary>')
        for column, values in summary["measurements"].items():
            label, unit, _ = MEASUREMENTS[column]
            content.append(f'<h4>{label}</h4><dl>'
                           f'<dt>Valides / manquantes</dt><dd>{format_count(values["valid"])} / {format_count(values["missing"])}</dd>'
                           f'<dt>Moyenne des moyennes journalières valides</dt><dd>{format_number(values["mean"])} {unit}</dd>'
                           f'<dt>Minimum / maximum bruts</dt><dd>{format_number(values["min"])} / {format_number(values["max"])} {unit}</dd></dl>')
        content.append('<p class="fine-print">Moyennes sur la période du CSV, avec le même poids pour chaque jour valide, comme dans le graphique. Chaque dernière mesure conserve sa propre date.</p></details>')
    content.append('<details class="gis-metadata"' + (' open' if summary is None else '')
                   + '><summary>Informations de la station</summary><dl>')
    for field, value in row.items():
        if field != "geometry" and pd.notna(value) and str(value).strip():
            if field == "TYPE_INSTR":
                value = INSTRUMENT_LABELS.get(value, value)
            elif value == "others":
                value = "Autres"
            label = GIS_LABELS.get(field, "Attribut source : " + str(field))
            content.append(f'<dt>{escape(label)}</dt><dd>{escape(str(value))}</dd>')
    content.append('</dl></details></section>')
    return ''.join(content)


class MapControls(MacroElement):
    """Connect lightweight search, exact marker selection and the station details panel."""

    def __init__(self, tile_layer, entries, groups, bounds, missing_sensor_names):
        super().__init__()
        self.tile_layer = tile_layer
        self.entries = entries
        self.groups = groups
        self.bounds = bounds
        self.missing_names = ", ".join(missing_sensor_names)
        self._template = Template((ASSETS / "map.js").read_text(encoding="utf-8"))


def map_sensors_orgeval(sensors_to_plot, limite, hydro, location=None, zoom_start=13,
                        output_path="map_bassin_lorgeval.html", sensor_details=None,
                        missing_sensor_names=()):
    """Validate declared CRS, transform layers to WGS84, and save a French map page."""
    sensor_details = sensor_details or {}
    layers = []
    for layer in (sensors_to_plot, limite, hydro):
        if layer.empty or layer.crs is None:
            raise ValueError("Each GIS layer must be nonempty and have a declared CRS.")
        if layer.geometry.isna().any() or layer.geometry.is_empty.any() or not layer.is_valid.all():
            raise ValueError("GIS layers must contain valid, nonempty geometries.")
        layers.append(layer.to_crs(epsg=4326))
    sensors, boundary, rivers = layers
    if not sensors.geom_type.eq("Point").all():
        raise ValueError("Sensor geometries must be Points.")
    unknown = set(sensors.TYPE_INSTR.unique()) - set(PIEZO_COLORS)
    if unknown:
        raise ValueError(f"Unknown instrument types: {unknown}")
    if sensors.ID_SENSOR.isna().any() or sensors.ID_SENSOR.duplicated().any():
        raise ValueError("Sensor ID_SENSOR values must be nonmissing and unique.")
    for name in sensor_details:
        if name not in CSV_GIS_IDS or sensors.ID_SENSOR.eq(CSV_GIS_IDS[name]).sum() != 1:
            raise ValueError(f"CSV summary requires one exact mapped ID_SENSOR match: {name}")
    bounds = np.vstack([layer.total_bounds for layer in layers])
    west, south = bounds[:, :2].min(axis=0)
    east, north = bounds[:, 2:].max(axis=0)
    location = location or [(south + north) / 2, (west + east) / 2]
    map_ = folium.Map(location=location, zoom_start=zoom_start, tiles=None,
                      zoom_control=False, prefer_canvas=True, min_zoom=8, max_zoom=19,
                      zoom_animation=False, fade_animation=False, marker_zoom_animation=False)
    tiles = folium.TileLayer(
        tiles=IGN_TILES, name="Fond de carte IGN", max_native_zoom=19, max_zoom=19, min_zoom=8,
        keep_buffer=3, update_when_idle=True, update_when_zooming=False,
        attr='<a href="https://www.ign.fr/">IGN</a> · '
             '<a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/">Licence Ouverte 2.0</a>',
    ).add_to(map_)
    css = (ASSETS / "map.css").read_text(encoding="utf-8")
    map_.get_root().header.add_child(Element('<title>Carte des stations · Orgeval</title><style>' + css + '</style>'))
    header = '<header class="map-header"><a href="index.html" class="map-brand">ORGEVAL <span>Observations hydrogéologiques</span></a><nav aria-label="Navigation principale"><a href="index.html">Accueil</a><a href="index.html#series" class="series-nav">Séries temporelles</a><button type="button" class="map-command" id="toggle-map-layers" aria-expanded="true">Couches</button><button type="button" class="map-command" id="toggle-map-legend" aria-expanded="true">Légende</button><button type="button" class="map-command map-home-command" id="reset-map-view">Recentrer</button></nav></header>'
    map_.get_root().html.add_child(Element(header))
    folium.GeoJson(boundary, name="Limite du bassin", style_function=lambda _: {
        "fillOpacity": 0, "color": "#385568", "weight": 2},
        tooltip=folium.GeoJsonTooltip(fields=["SBV_KM2"], aliases=["Superficie [km²]"]),
        popup=folium.GeoJsonPopup(fields=["ID_BV", "SBV_KM2", "PERI_M"],
                                 aliases=["Identifiant du bassin", "Superficie [km²]", "Périmètre [m]"])).add_to(map_)
    folium.GeoJson(rivers, name="Réseau hydrographique", style_function=lambda feature: {
        "color": "#3798bc", "weight": 0.7 + float(feature["properties"].get("strahler") or 1) * 0.55,
        "opacity": 0.85},
        tooltip=folium.GeoJsonTooltip(fields=["NOM", "strahler"], aliases=["Cours d’eau", "Ordre de Strahler"]),
        popup=folium.GeoJsonPopup(fields=["NOM", "strahler", "lengt", "slope"],
                                 aliases=["Cours d’eau", "Ordre de Strahler", "Longueur source", "Pente source"])).add_to(map_)
    entries, groups = [], {}
    for instrument, color in PIEZO_COLORS.items():
        subset = sensors.loc[sensors.TYPE_INSTR.eq(instrument)]
        label = "Piézomètres" if instrument == "piezometer" else "Stations en rivière"
        group = folium.FeatureGroup(name=f'<span style="color:{color}">●</span> {label} ({len(subset)})')
        groups[instrument] = group.get_name()
        cluster = MarkerCluster(
            name=label, control=False, max_cluster_radius=35, spiderfy_on_max_zoom=True,
            show_coverage_on_hover=False, animate=False, disable_clustering_at_zoom=16,
            icon_create_function="function(cluster) {return L.divIcon({html:'<span>' + cluster.getChildCount() + '</span>',className:'station-cluster " + instrument + "',iconSize:[36,36]});}",
        ).add_to(group)
        for _, row in subset.iterrows():
            name = str(row.LIBELLE)
            station_id = int(row.ID_SENSOR)
            csv_id = GIS_CSV_IDS.get(station_id)
            matched = csv_id in sensor_details
            marker = folium.Marker(
                location=[row.geometry.y, row.geometry.x], title=name, alt=name,
                station_name=name, station_id=station_id, instrument_type=instrument,
                z_index_offset=1000 if matched else 0,
                icon=folium.DivIcon(html=f'<span class="station-pin" style="--station-color:{color}"></span>'
                                         + (f'<span class="csv-marker-label">{escape(csv_id)}</span>' if matched else ""),
                                    class_name="station-icon" + (" csv-station" if matched else ""), icon_size=(20, 20), icon_anchor=(10, 10)),
                tooltip=folium.Tooltip(escape(name), direction="right", class_name="station-label"),
                popup=folium.Popup(f'<strong>{escape(name)}</strong><br>{INSTRUMENT_LABELS[instrument]}<br><span class="popup-note">Fiche ouverte dans le panneau.</span>', max_width=220, auto_pan=False),
            ).add_to(group if matched else cluster)
            entries.append({"id": station_id, "csv_id": csv_id if matched else None, "name": name, "type": instrument, "coordinate": [row.geometry.y, row.geometry.x], "marker": marker.get_name(),
                            "cluster": cluster.get_name(), "html": sensor_popup(row, sensor_details),
                            "matched": matched})
        group.add_to(map_)
    folium.LayerControl(collapsed=False, position="topright").add_to(map_)
    MapControls(tiles, entries, groups, [[south, west], [north, east]], missing_sensor_names).add_to(map_)
    map_.fit_bounds([[south, west], [north, east]], padding=(24, 24))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    page = map_.get_root().render().replace('<html>', '<html lang="fr">', 1)
    path.write_text(page, encoding="utf-8")
    return map_, location
