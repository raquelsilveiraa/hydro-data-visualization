# Orgeval ? carte des stations et s?ries temporelles

Static French-language presentation of the supplied groundwater technical test:
three Plotly station charts and a Folium map with a real IGN basemap. No server
or database is needed to view the generated website.

## Production files

```text
main.py                     Load, validate, calculate and generate pages
mapping.py                  Validate GIS layers and build the Folium map
presentation.py             Shared French labels, units and formatting
trends.py                   Original supplied trend method, unchanged
index.html                  Landing-page template
assets/                     Required map/chart CSS, JavaScript and notices
data/piezo_data/            pzps1.csv, pzps3.csv, pzps4.csv
data/GIS/                   Shapefiles and all supplied sidecar files
requirements.txt            Runtime dependencies
.gitignore                  Excludes local development artifacts
.gitattributes              Preserves original input bytes
.github/workflows/pages.yml Manual publication of docs/ only
docs/
    index.html
    map_sensors_orgeval.html
    pzps1.html
    pzps3.html
    pzps4.html
    .nojekyll
```

The local tests, environments, reports, screenshots, development configuration
and duplicate output/ are intentionally excluded from the release. Keep all
supplied GIS sidecars together; they contain attributes, indexes and CRS metadata.

## Install and generate

Python 3.10 or newer is required; this release was checked with Python 3.12.
Dependencies are NumPy, pandas, SciPy, Plotly, GeoPandas, Folium, branca and Jinja2.
From the project root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

On Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

The generator writes five HTML pages to output/ and copies the publishing bundle
to docs/, including its empty .nojekyll file. Open docs/index.html in a browser,
or run `python -m http.server 8000 --directory docs` for a local preview.
Changes to input files require running main.py again; HTML does not execute Python.

## Execution hierarchy and calculations

```text
main.main()
  load_sensor() -> validate/sort raw observations
  trends.trend_detection_time(raw)
    monthly_anomalies() -> monthly_means()
  summarize_sensor() -> latest values and summary metrics
  make_figure() -> display-only daily means and returned trend slope
  write_chart() -> Plotly page with assets/chart.css and assets/chart.js
  verify_sensor_matches() -> exact ID_SENSOR relationships
  mapping.map_sensors_orgeval() -> CRS conversion and station map
    sensor_popup() and MapControls -> assets/map.css and assets/map.js
  publish_static_pages() -> landing page and docs/ copy
```

presentation.py supplies French labels/formatting to the rendering modules.
The original CSVs use semicolons and day/month/year timestamps. Required columns
are dates, Hydraulic Head [mNGF], Temperature [?C] and Conductivity [mS/cm].
Invalid dates/numbers raise errors; missing measurements remain missing.

The upper chart panel shows hydraulic head in m NGF on the left and temperature
in ?C plus its trend on the right. Conductivity in mS/cm occupies a separate lower
panel. Daily means reduce rendering points only. Missing days remain gaps, with
no interpolation or zero filling. Conductivity is unavailable for pzps1/pzps4;
pzps3 displays only the supplied valid observations.

Only trend_detection_time computes the reported temperature trend, using complete
raw observations. Its monthly means require 20 valid days; it removes calendar-
month climatology and requires 36 valid months. The returned slope in ?C/decade is
divided by 10 for plotting per year (365.25 days). The straight line is positioned
at the mean valid raw temperature and mean corresponding timestamp; this anchor
is visual positioning, not another fitted regression or forecast. Summary averages
use valid daily means, distinct from averaging every raw sub-daily observation.

## Station matching and map

| CSV | GIS ID_SENSOR |
| --- | ---: |
| pzps1.csv | 1 |
| pzps3.csv | 4 |
| pzps4.csv | 8 |

Only those exact keys receive CSV measurements and chart links. Other stations
show supplied GIS metadata and a French no-series message. Latest valid values
are selected separately for each variable with its own timestamp; missing values
are shown as Non disponible.

Sensors are supplied in EPSG:2154; catchment and hydrography in EPSG:27572.
Declared CRSs are validated and reprojected to EPSG:4326; Folium receives
latitude/longitude. The catchment remains its supplied line geometry.
The map contains 52 positioned stations (44 piezometers, 8 river stations),
one catchment feature and 19 hydrographic segments. Four records have no location:
GRANGES-PZ3, RIV_LOGE, RIV_MELARCHEZ, RIV_THEIL. They are disclosed, not positioned.

## Publish on GitHub Pages

Publish only docs/ as the website. All page links are relative and work under a
repository-name URL prefix. Keep an existing working Pages setup if present;
do not add a duplicate workflow. Otherwise, the supplied manual workflow can be
used after committing the production files to your intended GitHub repository:

1. In Settings -> Pages -> Source, select GitHub Actions.
2. In Actions, run Publish GitHub Pages on the intended branch.
3. Wait for deployment success and open the public HTTPS URL shown by GitHub.
4. Verify index.html, map_sensors_orgeval.html and all three chart pages online.

A branch-based existing setup may instead publish its configured branch /docs.
Regenerate and commit docs/ whenever source or inputs change. Never force-push.
Do not stage tests/, reports/, output/, environments or screenshots.

Repository: https://github.com/raquelsilveiraa/hydro-data-visualization

The source repository is private. GitHub repository file links require authorized
login and do not render the interactive website. Pages availability for a private
repository depends on the account plan. After enabling Pages, its intended site
address is https://raquelsilveiraa.github.io/hydro-data-visualization/ ; this is
not a claim of successful deployment. Making the repository public exposes the
tracked CSV/GIS files; website deployment itself publishes only docs/.

## Limitations

IGN tiles and map JavaScript/CSS dependencies require internet. Tile failures
show a French warning; unavailable external services are separate from application
errors. Chart pages bundle Plotly and are about 5.5 MB each. No external forecasts,
rainfall, discharge, inferred coordinates or water-level classifications are added.
Local tests are retained outside the release; they are not installation requirements.
