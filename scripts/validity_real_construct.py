"""Phase C construct validity: PH donor-graph network vs NHD flowlines.

For each tile this writes THREE side-by-side comparisons (construct_validity
.compare run three times): PH-vs-NHD (the construct claim), whitebox-vs-NHD
(the field-standard agreement ceiling), and PH-vs-whitebox (the two
DEM-derived networks against each other). Each comparison carries junction
count, Strahler-order distribution, Strahler Wasserstein-1, and |dR_b|.

The headline computed at summary time is the GAP per criterion
(PH-vs-NHD minus whitebox-vs-NHD): a comparative-advantage reading. The
older "PH recovers >= 95% of the ceiling" verdict is still computed but
moved to a secondary section, so the construct-validity (A) vs
comparative-advantage (B) framing is deferred to post-run analysis.

Per-tile rows are written to <out_dir>/per_tile/{key}.json as each tile
completes, so a wallclock timeout or single-tile crash does not lose the
rest; a final roll-up reads them all into the summary at --out.

tau_channel is matched per tile to the NHD drainage density (proposal.md);
pass --no-match-density to use a fixed --tau-channel instead.

Network + compute dependent. --quick for a smoke run. --manifest to consume
a tile_manifest.json from scripts/select_tiles.py instead of --bbox.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.construct_validity import compare
from geo_tda.topo_eval.pipeline import AcquiredTile, acquire_tiles, process_tile

DEM_DIR = Path("data/dem")
NHD_DIR = Path("data/nhd")

DEFAULT_BBOX = (-86.0, 35.0, -85.0, 36.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C PH-vs-NHD construct validity")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="tile_manifest.json from select_tiles.py (overrides --bbox)")
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    ap.add_argument("--n-tiles", type=int, default=100)
    ap.add_argument("--tau-channel", type=float, default=1000.0,
                    help="fallback threshold when --no-match-density")
    ap.add_argument("--no-match-density", action="store_false", dest="match_density",
                    help="use a fixed --tau-channel instead of NHD-density matching")
    ap.set_defaults(match_density=True)
    ap.add_argument("--quick", action="store_true", help="smoke run, 2 tiles")
    ap.add_argument("--window", type=int, default=None,
                    help="centered window x window crop; --quick implies 512. "
                    "At the Sapelo2 window (4096) a 1-degree tile is not cropped.")
    ap.add_argument("--out", type=Path, default=Path("results/validity/construct.json"))
    ap.add_argument("--shard", type=str, default=None,
                    help="k/n: process only tiles with index %% n == k; writes "
                    "per-tile JSON only (no summary). For across-core sharding.")
    ap.add_argument("--rollup-only", action="store_true",
                    help="skip processing; roll up existing per_tile/*.json into --out")
    args = ap.parse_args()

    out_dir = args.out.parent
    per_tile_dir = out_dir / "per_tile"
    per_tile_dir.mkdir(parents=True, exist_ok=True)

    if args.rollup_only:
        return _rollup(per_tile_dir, args.out)

    window = args.window if args.window is not None else (512 if args.quick else None)
    specs = _load_specs(args)
    if args.shard is not None:
        k, n = (int(x) for x in args.shard.split("/"))
        specs = [s for i, s in enumerate(specs) if i % n == k]
    if not specs:
        print("no tile specs (empty manifest, bad bbox, or empty shard)")
        return 1

    rows = []
    for spec in specs:
        tile = _acquire(spec)
        if tile is None or tile.nhd_path is None:
            print(f"skip {spec['key']}: acquisition failed or no NHD")
            _write_tile(per_tile_dir, spec["key"],
                        {"key": spec["key"], "error": "acquisition failed"})
            continue
        res = process_tile(
            tile.dem_path, key=tile.key, tau_channel=args.tau_channel,
            nhd_geojson=tile.nhd_path, include_ph=True, include_whitebox=True,
            window=window, match_density=args.match_density,
        )
        row = _build_row(res, spec)
        _write_tile(per_tile_dir, res.key, row)
        if res.error or res.ph is None or res.nhd is None:
            print(f"skip {res.key}: {res.error or 'PH or NHD side missing'}")
            continue
        rows.append(row)
        print(f"{res.key}: 3-way computed "
              f"(tau={res.tau_channel:.0f}, H1_cubical={res.h1_cubical}, "
              f"missed_basin={res.windowed_missed_dominant_basin})")

    if args.shard is not None:
        print(f"\nshard {args.shard}: wrote {len(rows)} per-tile rows to "
              f"{per_tile_dir}; run --rollup-only for the summary")
        return 0

    if not rows:
        print("no comparable tiles; construct validity not assessed")
        return 1

    summary = _summarize(rows)
    out = {"summary": summary, "rows": rows}
    args.out.write_text(json.dumps(out, indent=2))

    print(f"\nPH-vs-NHD construct validity (n={summary['n_tiles']}):")
    _print_block("ph_vs_nhd", summary["ph_vs_nhd"])
    _print_block("whitebox_vs_nhd (ceiling)", summary["whitebox_vs_nhd"])
    print("\nheadline GAP (PH-vs-NHD minus whitebox-vs-NHD):")
    for k, v in summary["gap"].items():
        print(f"  {k}: {v:+.4f}")
    print("\nsecondary verdict (PH >= 95% of ceiling):")
    for k, v in summary["verdict_secondary"].items():
        print(f"  {k}: {v}")
    print(f"\nwrote {args.out} and per-tile rows to {per_tile_dir}")
    return 0


def _rollup(per_tile_dir: Path, out: Path) -> int:
    """Read all per_tile/*.json and write the summary roll-up at out."""
    rows = []
    for p in sorted(per_tile_dir.glob("*.json")):
        row = json.loads(p.read_text())
        if not row.get("error") and row.get("comparisons", {}).get("ph_vs_nhd"):
            rows.append(row)
    if not rows:
        print(f"no comparable per-tile rows in {per_tile_dir}")
        return 1
    summary = _summarize(rows)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(f"rolled up {len(rows)} tiles -> {out}")
    print("\nheadline GAP (PH-vs-NHD minus whitebox-vs-NHD):")
    for k, v in summary["gap"].items():
        print(f"  {k}: {v:+.4f}")
    print(f"tiles missing dominant basin: {summary['tiles_missing_dominant_basin']}; "
          f"min window processed fraction: {summary['window_processed_fraction_min']}")
    return 0


def _load_specs(args) -> list[dict]:
    """Per-tile specs (key, bbox, and any manifest metadata)."""
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text())
        tiles = manifest.get("tiles", [])
        return tiles[:2] if args.quick else tiles
    n_tiles = 2 if args.quick else args.n_tiles
    out = []
    import math
    min_lon, min_lat, max_lon, max_lat = args.bbox
    for lat in range(math.floor(min_lat), math.ceil(max_lat)):
        for lon in range(math.floor(min_lon), math.ceil(max_lon)):
            ns, ew = ("n" if lat >= 0 else "s"), ("w" if lon < 0 else "e")
            out.append({
                "key": f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}",
                "bbox": [float(lon), float(lat), float(lon + 1), float(lat + 1)],
            })
            if len(out) >= n_tiles:
                return out
    return out


def _acquire(spec: dict):
    """Resolve DEM + NHD for one tile spec, offline-first.

    On a cluster compute node there is no internet, so if both files are
    already staged locally (by key) use them directly and never touch the
    STAC catalog. Only fall back to network acquisition when a file is
    missing (login-node / laptop path).
    """
    key = spec["key"]
    dem = DEM_DIR / f"USGS_seamless_{key}_30m.tif"
    nhd = NHD_DIR / f"{key}.geojson"
    if dem.exists() and nhd.exists():
        return AcquiredTile(key=key, dem_path=dem, nhd_path=nhd,
                            bbox=tuple(spec["bbox"]))
    tiles = acquire_tiles(tuple(spec["bbox"]), n_tiles=1)
    return tiles[0] if tiles else None


def _write_tile(per_tile_dir: Path, key: str, row: dict) -> None:
    (per_tile_dir / f"{key}.json").write_text(json.dumps(row, indent=2))


def _intkeys(dist: dict) -> dict:
    return {str(k): int(v) for k, v in dist.items()}


def _pair(a, b, la: str, lb: str) -> dict | None:
    """compare(a, b) relabeled for sub-dict {la}_vs_{lb}, plus distributions."""
    if a is None or b is None:
        return None
    raw = compare(a, b)
    jc_a, jc_b = raw["junction_count_ph"], raw["junction_count_nhd"]
    return {
        f"junction_count_{la}": jc_a,
        f"junction_count_{lb}": jc_b,
        "junction_count_abs_diff": abs(jc_a - jc_b),
        "strahler_wasserstein": raw["strahler_wasserstein"],
        f"strahler_distribution_{la}": _intkeys(a.strahler_distribution),
        f"strahler_distribution_{lb}": _intkeys(b.strahler_distribution),
        f"bifurcation_ratio_{la}": raw["bifurcation_ratio_ph"],
        f"bifurcation_ratio_{lb}": raw["bifurcation_ratio_nhd"],
        "bifurcation_ratio_abs_diff": raw["bifurcation_ratio_abs_diff"],
        f"drainage_density_{la}": raw["drainage_density_ph"],
        f"drainage_density_{lb}": raw["drainage_density_nhd"],
    }


def _build_row(res, spec: dict) -> dict:
    row = {
        "key": res.key,
        "province": spec.get("province"),
        "quintile": spec.get("quintile"),
        "bbox": list(res.bbox),
        "error": res.error,
        "comparisons": {
            "ph_vs_nhd": _pair(res.ph, res.nhd, "ph", "nhd"),
            "whitebox_vs_nhd": _pair(res.whitebox, res.nhd, "whitebox", "nhd"),
            "ph_vs_whitebox": _pair(res.ph, res.whitebox, "ph", "whitebox"),
        },
        "diagnostics": {
            "h1_cubical_mask": res.h1_cubical,
            "tau_channel": res.tau_channel,
            "target_density_nhd": res.target_density,
            "manifest_nhd_drainage_density": spec.get("nhd_drainage_density"),
            "window_size": res.window_size,
            "window_processed_fraction": res.window_processed_fraction,
            "windowed_missed_dominant_basin": res.windowed_missed_dominant_basin,
            "ph_segment_count": res.ph_segment_count,
            "whitebox_segment_count": res.whitebox_segment_count,
        },
    }
    return row


def _side_summary(rows: list[dict], sub: str) -> dict:
    pairs = [r["comparisons"][sub] for r in rows if r["comparisons"].get(sub)]
    if not pairs:
        return {"n": 0, "junction_count_spearman_proxy": float("nan"),
                "strahler_wasserstein_median": float("nan"),
                "bifurcation_ratio_abs_diff_median": float("nan")}
    la, lb = sub.split("_vs_")
    jc_a = np.array([p[f"junction_count_{la}"] for p in pairs], dtype=float)
    jc_b = np.array([p[f"junction_count_{lb}"] for p in pairs], dtype=float)
    sw = np.array([p["strahler_wasserstein"] for p in pairs], dtype=float)
    rb = np.array([p["bifurcation_ratio_abs_diff"] for p in pairs], dtype=float)
    rho = (float(np.corrcoef(jc_a, jc_b)[0, 1])
           if len(pairs) > 1 and jc_a.std() > 0 and jc_b.std() > 0
           else float("nan"))
    return {
        "n": len(pairs),
        "junction_count_spearman_proxy": rho,
        "strahler_wasserstein_median": float(np.nanmedian(sw)),
        "bifurcation_ratio_abs_diff_median": float(np.nanmedian(rb)),
    }


def _summarize(rows: list[dict]) -> dict:
    ph = _side_summary(rows, "ph_vs_nhd")
    wb = _side_summary(rows, "whitebox_vs_nhd")
    pw = _side_summary(rows, "ph_vs_whitebox")
    # gap: junction-count higher is better (PH wins if >0); Wasserstein and
    # |dR_b| lower is better (PH wins if <0).
    gap = {
        "junction_count_spearman_proxy": _sub(
            ph["junction_count_spearman_proxy"], wb["junction_count_spearman_proxy"]),
        "strahler_wasserstein_median": _sub(
            ph["strahler_wasserstein_median"], wb["strahler_wasserstein_median"]),
        "bifurcation_ratio_abs_diff_median": _sub(
            ph["bifurcation_ratio_abs_diff_median"],
            wb["bifurcation_ratio_abs_diff_median"]),
    }
    h1 = [r["diagnostics"]["h1_cubical_mask"] for r in rows
          if r["diagnostics"].get("h1_cubical_mask") is not None]
    missed = sum(1 for r in rows
                 if r["diagnostics"].get("windowed_missed_dominant_basin"))
    fracs = [r["diagnostics"]["window_processed_fraction"] for r in rows
             if r["diagnostics"].get("window_processed_fraction") is not None]
    return {
        "n_tiles": len(rows),
        "ph_vs_nhd": ph,
        "whitebox_vs_nhd": wb,
        "ph_vs_whitebox": pw,
        "gap": gap,
        "verdict_secondary": _verdict(ph, wb),
        "h1_cubical_mask_median": float(np.median(h1)) if h1 else None,
        "window_processed_fraction_min": float(np.min(fracs)) if fracs else None,
        "tiles_missing_dominant_basin": missed,
        "gap_note": "junction-count gap >0 favors PH; Wasserstein and |dR_b| "
        "gap <0 favors PH (lower is better). A-vs-B framing is post-run.",
    }


def _sub(a: float, b: float) -> float:
    if np.isfinite(a) and np.isfinite(b):
        return float(a - b)
    return float("nan")


def _verdict(ph: dict, ceiling: dict) -> dict:
    """Secondary: PH passes if it recovers >= 95% of the whitebox ceiling."""
    verdict = {}
    c_rho = ceiling["junction_count_spearman_proxy"]
    if np.isfinite(c_rho):
        verdict["junction_count_pass"] = bool(
            ph["junction_count_spearman_proxy"] >= 0.95 * c_rho)
    c_sw = ceiling["strahler_wasserstein_median"]
    if np.isfinite(c_sw) and c_sw > 0:
        verdict["strahler_wasserstein_pass"] = bool(
            ph["strahler_wasserstein_median"] <= 1.05 * c_sw)
    c_rb = ceiling["bifurcation_ratio_abs_diff_median"]
    if np.isfinite(c_rb) and c_rb > 0:
        verdict["bifurcation_ratio_pass"] = bool(
            ph["bifurcation_ratio_abs_diff_median"] <= 1.05 * c_rb)
    return verdict


def _print_block(label: str, block: dict) -> None:
    print(f"  {label}:")
    for k, v in block.items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    raise SystemExit(main())
