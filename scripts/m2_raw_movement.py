"""Raw diagram-movement ratio (Stage 0, cached re-analysis).

Emits the "1.27x" raw sliced-Wasserstein movement figure to a committed JSON so the
manuscript can cite a reproducible source instead of a hardcoded fallback. This is the
SECOND currency in the Results (distinct from the 3.12x distributional MMD/floor
separation): the raw magnitude of diagram movement, mean generated-to-real divided by
mean real-to-real H0 sliced-Wasserstein distance. Both blocks are read straight from
the cached SW matrices (same flat order as the headline), so no whitebox, no
extraction, pure elis.

The real-to-real mean uses the strict upper triangle (the diagonal is self-distance 0
and would dilute the mean); the generated-to-real mean uses the full cross block.

Run from the repo root: .pixi/envs/cpu/bin/python scripts/m2_raw_movement.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "validity"
CACHE = V / "m2_diag_cache"
OUT = V / "m2_raw_movement.json"


def main() -> int:
    rr = np.load(CACHE / "sw_matrix.npy")            # real x real
    cross = np.load(CACHE / "sw_cross_realgen.npy")  # real x gen
    nr = rr.shape[0]
    ng = cross.shape[1]
    iu = np.triu_indices(nr, k=1)
    rr_vals = rr[iu]
    cross_vals = cross.ravel()

    mean_rr = float(rr_vals.mean())
    mean_cross = float(cross_vals.mean())
    med_rr = float(np.median(rr_vals))
    med_cross = float(np.median(cross_vals))
    ratio_mean = mean_cross / mean_rr
    ratio_median = med_cross / med_rr

    out = {
        "n_real": nr, "n_generated": ng,
        "mean_real_to_real_sw_h0": mean_rr,
        "mean_generated_to_real_sw_h0": mean_cross,
        "raw_movement_ratio_mean": ratio_mean,
        "median_real_to_real_sw_h0": med_rr,
        "median_generated_to_real_sw_h0": med_cross,
        "raw_movement_ratio_median": ratio_median,
        "note": "Raw diagram-movement magnitude (the SECOND Results currency, distinct "
                "from the 3.12x distributional MMD/floor separation). Mean generated-to-"
                "real over mean real-to-real H0 sliced-Wasserstein distance, from the "
                "cached SW blocks. The real-to-real mean excludes the zero diagonal. "
                "This is NOT a saddle fraction: it attributes no share of the divergence "
                "to saddle rerouting; it is only a magnitude, which the saddle probe "
                "shows D8 rerouting can itself reach.",
    }
    OUT.write_text(json.dumps(out, indent=2))
    # self-check: reproduces the pre-registered 1.27 (components 1.012e7 / 7.97e6)
    assert abs(ratio_mean - 1.27) < 0.01, f"raw movement ratio {ratio_mean} != 1.27"
    print(f"n_real={nr} n_gen={ng}")
    print(f"mean real-real   = {mean_rr:.6g}")
    print(f"mean gen-real    = {mean_cross:.6g}")
    print(f"raw movement ratio (mean)   = {ratio_mean:.4f}")
    print(f"raw movement ratio (median) = {ratio_median:.4f}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
