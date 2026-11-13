"""Present generated Orgeval pages without recalculating observations."""
import json
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
PAGES = {
    "map": ("Carte des stations", "map_sensors_orgeval.html"),
    "pzps1": ("Station pzps1", "pzps1.html"),
    "pzps3": ("Station pzps3", "pzps3.html"),
    "pzps4": ("Station pzps4", "pzps4.html"),
}


def prepare_page(html):
    """Route static links to app views without changing the saved HTML files."""
    routes = {"index.html": "map", "map_sensors_orgeval.html": "map"}
    routes.update({f"{sensor}.html": sensor for sensor in ("pzps1", "pzps3", "pzps4")})

    def replace_link(match):
        destination = routes[match.group(2)]
        return f'href="?view={destination}" target="_blank" rel="noopener"'

    pattern = r"href=([\"'])((?:index|map_sensors_orgeval|pzps1|pzps3|pzps4)\.html)\1"
    html = re.sub(pattern, replace_link, html)
    # Folium stores popup markup as JSON-escaped strings before creating the DOM.
    for filename, destination in routes.items():
        original = json.dumps(f'href="{filename}"')[1:-1]
        replacement = json.dumps(
            f'href="?view={destination}" target="_blank" rel="noopener"'
        )[1:-1]
        html = html.replace(original, replacement)
    return html


def main():
    """Embed existing map/chart pages with French navigation and downloads."""
    st.set_page_config(page_title="Orgeval | Observations", layout="wide")
    st.title("Orgeval — Observations hydrogéologiques")
    st.caption("Carte des stations et séries de mesures fournies dans le bassin de l’Orgeval.")
    requested = st.query_params.get("view", "map")
    if requested not in PAGES:
        st.warning("Page inconnue. La carte des stations est affichée.")
        requested = "map"
    selected = st.selectbox(
        "Vue à afficher", list(PAGES), index=list(PAGES).index(requested),
        format_func=lambda value: PAGES[value][0],
    )
    st.query_params["view"] = selected
    path = ROOT / "docs" / PAGES[selected][1]
    if not path.is_file():
        st.error("Page absente. Exécutez main.py puis ajoutez les pages générées dans docs/.")
        st.stop()
    html = path.read_text(encoding="utf-8")
    st.caption("Les liens de navigation dans la carte et les graphiques s’ouvrent dans un nouvel onglet.")
    st.iframe(prepare_page(html), height=950)
    st.download_button(
        "Télécharger cette page HTML", data=html, file_name=path.name,
        mime="text/html", on_click="ignore",
    )
    st.caption(
        "Affichage des HTML générés par main.py : aucun calcul de tendance n’est relancé ici. "
        "Les moyennes journalières servent à l’affichage ; la tendance utilise les observations originales. "
        "Le fond IGN et les bibliothèques de la carte nécessitent une connexion Internet."
    )


if __name__ == "__main__":
    main()
