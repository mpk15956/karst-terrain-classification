"""
Vector I/O and schema utilities.

Extracted from geoio.py for better organization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

import logging
import warnings

import geopandas as gpd
from shapely import make_valid

log = logging.getLogger(__name__)


# ---- Basic Vector I/O --------------------------------------------------------


def read_vector(
    path: Union[str, Path],
    layer: Optional[str] = None,
    columns: Optional[Sequence[str]] = None
) -> gpd.GeoDataFrame:
    """
    Read a vector dataset with geopandas. Supports common drivers (SHP, GPKG, GeoJSON).

    Parameters
    ----------
    path : str | Path
        File path to read.
    layer : str | None
        Optional layer name for multi-layer containers (e.g., GPKG).
    columns : Sequence[str] | None
        Optional list of columns to keep (plus geometry).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Vector file not found: {path}")
    gdf = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if columns is not None:
        keep = [c for c in columns if c in gdf.columns]
        missing = sorted(set(columns) - set(keep))
        if missing:
            warnings.warn(f"Requested columns not found and will be ignored: {missing}")
        gdf = gdf[keep + (["geometry"] if "geometry" not in keep else [])]
    return gdf


def write_vector(
    gdf: gpd.GeoDataFrame,
    path: Union[str, Path],
    layer: Optional[str] = None,
    driver: str = "GPKG",
    overwrite: bool = True,
) -> Path:
    """
    Write a GeoDataFrame to disk. Defaults to GeoPackage.

    If overwrite=True and the file exists, it will be unlinked first
    (simple and reliable for single-layer writes).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and path.exists():
        path.unlink()
    if layer is None and driver.upper() == "GPKG":
        raise ValueError("For GPKG writes, please provide a 'layer' name.")
    gdf.to_file(path, driver=driver, layer=layer) if layer else gdf.to_file(path, driver=driver)
    log.info("Wrote %s (%s%s)", path, driver, f":{layer}" if layer else "")
    return path


# ---- Schema / Naming Utilities -----------------------------------------------


def detect_name_column(
    gdf: gpd.GeoDataFrame,
    candidates: Optional[Iterable[str]] = None,
) -> str:
    """
    Detect a best-guess name column for administrative / region names.
    Returns the FIRST matching candidate (case-insensitive).
    """
    if candidates is None:
        candidates = ("PROVINCE", "PROV_NAME", "NAME", "PROVINCENM", "STATE_NAME", "REGION")
    ups = {c.upper(): c for c in gdf.columns}
    for want in candidates:
        if want.upper() in ups:
            return ups[want.upper()]
    raise KeyError(f"Could not detect a name column. Available columns: {list(gdf.columns)}")


def load_and_standardize(
    path: Union[str, Path],
    name_field_candidates: Optional[Iterable[str]] = None,
    out_field: str = "PROVINCE",
    drop_empty: bool = True,
) -> gpd.GeoDataFrame:
    """
    Load boundaries and normalize schema → ['PROVINCE','geometry'] by default.

    - Detects a province/name column (or use name_field_candidates)
    - Uppercases/strips names
    - Repairs invalid geometries and optionally drops empty/null geometries
    """
    gdf = read_vector(path)
    name_col = detect_name_column(gdf, candidates=name_field_candidates)
    gdf = gdf[[name_col, "geometry"]].rename(columns={name_col: out_field})
    gdf[out_field] = gdf[out_field].astype(str).str.upper().str.strip()

    # Repair invalids
    if not gdf.is_valid.all():
        warnings.warn("Invalid geometries found; repairing with make_valid().")
        gdf["geometry"] = gdf["geometry"].apply(make_valid)

    if drop_empty:
        gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty].copy()

    return gdf


__all__ = [
    'read_vector',
    'write_vector',
    'detect_name_column',
    'load_and_standardize',
]
