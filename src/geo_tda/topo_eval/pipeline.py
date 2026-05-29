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


# Planetary Computer 3DEP seamless DEM.
PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_3DEP_COLLECTION = "3dep-seamless"
PC_3DEP_ASSET = "data"


def _tile_keys_covering_bbox(
    bbox: tuple[float, float, float, float],
) -> list[tuple[int, int, tuple[float, float, float, float]]]:
    """Integer 1-degree tile SW corners covering bbox.

    Returns (sw_lon, sw_lat, tile_bbox) per 1x1 degree tile, where
    tile_bbox is (min_lon, min_lat, max_lon, max_lat).
    """
    import math

    min_lon, min_lat, max_lon, max_lat = bbox
    out = []
    for lat in range(math.floor(min_lat), math.ceil(max_lat)):
        for lon in range(math.floor(min_lon), math.ceil(max_lon)):
            out.append((lon, lat, (float(lon), float(lat), float(lon + 1), float(lat + 1))))
    return out


def acquire_tiles(
    bbox: tuple[float, float, float, float],
    *,
    n_tiles: int,
    dem_dir: str | Path = "data/dem",
    nhd_dir: str | Path = "data/nhd",
    gsd: int = 30,
    fetch_nhd: bool = True,
) -> list[AcquiredTile]:
    """Download up to n_tiles 3DEP DEMs covering bbox and their NHD flowlines.

    Network-dependent. DEMs from Planetary Computer 3DEP seamless (asset
    hrefs signed via planetary_computer); NHD flowline vectors from the
    USGS hydrography service. Per-tile failures are skipped with a warning
    rather than aborting the batch.
    """
    import planetary_computer
    from pystac_client import Client

    dem_dir = Path(dem_dir)
    nhd_dir = Path(nhd_dir)
    dem_dir.mkdir(parents=True, exist_ok=True)

    catalog = Client.open(PC_STAC_URL, modifier=planetary_computer.sign_inplace)
    tile_specs = _tile_keys_covering_bbox(bbox)

    out: list[AcquiredTile] = []
    for sw_lon, sw_lat, tbbox in tile_specs:
        if len(out) >= n_tiles:
            break
        key = _key_from_corner(sw_lon, sw_lat)
        try:
            dem_path = dem_dir / f"USGS_seamless_{key}_{gsd}m.tif"
            if not dem_path.exists():
                href = _find_3dep_href(catalog, tbbox, gsd)
                if href is None:
                    logger.warning("no 3DEP item for %s at gsd=%d", key, gsd)
                    continue
                _download(href, dem_path)
            nhd_path = None
            if fetch_nhd:
                from geo_tda.data_acquisition.nhd import fetch_nhd_flowlines

                nhd_path = nhd_dir / f"{key}.geojson"
                if not nhd_path.exists():
                    fetch_nhd_flowlines(tbbox, nhd_path)
            out.append(
                AcquiredTile(key=key, dem_path=dem_path, nhd_path=nhd_path, bbox=tbbox)
            )
        except Exception as exc:  # noqa: BLE001 - per-tile isolation
            logger.warning("acquisition failed for %s: %s", key, exc)
    return out


def _key_from_corner(lon: int, lat: int) -> str:
    ns = "n" if lat >= 0 else "s"
    ew = "w" if lon < 0 else "e"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def _find_3dep_href(catalog, tbbox, gsd) -> str | None:
    search = catalog.search(
        collections=[PC_3DEP_COLLECTION],
        bbox=tbbox,
        query={"gsd": {"eq": gsd}},
    )
    items = list(search.item_collection())
    if not items:
        # retry without the gsd filter; pick the finest available
        items = list(
            catalog.search(collections=[PC_3DEP_COLLECTION], bbox=tbbox).item_collection()
        )
        if not items:
            return None
        items.sort(key=lambda it: it.properties.get("gsd", 1e9))
    item = items[0]
    asset = item.assets.get(PC_3DEP_ASSET)
    return asset.href if asset else None


def _download(href: str, dest: Path) -> None:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with requests.get(href, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)


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
    window: int | None = None,
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
        window: if set, process a centered window x window crop of the
            flow grids instead of the full tile. The pure-Python donor
            union-find does not scale to full 1-degree tiles (~13M cells)
            on a laptop; windowing is the smoke/partial path, with the
            full-tile run deferred to Sapelo2. Windowing introduces an
            edge effect (cells whose donors lie outside the window read as
            channel heads), which biases junction/Strahler counts near the
            window border; acceptable for the demo, documented here.

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
            if window is not None:
                receiver_codes, accumulation = _center_window(
                    receiver_codes, accumulation, window
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


def _center_window(receiver_codes, accumulation, window):
    H, W = accumulation.shape
    if window >= H and window >= W:
        return receiver_codes, accumulation
    i0 = max(0, (H - window) // 2)
    j0 = max(0, (W - window) // 2)
    sl = (slice(i0, i0 + window), slice(j0, j0 + window))
    return receiver_codes[sl].copy(), accumulation[sl].copy()


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
