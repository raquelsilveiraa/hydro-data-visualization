"""Shared French display formatting; no statistical calculations live here."""
from math import isfinite

MEASUREMENTS = {
    "Hydraulic Head [mNGF]": ("Niveau piézométrique", "m NGF", "#1269a5"),
    "Temperature [°C]": ("Température", "°C", "#d8871b"),
    "Conductivity [mS/cm]": ("Conductivité", "mS/cm", "#0d887e"),
}
INSTRUMENT_LABELS = {"piezometer": "Piézomètre", "river_sensor": "Station en rivière"}


def format_number(value, decimals=3):
    """Format finite measurements with a decimal comma, without inventing a value."""
    if value is None or not isfinite(float(value)):
        return "Non disponible"
    return f"{value:,.{decimals}f}".replace(",", "\u202f").replace(".", ",")


def format_count(value):
    """Use French thousands grouping for observation counts."""
    return f"{int(value):,}".replace(",", "\u202f")


def format_date(value):
    """Use unambiguous French numeric dates, independent of the host locale."""
    return value.strftime("%d/%m/%Y %H:%M") if value is not None else None
