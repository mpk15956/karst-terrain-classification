"""
Raster and vector I/O utilities.

Extracted from geoio.py for better organization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union

import logging
import warnings

import geopandas as gpd
import numpy as np
import shapely
from shapely import make_valid, set_precision, union_all
from shapely.geometry import base as shapely_base
from pyproj import CRS

log = logging.getLogger(__name__)


# ---- Geometry repair / union / singlepart ------------------------------------


def fix_invalid(gdf: gpd.GeoDataFrame, buffer_zero: bool = False) -> gpd.GeoDataFrame:
    """
    Repair invalid geometries with shapely.make_valid; optionally apply buffer(0).
    """
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(make_valid)
    if buffer_zero:
        gdf["geometry"] = shapely.buffer(gdf["geometry"].values, 0)
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty]
    return gdf


def safe_union_all(
    gdf: gpd.GeoDataFrame,
    grid_size: float = 1e-6,
    repair: bool = True,
    fallback_unary: bool = True,
) -> shapely_base.BaseGeometry:
    """
    Robust union across many polygons with fallback strategies.
    """
    geoms = gdf.geometry.values
    try:
        return shapely.union_all(geoms, grid_size=grid_size)
    except Exception as e:
        log.debug("union_all(grid_size=%s) failed: %s", grid_size, e)

    if repair:
        try:
            geoms2 = shapely.buffer(shapely.make_valid(geoms), 0)
            return shapely.union_all(geoms2, grid_size=grid_size)
        except Exception as e:
            log.debug("union_all after repair failed: %s", e)

    if fallback_unary:
        from shapely.ops import unary_union as _uunion
        return _uunion(shapely.make_valid(geoms))

    raise


def ensure_crs(
    gdf: gpd.GeoDataFrame,
    target_crs: Union[int, str, CRS],
    allow_reproject: bool = True,
) -> gpd.GeoDataFrame:
    """
    Ensure a GeoDataFrame is in the target CRS.
    """
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS set.")
    target = CRS.from_user_input(target_crs)
    if CRS.from_user_input(gdf.crs) == target:
        return gdf
    if not allow_reproject:
        raise ValueError(f"CRS mismatch (have {gdf.crs}, want {target})")
    return gdf.to_crs(target)


__all__ = ['safe_union_all', 'ensure_crs', 'fix_invalid']
