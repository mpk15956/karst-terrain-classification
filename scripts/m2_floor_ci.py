"""Uncertainty on the spatial-null p95 floor (Stage 0).

The headline ratio 3.12 = test-median 0.0885 / null p95 floor 0.0283, and the
one-sided p < 0.005 is really 0/200 splits, i.e. resolution-limited by the split
count rather than a measured tail. This quantifies the floor's precision two ways,
on the CACHED real-real SW matrix only (no extraction):

1. TILE-LEVEL precision (the "precision cost" of ~10 independent units per side):
   leave-one-tile-out jackknife. With 19 tiles the max balanced split is K=9, so the
   reference is also computed at K=9; the spread across folds isolates how much the
   floor depends on WHICH tiles were sampled, at fixed K. (K=9 vs the K=10 operating
   point differs by the power curve, so this is a tile-set-sensitivity probe, not a
   K=10 interval.)
2. SPLIT-COUNT resolution: the p95 at reps in {200, 1000, 5000} plus a percentile
   bootstrap band over the 5000 null values, showing the estimate is stable well
   beyond 200 splits (so p<0.005 reflects the split budget, not floor noise). The
   splits share tiles and are dependent, so the band is approximate (mildly
   optimistic) and is reported as such.

Run from the repo root: .pixi/envs/cpu/bin/python scripts/m2_floor_ci.py
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from geo_tda.topo_eval.distributional import (  # noqa: E402
    global_sigma, mmd2_from_matrix, spatial_split_null_indexed,
)

V = ROOT / "results" / "validity"
CACHE = V / "m2_diag_cache"
OUT = V / "m2_floor_ci.json"
K_OP = 10                # operating point (the headline floor)
TEST_MEDIAN = 0.08851961546923048   # m2_generated_vs_real.json test_mmd2.median


def _floor_p95(tile_to_idx, D, k, reps, rng, sigma):
    recs = spatial_split_null_indexed(tile_to_idx, D, k, reps, rng, sigma)
    return np.array([r["mmd2"] for r in recs], float)


def main() -> int:
    pop = pickle.loads((CACHE / "diagrams.pkl").read_bytes())
    flat, tile_to_idx = [], {}
    for key, dgms in pop.items():
        tile_to_idx[key] = []
        for d in dgms:
            tile_to_idx[key].append(len(flat)); flat.append(d)
    D = np.load(CACHE / "sw_matrix.npy")
    sigma = float(json.loads((V / "m2_generated_vs_real.json").read_text())["sw_sigma"])
    assert abs(sigma - global_sigma(D)) / sigma < 1e-9, "sigma mismatch vs cached matrix"
    tiles = list(tile_to_idx)
    print(f"{len(flat)} patches / {len(tiles)} tiles; sigma={sigma:.6g}")

    out = {"sigma": sigma, "test_median": TEST_MEDIAN, "K_operating": K_OP}

    # --- self-check: reproduce the realized floor at K=10, reps=200 ---
    m200 = _floor_p95(tile_to_idx, D, K_OP, 200, np.random.default_rng(1), sigma)
    p95_200 = float(np.percentile(m200, 95))
    out["selfcheck_K10_reps200_p95"] = p95_200
    print(f"self-check floor K=10 reps=200 p95 = {p95_200:.5f} (committed 0.02834)")

    # --- split-count resolution ---
    res = {}
    for reps in (200, 1000, 5000):
        m = _floor_p95(tile_to_idx, D, K_OP, reps, np.random.default_rng(7), sigma)
        res[str(reps)] = float(np.percentile(m, 95))
    out["p95_by_reps"] = res
    # bootstrap band over the 5000 null values (dependent splits -> approximate)
    m5000 = _floor_p95(tile_to_idx, D, K_OP, 5000, np.random.default_rng(11), sigma)
    brng = np.random.default_rng(13)
    boot = [np.percentile(brng.choice(m5000, size=m5000.size, replace=True), 95)
            for _ in range(2000)]
    p95_hat = float(np.percentile(m5000, 95))
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    out["split_resolution"] = {
        "p95_5000": p95_hat, "p95_ci95_approx": ci,
        "ratio_at_p95": TEST_MEDIAN / p95_hat,
        "ratio_ci95_approx": [TEST_MEDIAN / ci[1], TEST_MEDIAN / ci[0]],
        "note": "splits share tiles (dependent), so the band is approximate/mildly optimistic",
    }
    print(f"split-count: p95 = {res['200']:.5f}/{res['1000']:.5f}/{res['5000']:.5f} "
          f"(reps 200/1000/5000); 5000 CI~[{ci[0]:.5f},{ci[1]:.5f}]; "
          f"ratio {TEST_MEDIAN/p95_hat:.2f} CI~[{TEST_MEDIAN/ci[1]:.2f},{TEST_MEDIAN/ci[0]:.2f}]")

    # --- tile-level precision: leave-one-tile-out jackknife at K=9 ---
    k_jk = (len(tiles) - 1) // 2  # 9
    ref = _floor_p95(tile_to_idx, D, k_jk, 5000, np.random.default_rng(5), sigma)
    ref_p95 = float(np.percentile(ref, 95))
    jk = []
    for t in tiles:
        sub = {k: v for k, v in tile_to_idx.items() if k != t}
        m = _floor_p95(sub, D, k_jk, 5000, np.random.default_rng(5), sigma)
        jk.append(float(np.percentile(m, 95)))
    jk = np.array(jk)
    out["tile_jackknife_K9"] = {
        "k": k_jk,
        "ref_p95_all20": ref_p95,
        "leave_one_out_p95_min": float(jk.min()),
        "leave_one_out_p95_max": float(jk.max()),
        "leave_one_out_p95_mean": float(jk.mean()),
        "leave_one_out_p95_std": float(jk.std(ddof=1)),
        "note": "K=9 (19-tile max balanced split); isolates tile-set sensitivity at "
                "fixed K. The K=10 operating floor differs per the power curve.",
    }
    print(f"tile jackknife K=9: ref(all20)={ref_p95:.5f}; "
          f"leave-one-out p95 in [{jk.min():.5f},{jk.max():.5f}] "
          f"mean {jk.mean():.5f} sd {jk.std(ddof=1):.5f}")

    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
