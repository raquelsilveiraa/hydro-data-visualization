"""Generate French groundwater charts, the Folium map, and a static Pages bundle."""
from html import escape
from pathlib import Path
from shutil import copy2
from time import perf_counter

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mapping import CSV_GIS_IDS, map_sensors_orgeval
from presentation import MEASUREMENTS, format_date, format_number
from trends import trend_detection_time

ROOT = Path(__file__).resolve().parent
HEAD = "Hydraulic Head [mNGF]"
TEMP = "Temperature [°C]"
COND = "Conductivity [mS/cm]"
CHART_CONFIG = {
    "responsive": True, "displaylogo": False, "scrollZoom": True, "locale": "fr",
    "doubleClick": "reset+autosize", "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}
CHART_FONT_SCRIPT = """
const chart = document.getElementById('{plot_id}');
const fullTitle = chart.layout.title.text;
let compactLayout;
function adaptChart() {
    const compact = window.innerWidth < 700;
    if (compact === compactLayout) return;
    compactLayout = compact;
    chart.style.height = (compact ? 1080 : 700) + 'px';
    chart.parentElement.style.height = 'auto';
    Plotly.relayout(chart, {
        'height': compact ? 1080 : 700,
        'margin.l': compact ? 64 : 90, 'margin.r': compact ? 62 : 95,
        'margin.t': compact ? 140 : 125, 'margin.b': compact ? 230 : 75,
        'title.text': compact ? fullTitle.replace(' · ', '<br>') : fullTitle,
        'annotations[0].y': compact ? 1.13 : 1.15,
        'annotations[0].visible': compact,
        'title.font.size': compact ? 15 : 22,
        'legend.y': compact ? -0.22 : 1.11, 'legend.yanchor': compact ? 'top' : 'bottom',
        'legend.entrywidth': compact ? 1 : 0,
        'legend.entrywidthmode': compact ? 'fraction' : 'pixels',
        'xaxis.nticks': compact ? 4 : 8, 'xaxis2.nticks': compact ? 4 : 8
    });
}
adaptChart();
window.addEventListener('resize', adaptChart);
"""

# important function
def load_sensor(path):
    """Read original semicolon observations, validate types, and preserve missing values."""
    df = pd.read_csv(path, sep=";", skipinitialspace=True, encoding="utf-8")
    df.columns = df.columns.str.strip()
    if list(df.columns) != ["dates", HEAD, TEMP, COND]: # only accept this 4 columns and >=20 days of valid data
        raise ValueError(f"Unexpected columns in {path.name}: {df.columns.tolist()}")
    df["dates"] = pd.to_datetime(df["dates"], format="%d/%m/%Y %H:%M", errors="raise") # insert explicit format to avoid blank spaces and empyt data
    if df["dates"].isna().any():
        raise ValueError(f"Missing dates in {path.name}")
    for column in df.columns[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    return df.sort_values("dates").reset_index(drop=True)


def make_figure(df, sensor, slope, daily=True):
    """Display three measurements in two panels using only the supplied trend slope."""
    display = df.set_index("dates")[[HEAD, TEMP, COND]]
    counts = display.resample("D").count() if daily else None
    if daily:
        display = display.resample("D").mean()
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
                           row_heights=[0.74, 0.26], vertical_spacing=0.12)
    trace_type = go.Scatter if daily else go.Scattergl
    for column in (HEAD, TEMP):
        label, unit, color = MEASUREMENTS[column]
        figure.add_trace(trace_type(
            x=display.index, y=display[column], name=label, mode="lines", connectgaps=False,
            line=dict(color=color, width=1.6),
            customdata=counts[column].to_numpy() if daily else None,
            hovertemplate="%{x|%d/%m/%Y}<br>" + label + ": %{y:.3f} " + unit
                          + ("<br>Observations valides : %{customdata}" if daily else "")
                          + "<extra></extra>"), row=1, col=1, secondary_y=column == TEMP)
    valid = df.loc[df[TEMP].notna(), ["dates", TEMP]]
    reference_date = valid.dates.mean()
    reference_temperature = valid[TEMP].mean()
    endpoints = pd.DatetimeIndex([valid.dates.min(), valid.dates.max()])
    # This reference positions the returned slope; it is not another regression.
    years = (endpoints - reference_date).total_seconds() / (365.25 * 86400)
    figure.add_trace(go.Scatter(
        x=endpoints, y=reference_temperature + slope / 10 * years,
        name="Tendance thermique", mode="lines", line=dict(color="#a42b3a", width=2.5, dash="dash"),
        hovertemplate="%{x|%d/%m/%Y}<br>Tendance thermique : %{y:.3f} °C<extra></extra>"),
        row=1, col=1, secondary_y=True)
    label, unit, color = MEASUREMENTS[COND]
    figure.add_trace(trace_type(
        x=display.index, y=display[COND], name=label, mode="lines", connectgaps=False,
        line=dict(color=color, width=1.5),
        customdata=counts[COND].to_numpy() if daily else None,
        hovertemplate="%{x|%d/%m/%Y}<br>Conductivité : %{y:.3f} mS/cm"
                      + ("<br>Observations valides : %{customdata}" if daily else "")
                      + "<extra></extra>"), row=2, col=1)
    figure.update_layout(
        template="simple_white", font=dict(family="Segoe UI, Arial, sans-serif", size=13, color="#263e50"),
        separators=", ", title=dict(
            text=f"<b>{sensor}</b> · Tendance thermique : {format_number(slope, 2)} °C/décennie",
            x=0.055, xanchor="left", y=0.98, yanchor="top", font=dict(size=22)),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.11, yanchor="bottom", font=dict(size=12)),
        margin=dict(l=90, r=95, t=125, b=75), height=700, autosize=True,
        paper_bgcolor="white", plot_bgcolor="white", hovermode="x unified", dragmode="zoom",
        hoverlabel=dict(bgcolor="white", font_size=13),
        modebar=dict(bgcolor="rgba(255,255,255,0.95)", color="#617789", activecolor="#1269a5"),
    )
    figure.add_annotation(
        text="Affichage : moyennes journalières.<br>Tendance calculée sur les observations originales."
             if daily else "Affichage : observations originales, sans agrégation.",
        visible=False, x=0, y=1.15, xref="paper", yref="paper", xanchor="left", showarrow=False,
        font=dict(size=11, color="#687c8c"))
    figure.update_xaxes(
        showline=True, linecolor="#bfcbd4", ticks="outside", showgrid=True, gridcolor="#edf0f3",
        nticks=8, tickfont=dict(size=11), automargin=True, zeroline=False, hoverformat="%d/%m/%Y",
        tickformatstops=[dict(dtickrange=[None, 86400000], value="%d/%m %H:%M"),
                         dict(dtickrange=[86400000, "M1"], value="%d/%m/%Y"),
                         dict(dtickrange=["M1", "M12"], value="%m/%Y"),
                         dict(dtickrange=["M12", None], value="%Y")],
    )
    figure.update_xaxes(rangeselector=dict(
        buttons=[dict(count=6, label="6 mois", step="month", stepmode="backward"),
                 dict(count=1, label="1 an", step="year", stepmode="backward"),
                 dict(count=5, label="5 ans", step="year", stepmode="backward"),
                 dict(label="Toute la période", step="all")],
        bgcolor="#eef3f6", activecolor="#d9e9f2", font=dict(size=11), y=1.02), row=1, col=1)
    figure.update_xaxes(title_text="Date", rangeslider=dict(visible=True, thickness=0.065,
                                                          bgcolor="#f4f7f9"), row=2, col=1)
    figure.update_yaxes(showline=True, linecolor="#bfcbd4", ticks="outside", showgrid=True,
                        gridcolor="#edf0f3", tickfont=dict(size=11), title_font=dict(size=13),
                        automargin=True, zeroline=False, fixedrange=False)
    figure.update_yaxes(title_text="Niveau piézométrique [m NGF]", row=1, col=1, secondary_y=False)
    figure.update_yaxes(title_text="Température [°C]", showgrid=False, row=1, col=1, secondary_y=True)
    figure.update_yaxes(title_text="Conductivité [mS/cm]", row=2, col=1)
    if display[COND].notna().sum() == 0:
        figure.add_annotation(text="Aucune mesure de conductivité disponible pour cette station.",
                              x=0.5, y=0.10, xref="paper", yref="paper", showarrow=False,
                              font=dict(size=12, color="#687c8c"))
        figure.update_yaxes(showticklabels=False, row=2, col=1)
    assert len(figure.data) == 4
    assert [trace.yaxis for trace in figure.data] == ["y", "y2", "y2", "y3"]
    return figure


