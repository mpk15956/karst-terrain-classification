"""Per-tile Phase C driver: DEM + NHD -> branching stats for comparison.

Glue between data acquisition, the whitebox hydrology engine, the
donor-graph merge tree, and the NHD construct-validity comparison.
Used by the three validity_real_* scripts.
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.construct_validity import (
    BranchingStats,
    stats_from_flowlines,
    stats_from_merge_tree,
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
    # diagnostics that survive the A-vs-B framing choice (Phase C change 3)
    tau_channel: float | None = None
    target_density: float | None = None
    window_size: int | None = None
    window_processed_fraction: float | None = None
    windowed_missed_dominant_basin: bool | None = None
    ph_segment_count: int | None = None
    whitebox_segment_count: int | None = None


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
        # retry without the gsd filter; ranking below prefers the finest gsd
        items = list(
            catalog.search(collections=[PC_3DEP_COLLECTION], bbox=tbbox).item_collection()
        )
        if not items:
            return None
    item = _best_covering_item(items, tbbox)
    asset = item.assets.get(PC_3DEP_ASSET) if item else None
    return asset.href if asset else None


def _best_covering_item(items, tbbox):
    """Pick the item that actually COVERS the tile, not one touching a corner.

    A bbox search returns every item intersecting the tile, including
    neighbors that share only an edge or corner. Rank by overlap area with
    the tile, then by finest gsd, so the returned DEM matches the tile
    (and so its NHD reference) rather than an adjacent footprint.
    """
    min_lon, min_lat, max_lon, max_lat = tbbox

    def overlap(it) -> float:
        ib = getattr(it, "bbox", None)
        if not ib:
            return 0.0
        ox = max(0.0, min(max_lon, ib[2]) - max(min_lon, ib[0]))
        oy = max(0.0, min(max_lat, ib[3]) - max(min_lat, ib[1]))
        return ox * oy

    ranked = sorted(
        items, key=lambda it: (overlap(it), -it.properties.get("gsd", 1e9)),
        reverse=True,
    )
    best = ranked[0]
    return best if overlap(best) > 0 else None


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
    match_density: bool = False,
    flag_dominant_basin: bool = True,
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
            window border; acceptable for the demo, documented here. At the
            Sapelo2 window (4096) a 1-degree 3DEP tile is not cropped, so
            the window diagnostics report full coverage.
        match_density: choose tau_channel per tile to match the NHD
            drainage density (proposal.md), instead of using the passed
            tau_channel. Requires nhd_geojson.
        flag_dominant_basin: when a crop happened, set
            windowed_missed_dominant_basin by checking whether the
            full-tile max-accumulation cell lies inside the window.

    Returns:
        TileResult with whichever sides were requested; on failure, the
        error field is set and the rest are None.
    """
    dem_path = Path(dem_path)
    tmp_run: Path | None = None
    owns_wd = workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="tile_")) if owns_wd else Path(workdir)
    try:
        # Materialize a plain GeoTIFF for the run: either a centered window
        # crop (laptop/partial tier) or a full-tile plain copy. Both go
        # through whitebox, which cannot read the raw 3DEP COG; the rewrite
        # is mandatory, not just a windowing convenience. Cropping the input
        # rather than post-whitebox arrays keeps PH and whitebox on the
        # identical raster.
        cropped = False
        if window is not None:
            tmp_run = _crop_dem_to_window(dem_path, window)
            cropped = tmp_run is not None
        if tmp_run is None:
            tmp_run = _materialize_plain(dem_path)
        run_path = tmp_run

        bbox = _tile_bbox_from_raster(run_path)
        area = _tile_area_km2(bbox)
        result = TileResult(key=key, bbox=bbox, window_size=window)
        clip_bbox = bbox if cropped else None
        result.window_processed_fraction = _processed_fraction(dem_path, run_path)

        # NHD first: it is the reference and supplies the density target.
        nhd_stats = None
        if nhd_geojson is not None:
            nhd_stats = stats_from_flowlines(
                nhd_geojson, area_km2=area, clip_bbox=clip_bbox
            )
            result.nhd = nhd_stats

        tau = tau_channel
        if include_ph or match_density:
            from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
            from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
            from geo_tda.topo_eval.segment_graph import (
                segment_graph_from_merge_tree,
            )
            from geo_tda.topo_eval.summaries import h1_cubical_mask

            receiver_codes, accumulation = d8_pointer_and_accumulation(
                run_path, workdir=workdir
            )
            cell_km = _cell_km(bbox, accumulation.shape)
            if match_density and nhd_stats is not None:
                tau = tau_for_target_density(
                    accumulation, nhd_stats.drainage_density, area, cell_km
                )
                result.target_density = float(nhd_stats.drainage_density)
                if not np.isfinite(tau):
                    tau = tau_channel
            result.tau_channel = float(tau)

            if include_ph:
                mask = accumulation >= tau
                channel_cells = int(mask.sum())
                tree = merge_tree_from_accumulation(
                    receiver_codes, accumulation, tau
                )
                result.ph = stats_from_merge_tree(
                    tree, area_km2=area,
                    channel_cell_count=channel_cells, cell_km=cell_km,
                )
                result.h1_cubical = int(h1_cubical_mask(mask))
                result.ph_segment_count = len(
                    segment_graph_from_merge_tree(tree).all_nodes()
                )
        else:
            result.tau_channel = float(tau)

        # Whitebox (ceiling side) and the dominant-basin diagnostic are
        # isolated: a whitebox failure or an extra-pass failure must not
        # cost the PH-vs-NHD comparison, which is the construct claim.
        if include_whitebox:
            try:
                result.whitebox, result.whitebox_segment_count = (
                    _whitebox_branching_stats(run_path, tau, area, workdir)
                )
            except Exception as exc:  # noqa: BLE001 - per-side isolation
                logger.warning("tile %s whitebox side failed: %s", key, exc)

        if cropped and flag_dominant_basin:
            try:
                result.windowed_missed_dominant_basin = _missed_dominant_basin(
                    dem_path, window, workdir
                )
            except Exception as exc:  # noqa: BLE001 - diagnostic only
                logger.warning("tile %s dominant-basin flag failed: %s", key, exc)

        return result
    except Exception as exc:  # noqa: BLE001 - per-tile isolation; report, don't crash the batch
        logger.warning("tile %s failed: %s", key, exc)
        return TileResult(key=key, bbox=(0, 0, 0, 0), error=str(exc))
    finally:
        if tmp_run is not None and tmp_run.exists():
            tmp_run.unlink()
        if owns_wd:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)


