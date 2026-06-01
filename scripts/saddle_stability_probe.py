"""Theorem 3 saddle-stability probe (Milestone 2 prerequisite).

Tests the one thing that can silently invalidate Milestone 2: whether the
flow-accumulation H0 persistence diagram is stable under DEM perturbations
that flip D8 routing at saddles (so the two-sample test reads drainage
pathology, not generator saddle-noise), while the merge-tree branching
summaries are not. This is Theorem 3 (bottleneck-stable in A, not stable in
the DEM) made empirical.

Design (locked after adversarial review; see
docs/topo_eval/notes/m2_reference_forward_feed.md and phase_c_postmortem.md):

- Hold tau FIXED per tile at the original NHD-density-matched value, for
  every perturbation of that tile. Re-matching would confound the
  filtration's sensitivity with the matcher's.
- Two perturbation classes, NOT pooled: additive sub-meter noise (the
  saddle-flipper / sensor-uncertainty analog) and Gaussian smoothing (the
  generator-diffusion analog). Smoothing moving H0 is M2-relevant signal,
  not a stability failure, so it is reported separately and not gated by
  S_STABLE.
- Normalize each perturbation's diagram movement by the movement a genuine
  high-A reroute (the positive control) induces ON THE SAME TILE, not by the
  diagram's total persistence. Total persistence is dominated by stable
  macro-basins the perturbation never threatens, which makes the stability
  bar pass vacuously. The control movement is the unit of a change that
  ought to matter, so "small" is non-vacuous and the asymmetry gate never
  divides by the near-zero noise movement.
- Read stability only where routing actually moved (flips >= F_MIN), and
  report the full movement-vs-flips curve, not just the threshold verdict.
- n=20 x seeds supports non-overlap / effect-size separation, NOT a
  significance test. Pass conditions are stated as separations, not p-values.

Pre-registered constants are at the top, loud, with rationale. Any change is
made in an open commit BEFORE checking whether it flips the pass.

Run on a compute node (whitebox per perturbation is the cost); offline-first
on staged DEM + NHD. Writes a JSON report with per-tile rows and the
aggregate invariant verdicts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS (commit changes in the open, before seeing the pass)
# ---------------------------------------------------------------------------
F_MIN = 100          # informative filter: a perturbation must flip at least
                     # this many D8 receivers to count toward stability; below
                     # it the perturbation tested nothing and a flat result is
                     # ambiguous. Chosen as a small fraction of a tile's
                     # channel cells; the flips-vs-movement curve is reported
                     # so this threshold is not silently load-bearing.
S_STABLE = 0.10      # stability bar: noise must move H0 by <= 10% of what the
                     # largest real reroute moves it (rr_H0). Scaled to the
                     # control, so 10% means "a tenth of a change that
                     # matters", not 10% of inflated total persistence.
GAP_MIN = 0.40       # asymmetry gap (Thm 3): median(rr_B noise) minus
                     # p95(rr_H0 noise), on the common control-unit scale.
                     # Positive and large means branching is perturbed a large
                     # fraction of a real change while H0 is not. A gap, not a
                     # quotient, so it degrades gracefully at the noise floor.

# White additive noise was REJECTED (open note): sub-meter white noise flips
# millions of D8 receivers (wholesale rerouting), unrepresentative of
# generator-vs-real differences, which are spatially CORRELATED. The probe
# uses correlated perturbations at graded amplitude (generator-like regime).
CORR_LEN_PX = 4                     # spatial correlation length (generator-like)
CORR_AMPS_M = (0.5, 1.0, 2.0, 4.0)  # graded amplitude -> the sensitivity curve
N_SEEDS = 3
TARGET_F = 0.15                     # constant control f for a consistent unit
                                    # across tiles (interpolated); <= min(max f)
SMOOTH_SIGMAS_PX = (1.0, 2.0)       # Gaussian smoothing (generator analog)
CONTROL_LENFRACS = (0.34, 0.67, 1.0)  # megachannel length frac -> increasing f
F_CONTROL_MIN = 0.20  # a trustworthy unit needs >=1 genuinely large reroute (this f)
SW_M = 50            # sliced-Wasserstein direction count
DEM_DIR = Path("data/dem")
NHD_DIR = Path("data/nhd")


def _sliced_wasserstein(dgm_a, dgm_b) -> float:
    """SW1 between two H0 diagrams, essentials capped at a common finite death.

    The essential (death=inf) classes are the surviving basins; reroutes
    change them, so they must be compared, not dropped. Cap inf at a common
    large finite value (the max finite death across both diagrams, scaled),
    consistent for orig and perturbed so the cap does not itself create
    movement.
    """
    a = np.asarray(dgm_a, dtype=float).reshape(-1, 2)
    b = np.asarray(dgm_b, dtype=float).reshape(-1, 2)
    finite = np.concatenate([a[np.isfinite(a[:, 1]), 1], b[np.isfinite(b[:, 1]), 1]])
    cap = (finite.max() * 1.5) if finite.size else 1.0
    a[~np.isfinite(a[:, 1]), 1] = cap
    b[~np.isfinite(b[:, 1]), 1] = cap
    try:
        from persim import sliced_wasserstein
        return float(sliced_wasserstein(a, b, M=SW_M))
    except Exception:
        from gudhi.representations import SlicedWassersteinDistance
        swd = SlicedWassersteinDistance(num_directions=SW_M)
        return float(swd.fit([a]).transform([b])[0][0])


def _branching_shift(s_a, s_b) -> float:
    """Dimensionless movement between two branching summaries."""
    jc = abs(s_a.junction_count - s_b.junction_count) / max(1, s_a.junction_count)
    rb = (abs(s_a.bifurcation_ratio - s_b.bifurcation_ratio)
          if np.isfinite(s_a.bifurcation_ratio) and np.isfinite(s_b.bifurcation_ratio)
          else 0.0)
    rb /= max(1e-6, abs(s_a.bifurcation_ratio)) if np.isfinite(s_a.bifurcation_ratio) else 1.0
    from geo_tda.topo_eval.construct_validity import strahler_wasserstein
    sw = strahler_wasserstein(s_a.strahler_distribution, s_b.strahler_distribution)
    sw /= max(1.0, max(s_a.strahler_distribution or {1: 1}))
    return float(max(jc, rb, sw))


def _summaries_for_array(arr, profile, tau, workdir):
    """Run the fixed-tau pipeline on a DEM array: H0 diagram, branching, codes."""
    import rasterio

    from geo_tda.topo_eval.construct_validity import stats_from_merge_tree
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
    from geo_tda.topo_eval.merge_tree import (
        merge_tree_from_accumulation, persistence_diagram,
    )

    tmp = workdir / "pert.tif"
    prof = {**profile, "driver": "GTiff", "compress": "none", "tiled": False, "count": 1}
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(arr.astype(profile["dtype"]), 1)
    codes, accum = d8_pointer_and_accumulation(tmp, workdir=str(workdir))
    tree = merge_tree_from_accumulation(codes, accum, tau)
    dgm = [(b, d if d is not None else np.inf) for (b, d) in persistence_diagram(tree)]
    ph = stats_from_merge_tree(tree, area_km2=1.0,
                               channel_cell_count=int((accum >= tau).sum()),
                               cell_km=1.0)
    return dgm, ph, codes, accum


def _carve_trench(arr, accum, lenfrac):
    """Positive control: a genuine large drainage reroute, not a divide nick.

    A single-row trench saturates near f~0.09 because it only captures the
    cells immediately draining into it. To force a high-A reroute, gouge a
    monotonic megachannel diagonally across the tile, sunk far below the
    surrounding terrain so it becomes the dominant drainage line and a large
    watershed re-drains into it. The channel descends along its length so D8
    routes into and along it. Depth scales severity, hence the rerouted mass
    fraction f, measured post-hoc. The control's only job is to be the scale
    of an unambiguous large drainage-topology change, not to be realistic.
    """
    out = arr.astype(float).copy()
    H, W = out.shape
    lo = float(out.min())
    n = max(H, W)
    span = max(2, int(lenfrac * n))   # carve only the first lenfrac of the diagonal
    for t in range(span):
        i = min(H - 1, int(t * (H - 1) / (n - 1)))
        j = min(W - 1, int(t * (W - 1) / (n - 1)))
        floor = lo - 50.0 - 50.0 * (t / n)  # deep descending megachannel
        out[i, j] = floor
        for di in (-1, 1):                          # widen to guarantee capture
            if 0 <= i + di < H:
                out[i + di, j] = min(out[i + di, j], floor + 0.5)
    return out


def _mass_moved_fraction(accum_orig, accum_pert) -> float:
    """Effect size f: fraction of accumulation mass relocated by a reroute."""
    denom = float(accum_orig.sum())
    if denom <= 0:
        return float("nan")
    return float(np.abs(accum_pert.astype(float) - accum_orig.astype(float)).sum() / (2 * denom))


def _interp_unit(controls, key, target_f):
    """Control-induced movement interpolated at a constant f, so the
    normalizing unit is consistent across tiles (fixes the cross-tile rr
    incomparability from variable control f). Falls back to the max-f control
    if target_f exceeds this tile's reach."""
    pts = sorted(((c["f"], c[key]) for c in controls), key=lambda t: t[0])
    fs = [f for f, _ in pts]; vs = [v for _, v in pts]
    if not fs or target_f > fs[-1]:
        return max(vs) if vs else 0.0
    return float(np.interp(target_f, fs, vs))


