"""Substrate comparability probe: is MESA elevation the same KIND of object as a
real DEM, for the drainage-topology comparison?

The precondition the M2 MMD assumes but had not been checked: MESA emits a
normalized ~[0,1] elevation channel from an OPTICALLY-trained model, not a
meters DEM. Before reading a large generated-vs-real MMD^2 as drainage
pathology (the headline), we must rule out that it is a scale/degeneracy
artifact of pulling a DEM out of a model that does not really emit one. Two
checks, both on the patches/pipeline the full batch will use:

(A) INVARIANCE -- D8 routing depends only on elevation ORDER, so the H0
    flow-accumulation diagram should be invariant to monotonic rescaling. We
    verify empirically: run a patch at native scale and x1000, confirm the H0
    diagram and accumulation field are identical. This LICENSES ignoring the
    [0,1]-vs-meters gap and fixes the normalization decision before the batch
    (no rescale needed; the statistic is scale-free).

(B) NON-DEGENERACY / IN-FAMILY -- scale-free, routing-derived descriptors
    (smoothness, accumulation concentration, basin structure, H0 feature
    count/persistence, channel connectivity at density-matched tau) computed on
    a real-patch sample and on MESA patches. MESA must fall in the real range;
    if it is low-frequency "mush" it would route degenerately and masquerade as
    pathology. H0=0/connected (the earlier precondition) is necessary, not
    sufficient -- a connected, acyclic, degenerate field still passes that.

Runs in the project pixi env (whitebox/rasterio/topo_eval). MESA patches are
dimensionless; we adopt the real grid's physical scale for them (768px at
1/3600 deg ~ 30 m, matching GLO-30), so density-matched tau uses identical
physical assumptions on both sides -- the comparison is fair by construction.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window, transform as win_transform

from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import (
    merge_tree_from_accumulation, persistence_diagram,
)
from geo_tda.topo_eval.pipeline import (
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

PATCH = 768
CELL_DEG = 1.0 / 3600  # GLO-30 / MESA-adopted: 768px at 1/3600 deg ~ 30 m


def _gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float).ravel())
    n = x.size
    if n == 0 or x.sum() <= 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return float((2 * (idx * x).sum() - (n + 1) * x.sum()) / (n * x.sum()))


def _descriptors(dem: np.ndarray, tif: Path, target_density: float,
                 scale: float = 1.0) -> dict:
    """Scale-free routing descriptors for one DEM patch via the donor pipeline."""
    dem = dem.astype("float32") * float(scale)
    H, W = dem.shape
    transform = from_origin(-85.0, 36.0, CELL_DEG, CELL_DEG)
    prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="float32",
                crs="EPSG:4326", transform=transform, compress="none", tiled=False)
    with rasterio.open(tif, "w", **prof) as d:
        d.write(dem, 1)
    bbox = _tile_bbox_from_raster(tif)
    area = _tile_area_km2(bbox); cell_km = _cell_km(bbox, (H, W))
    codes, accum = d8_pointer_and_accumulation(tif, workdir=str(tif.parent))
    tau = tau_for_target_density(accum, target_density, area, cell_km)
    tree = merge_tree_from_accumulation(codes, accum, tau)
    dgm = persistence_diagram(tree)
    pers = np.array([(d - b) for (b, d) in dgm if d is not None and np.isfinite(d)])
    amax = float(accum.max()) or 1.0
    # smoothness (scale-free), accumulation concentration, basin structure,
    # H0 diagram size + persistence (normalized by max accum), connectivity.
    gy, gx = np.gradient(dem.astype(float))
    grad_rms = float(np.sqrt((gx ** 2 + gy ** 2).mean()))
    rng = float(dem.max() - dem.min()) or 1.0
    acc = accum.ravel().astype(float)
    acc_desc = np.sort(acc)[::-1]
    top1 = float(acc_desc[: max(1, acc.size // 100)].sum() / acc.sum()) if acc.sum() else float("nan")
    chan = int((accum >= tau).sum())
    return {
        "grad_rms_over_range": grad_rms / rng,
        "std_over_range": float(dem.std()) / rng,
        "accum_gini": _gini(acc),
        "accum_top1pct_frac": top1,
        "largest_basin_frac": amax / (H * W),
        "n_h0_features": int(len(dgm)),
        "n_roots": int(len(tree.roots)),
        "median_persistence_norm": float(np.median(pers) / amax) if pers.size else 0.0,
        "max_persistence_norm": float(pers.max() / amax) if pers.size else 0.0,
        "channel_cells": chan,
        "roots_over_channel": float(len(tree.roots)) / max(1, chan),
        "tau": float(tau),
    }


def _real_patch(spec):
    tile_path, i, j, target_density = spec
    wd = Path(tempfile.mkdtemp(prefix="cmp_real_"))
    try:
        with rasterio.open(tile_path) as s:
            arr = s.read(1, window=Window(j, i, PATCH, PATCH)).astype("float32")
        if arr.shape != (PATCH, PATCH):
            return None
        return _descriptors(arr, wd / "p.tif", target_density)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def _mesa_patch(spec):
    npy, target_density = spec
    wd = Path(tempfile.mkdtemp(prefix="cmp_mesa_"))
    try:
        arr = np.load(npy).astype("float32")
        d = _descriptors(arr, wd / "p.tif", target_density)
        d["file"] = Path(npy).name
        return d
    except Exception as exc:  # noqa: BLE001
        return {"file": Path(npy).name, "error": str(exc)}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def _summary(rows: list[dict], keys: list[str]) -> dict:
    out = {}
    for k in keys:
        v = np.array([r[k] for r in rows if k in r and np.isfinite(r.get(k, np.nan))])
        if v.size:
            out[k] = {"p5": float(np.percentile(v, 5)), "p50": float(np.median(v)),
                      "p95": float(np.percentile(v, 95)),
                      "min": float(v.min()), "max": float(v.max())}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MESA-vs-real substrate comparability")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--mesa-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results/validity/substrate_comparability.json"))
    ap.add_argument("--real-per-tile", type=int, default=2)
    ap.add_argument("--cpus", type=int, default=8)
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text())["tiles"]
    target_density = float(np.median([t["nhd_drainage_density"] for t in tiles]))
    print(f"target density = {target_density:.3f}; cpus={args.cpus}", flush=True)

    import whitebox
    whitebox.WhiteboxTools().set_max_procs(1)

    # real sample: first --real-per-tile patches from each staged tile
    real_specs = []
    for t in tiles:
        f = args.glo30_dir / f"{t['key']}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as s:
            Hh, Ww = s.height, s.width
        got = 0
        for i in range(0, Hh - PATCH + 1, PATCH):
            for j in range(0, Ww - PATCH + 1, PATCH):
                if got >= args.real_per_tile:
                    break
                real_specs.append((str(f), i, j, target_density)); got += 1
    mesa_files = sorted(str(p) for p in args.mesa_dir.glob("*.npy"))
    mesa_specs = [(f, target_density) for f in mesa_files]
    print(f"real sample={len(real_specs)} patches; mesa={len(mesa_specs)} patches", flush=True)

    with mp.Pool(args.cpus) as pool:
        real = [r for r in pool.map(_real_patch, real_specs) if r and "error" not in r]
        mesa = pool.map(_mesa_patch, mesa_specs)
    mesa_ok = [r for r in mesa if "error" not in r]
    print(f"real ok={len(real)}; mesa ok={len(mesa_ok)}; mesa err={len(mesa)-len(mesa_ok)}", flush=True)

    keys = ["grad_rms_over_range", "std_over_range", "accum_gini",
            "accum_top1pct_frac", "largest_basin_frac", "n_h0_features",
            "n_roots", "median_persistence_norm", "max_persistence_norm",
            "channel_cells", "roots_over_channel"]
    real_sum = _summary(real, keys); mesa_sum = _summary(mesa_ok, keys)

    # in-family verdict: MESA median within the real [p5, p95] band per descriptor
    verdict = {}
    for k in keys:
        if k in real_sum and k in mesa_sum:
            lo, hi = real_sum[k]["p5"], real_sum[k]["p95"]
            verdict[k] = {"real_p5_p95": [lo, hi], "mesa_p50": mesa_sum[k]["p50"],
                          "in_family": bool(lo <= mesa_sum[k]["p50"] <= hi)}

    # (A) invariance: one MESA + one real patch at native scale vs x1000
    inv = {}
    wd = Path(tempfile.mkdtemp(prefix="cmp_inv_"))
    try:
        if mesa_files:
            a = np.load(mesa_files[0]).astype("float32")
            d1 = _descriptors(a, wd / "m1.tif", target_density, scale=1.0)
            dk = _descriptors(a, wd / "mk.tif", target_density, scale=1000.0)
            inv["mesa"] = {"n_h0_x1": d1["n_h0_features"], "n_h0_x1000": dk["n_h0_features"],
                           "gini_x1": d1["accum_gini"], "gini_x1000": dk["accum_gini"],
                           "identical": d1["n_h0_features"] == dk["n_h0_features"]
                           and abs(d1["accum_gini"] - dk["accum_gini"]) < 1e-9}
        if real_specs:
            tp, ii, jj, _ = real_specs[0]
            with rasterio.open(tp) as s:
                ra = s.read(1, window=Window(jj, ii, PATCH, PATCH)).astype("float32")
            d1 = _descriptors(ra, wd / "r1.tif", target_density, scale=1.0)
            dk = _descriptors(ra, wd / "rk.tif", target_density, scale=1000.0)
            inv["real"] = {"n_h0_x1": d1["n_h0_features"], "n_h0_x1000": dk["n_h0_features"],
                           "identical": d1["n_h0_features"] == dk["n_h0_features"]
                           and abs(d1["accum_gini"] - dk["accum_gini"]) < 1e-9}
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    n_in = sum(v["in_family"] for v in verdict.values())
    out = {"target_density": target_density,
           "n_real": len(real), "n_mesa": len(mesa_ok),
           "real_summary": real_sum, "mesa_summary": mesa_sum,
           "in_family_verdict": verdict, "n_in_family": n_in, "n_descriptors": len(verdict),
           "scale_invariance": inv,
           "mesa_per_patch": mesa_ok,
           "note": "Invariance (A): if identical, H0 is scale-free and the "
           "[0,1]-vs-meters gap is irrelevant -> no rescale, stated before batch. "
           "In-family (B): MESA median must sit in real [p5,p95] per descriptor; "
           "grad_rms_over_range and accum concentration are the mush detectors. "
           "Read a large MMD2 as drainage divergence only if both pass."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))

    print("\n=== scale invariance (A) ===", flush=True)
    print(f"  {inv}", flush=True)
    print("\n=== in-family (B): MESA p50 vs real [p5,p95] ===", flush=True)
    for k, v in verdict.items():
        flag = "OK " if v["in_family"] else "OUT"
        print(f"  [{flag}] {k}: mesa={v['mesa_p50']:.4g} real=[{v['real_p5_p95'][0]:.4g},{v['real_p5_p95'][1]:.4g}]", flush=True)
    print(f"\nIN-FAMILY: {n_in}/{len(verdict)} descriptors; wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
