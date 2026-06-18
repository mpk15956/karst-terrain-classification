"""Persistence-pruning diagnostic (Stage 0).

Does the headline test/floor ratio survive dropping low-persistence H0 features?
Pure elis re-analysis of the cached diagrams (no whitebox, no extraction): prune
each cached diagram at a sweep of persistence thresholds epsilon (the finite-class
persistence percentiles {10,25,50,75,90} of the real corpus, pre-registered in
m2_saddle_stable_prereg.md), recompute the sliced-Wasserstein matrices, and rerun
the SAME null/test loops as the headline (seed 1, reps 200, K=10, fixed sw_sigma).

This is a DIAGNOSTIC that informs the Stage-1 ensemble amplitude prior, NOT a gate.
Low persistence is not synonymous with saddle-driven: a generator can genuinely
differ in fine-channel branching, which is low-persistence yet real. So ratio
SURVIVING pruning only rules out "all low-persistence dust"; ratio COLLAPSING only
raises skepticism and argues for a tighter perturbation amplitude. Essentials
(death = inf) are always kept (the surviving basins); only finite classes are
pruned. epsilon = 0 reuses the cached matrices and must reproduce the committed
3.12 (self-check).

Run from the repo root: .pixi/envs/cpu/bin/python scripts/m2_pruning_diagnostic.py
"""
from __future__ import annotations

import json
import multiprocessing as mp
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from geo_tda.topo_eval.distributional import mmd2_from_matrix, sliced_wasserstein  # noqa: E402

V = ROOT / "results" / "validity"
CACHE = V / "m2_diag_cache"
OUT = V / "m2_pruning_diagnostic.json"
K = 10
REPS = 200
PCTS = [10, 25, 50, 75, 90]
CPUS = max(1, (mp.cpu_count() or 2) - 0)  # elis is 2-core; match the box, no oversubscribe

_FLAT = None  # set per epsilon; forked workers inherit it (Linux)


def _prune(d, eps):
    a = np.asarray(d, float).reshape(-1, 2)
    if eps <= 0:
        return a
    fin = np.isfinite(a[:, 1])
    keep = (~fin) | ((a[:, 1] - a[:, 0]) >= eps)
    return a[keep]


def _row_chunk(rows):
    F = _FLAT; n = len(F); out = []
    for i in rows:
        for j in range(i + 1, n):
            out.append((i, j, sliced_wasserstein(F[i], F[j], M=50)))
    return out


def _sw_matrix_parallel(flat):
    global _FLAT
    _FLAT = flat
    n = len(flat)
    D = np.zeros((n, n))
    chunks = [list(range(r, n, CPUS)) for r in range(CPUS)]
    with mp.Pool(CPUS) as pool:
        for block in pool.map(_row_chunk, chunks):
            for i, j, d in block:
                D[i, j] = D[j, i] = d
    return D


def _ratio(D, tile_to_idx, gen_idx, sigma):
    rng = np.random.default_rng(1)
    tn = list(tile_to_idx)
    null = []
    for _ in range(REPS):
        p = rng.permutation(len(tn))
        ia = [i for k in p[:K] for i in tile_to_idx[tn[k]]]
        ib = [i for k in p[K:2 * K] for i in tile_to_idx[tn[k]]]
        if ia and ib:
            null.append(mmd2_from_matrix(D, ia, ib, sigma))
    test = []
    for _ in range(REPS):
        p = rng.permutation(len(tn))
        ib = [i for k in p[:K] for i in tile_to_idx[tn[k]]]
        if ib:
            test.append(mmd2_from_matrix(D, gen_idx, ib, sigma))
    null = np.array(null); test = np.array(test)
    floor = float(np.percentile(null, 95))
    tmed = float(np.median(test))
    return {"floor_p95": floor, "test_median": tmed,
            "ratio": tmed / floor, "frac_above_floor": float((test > floor).mean())}


def main() -> int:
    pop = pickle.loads((CACHE / "diagrams.pkl").read_bytes())
    real_flat, tile_to_idx = [], {}
    for key, dgms in pop.items():
        tile_to_idx[key] = []
        for d in dgms:
            tile_to_idx[key].append(len(real_flat)); real_flat.append(d)
    nr = len(real_flat)
    gen_named = pickle.loads((CACHE / "gen_diagrams.pkl").read_bytes())
    gen_flat = [d for (_n, d) in gen_named]
    ng = len(gen_flat)
    gen_idx = list(range(nr, nr + ng))
    sigma = float(json.loads((V / "m2_generated_vs_real.json").read_text())["sw_sigma"])

    # pre-registered epsilon grid = finite-class persistence percentiles
    fin = np.concatenate([(lambda x: x[np.isfinite(x[:, 1]), 1] - x[np.isfinite(x[:, 1]), 0])
                          (np.asarray(d, float)) for d in real_flat])
    eps_grid = [0.0] + [float(np.percentile(fin, q)) for q in PCTS]
    print(f"{nr} real + {ng} gen; sigma={sigma:.5g}; "
          f"epsilon grid (pct {[0] + PCTS}): {[round(e, 1) for e in eps_grid]}", flush=True)

    rows = []
    for eps, pct in zip(eps_grid, [0] + PCTS):
        if eps <= 0:
            Dreal = np.load(CACHE / "sw_matrix.npy")
            Dcross = np.load(CACHE / "sw_cross_realgen.npy")
            Dgen = np.load(CACHE / "sw_gen.npy")
            D = np.zeros((nr + ng, nr + ng))
            D[:nr, :nr] = Dreal; D[:nr, nr:] = Dcross
            D[nr:, :nr] = Dcross.T; D[nr:, nr:] = Dgen
            med_pts = float(np.median([len(d) for d in real_flat]))
        else:
            flat = [_prune(d, eps) for d in real_flat] + [_prune(d, eps) for d in gen_flat]
            med_pts = float(np.median([len(d) for d in flat[:nr]]))
            D = _sw_matrix_parallel(flat)
        r = _ratio(D, tile_to_idx, gen_idx, sigma)
        r.update({"epsilon": eps, "pct_pruned_threshold": pct,
                  "median_real_points_kept": med_pts})
        rows.append(r)
        print(f"  pct={pct:>2d} eps={eps:>9.1f} -> ratio {r['ratio']:.2f} "
              f"(floor {r['floor_p95']:.4f}, test {r['test_median']:.4f}, "
              f"med pts {med_pts:.0f})", flush=True)

    base = rows[0]["ratio"]
    out = {"K": K, "reps": REPS, "sigma": sigma, "baseline_ratio": base,
           "note": "Diagnostic, not a gate. epsilon=0 reuses cached matrices and "
                   "reproduces the committed headline ratio. Essentials kept; only "
                   "finite low-persistence classes pruned. Low-persistence is not "
                   "synonymous with saddle-driven.",
           "sweep": rows}
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nbaseline (eps=0) ratio = {base:.2f}; "
          f"survives-to-pct90 ratio = {rows[-1]['ratio']:.2f}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