def _flips(codes_a, codes_b) -> int:
    return int(np.count_nonzero(codes_a != codes_b))


def main() -> int:
    import tempfile

    import rasterio
    from scipy.ndimage import gaussian_filter

    from geo_tda.topo_eval.construct_validity import stats_from_flowlines
    from geo_tda.topo_eval.pipeline import (
        _cell_km, _materialize_plain, _tile_area_km2, _tile_bbox_from_raster,
        tau_for_target_density,
    )

    ap = argparse.ArgumentParser(description="Theorem 3 saddle-stability probe")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--n-tiles", type=int, default=5,
                    help="subset is enough for a non-overlap separation")
    ap.add_argument("--out", type=Path, default=Path("results/validity/saddle_probe.json"))
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text())["tiles"][:args.n_tiles]
    rng = np.random.default_rng(0)
    rows = []

    for spec in tiles:
        key = spec["key"]
        dem = DEM_DIR / f"USGS_seamless_{key}_30m.tif"
        nhd = NHD_DIR / f"{key}.geojson"
        if not (dem.exists() and nhd.exists()):
            print(f"skip {key}: not staged")
            continue
        wd = Path(tempfile.mkdtemp(prefix=f"saddle_{key}_"))
        try:
            plain = _materialize_plain(dem)
            with rasterio.open(plain) as s:
                arr0 = s.read(1).astype("float64")
                profile = s.profile.copy()
                profile["dtype"] = "float64"
            bbox = _tile_bbox_from_raster(plain)
            area = _tile_area_km2(bbox)
            nhd_stats = stats_from_flowlines(nhd, area_km2=area)

            dgm0, ph0, codes0, acc0 = _summaries_for_array(arr0, profile, 1.0, wd)
            cell_km = _cell_km(bbox, acc0.shape)
            tau = tau_for_target_density(acc0, nhd_stats.drainage_density, area, cell_km)
            # recompute originals at the matched, frozen tau
            dgm0, ph0, codes0, acc0 = _summaries_for_array(arr0, profile, tau, wd)

            # positive controls at increasing depth -> increasing f
            controls = []
            for lf in CONTROL_LENFRACS:
                dgm_c, ph_c, codes_c, acc_c = _summaries_for_array(
                    _carve_trench(arr0, acc0, lf), profile, tau, wd)
                controls.append({
                    "lenfrac": lf,
                    "f": _mass_moved_fraction(acc0, acc_c),
                    "sw_h0": _sliced_wasserstein(dgm0, dgm_c),
                    "b": _branching_shift(ph0, ph_c),
                    "flips": _flips(codes0, codes_c),
                })
            u_h0 = _interp_unit(controls, "sw_h0", TARGET_F)  # consistent unit
            u_b = _interp_unit(controls, "b", TARGET_F)

            def record(kind, arr_p):
                dgm_p, ph_p, codes_p, _ = _summaries_for_array(arr_p, profile, tau, wd)
                sw = _sliced_wasserstein(dgm0, dgm_p)
                b = _branching_shift(ph0, ph_p)
                return {"kind": kind, "flips": _flips(codes0, codes_p),
                        "sw_h0": sw, "b": b,
                        "rr_h0": sw / u_h0 if u_h0 > 0 else float("nan"),
                        "rr_b": b / u_b if u_b > 0 else float("nan")}

            perts = []
            for amp in CORR_AMPS_M:
                for _ in range(N_SEEDS):
                    cn = gaussian_filter(rng.normal(0, 1, arr0.shape), CORR_LEN_PX)
                    cn *= amp / (cn.std() or 1.0)   # correlated field, amplitude amp (m)
                    perts.append(record(f"corr_{amp}", arr0 + cn))
            for sg in SMOOTH_SIGMAS_PX:
                perts.append(record(f"smooth_{sg}", gaussian_filter(arr0, sg)))

            rows.append({"key": key, "tau": float(tau),
                         "controls": controls, "perturbations": perts})
            print(f"{key}: controls f={[round(c['f'],3) for c in controls]} "
                  f"u_h0={u_h0:.3g}; corr rr_h0="
                  f"{[round(p['rr_h0'],3) for p in perts if p['kind'].startswith('corr')]}")
        except Exception as exc:  # noqa: BLE001 - per-tile isolation
            print(f"tile {key} failed: {exc}")
        finally:
            import shutil
            shutil.rmtree(wd, ignore_errors=True)

    verdict = _evaluate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"verdict": verdict, "rows": rows}, indent=2))
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k}: {v}")
    print(f"wrote {args.out}")
    return 0


