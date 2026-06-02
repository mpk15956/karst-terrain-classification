"""M2 power analysis: spatial-split real-vs-real null on free GLO-30 data.

The greenlight criterion for the MESA generation batch. Re-tiles the staged
GLO-30 tiles into 768x768 patches (MESA's native size), computes the H0
flow-accumulation diagram per patch at a COMMON target density, groups by tile,
and reports the spatial-split (by-tile) real-vs-real null band vs subpopulation
size. N for the generated population is set from where the band is tight enough
to resolve a difference; if it is wide even pooling all tiles, the experiment
is underpowered and that is learned here, before a GPU-hour. Doubles as a
dry-fire: real-vs-real MMD must come out small/sane, validating the machinery.

Compute (whitebox d8 per patch); offline-first on staged GLO-30.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from geo_tda.topo_eval.distributional import power_curve, spatial_split_null
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import (
    merge_tree_from_accumulation, persistence_diagram,
)
from geo_tda.topo_eval.pipeline import (
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

PATCH = 768


def _patch_h0(arr, profile, transform, target_density, wd):
    prof = {**profile, "driver": "GTiff", "compress": "none", "tiled": False,
            "count": 1, "height": arr.shape[0], "width": arr.shape[1],
            "transform": transform, "dtype": "float32"}
    tif = wd / "patch.tif"
    with rasterio.open(tif, "w", **prof) as d:
        d.write(arr.astype("float32"), 1)
    bbox = _tile_bbox_from_raster(tif)
    area = _tile_area_km2(bbox)
    codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
    cell_km = _cell_km(bbox, accum.shape)
    tau = tau_for_target_density(accum, target_density, area, cell_km)
    if not np.isfinite(tau):
        return None
    tree = merge_tree_from_accumulation(codes, accum, tau)
    return [(b, d if d is not None else np.inf) for (b, d) in persistence_diagram(tree)]


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 spatial-split power analysis")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_power.json"))
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text())["tiles"]
    target_density = float(np.median([t["nhd_drainage_density"] for t in tiles]))
    print(f"common target density = {target_density:.3f} km/km2")

    pop_by_tile = {}
    for t in tiles:
        f = args.glo30_dir / f"{t['key']}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as s:
            H, W = s.height, s.width
            full = s.read(1)
            profile = s.profile.copy()
            tf = s.transform
        diags = []
        for i in range(0, H - PATCH + 1, PATCH):
            for j in range(0, W - PATCH + 1, PATCH):
                wd = Path(tempfile.mkdtemp(prefix="patch_"))
                try:
                    win = Window(j, i, PATCH, PATCH)
                    dgm = _patch_h0(full[i:i + PATCH, j:j + PATCH], profile,
                                    rasterio.windows.transform(win, tf),
                                    target_density, wd)
                    if dgm:
                        diags.append(dgm)
                except Exception as exc:  # noqa: BLE001
                    print(f"  patch {t['key']} {i},{j} failed: {exc}")
                finally:
                    shutil.rmtree(wd, ignore_errors=True)
        pop_by_tile[t["key"]] = diags
        print(f"{t['key']}: {len(diags)} patches")

    rng = np.random.default_rng(0)
    n_tiles = len(pop_by_tile)
    sizes = [s for s in (2, 3, 4, 5, 6) if 2 * s <= n_tiles]
    curve = power_curve(pop_by_tile, sizes, reps=40, rng=rng)
    out = {"target_density": target_density,
           "n_tiles": n_tiles,
           "patches_per_tile": {k: len(v) for k, v in pop_by_tile.items()},
           "spatial_null_power_curve": curve,
           "note": "null split is by TILE (spatial), reps draw disjoint tile "
           "groups. N for generation = size where p95 is tight enough to "
           "resolve a difference; band is the floor the generated-vs-real MMD "
           "must clear. Dry-fire: these real-vs-real MMD2 values are the null."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print("\n=== spatial-split null band vs tiles-per-group ===")
    for r in curve:
        print(f"  {r['tiles_per_group']} tiles/group: median MMD2={r['null_mmd2_median']:.4g} "
              f"p95={r['null_mmd2_p95']:.4g} max={r['null_mmd2_max']:.4g} (reps {r['reps']})")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
