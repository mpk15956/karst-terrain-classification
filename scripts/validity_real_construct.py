"""Phase C construct validity: PH donor-graph network vs NHD flowlines.

Compares the PH-derived channel network (the donor-graph merge tree)
against NHD flowline vectors on the three branching criteria (junction
count, Strahler-order Wasserstein, Horton bifurcation ratio). Drainage
density is reported as a controlled covariate, NOT a criterion. The
per-tile cubical-mask H1 diagnostic is reported as a sidebar quantifying
how much spatial-adjacency contamination the donor-graph construction
removes on real data.

Thresholds are pre-registered RELATIVE to the whitebox-vs-NHD ceiling
from validity_real_ceiling.py (PH must recover >= 95% of whitebox's
agreement on each criterion), not against absolute targets.

Network + compute dependent. --quick for a smoke run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.construct_validity import compare
from geo_tda.topo_eval.pipeline import acquire_tiles, process_tile

DEFAULT_BBOX = (-86.0, 35.0, -85.0, 36.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C PH-vs-NHD construct validity")
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    ap.add_argument("--n-tiles", type=int, default=100)
    ap.add_argument("--tau-channel", type=float, default=1000.0)
    ap.add_argument("--quick", action="store_true", help="smoke run, 2 tiles")
    ap.add_argument(
        "--ceiling", type=Path, default=Path("results/validity/ceiling.json"),
        help="ceiling JSON from validity_real_ceiling.py for relative thresholds",
    )
    ap.add_argument("--out", type=Path, default=Path("results/validity/construct.json"))
    args = ap.parse_args()

    n_tiles = 2 if args.quick else args.n_tiles
    tiles = acquire_tiles(tuple(args.bbox), n_tiles=n_tiles)
    if not tiles:
        print("no tiles acquired (network or coverage issue); see logs")
        return 1

    rows = []
    h1_sidebar = []
    for t in tiles:
        if t.nhd_path is None:
            continue
        res = process_tile(
            t.dem_path, key=t.key, tau_channel=args.tau_channel,
            nhd_geojson=t.nhd_path, include_ph=True, include_whitebox=False,
        )
        if res.error or res.ph is None or res.nhd is None:
            print(f"skip {t.key}: {res.error}")
            continue
        row = compare(res.ph, res.nhd)
        row["key"] = t.key
        row["h1_cubical"] = res.h1_cubical
        rows.append(row)
        h1_sidebar.append(res.h1_cubical)
        print(f"{t.key}: PH-vs-NHD computed (H1_cubical={res.h1_cubical})")

    if not rows:
        print("no comparable tiles; construct validity not assessed")
        return 1

    summary = _summarize(rows, h1_sidebar)
    ceiling = _load_ceiling(args.ceiling)
    verdict = _verdict_relative_to_ceiling(summary, ceiling) if ceiling else None

    out = {"summary": summary, "ceiling": ceiling, "verdict": verdict, "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))

    print(f"\nPH-vs-NHD construct validity (n={summary['n_tiles']}):")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if verdict:
        print("\nverdict (relative to ceiling):")
        for k, v in verdict.items():
            print(f"  {k}: {v}")
    else:
        print("\n(no ceiling file; run validity_real_ceiling.py for relative verdict)")
    print(f"\nwrote {args.out}")
    return 0


def _summarize(rows, h1_sidebar) -> dict:
    jc_ph = np.array([r["junction_count_ph"] for r in rows], dtype=float)
    jc_nhd = np.array([r["junction_count_nhd"] for r in rows], dtype=float)
    sw = np.array([r["strahler_wasserstein"] for r in rows], dtype=float)
    rb = np.array([r["bifurcation_ratio_abs_diff"] for r in rows], dtype=float)
    jc_rho = (
        float(np.corrcoef(jc_ph, jc_nhd)[0, 1])
        if len(rows) > 1 and jc_ph.std() > 0 and jc_nhd.std() > 0
        else float("nan")
    )
    h1 = [h for h in h1_sidebar if h is not None]
    return {
        "n_tiles": len(rows),
        "junction_count_spearman_proxy": jc_rho,
        "strahler_wasserstein_median": float(np.nanmedian(sw)),
        "bifurcation_ratio_abs_diff_median": float(np.nanmedian(rb)),
        "h1_cubical_median": float(np.median(h1)) if h1 else None,
        "h1_cubical_note": "spatial-adjacency contamination the donor-graph "
        "construction removed (0 under donor graph by construction)",
    }


def _load_ceiling(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _verdict_relative_to_ceiling(summary: dict, ceiling: dict) -> dict:
    """PH passes if it recovers >= 95% of whitebox's agreement.

    For junction-count correlation higher is better (>= 0.95 * ceiling).
    For Wasserstein and |dR_b| lower is better (PH <= 105% of ceiling).
    """
    verdict = {}
    c_rho = ceiling.get("junction_count_spearman_proxy")
    if c_rho and np.isfinite(c_rho):
        verdict["junction_count_pass"] = bool(
            summary["junction_count_spearman_proxy"] >= 0.95 * c_rho
        )
    c_sw = ceiling.get("strahler_wasserstein_median")
    if c_sw and np.isfinite(c_sw):
        verdict["strahler_wasserstein_pass"] = bool(
            summary["strahler_wasserstein_median"] <= 1.05 * c_sw
        )
    c_rb = ceiling.get("bifurcation_ratio_abs_diff_median")
    if c_rb and np.isfinite(c_rb):
        verdict["bifurcation_ratio_pass"] = bool(
            summary["bifurcation_ratio_abs_diff_median"] <= 1.05 * c_rb
        )
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
