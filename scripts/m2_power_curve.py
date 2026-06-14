"""Power probe stage 3: the shared-axis MMD^2/floor curves (project env).

The adjudicating figure. For H0 and each optical metric, plot MMD^2/floor vs the
drainage effect size f. Construction makes the perturbation the ONLY difference
between floor and test, so n is consistent by design:
  floor(metric) = MMD^2(A_base, B_base) over random splits of the base patches.
  test(metric, level) = MMD^2(A_perturbed@level, B_base) over the same splits.
H0 uses sliced-Wasserstein distances at the HEADLINE sigma (so the curve is in
the same currency as the 3.12x); optical uses Euclidean feature distances at the
real-real-calibrated sigma. Reads which pre-registered branch fired.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

from geo_tda.topo_eval.distributional import (
    global_sigma, mmd2_from_matrix, sliced_wasserstein,
)

_DIAGS = None


def _sw_row(i):
    return [(i, j, sliced_wasserstein(_DIAGS[i], _DIAGS[j])) for j in range(i + 1, len(_DIAGS))]


def _sw_matrix(diags, cpus):
    global _DIAGS
    _DIAGS = diags
    n = len(diags); D = np.zeros((n, n))
    with mp.Pool(cpus) as pool:
        for row in pool.map(_sw_row, range(n)):
            for i, j, d in row:
                D[i, j] = D[j, i] = d
    return D


def _curve(Dmat, sigma, base_idx, pert_idx, levels, pids, provs, reps, rng):
    """floor + per-level test ratios, splitting base pids into A,B."""
    pid_list = list(pids)
    floor_vals = []
    test_vals = {li: [] for li in range(len(levels))}
    for _ in range(reps):
        p = rng.permutation(len(pid_list))
        half = len(pid_list) // 2
        A = [pid_list[k] for k in p[:half]]; B = [pid_list[k] for k in p[half:2 * half]]
        bA = [base_idx[x] for x in A if x in base_idx]
        bB = [base_idx[x] for x in B if x in base_idx]
        if not bA or not bB:
            continue
        floor_vals.append(mmd2_from_matrix(Dmat, bA, bB, sigma))
        for li in range(len(levels)):
            pA = [pert_idx[(x, li)] for x in A if (x, li) in pert_idx]
            if pA:
                test_vals[li].append(mmd2_from_matrix(Dmat, pA, bB, sigma))
    floor = float(np.percentile(floor_vals, 95)) if floor_vals else float("nan")
    rows = []
    for li in range(len(levels)):
        if test_vals[li]:
            rows.append({"level": li, "test_median": float(np.median(test_vals[li])),
                         "ratio": float(np.median(test_vals[li]) / floor) if floor else None})
    return floor, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_power_probe"))
    ap.add_argument("--power", type=Path, default=Path("results/validity/m2_power.json"))
    ap.add_argument("--topo", type=Path, default=Path("results/validity/m2_generated_vs_real.json"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_power_curve.json"))
    ap.add_argument("--reps", type=int, default=120)
    ap.add_argument("--cpus", type=int, default=24)
    args = ap.parse_args()

    diag = pickle.loads((args.cache / "diagrams.pkl").read_bytes())
    base = diag["base"]; pert = diag["pert"]; levels = diag["levels"]
    sigma_h0 = float(json.loads(args.power.read_text())["sw_sigma"])
    topo_ratio = json.loads(args.topo.read_text())["test_median_over_floor_ratio"]
    pids = [b["pid"] for b in base]
    provs = {b["pid"]: b["province"] for b in base}
    base_idx = {b["pid"]: k for k, b in enumerate(base)}
    nb = len(base)
    pert_idx = {(p["pid"], p["level"]): nb + k for k, p in enumerate(pert)}
    mean_f = {li: float(np.mean([p["f"] for p in pert if p["level"] == li and np.isfinite(p["f"])]))
              for li in range(len(levels))}
    print(f"base={nb} pert={len(pert)} levels={len(levels)} topo_ratio={topo_ratio:.2f}", flush=True)
    print(f"mean f by level: {[round(mean_f[li],4) for li in range(len(levels))]}", flush=True)

    rng = np.random.default_rng(11)
    out = {"levels": levels, "mean_f_by_level": mean_f, "topology_ref": topo_ratio,
           "sw_sigma_h0": sigma_h0, "curves": {}}

    # H0 curve (SW distances at headline sigma)
    print("building H0 SW matrix...", flush=True)
    all_dgms = [b["dgm"] for b in base] + [p["dgm"] for p in pert]
    Dh0 = _sw_matrix(all_dgms, args.cpus)
    floor, rows = _curve(Dh0, sigma_h0, base_idx, pert_idx, levels, pids, provs,
                         args.reps, np.random.default_rng(11))
    out["curves"]["h0"] = {"floor": floor, "rows": rows}
    print(f"[H0] floor={floor:.4g} ratios={[round(r['ratio'],2) for r in rows]}", flush=True)

    # optical curves (Euclidean feature distances at real-real sigma)
    for bb in ("clip", "incep"):
        for render in ("hill", "stack"):
            bf = np.load(args.cache / f"base_{bb}_{render}.npy")
            pf = np.load(args.cache / f"pert_{bb}_{render}.npy")
            feats = np.vstack([bf, pf]); D = cdist(feats, feats)
            sig = global_sigma(D[:nb, :nb])
            floor, rows = _curve(D, sig, base_idx, pert_idx, levels, pids, provs,
                                 args.reps, np.random.default_rng(11))
            out["curves"][f"{bb}_{render}"] = {"floor": floor, "sigma": sig, "rows": rows}
            print(f"[{bb}/{render}] floor={floor:.4g} ratios={[round(r['ratio'],2) for r in rows]}", flush=True)

    # branch read: at the lowest f where H0 clears 3.12x, where is CLIP?
    h0_rows = out["curves"]["h0"]["rows"]
    clip_rows = out["curves"]["clip_stack"]["rows"]
    h0_span = max((r["ratio"] for r in h0_rows), default=0)
    h0_cross = next((r["level"] for r in h0_rows if r["ratio"] and r["ratio"] >= topo_ratio), None)
    clip_at_cross = next((r["ratio"] for r in clip_rows if r["level"] == h0_cross), None) if h0_cross is not None else None
    out["branch_read"] = {"h0_spans_topo": bool(h0_span >= topo_ratio),
                          "h0_cross_level": h0_cross, "mean_f_at_cross":
                          mean_f.get(h0_cross) if h0_cross is not None else None,
                          "clip_ratio_at_h0_cross": clip_at_cross,
                          "note": "BRANCH1 if clip~1 at H0-cross; BRANCH2 if clip rises later; "
                          "BRANCH3 if clip~H0 throughout."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"\nbranch read: {out['branch_read']}", flush=True)
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
