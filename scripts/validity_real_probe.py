"""Phase C FID-blind found-pairs probe (Milestone 1.5 diagnostic).

Searches the real-tile corpus for a pair that is CLOSE in FID-feature
space (visually similar to an Inception-style feature extractor) but FAR
in flow-accumulation persistence (divergent drainage topology). Such a
pair is the FID-blind-to-drainage demonstration in miniature.

The outcome decides Milestone 1.5's scope:
- a convincing natural pair (feature-close, topology-far beyond the
  corpus 95th percentile) means 1.5 reduces to polishing that figure;
- only weak natural pairs means 1.5 needs gradient-based adversarial DEM
  construction, scoped as its own milestone.

The FID side is a PROXY: pooled features of a pretrained Inception
network, with pairwise L2 distance standing in for FID (true FID is a
distribution-level quantity; for a per-pair probe the feature distance is
the honest analogue). The FID threshold is a placeholder until baseline
corpus FID values are measured, per the plan. The topological-divergence
threshold IS pre-registered: Wasserstein-1 between H0 diagrams exceeding
the 95th percentile of the corpus's pairwise PD-distance distribution.

Network + compute dependent. --quick for a smoke run.
"""
from __future__ import annotations

import argparse
import json
import itertools
from pathlib import Path

import numpy as np

from geo_tda.topo_eval.pipeline import acquire_tiles

DEFAULT_BBOX = (-86.0, 35.0, -85.0, 36.0)


def _inception_features(dem_paths: list[Path]) -> np.ndarray:
    """Pooled Inception features per tile (FID-space proxy).

    Loads each DEM, normalizes to a 3-channel 299x299 image, and returns
    the pooled feature vector. Requires torch + torchvision.
    """
    import torch
    import torchvision.models as models
    import torchvision.transforms.functional as TF
    import rasterio

    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = models.inception_v3(weights=models.Inception_V3_Weights.DEFAULT)
    net.fc = torch.nn.Identity()  # pooled features, no classification head
    net.eval().to(device)

    feats = []
    with torch.no_grad():
        for p in dem_paths:
            with rasterio.open(p) as src:
                arr = src.read(1).astype("float32")
            finite = np.isfinite(arr)
            if finite.any():
                lo, hi = arr[finite].min(), arr[finite].max()
                arr = np.where(finite, (arr - lo) / (hi - lo + 1e-9), 0.0)
            t = torch.from_numpy(arr)[None, None].to(device)
            t = TF.resize(t, [299, 299], antialias=True).repeat(1, 3, 1, 1)
            t = (t - 0.5) / 0.5
            feats.append(net(t).cpu().numpy().ravel())
    return np.array(feats)


def _pd_distances(dem_paths: list[Path], tau_channel: float) -> tuple[list, np.ndarray]:
    """Per-tile flow-accumulation H0 diagrams and pairwise bottleneck dists."""
    import gudhi

    from geo_tda.topo_eval.filtrations import filtration_from_dem

    diagrams = []
    keep = []
    for p in dem_paths:
        try:
            _tree, diagram, _A = filtration_from_dem(p, tau_channel=tau_channel)
            finite = np.array(
                [[b, d] for b, d in diagram if np.isfinite(d)], dtype=float
            )
            diagrams.append(finite)
            keep.append(p)
        except Exception:  # noqa: BLE001
            continue

    n = len(diagrams)
    D = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        d = gudhi.bottleneck_distance(diagrams[i], diagrams[j])
        D[i, j] = D[j, i] = d
    return keep, D


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C FID-blind found-pairs probe")
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    ap.add_argument("--n-tiles", type=int, default=50)
    ap.add_argument("--tau-channel", type=float, default=1000.0)
    ap.add_argument("--quick", action="store_true", help="smoke run, 3 tiles")
    ap.add_argument("--out", type=Path, default=Path("results/validity/probe.json"))
    args = ap.parse_args()

    n_tiles = 3 if args.quick else args.n_tiles
    tiles = acquire_tiles(tuple(args.bbox), n_tiles=n_tiles, fetch_nhd=False)
    if len(tiles) < 2:
        print("need >= 2 tiles for a pairwise probe; acquired", len(tiles))
        return 1

    dem_paths = [t.dem_path for t in tiles]
    keep, pd_dist = _pd_distances(dem_paths, args.tau_channel)
    if len(keep) < 2:
        print("need >= 2 processable tiles; got", len(keep))
        return 1

    feats = _inception_features(keep)
    # pairwise FID-proxy (feature L2) and the pre-registered PD threshold
    n = len(keep)
    fid_proxy = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        fid_proxy[i, j] = fid_proxy[j, i] = float(
            np.linalg.norm(feats[i] - feats[j])
        )

    triu = np.triu_indices(n, k=1)
    pd_vals = pd_dist[triu]
    pd_threshold = float(np.percentile(pd_vals, 95)) if len(pd_vals) else 0.0

    # best found pair: among pairs with PD divergence above threshold,
    # the one with the smallest FID proxy (most "FID says identical,
    # topology says different")
    candidates = []
    for idx, (i, j) in enumerate(zip(*triu)):
        candidates.append(
            {
                "tile_a": Path(keep[i]).stem,
                "tile_b": Path(keep[j]).stem,
                "fid_proxy": float(fid_proxy[i, j]),
                "pd_bottleneck": float(pd_dist[i, j]),
                "above_pd_threshold": bool(pd_dist[i, j] >= pd_threshold),
            }
        )
    above = [c for c in candidates if c["above_pd_threshold"]]
    best = min(above, key=lambda c: c["fid_proxy"]) if above else None

    result = {
        "n_tiles": len(keep),
        "pd_threshold_95pct": pd_threshold,
        "fid_proxy_note": "Inception pooled-feature L2; placeholder for FID "
        "until baseline corpus FID measured",
        "best_found_pair": best,
        "verdict": (
            "natural pair found; Milestone 1.5 may reduce to polishing it"
            if best
            else "no natural pair above PD threshold; Milestone 1.5 likely "
            "needs adversarial DEM construction"
        ),
        "all_pairs": sorted(candidates, key=lambda c: c["fid_proxy"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "all_pairs"}, indent=2))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
