"""Two-sample distributional test on H0 flow-accumulation diagrams (M2 gate).

Sliced-Wasserstein-kernel MMD (Carriere-Cuturi-Oudot 2017 + Gretton 2012) with
a SPATIAL-split real-vs-real null. Patches from the same 1-degree tile are
spatially autocorrelated (shared drainage), so the null must split by TILE,
not by random patch, or the band is artificially tight and a generated-vs-real
difference clears a floor that is too low (a false-positive headline). See
docs/topo_eval/notes/m2_distributional_gate.md.

Pure statistics over diagrams (no IO/whitebox), so it is unit-testable and the
H0-diagram extraction (whitebox-dependent) lives in the driver.
"""
from __future__ import annotations

import numpy as np


def sliced_wasserstein(dgm_a, dgm_b, M: int = 50) -> float:
    """SW1 between two H0 diagrams; essentials capped at a common finite death."""
    a = np.asarray(dgm_a, dtype=float).reshape(-1, 2)
    b = np.asarray(dgm_b, dtype=float).reshape(-1, 2)
    fin = np.concatenate([a[np.isfinite(a[:, 1]), 1], b[np.isfinite(b[:, 1]), 1]])
    cap = (fin.max() * 1.5) if fin.size else 1.0
    a[~np.isfinite(a[:, 1]), 1] = cap
    b[~np.isfinite(b[:, 1]), 1] = cap
    try:
        from persim import sliced_wasserstein
        return float(sliced_wasserstein(a, b, M=M))
    except Exception:
        from gudhi.representations import SlicedWassersteinDistance
        return float(SlicedWassersteinDistance(num_directions=M).fit([a]).transform([b])[0][0])


def sw_distance_matrix(pop, M: int = 50) -> np.ndarray:
    """Symmetric pairwise SW distance matrix over a list of diagrams."""
    n = len(pop)
    D = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            D[i, j] = D[j, i] = sliced_wasserstein(pop[i], pop[j], M=M)
    return D


def _kernel_from_dist(D, sigma):
    return np.exp(-(D ** 2) / (2.0 * sigma ** 2))


def mmd2(pop_a, pop_b, M: int = 50, sigma: float | None = None) -> float:
    """Biased MMD^2 with the SW Gaussian kernel; sigma via the median heuristic."""
    pop = list(pop_a) + list(pop_b)
    na, nb = len(pop_a), len(pop_b)
    D = sw_distance_matrix(pop, M=M)
    if sigma is None:
        off = D[np.triu_indices(len(pop), k=1)]
        sigma = float(np.median(off[off > 0])) if np.any(off > 0) else 1.0
    K = _kernel_from_dist(D, sigma)
    Kaa = K[:na, :na]; Kbb = K[na:, na:]; Kab = K[:na, na:]
    # unbiased within-block diagonals removed
    saa = (Kaa.sum() - np.trace(Kaa)) / (na * (na - 1)) if na > 1 else 0.0
    sbb = (Kbb.sum() - np.trace(Kbb)) / (nb * (nb - 1)) if nb > 1 else 0.0
    sab = Kab.mean() if na and nb else 0.0
    return float(saa + sbb - 2 * sab)


def spatial_split_null(pop_by_tile: dict, tiles_per_group: int, reps: int,
                       rng, M: int = 50, sigma: float | None = None) -> list[float]:
    """Real-vs-real MMD^2 distribution under SPATIAL splits.

    Each rep draws two DISJOINT groups of whole tiles and computes MMD between
    their pooled patch populations. Splitting by tile (not patch) makes the two
    subpopulations as independent as the generated-vs-real comparison, so the
    null band is not deflated by within-tile autocorrelation.
    """
    tiles = list(pop_by_tile)
    out = []
    for _ in range(reps):
        if len(tiles) < 2 * tiles_per_group:
            break
        pick = rng.permutation(len(tiles))
        ga = [tiles[k] for k in pick[:tiles_per_group]]
        gb = [tiles[k] for k in pick[tiles_per_group:2 * tiles_per_group]]
        pa = [d for t in ga for d in pop_by_tile[t]]
        pb = [d for t in gb for d in pop_by_tile[t]]
        if pa and pb:
            out.append(mmd2(pa, pb, M=M, sigma=sigma))
    return out


def mmd2_from_matrix(D, idx_a, idx_b, sigma) -> float:
    """Biased MMD^2 from a PRECOMPUTED SW distance matrix D over all items.

    The matrix is computed once; every MMD is an index lookup, so the power
    analysis does not recompute millions of pairwise SW distances. sigma is
    fixed globally (not per split) so kernels are comparable across reps.
    """
    ia = np.asarray(idx_a); ib = np.asarray(idx_b)
    K = np.exp(-(D ** 2) / (2.0 * sigma ** 2))
    Kaa = K[np.ix_(ia, ia)]; Kbb = K[np.ix_(ib, ib)]; Kab = K[np.ix_(ia, ib)]
    na, nb = len(ia), len(ib)
    saa = (Kaa.sum() - np.trace(Kaa)) / (na * (na - 1)) if na > 1 else 0.0
    sbb = (Kbb.sum() - np.trace(Kbb)) / (nb * (nb - 1)) if nb > 1 else 0.0
    return float(saa + sbb - 2 * Kab.mean())


def global_sigma(D) -> float:
    off = D[np.triu_indices(D.shape[0], k=1)]
    return float(np.median(off[off > 0])) if np.any(off > 0) else 1.0


def spatial_split_null_indexed(tile_to_idx: dict, D, tiles_per_group: int,
                               reps: int, rng, sigma: float) -> list[float]:
    """Real-vs-real MMD^2 under SPATIAL (by-tile) splits, via the SW matrix."""
    tiles = list(tile_to_idx); out = []
    for _ in range(reps):
        if len(tiles) < 2 * tiles_per_group:
            break
        p = rng.permutation(len(tiles))
        ia = [i for k in p[:tiles_per_group] for i in tile_to_idx[tiles[k]]]
        ib = [i for k in p[tiles_per_group:2 * tiles_per_group] for i in tile_to_idx[tiles[k]]]
        if ia and ib:
            out.append(mmd2_from_matrix(D, ia, ib, sigma))
    return out


def power_curve_indexed(tile_to_idx: dict, D, sizes, reps: int, rng,
                        sigma: float) -> list[dict]:
    rows = []
    for s in sizes:
        n = spatial_split_null_indexed(tile_to_idx, D, s, reps, rng, sigma)
        if n:
            rows.append({"tiles_per_group": int(s), "reps": len(n),
                         "null_mmd2_median": float(np.median(n)),
                         "null_mmd2_p95": float(np.percentile(n, 95)),
                         "null_mmd2_max": float(np.max(n))})
    return rows


def power_curve(pop_by_tile: dict, sizes, reps: int, rng, M: int = 50) -> list[dict]:
    """Null-band (p95 of spatial real-vs-real MMD^2) vs tiles-per-group size."""
    rows = []
    for s in sizes:
        nulls = spatial_split_null(pop_by_tile, s, reps, rng, M=M)
        if nulls:
            rows.append({"tiles_per_group": int(s), "reps": len(nulls),
                         "null_mmd2_median": float(np.median(nulls)),
                         "null_mmd2_p95": float(np.percentile(nulls, 95)),
                         "null_mmd2_max": float(np.max(nulls))})
    return rows
