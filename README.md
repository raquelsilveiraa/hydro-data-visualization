# hydro-data-visualization

Interactive groundwater charts and a station map for the Orgeval study area.
The project transforms the supplied sensor CSVs and GIS layers into a static,
French-language website using Python, Plotly and Folium.

## Requirements

- Python 3.10 or newer (tested with Python 3.12).
- Dependencies listed in requirements.txt: NumPy, pandas, SciPy, Plotly,
  GeoPandas, Folium, branca and Jinja2.
- Internet access for the IGN basemap and external map libraries.

## Run from the terminal

Run these commands from the project root.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Linux and macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Once installed, run only the last command to regenerate the website.

## View the website

Open docs/index.html in your browser. Alternatively, start a local server:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 --directory docs
```

On Linux/macOS, use `.venv/bin/python` instead of the Windows executable.
Open http://localhost:8000 and press Ctrl+C in the terminal to stop the server.

The generated pages are:

| Page | Content |
| --- | --- |
| index.html | Landing page and navigation to the map and three stations |
| map_sensors_orgeval.html | Interactive catchment map and station details |
| pzps1.html | Groundwater, temperature and conductivity panels for pzps1 |
| pzps3.html | Groundwater, temperature and conductivity panels for pzps3 |
| pzps4.html | Groundwater, temperature and conductivity panels for pzps4 |

HTML files contain the generated results. They do not rerun Python or reload the
CSVs: run main.py again after changing source code or inputs.

## Project structure

```text
hydro-data-visualization/
|-- main.py
|-- mapping.py
|-- presentation.py
|-- trends.py
|-- index.html
|-- requirements.txt
|-- assets/
|   |-- chart.css
|   |-- chart.js
|   |-- map.css
|   |-- map.js
|   |-- plotly-locale-fr.js
|   `-- NOTICE.txt
|-- data/
|   |-- piezo_data/          # Original sensor CSVs
|   `-- GIS/                 # Original shapefiles and their sidecars
|-- docs/                    # Generated website for static hosting
|-- output/                  # Local generated copy; ignored by Git
|-- .github/workflows/pages.yml
|-- .gitattributes
`-- .gitignore
```

## What each file does

| File or folder | Responsibility and effect on the website |
| --- | --- |
| main.py | Orchestrates CSV loading, validation, trend calculations, station summaries, Plotly charts, map creation and HTML generation. |
| mapping.py | Validates GIS layers, reprojects coordinates, matches station IDs and builds the Folium map with layers and station details. |
| presentation.py | Centralizes French variable labels, units and number/date formatting used in the interface. |
| trends.py | Supplied scientific method for monthly aggregation, deseasonalization and temperature trend estimation. Kept unchanged. |
| index.html | Landing-page template used by the generator to create website navigation. |
| assets/chart.css | Styles the station pages, chart headers, controls and responsive layout. |
| assets/chart.js | Implements curve selection, time navigation, panning and reset controls. |
| assets/map.css | Styles the map, search, legend, controls and station-details panel. |
| assets/map.js | Handles search, station selection, details, map interactions and tile-failure warnings. |
| assets/plotly-locale-fr.js | Provides French translations for Plotly controls. |
| assets/NOTICE.txt | Records third-party asset attribution. |
| data/piezo_data/ | Contains pzps1.csv, pzps3.csv and pzps4.csv with the original observations. |
| data/GIS/ | Contains station geometries, catchment boundary and hydrography. Keep shapefiles and all supplied sidecars together. |
| requirements.txt | Lists the Python packages needed to generate the website. |
| output/ | Receives locally generated HTML pages. |
| docs/ | Contains the same five pages and .nojekyll, ready for static hosting. |
| .github/workflows/pages.yml | Provides a manually triggered GitHub Pages deployment of docs/. |
| .gitattributes | Prevents Git text conversion from changing supplied input files and trends.py. |
| .gitignore | Keeps environments, caches and local development artifacts out of Git. |

## Processing workflow

```text
main.py
  -> load_sensor(): read and validate original CSV observations
  -> trends.trend_detection_time(): calculate the temperature trend
  -> summarize_sensor(): prepare latest values and summary metrics
  -> make_figure(): build display series and Plotly panels
  -> write_chart(): combine figures, styles and interactions into HTML
  -> verify_sensor_matches(): check the exact CSV-to-GIS relationships
  -> mapping.map_sensors_orgeval(): create the interactive station map
  -> publish_static_pages(): generate navigation and copy pages into docs/
```

presentation.py supplies shared display labels and formatting. The CSS and
JavaScript assets are included in the generated HTML by the Python modules.
Opening the website requires no Python server or database.

## Data and chart interpretation

The CSVs use semicolons and day/month/year timestamps. Required columns are:

- dates
- Hydraulic Head [mNGF]
- Temperature [°C]
- Conductivity [mS/cm]

Dates and numeric fields are validated. Missing measurements remain missing;
they are not interpolated or replaced with zero.

The upper chart panel shows hydraulic head in m NGF on the left axis and
temperature in °C on the right. The dashed thermal trend shares the temperature
axis, with its value reported in °C per decade in the title. Conductivity in
mS/cm appears in a separate panel with the same date axis.

Daily means are used only to reduce the number of displayed points. The supplied
trend_detection_time function receives the original observations and calculates
the trend from deseasonalized monthly anomalies. The displayed straight line
uses that returned slope, divided by 10 to convert decades to years, and is
anchored at the mean valid raw temperature and its mean timestamp. The anchor
positions the line; it does not fit a second trend or create a forecast.

Conductivity is unavailable for pzps1 and pzps4 and is explicitly marked as such.
For pzps3, only valid supplied measurements are displayed. Missing periods remain
gaps. Latest values in station details use a separate valid timestamp for each
variable.

## Map and station matching

CSV measurements and chart links are attached only through these exact keys:

| CSV | GIS ID_SENSOR |
| --- | ---: |
| pzps1.csv | 1 |
| pzps3.csv | 4 |
| pzps4.csv | 8 |

Other stations show their available GIS metadata and a French message stating
that no time series was supplied. No name approximation or proximity matching is
used.

The map includes the catchment boundary, hydrographic network, 44 piezometers
and 8 river stations. Source coordinates are reprojected from their declared
CRSs to EPSG:4326 before use in Folium. Four stations have no supplied coordinates
and are listed without invented locations: GRANGES-PZ3, RIV_LOGE, RIV_MELARCHEZ
and RIV_THEIL.

## Static hosting

The docs/ folder is the publishing bundle. It contains five HTML pages and an
empty .nojekyll file. Relative links support hosting under a repository path.
The included GitHub Pages workflow publishes this folder when run manually.
Regenerate and commit docs/ whenever the website needs to be updated.

## Limitations

The map requires internet access for IGN tiles and external mapping libraries;
if tiles fail, the interface displays a warning. The chart pages bundle Plotly
and can be opened offline. Only three stations have supplied time series. No
forecasts, discharge, rainfall or inferred measurements are included.
