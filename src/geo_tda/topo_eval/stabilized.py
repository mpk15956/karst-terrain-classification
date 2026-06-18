"""Saddle-stable statistic: ensemble persistence-image feature, plus pruning.

Per the pre-registration (docs/topo_eval/notes/m2_saddle_stable_prereg.md). The base
sliced-Wasserstein-kernel MMD on per-realization H0 diagrams stays the primary
INTERPRETIVE statistic (theorem-backed, NHD-validated, names the axis). This module
provides the ATTRIBUTION/robustness statistic: the expectation, over J small
locally-scaled DEM perturbations, of the H0 persistence image on a frozen global
grid. The averaged feature is NOT a merge-tree invariant (no Strahler claim
attaches); it is the expected drainage organization under divide-migration
uncertainty.

Constraints honored (pre-registration):
- Each realization uses single-receiver D8, so its donor graph is a forest
  (beta1 = 0); the averaging happens in persistence-image space, never on
  accumulation fields.
- The PI grid and the essential-class cap are FROZEN once over the pooled corpus
  (a per-patch or per-realization grid would inject movement).
- Imaging is in log10-accumulation COORDINATES, not raw (heavy-tailed deaths span
  ~3.5 log decades; a linear grid collapses). See _logc and the 2026-06-18
  pre-registration amendment; log the coordinates, never the persistence value.
- tau is frozen per patch on the unperturbed DEM; merge_tree recomputes the mask
  {A >= tau} on each realization's perturbed accumulation at that frozen threshold.
- The PI weight vanishes on the diagonal (persim default), satisfying the Adams
  2017 stability conditions; the kernel covariance is set to one pixel.

Pure functions (prune_diagram, make_imager, persistence_image, features,
feature_distance_matrix) operate on cached diagrams with no whitebox. The ensemble
functions call whitebox D8 per realization.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

PI_PIXELS = 30        # ~30 pixels across the (capped) persistence axis
CORR_LEN_PX = 4       # correlated-noise length, matching the saddle probe
ROUGHNESS_WIN = 5     # window for the local-roughness amplitude scaling
ESS_MARGIN = 0.5      # log10 units: essential cap = max finite log10-death + this


def _logc(d) -> np.ndarray:
    """(birth, death) -> (log10 birth, log10 death); essentials keep death = inf.

    Imaging is in log10-accumulation COORDINATES because flow accumulation is heavy
    tailed (deaths span ~3.5 log decades; births pin near tau, ~115-512): a linear
    grid buries ~85% of features in one pixel (the grid-collapse this fixes). Logging
    the COORDINATES keeps the diagonal at persistence' = log(d/b) = 0, where the Adams
    weight must vanish; logging the persistence VALUE would send the diagonal to -inf
    and break that condition (the trap). The transform is strictly monotone, so the
    merge-tree combinatorics and the cardinality exponent N are unchanged, and on the
    masked range A >= tau it is a (1/(tau ln10))-Lipschitz CONTRACTION, so the Adams
    stability bound only improves (constant C_Adams |G| / (tau ln10)). Justified by
    heavy-tailedness, NOT a power-law/Hack exponent (which is on A, not the deaths).
    See docs/topo_eval/notes/m2_saddle_stable_prereg.md (2026-06-18 amendment).
    """
    a = np.asarray(d, float).reshape(-1, 2).copy()
    a[:, 0] = np.log10(np.maximum(a[:, 0], 1.0))
    fin = np.isfinite(a[:, 1])
    a[fin, 1] = np.log10(np.maximum(a[fin, 1], 1.0))
    return a


def diagram_cap(diagrams) -> float:
    """Global essential-class cap in log10-accumulation coordinates.

    Essentials (death = inf) are capped a fixed ADDITIVE margin above the largest
    finite log10-death in the pooled corpus (one essential band above the finite
    mass). A multiplicative 1.5x in log space would place essentials at 10^(1.5*max)
    accumulation, far past the |G| cell-count ceiling, so it is wrong here.
    """
    fins = []
    for d in diagrams:
        a = _logc(d)
        fins.append(a[np.isfinite(a[:, 1]), 1])
    fin = np.concatenate(fins) if fins else np.array([1.0])
    return float(fin.max() + ESS_MARGIN) if fin.size else 1.0


def _capped(d, cap) -> np.ndarray:
    """log10-accumulation coordinates with essentials set to the frozen cap."""
    a = _logc(d)
    a[~np.isfinite(a[:, 1]), 1] = cap
    return a


def prune_diagram(d, eps: float):
    """Drop finite classes with persistence < eps; keep essentials (death = inf)."""
    a = np.asarray(d, float).reshape(-1, 2)
    if eps <= 0:
        return a.copy()
    fin = np.isfinite(a[:, 1])
    keep = (~fin) | ((a[:, 1] - a[:, 0]) >= eps)
    return a[keep].copy()


def make_imager(diagrams, cap: float | None = None, pixels: int = PI_PIXELS):
    """Frozen global PersistenceImager, fit ONCE on the pooled corpus.

    Returns (imager, cap). Ranges, pixel size, and kernel covariance are fixed here
    so every patch and every realization is imaged on the identical grid.
    """
    from persim import PersistenceImager
    if cap is None:
        cap = diagram_cap(diagrams)
    # Size pixels to the PERSISTENCE span (pixels across the persistence axis), not the
    # death cap. In log coordinates births are not negligible relative to persistence,
    # so cap-sized pixels would over-smooth; persistence-sized pixels give the
    # pre-registered ~PI_PIXELS resolution and a one-pixel kernel near the verified
    # sigma. Ranges are tight to the pooled (capped) corpus so the grid is frozen.
    min_birth, max_birth, max_pers = np.inf, 0.0, 0.0
    for d in diagrams:
        a = _capped(d, cap)
        if a.size:
            min_birth = min(min_birth, float(a[:, 0].min()))
            max_birth = max(max_birth, float(a[:, 0].max()))
            max_pers = max(max_pers, float((a[:, 1] - a[:, 0]).max()))
    if not np.isfinite(min_birth):
        min_birth, max_birth, max_pers = 0.0, cap, cap
    ps = (max_pers / pixels) if max_pers > 0 else (cap / pixels)
    pim = PersistenceImager(
        birth_range=(min_birth, max_birth if max_birth > min_birth else min_birth + ps),
        pers_range=(0.0, max_pers if max_pers > 0 else cap),
        pixel_size=ps,
        kernel_params={"sigma": [[ps ** 2, 0.0], [0.0, ps ** 2]]},
    )
    return pim, float(cap)


def persistence_image(d, pim, cap: float) -> np.ndarray:
    """Flatten the persistence image of one diagram (essentials capped)."""
    a = _capped(d, cap)
    return np.asarray(pim.transform(a, skew=True), float).ravel()


def features(diagrams, pim, cap: float) -> np.ndarray:
    return np.array([persistence_image(d, pim, cap) for d in diagrams])


def feature_distance_matrix(feats) -> np.ndarray:
    """Pairwise Euclidean (L2) distance matrix over PI feature vectors.

    A drop-in for the sliced-Wasserstein matrix: mmd2_from_matrix / global_sigma /
    spatial_split_null_indexed all operate on it unchanged. The kernel sigma MUST be
    re-derived in this feature space (do not reuse the SW sigma).
    """
    F = np.asarray(feats, float)
    g = (F * F).sum(1)
    d2 = g[:, None] + g[None, :] - 2.0 * (F @ F.T)
    np.maximum(d2, 0.0, out=d2)
    D = np.sqrt(d2)
    np.fill_diagonal(D, 0.0)  # exact zero self-distance (kill the |a|^2+|b|^2-2ab roundoff)
    return D


def _local_roughness(dem: np.ndarray, win: int = ROUGHNESS_WIN) -> np.ndarray:
    """Windowed standard deviation of elevation, the local DEM-error scale."""
    from scipy.ndimage import uniform_filter
    m = uniform_filter(dem, win)
    m2 = uniform_filter(dem * dem, win)
    return np.sqrt(np.maximum(m2 - m * m, 0.0))


def ensemble_diagrams(dem_m, profile, tau, J, base_amp_m, rng,
                      local_scale: str = "roughness", workdir=None):
    """J H0 diagrams of (DEM + locally-scaled correlated noise), each D8-routed.

    dem_m must be in METRES (the caller rescales generated [0,1] patches to a physical
    relief first, so the additive perturbation means the same thing on both). The j=0
    member is the unperturbed DEM, so the ensemble is centered on the real routing.
    Each diagram is from single-receiver D8 (a forest, beta1 = 0).
    """
    from scipy.ndimage import gaussian_filter
    import rasterio
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
    from geo_tda.topo_eval.merge_tree import (
        merge_tree_from_accumulation, persistence_diagram,
    )
    own = workdir is None
    wd = Path(tempfile.mkdtemp(prefix="ens_")) if own else Path(workdir)
    try:
        if local_scale == "roughness":
            r = _local_roughness(dem_m)
            scale = r / (float(np.median(r)) or 1.0)
        elif local_scale == "uniform":
            scale = np.ones_like(dem_m)
        else:
            raise ValueError(f"local_scale must be 'roughness' or 'uniform', got {local_scale!r}")
        out = []
        for j in range(J):
            if j == 0:
                arr = np.asarray(dem_m, float)
            else:
                cn = gaussian_filter(rng.normal(0, 1, dem_m.shape), CORR_LEN_PX)
                cn *= 1.0 / (cn.std() or 1.0)
                arr = np.asarray(dem_m, float) + base_amp_m * scale * cn
            tif = wd / f"r{j}.tif"
            prof = {**profile, "driver": "GTiff", "compress": "none",
                    "tiled": False, "count": 1}
            with rasterio.open(tif, "w", **prof) as dst:
                dst.write(arr.astype(profile["dtype"]), 1)
            codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
            tree = merge_tree_from_accumulation(codes, accum, tau)
            dgm = [(b, d if d is not None else np.inf)
                   for (b, d) in persistence_diagram(tree)]
            out.append(np.asarray(dgm, float).reshape(-1, 2))
        return out
    finally:
        if own:
            shutil.rmtree(wd, ignore_errors=True)


def ensemble_feature(dem_m, profile, tau, J, base_amp_m, rng, pim, cap, **kw):
    """Mean persistence image over the J ensemble realizations (the stabilized feature)."""
    dgms = ensemble_diagrams(dem_m, profile, tau, J, base_amp_m, rng, **kw)
    return np.mean([persistence_image(d, pim, cap) for d in dgms], axis=0)