def _window_indices(
    H: int, W: int, window: int
) -> tuple[int, int, int, int] | None:
    """Centered window crop indices (i0, j0, h, w), or None if no crop.

    Shared by the cropper and the dominant-basin diagnostic so both agree
    on exactly which cells the window covers.
    """
    if window >= H and window >= W:
        return None
    i0 = max(0, (H - window) // 2)
    j0 = max(0, (W - window) // 2)
    h = min(window, H)
    w = min(window, W)
    return i0, j0, h, w


def tau_for_target_density(
    accumulation: np.ndarray,
    target_density: float,
    area_km2: float,
    cell_km: float,
) -> float:
    """Channelization threshold whose channel density matches a target.

    proposal.md fixes tau_channel per tile to match NHD's drainage density
    (drainage density is a controlled covariate, not a criterion). Density
    is reported as channel_cell_count * cell_km / area, so the cell count
    that reproduces target_density is target_density * area / cell_km, and
    tau is the accumulation value with exactly that many cells at or above
    it. NHD density is substrate-independent (it comes from the vectors,
    not the DEM), so this rule re-derives tau at any grid resolution by
    swapping cell_km; see docs/topo_eval/notes/m2_reference_forward_feed.md.
    """
    if not (np.isfinite(target_density) and cell_km > 0 and area_km2 > 0):
        return float("nan")
    acc = accumulation.ravel()
    acc = acc[np.isfinite(acc)]
    n = acc.size
    if n == 0:
        return float("nan")
    target_cells = int(round(target_density * area_km2 / cell_km))
    target_cells = max(1, min(target_cells, n))
    kth = n - target_cells
    tau = float(np.partition(acc, kth)[kth])
    return max(tau, 1.0)


def _full_tile_max_accum_cell(
    dem_path: Path, workdir: Path | None = None
) -> tuple[int, int] | None:
    """(row, col) of the max-accumulation cell on the FULL (uncropped) tile.

    Used only to set windowed_missed_dominant_basin: whitebox D8 routing on
    the whole tile is compiled and cheap (unlike the pure-Python merge
    tree), so this is an acceptable extra pass to learn whether the centered
    window excluded the tile's dominant basin.
    """
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation

    plain = _materialize_plain(dem_path)
    try:
        _codes, accum = d8_pointer_and_accumulation(plain, workdir=workdir)
    finally:
        if plain.exists():
            plain.unlink()
    acc = np.where(np.isfinite(accum), accum, -np.inf)
    idx = int(np.argmax(acc))
    return divmod(idx, accum.shape[1])


# Whitebox cannot read Planetary Computer's 3DEP COGs directly (its GDAL
# build returns no output, silently, on the tiled/compressed structure).
# Re-writing to a plain single-band uncompressed GeoTIFF before any whitebox
# call is required; these overrides force that.
_PLAIN = {"driver": "GTiff", "compress": "none", "tiled": False, "count": 1}


def _write_plain(profile: dict, data, suffix: str) -> Path:
    import os

    import rasterio

    profile = {**profile, **_PLAIN}
    fd, tmp_name = tempfile.mkstemp(prefix="dem_", suffix=suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)
    with rasterio.open(tmp_path, "w", **profile) as dst:
        dst.write(data, 1)
    return tmp_path


def _materialize_plain(dem_path: Path) -> Path:
    """Full-tile plain-GeoTIFF copy so whitebox can read it (COG workaround)."""
    import rasterio

    with rasterio.open(dem_path) as src:
        profile = src.profile.copy()
        data = src.read(1)
    return _write_plain(profile, data, "_plain.tif")


def _crop_dem_to_window(dem_path: Path, window: int) -> Path | None:
    """Write a centered window x window crop of a DEM to a plain GeoTIFF.

    Returns the temp path, or None if the DEM is already <= window in both
    dimensions (no crop needed). The crop preserves CRS and writes a
    correct transform so downstream bbox/area are accurate for the window;
    it is written plain so whitebox can read it.
    """
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(dem_path) as src:
        H, W = src.height, src.width
        idx = _window_indices(H, W, window)
        if idx is None:
            return None
        i0, j0, h, w = idx
        win = Window(j0, i0, w, h)
        data = src.read(1, window=win)
        profile = src.profile.copy()
        profile.update(height=h, width=w, transform=src.window_transform(win))

    return _write_plain(profile, data, "_window.tif")


def _processed_fraction(full_dem: Path, run_path: Path) -> float:
    """Fraction of the full tile's cells the window actually processed."""
    import rasterio

    with rasterio.open(full_dem) as src:
        fH, fW = src.height, src.width
    with rasterio.open(run_path) as src:
        rH, rW = src.height, src.width
    if fH * fW == 0:
        return 1.0
    return float((rH * rW) / (fH * fW))


def _missed_dominant_basin(
    dem_path: Path, window: int, workdir: Path | None = None
) -> bool | None:
    """True if the full-tile dominant-A cell lies outside the centered window."""
    import rasterio

    with rasterio.open(dem_path) as src:
        H, W = src.height, src.width
    idx = _window_indices(H, W, window)
    if idx is None:
        return False
    i0, j0, h, w = idx
    cell = _full_tile_max_accum_cell(dem_path, workdir)
    if cell is None:
        return None
    r, c = cell
    return not (i0 <= r < i0 + h and j0 <= c < j0 + w)


def _cell_km(bbox, shape) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    H, W = shape
    mid_lat = np.radians((min_lat + max_lat) / 2)
    km_per_deg_lon = 111.32 * np.cos(mid_lat)
    cell_w = abs(max_lon - min_lon) / W * km_per_deg_lon
    cell_h = abs(max_lat - min_lat) / H * 110.57
    return float((cell_w + cell_h) / 2)


def _whitebox_branching_stats(
    dem_path, tau_channel, area, workdir
) -> tuple[BranchingStats, int]:
    """Whitebox's field-standard network summarized into BranchingStats.

    Vectorizes whitebox's stream raster and runs it through the SAME
    graph-builder used for NHD flowlines (stats_from_flowlines), so the
    whitebox and NHD sides count network elements identically (per-segment
    Strahler on a snapped graph). This is what makes the ceiling
    (whitebox-vs-NHD) and the construct comparison (PH-vs-NHD)
    methodologically consistent: both reference sides and the metric side
    count network nodes, never raster cells.

    Returns (stats, segment_count). segment_count is the raw whitebox
    vector feature count, a representation-granularity diagnostic reported
    alongside (not folded into) the agreement-with-NHD numbers.
    """
    import geopandas as gpd

    from geo_tda.topo_eval.construct_validity import stats_from_flowlines
    from geo_tda.topo_eval.hydrology import whitebox_stream_vector

    stream_vec = whitebox_stream_vector(
        dem_path, threshold=tau_channel, workdir=workdir
    )
    segment_count = int(len(gpd.read_file(stream_vec)))
    return stats_from_flowlines(stream_vec, area_km2=area), segment_count
