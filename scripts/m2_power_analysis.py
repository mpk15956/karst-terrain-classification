"""M2 power analysis: spatial-split real-vs-real null on free GLO-30 data.

The greenlight criterion for the MESA generation batch (the free half before the
expensive half). Re-tiles staged GLO-30 into 768x768 patches, computes the H0
flow-accumulation diagram per patch at a COMMON target density (parallel across
cores, cached), computes the pairwise sliced-Wasserstein matrix ONCE (cached),
then reports the spatial-split (by-tile) real-vs-real null band vs subpopulation
size via index lookups into that matrix. N for generation = the size where the
band is tight enough to resolve a difference. Also the dry-fire: real-vs-real
MMD2 must sit near 0.

Compute; offline-first on staged GLO-30. Re-runnable: cached diagrams + SW
matrix let the power curve be retuned without recomputing the expensive parts.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, transform as win_transform

from geo_tda.topo_eval.distributional import (
    global_sigma, power_curve_indexed, sliced_wasserstein,
)
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import (
    merge_tree_from_accumulation, persistence_diagram,
)
from geo_tda.topo_eval.pipeline import (
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

PATCH = 768
TARGET_DENSITY = None  # set in main from the manifest median

_FLAT_DIAGS = None  # fork-shared diagram list for the parallel SW matrix


def _sw_block(rows):
    """SW distances for a set of upper-triangle rows of the global matrix.

    _FLAT_DIAGS is inherited by fork, so only the (i, j) indices cross the
    pool boundary, not the diagrams. Each row i contributes pairs (i, j>i).
    """
    out = []
    n = len(_FLAT_DIAGS)
    for i in rows:
        for j in range(i + 1, n):
            out.append((i, j, sliced_wasserstein(_FLAT_DIAGS[i], _FLAT_DIAGS[j])))
    return out


def _parallel_sw_matrix(flat, cpus):
    """Pairwise SW matrix over `flat`, computed across `cpus` fork workers."""
    global _FLAT_DIAGS
    _FLAT_DIAGS = flat
    n = len(flat)
    D = np.zeros((n, n), dtype=float)
    # interleave rows so each worker gets a mix of long (small i) and short
    # (large i) rows -> balanced load despite the triangular shape.
    row_chunks = [list(range(r, n, cpus)) for r in range(cpus)]
    with mp.Pool(cpus) as pool:
        for block in pool.map(_sw_block, row_chunks):
            for i, j, d in block:
                D[i, j] = D[j, i] = d
    return D


def _extract_one(spec):
    tile_path, i, j, key, target_density = spec
    wd = Path(tempfile.mkdtemp(prefix="patch_"))
    try:
        with rasterio.open(tile_path) as s:
            prof = s.profile.copy(); tf = s.transform
            win = Window(j, i, PATCH, PATCH)
            arr = s.read(1, window=win).astype("float32")
        prof.update(driver="GTiff", compress="none", tiled=False, count=1,
                    height=PATCH, width=PATCH, dtype="float32",
                    transform=win_transform(win, tf))
        tif = wd / "patch.tif"
        with rasterio.open(tif, "w", **prof) as d:
            d.write(arr, 1)
        bbox = _tile_bbox_from_raster(tif); area = _tile_area_km2(bbox)
        # whitebox max_procs is capped to 1 ONCE in the parent (see main); it
        # persists via the shared settings.json, so workers inherit it without
        # racing on that file. Without the cap, 24 workers each grab all cores
        # and the pool thrashes (job 28639 was stuck "extracting" >25 min).
        codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
        tau = tau_for_target_density(accum, target_density, area, _cell_km(bbox, accum.shape))
        if not np.isfinite(tau):
            return (key, None)
        tree = merge_tree_from_accumulation(codes, accum, tau)
        return (key, [(b, d if d is not None else np.inf)
                      for (b, d) in persistence_diagram(tree)])
    except Exception as exc:  # noqa: BLE001
        return (key, ("ERR", str(exc)))
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 spatial-split power analysis")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_power.json"))
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_diag_cache"))
    ap.add_argument("--cpus", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 8)))
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)

    tiles = json.loads(args.manifest.read_text())["tiles"]
    target_density = float(np.median([t["nhd_drainage_density"] for t in tiles]))
    print(f"common target density = {target_density:.3f} km/km2; cpus={args.cpus}")

    diag_pkl = args.cache / "diagrams.pkl"
    if diag_pkl.exists():
        pop_by_tile = pickle.loads(diag_pkl.read_bytes())
        print("loaded cached diagrams")
    else:
        specs = []
        for t in tiles:
            f = args.glo30_dir / f"{t['key']}.tif"
            if not f.exists():
                continue
            with rasterio.open(f) as s:
                H, W = s.height, s.width
            for i in range(0, H - PATCH + 1, PATCH):
                for j in range(0, W - PATCH + 1, PATCH):
                    specs.append((str(f), i, j, t["key"], target_density))
        print(f"extracting {len(specs)} patches across {args.cpus} cores...")
        # Cap whitebox to 1 core ONCE here (writes the shared settings.json the
        # forked workers read), so 24 concurrent workers don't each spawn an
        # all-cores whitebox and oversubscribe the node.
        import whitebox
        whitebox.WhiteboxTools().set_max_procs(1)
        with mp.Pool(args.cpus) as pool:
            results = pool.map(_extract_one, specs)
        pop_by_tile = {}
        errs = 0
        for key, dgm in results:
            if dgm is None or (isinstance(dgm, tuple) and dgm and dgm[0] == "ERR"):
                errs += 1
                continue
            pop_by_tile.setdefault(key, []).append(dgm)
        print(f"extracted; tiles={len(pop_by_tile)} errors={errs}")
        diag_pkl.write_bytes(pickle.dumps(pop_by_tile))

    # flatten to a global index list + tile->indices, compute SW matrix once
    flat = []; tile_to_idx = {}
    for key, diags in pop_by_tile.items():
        tile_to_idx[key] = []
        for d in diags:
            tile_to_idx[key].append(len(flat)); flat.append(d)
    print(f"{len(flat)} patches over {len(tile_to_idx)} tiles; "
          f"computing SW matrix on {args.cpus} cores...", flush=True)
    Dnpy = args.cache / "sw_matrix.npy"
    if Dnpy.exists() and np.load(Dnpy).shape == (len(flat), len(flat)):
        D = np.load(Dnpy)
        print("loaded cached SW matrix", flush=True)
    else:
        D = _parallel_sw_matrix(flat, args.cpus)
        np.save(Dnpy, D)
    sigma = global_sigma(D)
    print(f"SW matrix done; sigma={sigma:.4g}", flush=True)

    rng = np.random.default_rng(0)
    n_tiles = len(tile_to_idx)
    # sweep to the MAX balanced spatial split the corpus supports (2*s <= n_tiles),
    # not an arbitrary cap -- the tightest floor lives at the largest split.
    sizes = [s for s in range(2, n_tiles // 2 + 1) if 2 * s <= n_tiles]
    curve = power_curve_indexed(tile_to_idx, D, sizes, reps=120, rng=rng, sigma=sigma)

    # Operating point = the largest balanced split (tightest floor, most
    # patches/side). The generated-vs-real test MUST be run at this per-side
    # PATCH count so test-n == null-n by construction (MMD^2 bias/variance are
    # n-dependent). A MESA call emits exactly one 768px patch, so the generation
    # target is a patch count, drawn in the real reference's 7:7:6 province mix.
    op = curve[-1] if curve else None
    gen_patches = int(round(op["patches_per_side_mean"])) if op else None
    prov_counts = {}
    for t in tiles:
        prov_counts[t["province"]] = prov_counts.get(t["province"], 0) + 1
    total = sum(prov_counts.values())
    gen_alloc = ({p: int(round(gen_patches * c / total)) for p, c in prov_counts.items()}
                 if gen_patches else None)

    out = {"target_density": target_density, "n_tiles": n_tiles,
           "n_patches": len(flat), "sw_sigma": sigma,
           "patches_per_tile": {k: len(v) for k, v in tile_to_idx.items()},
           "spatial_null_power_curve": curve,
           "operating_point": op,
           "generation_target": {
               "patches_total": gen_patches,
               "by_province": gen_alloc,
               "province_mix_source": "real reference corpus (FORCED mirror, "
               "not a chosen N): generated mix = real mix so the two-sample MMD "
               "cannot read province-mix as topology",
               "patch_size_px": PATCH,
               "rationale": "test-n == null-n: generate this many 768px patches "
               "so the generated-vs-real MMD2 is computed at the same per-side "
               "patch count as the spatial null's operating point"},
           "note": "Null split is by TILE (spatial), reported in PATCHES (the "
           "MMD unit). The band (p95) is the floor generated-vs-real MMD2 must "
           "exceed AT THE SAME per-side patch n. Real-vs-real medians are the "
           "biased-estimator O(1/n) floor (test vs the empirical band, not vs "
           "0). N is set in patches, not tiles."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print("\n=== spatial-split null band vs tiles-per-group (n in PATCHES/side) ===")
    for r in curve:
        print(f"  {r['tiles_per_group']} tiles/grp (~{r['patches_per_side_mean']:.0f} "
              f"patches/side): median={r['null_mmd2_median']:.4g} "
              f"p95={r['null_mmd2_p95']:.4g} max={r['null_mmd2_max']:.4g} (reps {r['reps']})")
    if op:
        print(f"\nOPERATING POINT: {op['tiles_per_group']} tiles/side "
              f"(~{gen_patches} patches/side), floor p95={op['null_mmd2_p95']:.4g}")
        print(f"GENERATION TARGET: {gen_patches} patches in {gen_alloc} (province mix)")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
