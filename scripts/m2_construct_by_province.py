"""Per-province breakdown of the NHD construct-validity result (Stage 0).

Pure re-analysis of results/validity/teach_run_20260530/construct.json (no
extraction). Addresses the review concern that the aggregate construct-validity
numbers could mask a sinkhole-rich or otherwise atypical province as an outlier:
group the 20 tiles by physiographic province and recompute, per province and per
comparison (PH-vs-NHD and the WhiteboxTools ceiling), the junction-count rank
agreement (Spearman) and the medians of the Strahler Wasserstein-1 distance and the
absolute bifurcation-ratio difference. The overall numbers are recomputed too and
checked against the committed summary so the breakdown is known to be consistent.

Per-province junction Spearman is over 6-7 tiles, so it is reported with its n and
read as a coarse check, not a precise estimate; the medians are the robust signal.

Run from the repo root: .pixi/envs/cpu/bin/python scripts/m2_construct_by_province.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CONSTRUCT = ROOT / "results" / "validity" / "teach_run_20260530" / "construct.json"
OUT = ROOT / "results" / "validity" / "m2_construct_by_province.json"

# (comparison key in the JSON, the method-side suffix for junction_count_<side>)
COMPARISONS = [("ph_vs_nhd", "ph"), ("whitebox_vs_nhd", "whitebox")]


def _agg(rows, cmp_key, side):
    """Junction Spearman + Strahler/bifurcation medians over a set of tile rows."""
    method_jc, nhd_jc, sw, brd = [], [], [], []
    for r in rows:
        comp = r["comparisons"][cmp_key]
        method_jc.append(comp[f"junction_count_{side}"])
        nhd_jc.append(comp["junction_count_nhd"])
        sw.append(comp["strahler_wasserstein"])
        brd.append(comp["bifurcation_ratio_abs_diff"])
    method_jc, nhd_jc = np.array(method_jc, float), np.array(nhd_jc, float)
    # Match the committed summary's definition exactly: the field is named
    # "spearman_proxy" but validity_real_construct._side_summary computes it as a
    # Pearson np.corrcoef of the raw junction counts (a misnomer in the source).
    rho = (float(np.corrcoef(method_jc, nhd_jc)[0, 1])
           if method_jc.size > 1 and method_jc.std() > 0 and nhd_jc.std() > 0
           else float("nan"))
    return {
        "n": len(rows),
        "junction_count_spearman_proxy": rho,
        "strahler_wasserstein_median": float(np.median(sw)),
        "bifurcation_ratio_abs_diff_median": float(np.median(brd)),
    }


def main() -> int:
    doc = json.loads(CONSTRUCT.read_text())
    rows = [r for r in doc["rows"] if not r.get("error")]
    by_prov: dict[str, list] = {}
    for r in rows:
        by_prov.setdefault(r["province"], []).append(r)

    out = {"comparisons": {}, "overall_check": {}}
    for cmp_key, side in COMPARISONS:
        out["comparisons"][cmp_key] = {
            "overall": _agg(rows, cmp_key, side),
            "by_province": {p: _agg(rs, cmp_key, side) for p, rs in sorted(by_prov.items())},
        }
        # consistency check vs the committed summary
        recomputed = out["comparisons"][cmp_key]["overall"]
        summ = doc["summary"][cmp_key]
        out["overall_check"][cmp_key] = {
            k: {"recomputed": recomputed[k], "summary": summ[k],
                "match": bool(abs(recomputed[k] - summ[k]) < 1e-6)}
            for k in ("junction_count_spearman_proxy",
                      "strahler_wasserstein_median",
                      "bifurcation_ratio_abs_diff_median")
        }

    OUT.write_text(json.dumps(out, indent=2))

    # readable report
    print(f"tiles: {len(rows)}; provinces: "
          f"{ {p: len(rs) for p, rs in sorted(by_prov.items())} }")
    for cmp_key, _ in COMPARISONS:
        print(f"\n=== {cmp_key} ===")
        hdr = f"  {'group':22s} {'n':>2s} {'junc_rho':>9s} {'strahler_W':>11s} {'|dRb|':>7s}"
        print(hdr)
        blk = out["comparisons"][cmp_key]
        for label, a in [("OVERALL", blk["overall"])] + list(blk["by_province"].items()):
            print(f"  {label:22s} {a['n']:>2d} {a['junction_count_spearman_proxy']:>9.3f} "
                  f"{a['strahler_wasserstein_median']:>11.4f} "
                  f"{a['bifurcation_ratio_abs_diff_median']:>7.3f}")
        chk = out["overall_check"][cmp_key]
        allok = all(v["match"] for v in chk.values())
        print(f"  overall-vs-summary consistency: {'PASS' if allok else 'FAIL -> ' + json.dumps(chk)}")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
