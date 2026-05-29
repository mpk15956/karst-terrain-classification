"""Whitebox wrappers for D8 hydrology on real DEMs.

Thin wrappers around WhiteboxTools for the steps the merge-tree
construction needs from a real DEM: breach/fill conditioning, D8 flow
pointer, D8 flow accumulation, and (for Phase C cross-checks) whitebox's
own stream extraction and Strahler order. The merge tree itself is built
by geo_tda.topo_eval.merge_tree from the pointer + accumulation arrays;
whitebox is only the upstream hydrology engine, not the topology.

Whitebox emits its D8 pointer as powers of two (1, 2, 4, ..., 128)
clockwise from East. merge_tree expects receiver codes 0..7 indexed
N, NE, E, SE, S, SW, W, NW per D8_OFFSETS. `pointer_to_receiver_codes`
translates between the two conventions.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.merge_tree import D8_OFFSETS

# Whitebox D8 pointer values (powers of two) -> (dy, dx) on a row-major
# grid where row index increases southward. Whitebox: 1=E, 2=SE, 4=S,
# 8=SW, 16=W, 32=NW, 64=N, 128=NE.
_WBT_POINTER_TO_OFFSET: dict[int, tuple[int, int]] = {
    1: (0, 1),    # E
    2: (1, 1),    # SE
    4: (1, 0),    # S
    8: (1, -1),   # SW
    16: (0, -1),  # W
    32: (-1, -1), # NW
    64: (-1, 0),  # N
    128: (-1, 1), # NE
}

# (dy, dx) -> receiver code index into D8_OFFSETS
_OFFSET_TO_CODE: dict[tuple[int, int], int] = {
    off: idx for idx, off in enumerate(D8_OFFSETS)
}


def pointer_to_receiver_codes(wbt_pointer: np.ndarray) -> np.ndarray:
    """Translate a whitebox D8 pointer grid to merge_tree receiver codes.

    Args:
        wbt_pointer: array of whitebox pointer values (powers of two; 0 at
            cells with no flow, e.g. outlets after conditioning).

    Returns:
        int8 array of receiver codes 0..7 per D8_OFFSETS, with -1 where the
        pointer is 0 (no receiver).
    """
    out = np.full(wbt_pointer.shape, -1, dtype=np.int8)
    for val, off in _WBT_POINTER_TO_OFFSET.items():
        out[wbt_pointer == val] = _OFFSET_TO_CODE[off]
    return out


def _read_single_band(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as src:
        return src.read(1)


def d8_pointer_and_accumulation(
    dem_path: str | Path,
    *,
    condition: str = "breach",
    workdir: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run whitebox conditioning + D8 pointer + D8 accumulation on a DEM.

    Args:
        dem_path: path to a single-band DEM GeoTIFF.
        condition: "breach" (breach_depressions_least_cost) or "fill"
            (fill_depressions). Breaching is the default per the proof's
            setup (less aggressive elevation modification).
        workdir: directory for whitebox intermediates; a temp dir if None.

    Returns:
        (receiver_codes, accumulation): receiver_codes is int8 0..7/-1 per
        D8_OFFSETS, ready for merge_tree_from_accumulation; accumulation is
        the D8 flow accumulation field (cell counts).
    """
    import whitebox

    dem_path = Path(dem_path).resolve()
    owns_tmp = workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="wbt_")) if owns_tmp else Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(workdir))
    wbt.verbose = False

    conditioned = workdir / "conditioned.tif"
    if condition == "breach":
        wbt.breach_depressions_least_cost(str(dem_path), str(conditioned), dist=100)
    elif condition == "fill":
        wbt.fill_depressions(str(dem_path), str(conditioned))
    else:
        raise ValueError(f"condition must be 'breach' or 'fill', got {condition!r}")

    pointer = workdir / "pointer.tif"
    accum = workdir / "accum.tif"
    wbt.d8_pointer(str(conditioned), str(pointer))
    wbt.d8_flow_accumulation(str(conditioned), str(accum), out_type="cells")

    pointer_arr = _read_single_band(pointer)
    accum_arr = _read_single_band(accum)
    receiver_codes = pointer_to_receiver_codes(pointer_arr)
    return receiver_codes, accum_arr


def whitebox_strahler(
    dem_path: str | Path,
    *,
    threshold: float,
    condition: str = "breach",
    workdir: str | Path | None = None,
) -> np.ndarray:
    """Whitebox's own Strahler stream order, for Phase C cross-checks.

    This is the field-standard extraction the construct-validity ceiling
    is calibrated against (whitebox-vs-NHD), NOT the PH construction.

    Args:
        dem_path: single-band DEM GeoTIFF.
        threshold: flow-accumulation threshold for stream extraction.
        condition: "breach" or "fill".
        workdir: whitebox intermediates dir; temp if None.

    Returns:
        Strahler order raster (0 off-stream, >=1 on stream).
    """
    import whitebox

    dem_path = Path(dem_path).resolve()
    owns_tmp = workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="wbt_")) if owns_tmp else Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(workdir))
    wbt.verbose = False

    conditioned = workdir / "conditioned.tif"
    if condition == "breach":
        wbt.breach_depressions_least_cost(str(dem_path), str(conditioned), dist=100)
    else:
        wbt.fill_depressions(str(dem_path), str(conditioned))

    pointer = workdir / "pointer.tif"
    accum = workdir / "accum.tif"
    streams = workdir / "streams.tif"
    strahler = workdir / "strahler.tif"
    wbt.d8_pointer(str(conditioned), str(pointer))
    wbt.d8_flow_accumulation(str(conditioned), str(accum), out_type="cells")
    wbt.extract_streams(str(accum), str(streams), threshold=threshold)
    wbt.strahler_stream_order(str(pointer), str(streams), str(strahler))
    return _read_single_band(strahler)
