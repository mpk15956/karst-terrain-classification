"""M2 headline: generated-vs-real drainage-topology MMD vs the spatial null.

The actual contribution-1 measurement, run ONLY after its preconditions cleared
(saddle + resolution confounds characterized, power analysis powered, substrate
comparability passed). Tests H0: real and MESA-generated H0 flow-accumulation
diagram populations (at matched density) come from the same distribution. Reject
iff the generated-vs-real MMD^2 exceeds the spatial-split real-vs-real null band
(p95) AT THE SAME per-side patch n (the operating point).

Design (all pre-registered):
- Statistic: sliced-Wasserstein-kernel MMD^2, sigma FIXED to the null's value
  (m2_power.json sw_sigma) so the kernel and the 0.0263 floor are comparable.
- Combined SW matrix over [real | generated]: the real-real block is the cached
  sw_matrix.npy (same flat order as diagrams.pkl); the real-gen and gen-gen
  blocks are computed here (parallel). Then null and test are both index lookups.
- Null: real-half vs disjoint real-half, 10 tiles/side (~113 patches), by-tile
  spatial split -- reproduces the 0.0263 floor.
- Test: generated patches vs a real 10-tile half (n-matched to the null), over
  many real-half draws. Reject if the test MMD^2 clears the null p95.
- Extraction has RETRY (whitebox-under-pool failures are spurious transients;
  see substrate comparability) so the generated n is not lossy.

Read-out is licensed by substrate comparability: a clear-the-floor MMD^2 is
drainage divergence, not a scale/degeneracy artifact.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from geo_tda.topo_eval.distributional import mmd2_from_matrix, sliced_wasserstein
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import (
    merge_tree_from_accumulation, persistence_diagram,
)
from geo_tda.topo_eval.pipeline import (
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

PATCH = 768
CELL_DEG = 1.0 / 3600  # adopt the real grid's physical scale for MESA patches

_REAL_FLAT = None
_GEN_FLAT = None


def _extract_gen(spec):
    """H0 diagram for one generated patch, density-matched tau, with RETRY."""
    npy, target_density = spec
    arr = np.load(npy).astype("float32")
    H, W = arr.shape
    for attempt in range(3):  # spurious whitebox-under-pool failures are transient
        wd = Path(tempfile.mkdtemp(prefix="gen_"))
        try:
            tif = wd / "p.tif"
            prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="float32",
                        crs="EPSG:4326", transform=from_origin(-85.0, 36.0, CELL_DEG, CELL_DEG),
                        compress="none", tiled=False)
            with rasterio.open(tif, "w", **prof) as d:
                d.write(arr, 1)
            bbox = _tile_bbox_from_raster(tif); area = _tile_area_km2(bbox)
            codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
            tau = tau_for_target_density(accum, target_density, area, _cell_km(bbox, (H, W)))
            if not np.isfinite(tau):
                return (Path(npy).name, None)
            tree = merge_tree_from_accumulation(codes, accum, tau)
            dgm = [(b, d if d is not None else np.inf) for (b, d) in persistence_diagram(tree)]
            return (Path(npy).name, dgm)
        except Exception:  # noqa: BLE001
            if attempt == 2:
                return (Path(npy).name, ("ERR",))
        finally:
            shutil.rmtree(wd, ignore_errors=True)
    return (Path(npy).name, ("ERR",))


def _cross_block(rows):
    """SW distances real[i] vs every generated[j], for a set of real rows i."""
    out = []
    ng = len(_GEN_FLAT)
    for i in rows:
        for j in range(ng):
            out.append((i, j, sliced_wasserstein(_REAL_FLAT[i], _GEN_FLAT[j])))
    return out


def _gen_block(rows):
    """SW distances among generated patches (upper triangle), for rows i."""
    out = []
    ng = len(_GEN_FLAT)
    for i in rows:
        for j in range(i + 1, ng):
            out.append((i, j, sliced_wasserstein(_GEN_FLAT[i], _GEN_FLAT[j])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 generated-vs-real MMD test")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--mesa-dir", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_diag_cache"))
    ap.add_argument("--power", type=Path, default=Path("results/validity/m2_power.json"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_generated_vs_real.json"))
    ap.add_argument("--tiles-per-group", type=int, default=10)  # operating point
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--cpus", type=int, default=16)
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text())["tiles"]
    target_density = float(np.median([t["nhd_drainage_density"] for t in tiles]))
    power = json.loads(args.power.read_text())
    sigma = float(power["sw_sigma"])  # FIXED to the null's sigma
    print(f"target_density={target_density:.3f} sigma={sigma:.4g} cpus={args.cpus}", flush=True)

    # real diagrams + cached SW matrix, rebuilt in the SAME flat order
    pop_by_tile = pickle.loads((args.cache / "diagrams.pkl").read_bytes())
    real_flat = []; tile_to_idx = {}
    for key, diags in pop_by_tile.items():
        tile_to_idx[key] = []
        for d in diags:
            tile_to_idx[key].append(len(real_flat)); real_flat.append(d)
    Dreal = np.load(args.cache / "sw_matrix.npy")
    assert Dreal.shape == (len(real_flat), len(real_flat)), "real matrix / flat mismatch"
    nr = len(real_flat)
    print(f"real: {nr} patches over {len(tile_to_idx)} tiles", flush=True)

    import whitebox
    whitebox.WhiteboxTools().set_max_procs(1)

    # generated diagrams (with retry)
    gen_pkl = args.cache / "gen_diagrams.pkl"
    if gen_pkl.exists():
        gen_named = pickle.loads(gen_pkl.read_bytes())
        print("loaded cached generated diagrams", flush=True)
    else:
        files = sorted(str(p) for p in args.mesa_dir.glob("*.npy"))
        specs = [(f, target_density) for f in files]
        # SERIAL extraction: whitebox races on its shared install dir under a
        # pool (~half the patches spuriously fail "no output", and retrying
        # inside the still-concurrent pool hits the same race). Serial removes
        # the contention entirely -- the diagnostic showed failed patches all
        # succeed one-at-a-time. ~5s/patch, so ~10 min for 114; the SW blocks
        # below stay parallel (pure-Python SW, no whitebox, no race). Keeping
        # the generated n complete also preserves the n-match to the null and
        # the pre-registered province mix (a lossy extraction skews both).
        print(f"extracting {len(specs)} generated patches SERIALLY...", flush=True)
        res = []
        for k, s in enumerate(specs):
            res.append(_extract_gen(s))
            if (k + 1) % 20 == 0:
                print(f"  {k + 1}/{len(specs)} extracted", flush=True)
        gen_named = [(n, d) for (n, d) in res if d is not None and not (isinstance(d, tuple) and d and d[0] == "ERR")]
        errs = len(res) - len(gen_named)
        print(f"generated ok={len(gen_named)} err={errs}", flush=True)
        gen_pkl.write_bytes(pickle.dumps(gen_named))
    gen_flat = [d for (_n, d) in gen_named]
    ng = len(gen_flat)
    # province of each generated patch (filename prefix) for reporting
    gen_prov = [n.rsplit("_", 1)[0] for (n, _d) in gen_named]
    print(f"generated: {ng} patches", flush=True)

    # combined SW matrix [real | gen]; real-real cached, fill cross + gen-gen
    global _REAL_FLAT, _GEN_FLAT
    _REAL_FLAT = real_flat; _GEN_FLAT = gen_flat
    Dcross_npy = args.cache / "sw_cross_realgen.npy"
    Dgen_npy = args.cache / "sw_gen.npy"
    if Dcross_npy.exists() and np.load(Dcross_npy).shape == (nr, ng):
        Dcross = np.load(Dcross_npy); Dgen = np.load(Dgen_npy)
        print("loaded cached cross + gen SW blocks", flush=True)
    else:
        print(f"computing {nr}x{ng} cross + {ng}x{ng} gen SW on {args.cpus} cores...", flush=True)
        Dcross = np.zeros((nr, ng)); Dgen = np.zeros((ng, ng))
        real_chunks = [list(range(r, nr, args.cpus)) for r in range(args.cpus)]
        gen_chunks = [list(range(r, ng, args.cpus)) for r in range(args.cpus)]
        with mp.Pool(args.cpus) as pool:
            for block in pool.map(_cross_block, real_chunks):
                for i, j, d in block:
                    Dcross[i, j] = d
            for block in pool.map(_gen_block, gen_chunks):
                for i, j, d in block:
                    Dgen[i, j] = Dgen[j, i] = d
        np.save(Dcross_npy, Dcross); np.save(Dgen_npy, Dgen)

    N = nr + ng
    D = np.zeros((N, N))
    D[:nr, :nr] = Dreal
    D[:nr, nr:] = Dcross; D[nr:, :nr] = Dcross.T
    D[nr:, nr:] = Dgen
    gen_idx = list(range(nr, N))

    rng = np.random.default_rng(1)
    tnames = list(tile_to_idx)
    K = args.tiles_per_group

    # NULL: real-half vs disjoint real-half (reproduces the 0.0263 floor)
    null = []
    for _ in range(args.reps):
        p = rng.permutation(len(tnames))
        ia = [i for k in p[:K] for i in tile_to_idx[tnames[k]]]
        ib = [i for k in p[K:2 * K] for i in tile_to_idx[tnames[k]]]
        if ia and ib:
            null.append(mmd2_from_matrix(D, ia, ib, sigma))

    # TEST: generated vs a real K-tile half (n-matched), over draws
    test = []
    for _ in range(args.reps):
        p = rng.permutation(len(tnames))
        ib = [i for k in p[:K] for i in tile_to_idx[tnames[k]]]
        if ib:
            test.append(mmd2_from_matrix(D, gen_idx, ib, sigma))

    null = np.array(null); test = np.array(test)
    floor = float(np.percentile(null, 95))
    # one-sided p: P(null >= median test)
    pval = float((null >= np.median(test)).mean())
    frac_above = float((test > floor).mean())

    out = {"target_density": target_density, "sw_sigma": sigma,
           "n_real": nr, "n_generated": ng, "tiles_per_group": K, "reps": args.reps,
           "generated_by_province": {p: gen_prov.count(p) for p in set(gen_prov)},
           "null_mmd2": {"median": float(np.median(null)), "p95": floor,
                         "max": float(null.max())},
           "test_mmd2": {"median": float(np.median(test)), "p5": float(np.percentile(test, 5)),
                         "p95": float(np.percentile(test, 95)), "min": float(test.min()),
                         "max": float(test.max())},
           "null_p95_floor": floor,
           "test_median_over_floor_ratio": float(np.median(test) / floor) if floor else None,
           "frac_test_above_floor": frac_above,
           "p_value_one_sided": pval,
           "reject_H0": bool(np.median(test) > floor),
           "note": "Reject H0 (generated drainage topology diverges from real) iff "
           "test median MMD^2 > null p95 floor, at matched per-side patch n. "
           "Read-out licensed by substrate comparability (divergence, not artifact)."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))

    print("\n=== M2 HEADLINE: generated-vs-real drainage-topology MMD ===", flush=True)
    print(f"  null  MMD^2: median={np.median(null):.4g} p95(floor)={floor:.4g}", flush=True)
    print(f"  test  MMD^2: median={np.median(test):.4g} [p5={np.percentile(test,5):.4g}, p95={np.percentile(test,95):.4g}]", flush=True)
    print(f"  test/floor ratio={np.median(test)/floor:.2f}  frac_above_floor={frac_above:.3f}  p={pval:.4g}", flush=True)
    print(f"  REJECT H0: {out['reject_H0']} (generated drainage {'DIVERGES from' if out['reject_H0'] else 'matches'} real)", flush=True)
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
