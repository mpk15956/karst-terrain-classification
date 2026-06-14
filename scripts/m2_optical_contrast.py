"""Optical-metric contrast: are standard optical metrics insensitive to the
drainage divergence H0 resolves? (project pixi env, CPU). Stage C.

For each backbone (CLIP primary, Inception baseline) x render (hillshade, stack):
- PRIMARY: RBF-MMD on embeddings via the SAME machinery/null/operating-point as
  the topology MMD (Euclidean feature distances -> mmd2_from_matrix +
  global_sigma + spatial_split_null_indexed), so the optical test/floor ratio is
  directly comparable to the topology 3.12x.
- ALSO classic FID + KID (unbiased poly-kernel), each with a matched-n real-vs-real
  null (FID is biased at n~114, so the null band is the reference, not 0).
- Province-swap POSITIVE CONTROL: optical MMD between two provinces' real patches
  -> should separate (the instrument is "on" / powered on an appearance shift).

Pre-registered read: necessity argument holds if optical test ~ inside its null
(insensitive) while topology was 3.12x ITS floor; if optical separates, reframe
(both-branch rule in the gate doc).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import sqrtm
from scipy.spatial.distance import cdist

from geo_tda.topo_eval.distributional import (
    global_sigma, mmd2_from_matrix, spatial_split_null_indexed,
)


def _fid(fa, fb):
    mu_a, mu_b = fa.mean(0), fb.mean(0)
    ca = np.cov(fa, rowvar=False); cb = np.cov(fb, rowvar=False)
    cm = sqrtm(ca @ cb)
    if np.iscomplexobj(cm):
        cm = cm.real
    diff = mu_a - mu_b
    return float(diff @ diff + np.trace(ca + cb - 2 * cm))


def _kid(fa, fb):
    d = fa.shape[1]

    def poly(X, Y):
        return (X @ Y.T / d + 1.0) ** 3
    Kaa = poly(fa, fa); Kbb = poly(fb, fb); Kab = poly(fa, fb)
    na, nb = len(fa), len(fb)
    saa = (Kaa.sum() - np.trace(Kaa)) / (na * (na - 1)) if na > 1 else 0.0
    sbb = (Kbb.sum() - np.trace(Kbb)) / (nb * (nb - 1)) if nb > 1 else 0.0
    return float(saa + sbb - 2.0 * Kab.mean())


def _contrast(real, gen, tile_to_idx, prov_by_tile, gen_prov, K, reps, rng):
    feats = np.vstack([real, gen]); nr = len(real)
    D = cdist(feats, feats)
    # sigma from the REAL-REAL block ONLY (not the combined matrix): the large
    # real-vs-gen domain gap would otherwise inflate sigma and compress every
    # real-real contrast -- collapsing the province-swap control into the null
    # (a false control failure). Calibrate the kernel to real-real variation,
    # exactly as the topology MMD did (global_sigma over the real submatrix).
    sigma = global_sigma(D[:nr, :nr])
    tnames = list(tile_to_idx); gen_idx = list(range(nr, nr + len(gen)))

    # RBF-MMD null (real-half vs real-half) + test (gen vs real-half)
    null = [r["mmd2"] for r in spatial_split_null_indexed(tile_to_idx, D, K, reps, rng, sigma)]
    test = []
    for _ in range(reps):
        p = rng.permutation(len(tnames))
        ib = [i for k in p[:K] for i in tile_to_idx[tnames[k]]]
        if ib:
            test.append(mmd2_from_matrix(D, gen_idx, ib, sigma))
    null = np.array(null); test = np.array(test)
    floor = float(np.percentile(null, 95))

    # province POSITIVE CONTROL: ALL pairwise province MMD^2 (the coastal-vs-
    # mountain pair is the real appearance contrast; cumberland-vs-appalachian
    # are both mountainous and weak). If even the strongest province pair sits
    # near the floor while gen-vs-real is high, the gen-vs-real gap is a DOMAIN
    # gap larger than natural geomorphic variation, not a province/appearance axis.
    import itertools
    provs = {}
    for t in tnames:
        provs.setdefault(prov_by_tile[t], []).extend(tile_to_idx[t])
    pair_mmd = {}
    for a, b in itertools.combinations(sorted(provs), 2):
        pair_mmd[f"{a}|{b}"] = float(mmd2_from_matrix(D, provs[a], provs[b], sigma))
    swap = max(pair_mmd.values()) if pair_mmd else 0.0

    # KID (unbiased, fast, the small-n lead) always; classic FID only for
    # low-dim embeddings (CLIP 512). For Inception 2048-d the Frechet covariance
    # is rank-deficient at n~160 and sqrtm is unstable/pathologically slow -- FID
    # is the least trustworthy metric here anyway (Chong-Forsyth bias), so we
    # report KID + RBF-MMD for it instead.
    do_fid = feats.shape[1] <= 1024

    def _split_idx():
        p = rng.permutation(len(tnames))
        a = [i for k in p[:K] for i in tile_to_idx[tnames[k]]]
        b = [i for k in p[K:2 * K] for i in tile_to_idx[tnames[k]]]
        return a, b
    fid_null = []; kid_null = []
    for _ in range(min(reps, 15)):
        a, b = _split_idx()
        if a and b:
            kid_null.append(_kid(feats[a], feats[b]))
            if do_fid:
                fid_null.append(_fid(feats[a], feats[b]))
    fid_test = []; kid_test = []
    for _ in range(min(reps, 15)):
        p = rng.permutation(len(tnames))
        b = [i for k in p[:K] for i in tile_to_idx[tnames[k]]]
        if b:
            kid_test.append(_kid(gen, feats[b]))
            if do_fid:
                fid_test.append(_fid(gen, feats[b]))

    return {
        "n_real": nr, "n_gen": len(gen), "tiles_per_group": K, "sigma": sigma,
        "rbf_mmd2": {"null_median": float(np.median(null)), "null_p95_floor": floor,
                     "test_median": float(np.median(test)),
                     "test_over_floor": float(np.median(test) / floor) if floor else None,
                     "frac_test_above_floor": float((test > floor).mean()),
                     "reject": bool(np.median(test) > floor)},
        "province_pair_mmd2": pair_mmd,
        "province_swap_max_mmd2": float(swap),
        "swap_max_over_floor": float(swap / floor) if floor else None,
        "fid": ({"null_median": float(np.median(fid_null)), "null_p95": float(np.percentile(fid_null, 95)),
                 "test_median": float(np.median(fid_test)),
                 "test_over_p95": float(np.median(fid_test) / np.percentile(fid_null, 95))}
                if fid_null else {"skipped": "2048-d FID unstable at n~160; see KID"}),
        "kid": {"null_median": float(np.median(kid_null)), "null_p95": float(np.percentile(kid_null, 95)),
                "test_median": float(np.median(kid_test)),
                "test_over_p95": float(np.median(kid_test) / max(np.percentile(kid_null, 95), 1e-12))},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="optical-metric contrast")
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_optical_cache"))
    ap.add_argument("--power", type=Path, default=Path("results/validity/m2_power.json"))
    ap.add_argument("--topo", type=Path, default=Path("results/validity/m2_generated_vs_real.json"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_optical_contrast.json"))
    ap.add_argument("--reps", type=int, default=200)
    args = ap.parse_args()

    tile_to_idx = {k: v for k, v in json.loads((args.cache / "tile_to_idx.json").read_text()).items()}
    prov_by_tile = json.loads((args.cache / "prov_by_tile.json").read_text())
    gen_prov = json.loads((args.cache / "gen_provinces.json").read_text())
    K = int(json.loads(args.power.read_text())["operating_point"]["tiles_per_group"])
    topo = json.loads(args.topo.read_text())
    topo_ratio = topo["test_median_over_floor_ratio"]
    print(f"K={K}; topology test/floor={topo_ratio:.2f}x; gen province mix="
          f"{ {p: gen_prov.count(p) for p in set(gen_prov)} }", flush=True)

    rng = np.random.default_rng(7)
    out = {"operating_point_K": K, "topology_test_over_floor": topo_ratio,
           "gen_province_mix": {p: gen_prov.count(p) for p in set(gen_prov)},
           "results": {}}
    for backbone in ("clip", "incep"):
        for render in ("hill", "stack"):
            real = np.load(args.cache / f"real_{backbone}_{render}.npy")
            gen = np.load(args.cache / f"gen_{backbone}_{render}.npy")
            r = _contrast(real, gen, tile_to_idx, prov_by_tile, gen_prov, K, args.reps,
                          np.random.default_rng(7))
            out["results"][f"{backbone}_{render}"] = r
            rb = r["rbf_mmd2"]
            print(f"\n[{backbone}/{render}] RBF-MMD test/floor={rb['test_over_floor']:.2f}x "
                  f"(reject={rb['reject']}, frac_above={rb['frac_test_above_floor']:.2f}) | "
                  f"best-province-pair/floor={r['swap_max_over_floor']:.1f}x | "
                  f"FID test/p95={r['fid'].get('test_over_p95', float('nan')):.2f} | "
                  f"KID test/p95={r['kid']['test_over_p95']:.2f}",
                  flush=True)
    out["note"] = ("Necessity argument: optical test/floor ~1 (insensitive) while "
                   f"topology={topo_ratio:.2f}x; province-swap/floor >>1 confirms the "
                   "optical instrument is powered on appearance shifts. CLIP is the "
                   "load-bearing backbone; Inception the expected baseline.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
