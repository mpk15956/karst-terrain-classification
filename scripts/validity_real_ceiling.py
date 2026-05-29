"""Phase C ceiling calibration: whitebox standard extraction vs NHD.

Estimates the achievable agreement ceiling between ANY DEM-derived
channel network and the photo-digitized NHD flowline vectors, by running
whitebox's own field-standard Strahler extraction (NOT the PH metric)
against NHD on a held-out tile set. DEM-extracted and photo-digitized
networks disagree for epoch and cartographic-convention reasons unrelated
to any metric's quality; this run measures that floor so the PH-vs-NHD
thresholds in validity_real_construct.py can be pre-registered RELATIVE to
it (PH must recover >= 95% of whitebox's agreement), not against absolute
targets.

Network + compute dependent. Use --quick for a 1-2 tile smoke run on a
laptop; the full held-out set is a deliberate larger launch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.construct_validity import compare
from geo_tda.topo_eval.pipeline import acquire_tiles, process_tile

# A karst-bearing region of the SE US (Cumberland Plateau / Highland Rim),
# the pilot's physiographic setting. Override with --bbox.
DEFAULT_BBOX = (-86.0, 35.0, -85.0, 36.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C whitebox-vs-NHD ceiling")
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    ap.add_argument("--n-tiles", type=int, default=20)
    ap.add_argument("--tau-channel", type=float, default=1000.0)
    ap.add_argument("--quick", action="store_true", help="smoke run, 2 tiles")
    ap.add_argument("--out", type=Path, default=Path("results/validity/ceiling.json"))
    args = ap.parse_args()

    n_tiles = 2 if args.quick else args.n_tiles
    tiles = acquire_tiles(tuple(args.bbox), n_tiles=n_tiles)
    if not tiles:
        print("no tiles acquired (network or coverage issue); see logs")
        return 1

    rows = []
    for t in tiles:
        if t.nhd_path is None:
            continue
        res = process_tile(
            t.dem_path, key=t.key, tau_channel=args.tau_channel,
            nhd_geojson=t.nhd_path, include_whitebox=True, include_ph=False,
        )
        if res.error or res.whitebox is None or res.nhd is None:
            print(f"skip {t.key}: {res.error}")
            continue
        rows.append(compare(res.whitebox, res.nhd))
        print(f"{t.key}: whitebox-vs-NHD computed")

    if not rows:
        print("no comparable tiles; ceiling not estimated")
        return 1

    ceiling = _summarize(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ceiling, indent=2))
    print(f"\nceiling (whitebox vs NHD, n={len(rows)}):")
    for k, v in ceiling.items():
        print(f"  {k}: {v}")
    print(f"\nwrote {args.out}")
    return 0


def _summarize(rows: list[dict]) -> dict:
    jc_ph = np.array([r["junction_count_ph"] for r in rows], dtype=float)
    jc_nhd = np.array([r["junction_count_nhd"] for r in rows], dtype=float)
    sw = np.array([r["strahler_wasserstein"] for r in rows], dtype=float)
    rb = np.array(
        [r["bifurcation_ratio_abs_diff"] for r in rows], dtype=float
    )
    jc_rho = (
        float(np.corrcoef(jc_ph, jc_nhd)[0, 1])
        if len(rows) > 1 and jc_ph.std() > 0 and jc_nhd.std() > 0
        else float("nan")
    )
    return {
        "n_tiles": len(rows),
        "junction_count_spearman_proxy": jc_rho,
        "strahler_wasserstein_median": float(np.nanmedian(sw)),
        "bifurcation_ratio_abs_diff_median": float(np.nanmedian(rb)),
        "note": "this is the agreement CEILING; PH-vs-NHD is calibrated "
        "relative to it (PH >= 95% of this agreement)",
    }


if __name__ == "__main__":
    raise SystemExit(main())
