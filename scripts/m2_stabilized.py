"""Saddle-stable statistic driver: amplitude sweep (Stage 0.5), with the stabilized
floor / validation / headline (Stages 1-2) added as subcommands later.

Stage 0.5 (`sweep`), run on elis over the saddle-probe corpus (whole 30 m tiles with
known ground truth). Measures the stabilization-versus-power frontier of the
saddle-stable ensemble feature as a function of the marginalization base amplitude:

  M_saddle(amp) = || F_stress(amp) - F_orig(amp) ||_2   should FALL with amp:
        marginalizing over divide-migration uncertainty washes out a saddle-flipping
        stress (the Theorem 3b sensitivity the stabilizer is built to remove).
  M_power(amp)  = || F_control(amp) - F_orig(amp) ||_2   should STAY large: a genuine
        large-watershed-capture megachannel survives marginalization (non-vacuity).

F_*(amp) is the stabilized feature: the mean H0 persistence image over J D8-routed
realizations of (DEM + locally roughness-scaled correlated noise at base amplitude
amp), on a FROZEN global persistence-image grid (src/geo_tda/topo_eval/stabilized.py).
The marginalization perturbation (the amp grid) is DISTINCT from the validation stress
perturbation (a fixed saddle-flipping correlated field); the two RNG streams never
share draws, except that M_saddle deliberately PAIRS the marginalization noise between
F_orig and F_stress (variance reduction: the only difference left is the base DEM,
arr0 versus the stressed arr0, so M_saddle isolates the residual stress effect).

The J=1 ensemble is the honest "before" (no stabilization): M_saddle_raw and
M_power_raw are the raw single-route persistence-image movements, in the SAME L2
currency as the J-member features, so the frontier reads as a fraction of raw.

Pre-registered grid, J, and the conservative-pick rule live in
docs/topo_eval/notes/m2_saddle_stable_prereg.md. This script REPORTS the frontier and
a suggested pick; the actual pick is committed separately, before any real-vs-real
null. Each realization is single-receiver D8, so its donor graph is a forest (first
Betti number 0) BY CONSTRUCTION; the averaging is in persistence-image space, never on
accumulation fields.

Run (smoke):
  .pixi/envs/cpu/bin/python scripts/m2_stabilized.py sweep \
      --manifest <tiles.json> --n-tiles 2 --J 8 --amps 0.5 1.0 --smoke
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from geo_tda.topo_eval.stabilized import (  # noqa: E402
    ensemble_diagrams, make_imager, persistence_image,
)
# probe helpers (module-level, lazy heavy imports inside): the megachannel control,
# the mass-moved effect size, and the staged-data locations / correlation length.
from saddle_stability_probe import (  # noqa: E402
    CORR_LEN_PX, DEM_DIR, NHD_DIR, _carve_trench, _mass_moved_fraction,
    _summaries_for_array,
)

# Pre-registered defaults (docs/topo_eval/notes/m2_saddle_stable_prereg.md).
AMPS_M = (0.25, 0.5, 1.0, 2.0)   # marginalization base-amplitude grid (metres)
J_DEFAULT = 16                   # ensemble size
STRESS_AMP_M = 2.0               # validation stress: a saddle-flipping correlated field
CONTROL_LENFRAC = 1.0            # megachannel length fraction -> the largest reroute


def _correlated_field(shape, amp_m, rng):
    """One correlated perturbation field at amplitude amp_m (metres), probe-style."""
    from scipy.ndimage import gaussian_filter
    cn = gaussian_filter(rng.normal(0.0, 1.0, shape), CORR_LEN_PX)
    cn *= amp_m / (cn.std() or 1.0)
    return cn


def _l2(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


def _ensemble_feature_paired(dem_m, profile, tau, J, amp, rng, pim, cap):
    """Stabilized feature, advancing rng so a later call can REPLAY the same draws.

    Returns (feature, rng_state_before) so the caller can restore the bit-generator to
    pair the marginalization noise across two base DEMs (orig vs stressed).
    """
    state = rng.bit_generator.state
    dgms = ensemble_diagrams(dem_m, profile, tau, J, amp, rng, local_scale="roughness")
    feat = np.mean([persistence_image(d, pim, cap) for d in dgms], axis=0)
    return feat, state


def _load_tile(spec, wd):
    """Materialize one probe tile: arr0 (metres), profile, frozen tau, acc0, dgm0."""
    import rasterio

    from geo_tda.topo_eval.construct_validity import stats_from_flowlines
    from geo_tda.topo_eval.pipeline import (
        _cell_km, _materialize_plain, _tile_area_km2, _tile_bbox_from_raster,
        tau_for_target_density,
    )
    key = spec["key"]
    dem = DEM_DIR / f"USGS_seamless_{key}_30m.tif"
    nhd = NHD_DIR / f"{key}.geojson"
    if not (dem.exists() and nhd.exists()):
        return None
    plain = _materialize_plain(dem)
    with rasterio.open(plain) as s:
        arr0 = s.read(1).astype("float64")
        profile = s.profile.copy()
        profile["dtype"] = "float64"
    bbox = _tile_bbox_from_raster(plain)
    area = _tile_area_km2(bbox)
    nhd_stats = stats_from_flowlines(nhd, area_km2=area)
    _d, _p, _c, acc0 = _summaries_for_array(arr0, profile, 1.0, wd)
    cell_km = _cell_km(bbox, acc0.shape)
    tau = tau_for_target_density(acc0, nhd_stats.drainage_density, area, cell_km)
    dgm0, _p, _c, acc0 = _summaries_for_array(arr0, profile, tau, wd)
    return {"key": key, "arr0": arr0, "profile": profile, "tau": float(tau),
            "acc0": acc0, "dgm0": dgm0}


def cmd_sweep(args) -> int:
    rng = np.random.default_rng(args.seed)
    amps = list(args.amps) if args.amps else list(AMPS_M)
    J = args.J
    tiles = json.loads(args.manifest.read_text())["tiles"][: args.n_tiles]
    print(f"sweep: {len(tiles)} tiles, J={J}, amps={amps}, "
          f"stress={args.stress_amp} m, seed={args.seed}", flush=True)

    # PASS 1: load tiles; build the fixed stress + megachannel variants; collect the
    # single-route diagrams that freeze the global imager grid (over EVERY variant that
    # appears, so neither the megachannel's large basin nor the stress is clipped).
    loaded, frozen_diags = [], []
    for spec in tiles:
        wd = Path(tempfile.mkdtemp(prefix=f"stab_{spec.get('key','t')}_"))
        try:
            t = _load_tile(spec, wd)
            if t is None:
                print(f"  skip {spec.get('key')}: not staged", flush=True)
                continue
            stress_field = _correlated_field(t["arr0"].shape, args.stress_amp,
                                             np.random.default_rng(args.seed + 1))
            arr_stress = t["arr0"] + stress_field
            arr_control = _carve_trench(t["arr0"], t["acc0"], CONTROL_LENFRAC)
            dgm_stress, _p, _c, _a = _summaries_for_array(arr_stress, t["profile"], t["tau"], wd)
            dgm_control, _p, _c, acc_c = _summaries_for_array(arr_control, t["profile"], t["tau"], wd)
            t.update({"arr_stress": arr_stress, "arr_control": arr_control,
                      "dgm_stress": dgm_stress, "dgm_control": dgm_control,
                      "control_f": _mass_moved_fraction(t["acc0"], acc_c)})
            frozen_diags += [t["dgm0"], dgm_stress, dgm_control]
            loaded.append(t)
            print(f"  loaded {t['key']}: tau={t['tau']:.4g} "
                  f"control_f={t['control_f']:.3f}", flush=True)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
    if not loaded:
        print("no tiles staged; nothing to sweep", flush=True)
        return 1

    pim, cap = make_imager(frozen_diags)
    print(f"frozen imager: cap={cap:.4g}, "
          f"feature_len={persistence_image(loaded[0]['dgm0'], pim, cap).size}", flush=True)

    # PASS 2: per tile, the raw (J=1) movements and the J-member frontier per amplitude.
    rows = []
    for t in loaded:
        pi0 = persistence_image(t["dgm0"], pim, cap)
        pis = persistence_image(t["dgm_stress"], pim, cap)
        pic = persistence_image(t["dgm_control"], pim, cap)
        m_saddle_raw = _l2(pis, pi0)
        m_power_raw = _l2(pic, pi0)
        per_amp = []
        for amp in amps:
            # PAIRED marginalization noise for orig vs stress (variance reduction).
            f_orig, state = _ensemble_feature_paired(
                t["arr0"], t["profile"], t["tau"], J, amp, rng, pim, cap)
            rng.bit_generator.state = state
            f_stress, _ = _ensemble_feature_paired(
                t["arr_stress"], t["profile"], t["tau"], J, amp, rng, pim, cap)
            # control uses a fresh (independent) stream; its base differs by ~50 m so
            # pairing buys nothing.
            f_ctrl, _ = _ensemble_feature_paired(
                t["arr_control"], t["profile"], t["tau"], J, amp, rng, pim, cap)
            for f in (f_orig, f_stress, f_ctrl):
                assert np.all(np.isfinite(f)), "non-finite stabilized feature"
            m_saddle = _l2(f_stress, f_orig)
            m_power = _l2(f_ctrl, f_orig)
            per_amp.append({
                "amp_m": amp,
                "m_saddle": m_saddle, "m_power": m_power,
                "saddle_frac_of_raw": m_saddle / m_saddle_raw if m_saddle_raw else None,
                "power_frac_of_raw": m_power / m_power_raw if m_power_raw else None,
                "rho_saddle_over_power": m_saddle / m_power if m_power else None,
            })
            print(f"    {t['key']} amp={amp:>4}: M_saddle={m_saddle:.4g} "
                  f"({m_saddle / m_saddle_raw:.2f}x raw) M_power={m_power:.4g} "
                  f"({m_power / m_power_raw:.2f}x raw)", flush=True)
        rows.append({"key": t["key"], "tau": t["tau"], "control_f": t["control_f"],
                     "m_saddle_raw": m_saddle_raw, "m_power_raw": m_power_raw,
                     "by_amp": per_amp})

    # AGGREGATE frontier: median across tiles of each amp's fractions, and the
    # conservative-pick suggestion (largest amp whose saddle is flattened while power
    # is retained). The thresholds here are SUGGESTIONS for the pre-registered pick,
    # not the gate (the gate is defined on the stabilized statistic at Stage 1).
    def med(amp, key):
        vals = [a[key] for r in rows for a in r["by_amp"]
                if a["amp_m"] == amp and a[key] is not None]
        return float(np.median(vals)) if vals else None

    frontier = []
    for amp in amps:
        frontier.append({
            "amp_m": amp,
            "median_saddle_frac_of_raw": med(amp, "saddle_frac_of_raw"),
            "median_power_frac_of_raw": med(amp, "power_frac_of_raw"),
            "median_rho_saddle_over_power": med(amp, "rho_saddle_over_power"),
        })
    flattened = [f for f in frontier
                 if f["median_saddle_frac_of_raw"] is not None
                 and f["median_saddle_frac_of_raw"] <= args.saddle_flat_frac
                 and f["median_power_frac_of_raw"] is not None
                 and f["median_power_frac_of_raw"] >= args.power_keep_frac]
    suggested = max((f["amp_m"] for f in flattened), default=None)

    out = {
        "stage": "0.5_amplitude_sweep",
        "J": J, "amps_m": amps, "stress_amp_m": args.stress_amp,
        "control_lenfrac": CONTROL_LENFRAC, "seed": args.seed,
        "imager_cap": float(cap),
        "suggested_pick_amp_m": suggested,
        "suggested_pick_rule": (
            f"largest amp with median M_saddle <= {args.saddle_flat_frac} of raw AND "
            f"median M_power >= {args.power_keep_frac} of raw (SUGGESTION; the "
            "pre-registered pick is committed separately, before any real-vs-real null)"),
        "frontier": frontier,
        "rows": rows,
        "note": ("Stage 0.5 diagnostic on the saddle-probe corpus. M_saddle should "
                 "fall with amp (stabilization), M_power should stay near raw "
                 "(non-vacuity). Marginalization and stress perturbations are distinct "
                 "RNG streams; orig-vs-stress marginalization noise is paired. Each "
                 "realization is single-receiver D8 (a forest, first Betti number 0)."),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print("\n=== STAGE 0.5 FRONTIER (median across tiles) ===", flush=True)
    for f in frontier:
        print(f"  amp={f['amp_m']:>4} m: saddle {f['median_saddle_frac_of_raw']:.2f}x raw, "
              f"power {f['median_power_frac_of_raw']:.2f}x raw, "
              f"rho={f['median_rho_saddle_over_power']:.3f}", flush=True)
    print(f"  suggested pick: {suggested} m", flush=True)
    print(f"wrote {args.out.relative_to(ROOT)}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Saddle-stable statistic driver")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sw = sub.add_parser("sweep", help="Stage 0.5 amplitude sweep (elis, probe corpus)")
    sw.add_argument("--manifest", type=Path, required=True)
    sw.add_argument("--n-tiles", type=int, default=5)
    sw.add_argument("--J", type=int, default=J_DEFAULT)
    sw.add_argument("--amps", type=float, nargs="*", default=None,
                    help="marginalization base amplitudes (m); default = pre-reg grid")
    sw.add_argument("--stress-amp", type=float, default=STRESS_AMP_M)
    sw.add_argument("--seed", type=int, default=0)
    sw.add_argument("--saddle-flat-frac", type=float, default=0.25,
                    help="suggestion only: M_saddle this fraction of raw counts as flat")
    sw.add_argument("--power-keep-frac", type=float, default=0.75,
                    help="suggestion only: M_power must stay >= this fraction of raw")
    sw.add_argument("--smoke", action="store_true", help="(reserved) smaller defaults")
    sw.add_argument("--out", type=Path,
                    default=Path("results/validity/m2_stabilized_sweep.json"))
    sw.set_defaults(func=cmd_sweep)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