def summarize_sensor(df, result):
    """Compute latest raw readings and period means once, independently of trend fitting."""
    summary = {
        "rows": len(df), "start": format_date(df.dates.min()), "end": format_date(df.dates.max()),
        "trend": result["trend_decade"], "months": int(result["months"]),
        "ci": result.get("trend_ci_decade", np.nan), "p_value": result.get("p_value", np.nan),
        "measurements": {},
    }
    daily = df.set_index("dates")[list(MEASUREMENTS)].resample("D").mean()
    for column in MEASUREMENTS:
        valid = df.loc[df[column].notna(), ["dates", column]]
        last = valid.iloc[-1] if not valid.empty else None
        summary["measurements"][column] = {
            "valid": int(df[column].notna().sum()), "missing": int(df[column].isna().sum()),
            "mean": float(daily[column].mean()), "min": float(df[column].min()), "max": float(df[column].max()),
            "last": float(last[column]) if last is not None else None,
            "last_date": format_date(last.dates) if last is not None else None,
        }
    return summary


def verify_sensor_matches(sensors, details):
    """Validate the supplied CSV-to-ID_SENSOR mapping, without a name-based join."""
    matches = {}
    for name in details:
        station_id = CSV_GIS_IDS.get(name)
        rows = sensors.loc[sensors.ID_SENSOR.eq(station_id)]
        if station_id is None or len(rows) != 1:
            raise ValueError(f"Expected one exact GIS match by ID_SENSOR for CSV {name}; found {len(rows)}")
        matches[name] = station_id
        print(f"Verified CSV/GIS match: {name}, ID_SENSOR={station_id}, LIBELLE={rows.iloc[0].LIBELLE}")
    return matches


