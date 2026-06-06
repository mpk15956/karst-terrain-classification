"""Throwaway: why do some MESA patches fail the donor pipeline in the
comparability probe? Run the failed patches with whitebox verbose ON and a
fresh per-patch workdir, print the real error + DEM stats. Distinguishes a
benign transient/edge issue from a structural degeneracy.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation

FAILED = [
    "appalachian_highlands_002.npy", "appalachian_highlands_004.npy",
    "coastal_plain_000.npy", "coastal_plain_002.npy",
    "cumberland_plateau_003.npy", "cumberland_plateau_004.npy",
]
MDIR = Path("results/validity/mesa_small")

import whitebox
whitebox.WhiteboxTools().set_max_procs(1)

for fn in FAILED:
    arr = np.load(MDIR / fn).astype("float32")
    wd = Path(tempfile.mkdtemp(prefix="diag_"))
    tif = wd / "p.tif"
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                dtype="float32", crs="EPSG:4326",
                transform=from_origin(-85.0, 36.0, 1 / 3600, 1 / 3600),
                compress="none", tiled=False)
    with rasterio.open(tif, "w", **prof) as d:
        d.write(arr, 1)
    nan = int(np.isnan(arr).sum())
    uniq = int(np.unique(arr).size)
    msg = "OK"
    try:
        codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
        msg = f"OK accum_max={float(accum.max()):.0f}"
    except Exception as exc:  # noqa: BLE001
        msg = f"FAIL: {type(exc).__name__}: {exc}"
    # retry once (transient?)
    retry = ""
    if msg.startswith("FAIL"):
        wd2 = Path(tempfile.mkdtemp(prefix="diag2_"))
        try:
            d8_pointer_and_accumulation(tif, workdir=str(wd2))
            retry = " | RETRY: OK (transient)"
        except Exception as exc:  # noqa: BLE001
            retry = f" | RETRY: still {type(exc).__name__}"
    print(f"{fn}: range[{arr.min():.3f},{arr.max():.3f}] std{arr.std():.3f} "
          f"nan={nan} uniq={uniq} -> {msg}{retry}", flush=True)
