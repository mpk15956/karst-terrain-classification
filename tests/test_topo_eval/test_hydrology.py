"""Real-DEM hydrology path: whitebox D8 + the pointer->receiver-code
translation + the merge-tree construction on a synthetic GeoTIFF.

Slower than the pure-Python toy tests (runs whitebox, writes a raster), so
marked slow. Validates the one Phase C code path with no other coverage:
hydrology.pointer_to_receiver_codes and d8_pointer_and_accumulation, plus
the full process_tile PH side."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.slow

whitebox = pytest.importorskip("whitebox")


def test_pointer_to_receiver_codes_translation():
    from geo_tda.topo_eval.hydrology import pointer_to_receiver_codes
    from geo_tda.topo_eval.merge_tree import D8_OFFSETS

    # WhiteboxTools pointer grid (64 128 1 / 32 0 2 / 16 8 4):
    # 1=NE 2=E 4=SE 8=S 16=SW 32=W 64=NW 128=N. Verified empirically
    # against the accumulation gradient on real whitebox output.
    wbt_to_offset = {
        1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0),
        16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0),
    }
    grid = np.array([[1, 2, 4, 8], [16, 32, 64, 128]])
    codes = pointer_to_receiver_codes(grid)
    for i in range(2):
        for j in range(4):
            off = wbt_to_offset[int(grid[i, j])]
            assert D8_OFFSETS[codes[i, j]] == off
    # 0 (no flow) maps to -1
    assert pointer_to_receiver_codes(np.array([[0]]))[0, 0] == -1


@pytest.fixture
def synthetic_valley_dem():
    import rasterio
    from rasterio.transform import from_origin

    H = W = 64
    yy, xx = np.mgrid[0:H, 0:W]
    elev = (np.abs(xx - 32) * 1.0 + (H - yy) * 0.5).astype("float32")
    tmp = Path(tempfile.mkdtemp(prefix="hydro_test_"))
    dem_path = tmp / "valley.tif"
    transform = from_origin(-85.0, 36.0, 1.0 / W, 1.0 / H)
    with rasterio.open(
        dem_path, "w", driver="GTiff", height=H, width=W, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(elev, 1)
    return dem_path


def test_d8_pointer_and_accumulation_sane(synthetic_valley_dem):
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation

    codes, accum = d8_pointer_and_accumulation(
        synthetic_valley_dem, condition="breach"
    )
    assert codes.dtype == np.int8
    assert codes.min() >= -1 and codes.max() <= 7
    # a single draining valley accumulates a large fraction of cells
    assert accum.max() > 0.4 * accum.size
    # almost every cell routes somewhere (only outlets/edges do not)
    assert (codes >= 0).sum() > 0.95 * codes.size


def test_process_tile_real_path_produces_connected_tree(synthetic_valley_dem):
    from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
    from geo_tda.topo_eval.pipeline import process_tile

    res = process_tile(
        synthetic_valley_dem, key="valley", tau_channel=20,
        include_ph=True, include_whitebox=False,
    )
    assert res.error is None
    assert res.ph is not None

    # Connectivity is THE regression guard for the whitebox-pointer ->
    # receiver-code translation. This surface drains to a single outlet, so
    # the donor merge tree must be ONE connected basin (one root). The
    # original pointer table was the ESRI convention rotated one step off
    # WhiteboxTools', which mis-routed every cell 45 degrees and shattered
    # the donor graph into one component per cell (thousands of roots) while
    # every toy test passed, because the toys hand-build receiver codes and
    # never exercise this translation. Assert it directly on real whitebox
    # output so the seam can never silently break again.
    codes, accum = d8_pointer_and_accumulation(synthetic_valley_dem)
    tree = merge_tree_from_accumulation(codes, accum, tau_channel=20)
    assert len(tree.roots) == 1, (
        f"single-outlet valley must be one connected basin, got "
        f"{len(tree.roots)} roots (rotated/!connected donor graph?)"
    )
    # structural sanity (robust, not calibrated to a specific count):
    dist = res.ph.strahler_distribution
    assert min(dist) == 1 and set(dist) == set(range(1, max(dist) + 1)), \
        f"Strahler orders must be contiguous from 1, got {dist}"
    assert max(dist) >= 2, f"a branching network needs order >= 2, got {dist}"
    assert dist[1] == max(dist.values()), \
        f"order-1 should be the most numerous, got {dist}"
    assert res.ph.junction_count >= 1
    # donor graph is a forest, so cubical H1 (>0 here) is exactly the
    # spatial-adjacency contamination the donor construction removes
    assert res.h1_cubical is not None and res.h1_cubical > 0
