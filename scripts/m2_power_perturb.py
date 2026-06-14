"""Power probe stage 1: perturb real patches with graded drainage reroutes
(project pixi env; whitebox -> SERIAL). The adjudicating experiment.

For a province-balanced PERTURBATION group of real tiles, carve RANDOMIZED
megachannel reroutes at increasing effect size f (mass-moved-fraction), and for
each perturbed patch compute its H0 flow-accumulation diagram (common-density
tau, the M2 substrate) AND render it to RGB with the ORIGINAL patch's
normalization bounds (so optical sees the true visual delta, not a renorm
artifact). The randomized geometry (placement/orientation/length/depth/width)
keeps the perturbation DISTRIBUTIONAL, not a systematic scar that hands optical a
trivial signal.

Outputs (-> results/validity/m2_power_probe/): perturbed H0 diagrams + measured f
(pkl), perturbed rendered images (npy, for stage-2 embedding), and the
unperturbed P-group H0 diagrams + renders (the f=0 reference). Stage 2 embeds the
renders; stage 3 builds the MMD^2/floor curves for H0 and optical.
"""
from __future__ import annotations

import argparse
import json
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window, transform as win_transform

import sys
sys.path.insert(0, "scripts")
from render_terrain_rgb import robust_bounds, render_hillshade_rgb, render_stack_rgb
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation, persistence_diagram
from geo_tda.topo_eval.pipeline import (
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

PATCH = 768
CELL_DEG = 1.0 / 3600


def _random_trench(arr, rng, lenfrac, depth_mult, width):
    """Randomly placed/oriented descending megachannel. depth_mult scales the
    gouge depth (small -> shallow -> small f, for fine low-f resolution); width
    gives it a fair optical footprint (a 1px line is sub-pixel after resize)."""
    out = arr.astype(float).copy()
    H, W = out.shape
    lo = float(out.min())
    n = max(H, W)
    span = max(2, int(lenfrac * n))
    # random start + direction (8-connected diagonal-ish)
    si, sj = int(rng.integers(0, H)), int(rng.integers(0, W))
    di, dj = rng.choice([-1, 1]), rng.choice([-1, 1])
    half = width // 2
    for t in range(span):
        i = si + int(round(t * di * (H - 1) / (n - 1)))
        j = sj + int(round(t * dj * (W - 1) / (n - 1)))
        if not (0 <= i < H and 0 <= j < W):
            break
        floor = lo - depth_mult * (50.0 + 50.0 * (t / n))
        for wi in range(-half, half + 1):
            for wj in range(-half, half + 1):
                ii, jj = i + wi, j + wj
                if 0 <= ii < H and 0 <= jj < W:
                    out[ii, jj] = min(out[ii, jj], floor + 0.5 * (abs(wi) + abs(wj)))
    return out


def _h0(arr, wd, target_density):
    tif = wd / "p.tif"
    prof = dict(driver="GTiff", height=PATCH, width=PATCH, count=1, dtype="float32",
                crs="EPSG:4326", transform=from_origin(-85, 36, CELL_DEG, CELL_DEG),
                compress="none", tiled=False)
    with rasterio.open(tif, "w", **prof) as d:
        d.write(arr.astype("float32"), 1)
    bbox = _tile_bbox_from_raster(tif); area = _tile_area_km2(bbox)
    codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
    tau = tau_for_target_density(accum, target_density, area, _cell_km(bbox, (PATCH, PATCH)))
    tree = merge_tree_from_accumulation(codes, accum, tau)
    dgm = [(b, d if d is not None else np.inf) for (b, d) in persistence_diagram(tree)]
    return dgm, accum


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_power_probe"))
    ap.add_argument("--tiles-per-province", type=int, default=2)
    ap.add_argument("--max-per-tile", type=int, default=5,
                    help="cap windows/tile: perturbed-trench breach is slow; ~30 "
                    "base patches is enough for a clean calibration (advisor).")
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tiles = json.loads(args.manifest.read_text())["tiles"]
    target_density = float(np.median([t["nhd_drainage_density"] for t in tiles]))
    rng = np.random.default_rng(args.seed)

    # province-balanced perturbation group (first N tiles per province)
    by_prov = {}
    for t in tiles:
        by_prov.setdefault(t["province"], []).append(t)
    P = []
    for prov, ts in by_prov.items():
        P.extend(ts[:args.tiles_per_province])
    print(f"perturbation group: {len(P)} tiles "
          f"{ {p: sum(1 for t in P if t['province']==p) for p in by_prov} }", flush=True)

    import whitebox
    whitebox.WhiteboxTools().set_max_procs(1)

    # graded levels: (lenfrac, depth_mult) sweeping fine low-f -> gross
    LEVELS = [(0.04, 0.2), (0.08, 0.4), (0.15, 0.7), (0.30, 1.0),
              (0.55, 1.0), (1.0, 1.0)]
    WIDTH = 9  # realistic channel width (fair optical footprint, not sub-pixel)

    records = []  # one per (tile, window, level)
    base = []     # f=0 reference: unperturbed P-group patches
    n_done = 0
    for t in P:
        f = args.glo30_dir / f"{t['key']}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as s:
            Hh, Ww = s.height, s.width
        got = 0
        for i in range(0, Hh - PATCH + 1, PATCH):
            for j in range(0, Ww - PATCH + 1, PATCH):
                if got >= args.max_per_tile:
                    break
                with rasterio.open(f) as s:
                    arr = s.read(1, window=Window(j, i, PATCH, PATCH)).astype("float32")
                if arr.shape != (PATCH, PATCH):
                    continue
                got += 1
                bounds = robust_bounds(arr)  # ORIGINAL bounds, shared with perturbed
                wd = Path(tempfile.mkdtemp(prefix="pb0_"))
                try:
                    dgm0, accum0 = _h0(arr, wd, target_density)
                finally:
                    shutil.rmtree(wd, ignore_errors=True)
                pid = f"{t['key']}_{i}_{j}"
                base.append({"pid": pid, "province": t["province"], "dgm": dgm0,
                             "hill": render_hillshade_rgb(arr, bounds=bounds),
                             "stack": render_stack_rgb(arr, bounds=bounds)})
                denom = float(accum0.sum())
                for li, (lenfrac, dmult) in enumerate(LEVELS):
                    pert = _random_trench(arr, rng, lenfrac, dmult, WIDTH)
                    wd = Path(tempfile.mkdtemp(prefix="pbp_"))
                    try:
                        dgm, accum = _h0(pert, wd, target_density)
                    except Exception:  # noqa: BLE001
                        shutil.rmtree(wd, ignore_errors=True); continue
                    shutil.rmtree(wd, ignore_errors=True)
                    fmoved = float(np.abs(accum.astype(float) - accum0.astype(float)).sum()
                                   / (2 * denom)) if denom > 0 else float("nan")
                    records.append({"pid": pid, "province": t["province"], "level": li,
                                    "lenfrac": lenfrac, "depth_mult": dmult, "f": fmoved,
                                    "dgm": dgm,
                                    "hill": render_hillshade_rgb(pert, bounds=bounds),
                                    "stack": render_stack_rgb(pert, bounds=bounds)})
                n_done += 1
                if n_done % 10 == 0:
                    print(f"  {n_done} base patches done; {len(records)} perturbations", flush=True)

    # save diagrams + f (pkl) and renders (npy stacks) separately
    diag = {"target_density": target_density, "width": WIDTH, "levels": LEVELS,
            "base": [{k: r[k] for k in ("pid", "province", "dgm")} for r in base],
            "pert": [{k: r[k] for k in ("pid", "province", "level", "lenfrac", "depth_mult", "f", "dgm")}
                     for r in records]}
    (args.out / "diagrams.pkl").write_bytes(pickle.dumps(diag))
    np.save(args.out / "base_hill.npy", np.stack([r["hill"] for r in base]))
    np.save(args.out / "base_stack.npy", np.stack([r["stack"] for r in base]))
    np.save(args.out / "pert_hill.npy", np.stack([r["hill"] for r in records]))
    np.save(args.out / "pert_stack.npy", np.stack([r["stack"] for r in records]))
    print(f"base={len(base)} pert={len(records)}; f range "
          f"[{min(r['f'] for r in records):.4f},{max(r['f'] for r in records):.4f}]", flush=True)
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
