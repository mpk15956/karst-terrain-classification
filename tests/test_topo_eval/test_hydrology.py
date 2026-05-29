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

    # whitebox powers-of-two -> (dy, dx) -> receiver-code index
    wbt_to_offset = {
        1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1),
        16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1),
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


def test_process_tile_real_path_produces_sane_tree(synthetic_valley_dem):
    from geo_tda.topo_eval.pipeline import process_tile

    res = process_tile(
        synthetic_valley_dem, key="valley", tau_channel=20,
        include_ph=True, include_whitebox=False,
    )
    assert res.error is None
    assert res.ph is not None
    # This synthetic surface is a single central channel fed by parallel
    # hillslope flow (a "feather"), so the analytical answer is many
    # order-1 tributaries on one order-2 trunk: dist == {1: many, 2: 1}.
    # The point of this test is that the real whitebox -> pointer ->
    # merge-tree path runs and yields that structurally-correct feather,
    # not a dendritic network (which this geometry does not contain).
    dist = res.ph.strahler_distribution
    assert set(dist) == {1, 2}, f"feather geometry -> orders {{1,2}}, got {dist}"
    assert dist[2] == 1, f"single trunk -> one order-2 stream, got {dist}"
    assert dist[1] > 10, f"many order-1 tributaries expected, got {dist}"
    assert res.ph.junction_count >= 1
    # the donor graph is a forest, so cubical H1 (>0 here) is exactly the
    # spatial-adjacency contamination the donor construction removes
    assert res.h1_cubical is not None and res.h1_cubical > 0