def write_chart(figure, sensor, output):
    """Embed the local French locale before Plotly initializes, retaining offline chart use."""
    interactions = (ROOT / "assets" / "chart.js").read_text(encoding="utf-8")
    curve_options = []
    for index, trace in enumerate(figure.data):
        available = bool(np.isfinite(np.asarray(trace.y, dtype=float)).any())
        unavailable = " — non disponible" if not available else ""
        disabled = " disabled" if not available else ""
        curve_options.append(
            f'<label><input type="checkbox" data-trace="{index}" checked{disabled}>'
            f'<i style="--curve-color:{escape(trace.line.color)}"></i>'
            f'{escape(trace.name)}{unavailable}</label>')
    curves = "".join(curve_options)
    body = figure.to_html(full_html=False, include_plotlyjs=True, config=CHART_CONFIG,
                          post_script=CHART_FONT_SCRIPT + "\n" + interactions)
    position = body.rindex("Plotly.newPlot(")
    locale_script = (ROOT / "assets" / "plotly-locale-fr.js").read_text(encoding="utf-8")
    body = body[:position] + locale_script + ";\n" + body[position:]
    css = (ROOT / "assets" / "chart.css").read_text(encoding="utf-8")
    page = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{sensor} — Séries temporelles · Orgeval</title>
<style>{css}</style></head><body><header class="page-header"><a class="brand" href="index.html">ORGEVAL <span>Observations hydrogéologiques</span></a>
<nav aria-label="Navigation principale"><a href="index.html">Accueil</a><a href="map_sensors_orgeval.html">Carte des stations</a></nav></header>
<main class="chart-page"><section class="station-banner" aria-label="Identification de la station"><div><strong>Station {sensor}</strong><span class="station-id">Identifiant {CSV_GIS_IDS.get(sensor, "non renseigné")}</span></div><span>Bassin de l’Orgeval · Observations fournies</span></section>
<section class="chart-toolbar" aria-label="Outils des séries temporelles">
  <div class="chart-period"><span>Chroniques de mesure</span><output id="chart-period" aria-live="polite"></output></div>
  <div class="chart-actions">
    <details class="curve-menu"><summary>Courbes</summary><fieldset aria-label="Sélection des courbes">{curves}</fieldset></details>
    <button type="button" data-chart-action="pan" aria-pressed="false">Déplacer</button>
    <button type="button" data-chart-action="reset">Réinitialiser la vue</button>
    <div class="period-navigation" aria-label="Navigation temporelle"><button type="button" data-chart-action="previous" aria-label="Période précédente">←</button><button type="button" data-chart-action="next" aria-label="Période suivante">→</button></div>
  </div>
