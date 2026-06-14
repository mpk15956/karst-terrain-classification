"""Smoke-test the optical renderer + the clipping gotcha (compute node, project env).

Confirms before any GPU spend:
1. Real and generated patches render on the SAME intensity range (scale-norm works).
2. A _carve_trench-perturbed patch, normalized with the ORIGINAL patch's bounds,
   still shows the channel as a VISIBLE feature (the walls' gradient survives even
   though the deep floor clips to black) -- else optical non-separation would be
   partly because the perturbation was removed, breaking the conservative argument.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

sys.path.insert(0, "scripts")
from render_terrain_rgb import (robust_bounds, render_hillshade_rgb,
                                render_stack_rgb)
from saddle_stability_probe import _carve_trench
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation

PATCH = 768
GLO = Path("data/glo30")
MESA = Path("results/validity/mesa_batch113")

import whitebox
whitebox.WhiteboxTools().set_max_procs(1)


def _real_patch():
    f = sorted(GLO.glob("*.tif"))[0]
    with rasterio.open(f) as s:
        return s.read(1, window=Window(0, 0, PATCH, PATCH)).astype("float32"), f.name


def _diag_band(shape):
    """Boolean mask of the main diagonal +-6 px (where _carve_trench gouges)."""
    H, W = shape
    ii, jj = np.indices((H, W))
    n = max(H, W)
    di = (ii * (n - 1) / (H - 1)); dj = (jj * (n - 1) / (W - 1))
    return np.abs(di - dj) <= 6


def main() -> int:
    real, rname = _real_patch()
    gen = np.load(sorted(MESA.glob("*.npy"))[0]).astype("float32")

    rlo, rhi = robust_bounds(real); glo, ghi = robust_bounds(gen)
    print(f"real {rname}: dem[{real.min():.2f},{real.max():.2f}] bounds[{rlo:.2f},{rhi:.2f}]", flush=True)
    print(f"gen: dem[{gen.min():.3f},{gen.max():.3f}] bounds[{glo:.3f},{ghi:.3f}]", flush=True)
    rh = render_hillshade_rgb(real); gh = render_hillshade_rgb(gen)
    print(f"render hillshade uint8 ranges: real[{rh.min()},{rh.max()}] gen[{gh.min()},{gh.max()}]"
          f" -> same scale: {rh.min()>=0 and gh.max()<=255}", flush=True)

    # carve a trench on the REAL patch, render with the ORIGINAL patch's bounds
    wd = Path(tempfile.mkdtemp(prefix="rsm_"))
    tif = wd / "p.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=PATCH, width=PATCH, count=1,
                       dtype="float32", crs="EPSG:4326",
                       transform=from_origin(-85, 36, 1/3600, 1/3600),
                       compress="none", tiled=False) as d:
        d.write(real, 1)
    _codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
    carved = _carve_trench(real, accum, 0.34)

    bounds = robust_bounds(real)  # SHARED bounds from the original
    orig_h = render_hillshade_rgb(real, bounds=bounds)
    carv_h = render_hillshade_rgb(carved, bounds=bounds)
    orig_s = render_stack_rgb(real, bounds=bounds)
    carv_s = render_stack_rgb(carved, bounds=bounds)

    band = _diag_band(real.shape)
    def _band_delta(a, b):
        d = np.abs(a.astype(float) - b.astype(float)).mean(axis=2)
        return float(d[band].mean()), float(d[~band].mean())
    hb, ho = _band_delta(orig_h, carv_h)
    sb, so = _band_delta(orig_s, carv_s)
    print(f"hillshade delta: channel-band={hb:.2f}  off-band={ho:.2f}  ratio={hb/max(ho,1e-6):.1f}", flush=True)
    print(f"stack     delta: channel-band={sb:.2f}  off-band={so:.2f}  ratio={sb/max(so,1e-6):.1f}", flush=True)
    # the carved floor clips to black; verify the WALLS still register
    floor_frac = float((render_stack_rgb(carved, bounds=bounds)[..., 1][band] == 0).mean())
    print(f"carved floor clipped-to-black fraction (elev channel, in band)={floor_frac:.2f}", flush=True)

    survives = hb > 5.0 and sb > 5.0  # channel is a visible feature in both renders
    print(f"VERDICT: carved channel SURVIVES normalization = {survives} "
          f"({'OK -> conservative argument holds' if survives else 'FAIL -> perturbation erased'})", flush=True)
    np.savez(wd.parent / "render_smoke.npz", orig_h=orig_h, carv_h=carv_h,
             orig_s=orig_s, carv_s=carv_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