def _flip_curve(noise):
    if not noise:
        return []
    fl = np.array([p["flips"] for p in noise], float)
    rr = np.array([p["rr_h0"] for p in noise], float)
    edges = np.quantile(fl, [0, .25, .5, .75, 1.0])
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (fl >= lo) & (fl <= hi)
        if m.any():
            out.append({"flips_lo": float(lo), "flips_hi": float(hi),
                        "rr_h0_median": float(np.nanmedian(rr[m])), "n": int(m.sum())})
    return out


def _evaluate(rows) -> dict:
    """Apply the four pre-registered invariants over informative instances."""
    noise = [p for r in rows for p in r["perturbations"]
             if p["kind"].startswith("corr") and p["flips"] >= F_MIN]
    smooth = [p for r in rows for p in r["perturbations"]
              if p["kind"].startswith("smooth")]
    excluded = sum(1 for r in rows for p in r["perturbations"]
                   if p["kind"].startswith("corr") and p["flips"] < F_MIN)
    if not noise:
        return {"status": "no informative noise instances (raise sigma)"}
    rr_h0 = np.array([p["rr_h0"] for p in noise], dtype=float)
    rr_b = np.array([p["rr_b"] for p in noise], dtype=float)
    # control validity: SW1 rises with f across controls (pooled rank corr)
    fs = np.array([c["f"] for r in rows for c in r["controls"]], dtype=float)
    cs = np.array([c["sw_h0"] for r in rows for c in r["controls"]], dtype=float)
    from scipy.stats import spearmanr
    rho = float(spearmanr(fs, cs).statistic) if fs.size > 2 else float("nan")
    p95_h0 = float(np.nanpercentile(rr_h0, 95))
    med_b = float(np.nanmedian(rr_b))
    return {
        "n_noise_informative": len(noise),
        "n_noise_excluded_below_Fmin": excluded,
        "control_validity_spearman_f_vs_swh0": rho,
        "control_max_f": float(np.nanmax(fs)) if fs.size else float("nan"),
        "control_validity_pass": bool(fs.size and np.nanmax(fs) >= F_CONTROL_MIN),
        "stability_p95_rr_h0": p95_h0,
        "stability_pass": bool(p95_h0 <= S_STABLE),
        "asymmetry_gap": med_b - p95_h0,
        "asymmetry_pass": bool((med_b - p95_h0) >= GAP_MIN),
        "smoothing_rr_h0_median": float(np.nanmedian([p["rr_h0"] for p in smooth])) if smooth else None,
        "curve_rr_h0_by_flipbin": _flip_curve(noise),
        "note": "CHARACTERIZATION, not a gate. Correlated (generator-like) "
        "regime; constant-f unit. The flip->rr_h0 curve is the pre-MESA "
        "artifact; the M2 operating point and the saddle verdict are read by "
        "measuring MESA real-vs-generated H0 movement DIRECTLY (flip-count is "
        "not assumed a sufficient statistic). n supports non-overlap, not p.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