</section>{body}<aside class="method-note"><strong>Lecture des données.</strong> Affichage : moyennes journalières ; calcul de tendance : observations originales. Le niveau est exprimé en altitude NGF, pas en profondeur.
Les lacunes restent visibles. La tendance décrit l’évolution observée : elle ne constitue ni une prévision ni une preuve de causalité.
La conductivité est affichée uniquement lorsqu’une mesure a été fournie. La tendance provient des anomalies mensuelles désaisonnalisées ; sa droite en °C est positionnée à la date et à la température moyennes des observations valides.</aside></main></body></html>'''
    (output / f"{sensor}.html").write_text(page, encoding="utf-8")


def publish_static_pages(output):
    """Build relative-link landing pages and a self-contained docs/ Pages directory."""
    landing = (ROOT / "index.html").read_text(encoding="utf-8")
    landing = landing.replace('href="output/', 'href="').replace('src="output/', 'src="')
    (output / "index.html").write_text(landing, encoding="utf-8")
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    for filename in ("index.html", "pzps1.html", "pzps3.html", "pzps4.html", "map_sensors_orgeval.html"):
        copy2(output / filename, docs / filename)
    (docs / ".nojekyll").touch()


def main():
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    sensor_details = {}
    for sensor in ("pzps1", "pzps3", "pzps4"):
        df = load_sensor(ROOT / "data" / "piezo_data" / f"{sensor}.csv")
        result = trend_detection_time(df, "dates", TEMP)
        slope = result["trend_decade"]
        if not np.isfinite(slope):
            raise ValueError(f"Non-finite temperature trend for {sensor}: {result}")
        print(f"{sensor}: rows={len(df)}, dates={df.dates.min()} to {df.dates.max()}, "
              f"missing={df[list(MEASUREMENTS)].isna().sum().to_dict()}, "
              f"trend={slope:.6f} C/decade, valid months={result['months']}")
        sensor_details[sensor] = summarize_sensor(df, result)
        for daily in (False, True):
            start = perf_counter()
            figure = make_figure(df, sensor, slope, daily=daily)
            payload = figure.to_json()
            print(f"  {'daily' if daily else 'full Scattergl'}: {len(figure.data[0].x)} points/measurement, "
                  f"JSON={len(payload.encode('utf-8')) / 1e6:.2f} MB, build+serialize={perf_counter()-start:.2f}s")
            del payload
        write_chart(figure, sensor, output)
    gis = ROOT / "data" / "GIS"
    layers = [gpd.read_file(gis / filename) for filename in (
        "stations_water_temp_piezo.shp", "limites_avenelles.shp", "reseau_hydraugraphique.shp")]
    for name, layer in zip(("sensors", "catchment", "hydro"), layers):
        print(f"{name}: features={len(layer)}, CRS={layer.crs}, geometry={layer.geom_type.value_counts().to_dict()}")
    verify_sensor_matches(layers[0], sensor_details)
    missing_geometry = layers[0].geometry.isna() | layers[0].geometry.is_empty
    missing_names = layers[0].loc[missing_geometry, "LIBELLE"].tolist()
    if missing_names:
        print("Excluded sensors without coordinates:", missing_names)
        layers[0] = layers[0].loc[~missing_geometry].copy()
    map_sensors_orgeval(*layers, output_path=output / "map_sensors_orgeval.html",
                        sensor_details=sensor_details, missing_sensor_names=missing_names)
    publish_static_pages(output)
    for path in sorted(output.glob("*.html")):
        assert path.stat().st_size > 0
        print(f"Created {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
