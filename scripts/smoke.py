"""Smoke test: import every load-bearing dependency and run a tiny TDA +
raster operation. Expected runtime: a few seconds on a laptop core.

The point is to fail loudly when the environment is wrong, not to validate
scientific output.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np


def check_imports() -> None:
    import gudhi  # noqa: F401
    import persim  # noqa: F401
    import ripser  # noqa: F401
    import cripser  # noqa: F401
    import euchar  # noqa: F401
    import geopandas  # noqa: F401
    import rasterio  # noqa: F401
    import rioxarray  # noqa: F401
    import xarray  # noqa: F401
    import shapely  # noqa: F401
    import sklearn  # noqa: F401
    import scipy  # noqa: F401
    import matplotlib  # noqa: F401
    import torch  # noqa: F401


def cubical_persistence_roundtrip() -> int:
    from gudhi import CubicalComplex

    rng = np.random.default_rng(42)
    grid = rng.standard_normal((16, 16))
    cc = CubicalComplex(top_dimensional_cells=grid)
    diagram = cc.persistence()
    return len(diagram)


def raster_roundtrip() -> tuple[int, int]:
    import rasterio
    from rasterio.transform import from_origin

    arr = np.arange(64, dtype=np.float32).reshape(8, 8)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "smoke.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype=arr.dtype,
            crs="EPSG:4326",
            transform=from_origin(0, 0, 1, 1),
        ) as dst:
            dst.write(arr, 1)
        with rasterio.open(path) as src:
            band = src.read(1)
    return band.shape


def main() -> int:
    print(f"python: {sys.version.split()[0]}")
    check_imports()
    n_features = cubical_persistence_roundtrip()
    raster_shape = raster_roundtrip()
    print(f"cubical persistence features: {n_features}")
    print(f"raster roundtrip shape: {raster_shape}")
    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
