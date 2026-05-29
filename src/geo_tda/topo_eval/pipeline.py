"""Per-tile Phase C driver: DEM + NHD -> branching stats for comparison.

Glue between data acquisition, the whitebox hydrology engine, the
donor-graph merge tree, and the NHD construct-validity comparison.
Used by the three validity_real_* scripts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.construct_validity import (
    BranchingStats,
    stats_from_merge_tree,
    stats_from_nhd_flowlines,
)

logger = logging.getLogger(__name__)


@dataclass
class TileResult:
    key: str
    bbox: tuple[float, float, float, float]
    ph: BranchingStats | None = None
    whitebox: BranchingStats | None = None
    nhd: BranchingStats | None = None
    h1_cubical: int | None = None
    error: str | None = None


@dataclass
class AcquiredTile:
    key: str
    dem_path: Path
    nhd_path: Path | None
    bbox: tuple[float, float, float, float]


def acquire_tiles(
    bbox: tuple[float, float, float, float],
    *,
    n_tiles: int,
    dem_dir: str | Path = "data/dem",
    nhd_dir: str | Path = "data/nhd",
    resolution: int = 30,
    fetch_nhd: bool = True,
) -> list[AcquiredTile]:
    """Discover/download up to n_tiles DEMs in bbox and their NHD flowlines.

    Network-dependent. DEMs from Planetary Computer 3DEP; NHD flowline
    vectors from the USGS hydrography service. Per-tile failures are
    skipped with a warning rather than aborting the batch.
    """
    from geo_tda.data_acquisition.dem import discover_dem_tiles, download_dem_tile

    dem_dir = Path(dem_dir)
    nhd_dir = Path(nhd_dir)
    discovered = discover_dem_tiles(bbox, resolution=resolution)
    if not discovered:
        logger.warning("no DEM tiles discovered for bbox %s", bbox)
        return []

    out: list[AcquiredTile] = []
    for tile in discovered[:n_tiles]:
        try:
            dem_path = download_dem_tile(tile, dem_dir)
            tbbox = _tile_bbox_from_raster(dem_path)
            nhd_path = None
            if fetch_nhd:
                from geo_tda.data_acquisition.nhd import fetch_nhd_flowlines

                nhd_path = nhd_dir / f"{tile.key}.geojson"
                if not nhd_path.exists():
                    fetch_nhd_flowlines(tbbox, nhd_path)
            out.append(
                AcquiredTile(
                    key=tile.key, dem_path=dem_path, nhd_path=nhd_path, bbox=tbbox
                )
            )
        except Exception as exc:  # noqa: BLE001 - per-tile isolation
            logger.warning("acquisition failed for %s: %s", tile.key, exc)
    return out


def _tile_bbox_from_raster(dem_path: Path) -> tuple[float, float, float, float]:
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(dem_path) as src:
        b = src.bounds
        if src.crs and src.crs.to_epsg() != 4326:
            return transform_bounds(src.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
        return (b.left, b.bottom, b.right, b.top)


def _tile_area_km2(bbox: tuple[float, float, float, float]) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lat = np.radians((min_lat + max_lat) / 2)
    km_per_deg_lon = 111.32 * np.cos(mid_lat)
    km_per_deg_lat = 110.57
    return abs((max_lon - min_lon) * km_per_deg_lon) * abs(
        (max_lat - min_lat) * km_per_deg_lat
    )


def process_tile(
    dem_path: str | Path,
    *,
    key: str,
    tau_channel: float,
    nhd_geojson: str | Path | None = None,
    include_whitebox: bool = False,
    include_ph: bool = True,
    workdir: str | Path | None = None,
) -> TileResult:
    """Run the requested sides of the comparison for one tile.

    Args:
        dem_path: local DEM GeoTIFF.
        key: tile identifier for reporting.
        tau_channel: channelization threshold (cells).
        nhd_geojson: NHD flowline GeoJSON for this tile's bbox; if None,
            the NHD side is skipped.
        include_whitebox: also run whitebox's own Strahler extraction (the
            field-standard, for the ceiling calibration).
        include_ph: run the PH donor-graph merge tree (the metric).
        workdir: whitebox intermediates dir.

    Returns:
        TileResult with whichever sides were requested; on failure, the
        error field is set and the rest are None.
    """
    dem_path = Path(dem_path)
    try:
        bbox = _tile_bbox_from_raster(dem_path)
        area = _tile_area_km2(bbox)
        result = TileResult(key=key, bbox=bbox)

        if include_ph or include_whitebox:
            from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
            from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
            from geo_tda.topo_eval.summaries import h1_cubical_mask

            receiver_codes, accumulation = d8_pointer_and_accumulation(
                dem_path, workdir=workdir
            )
            mask = accumulation >= tau_channel
            channel_cells = int(mask.sum())
            cell_km = _cell_km(bbox, accumulation.shape)

            if include_ph:
                tree = merge_tree_from_accumulation(
                    receiver_codes, accumulation, tau_channel
                )
                result.ph = stats_from_merge_tree(
                    tree, area_km2=area,
                    channel_cell_count=channel_cells, cell_km=cell_km,
                )
                result.h1_cubical = int(h1_cubical_mask(mask))

        if include_whitebox:
            result.whitebox = _whitebox_branching_stats(
                dem_path, tau_channel, area, workdir
            )

        if nhd_geojson is not None:
            result.nhd = stats_from_nhd_flowlines(nhd_geojson, area_km2=area)

        return result
    except Exception as exc:  # noqa: BLE001 - per-tile isolation; report, don't crash the batch
        logger.warning("tile %s failed: %s", key, exc)
        return TileResult(key=key, bbox=(0, 0, 0, 0), error=str(exc))


def _cell_km(bbox, shape) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    H, W = shape
    mid_lat = np.radians((min_lat + max_lat) / 2)
    km_per_deg_lon = 111.32 * np.cos(mid_lat)
    cell_w = abs(max_lon - min_lon) / W * km_per_deg_lon
    cell_h = abs(max_lat - min_lat) / H * 110.57
    return float((cell_w + cell_h) / 2)


def _whitebox_branching_stats(dem_path, tau_channel, area, workdir) -> BranchingStats:
    """Whitebox's own Strahler raster summarized into BranchingStats.

    The field-standard extraction for the ceiling calibration. Reads the
    Strahler raster and counts order occurrences; junctions are estimated
    as the count of order increases (a proxy consistent across tiles).
    """
    from geo_tda.topo_eval.construct_validity import _bifurcation_ratio
    from geo_tda.topo_eval.hydrology import whitebox_strahler

    strahler = whitebox_strahler(dem_path, threshold=tau_channel, workdir=workdir)
    on_stream = strahler[strahler >= 1]
    dist: dict[int, int] = {}
    for order in np.unique(on_stream):
        dist[int(order)] = int((on_stream == order).sum())
    rb = _bifurcation_ratio(dist)
    return BranchingStats(
        junction_count=sum(
            dist.get(o, 0) for o in dist if o >= 2
        ),
        strahler_distribution=dist,
        bifurcation_ratio=rb,
        drainage_density=float("nan"),
    )
