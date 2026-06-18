"""Unit tests for the pure (no-whitebox) layer of the saddle-stable statistic.

Verifies the pre-registered correctness requirements that do not need extraction:
the frozen global PI grid (every input images to the same fixed length), pruning
semantics (essentials kept, low-persistence finite classes dropped, monotone), and
the L2 feature-distance matrix. The whitebox-dependent ensemble path is smoke-tested
separately on a staged DEM, not here.
"""
import pickle
from pathlib import Path

import numpy as np
import pytest

from geo_tda.topo_eval import stabilized as st

CACHE = Path(__file__).resolve().parent.parent / "results" / "validity" / "m2_diag_cache"


def _cached_real():
    pop = pickle.loads((CACHE / "diagrams.pkl").read_bytes())
    return [np.asarray(d, float) for k in pop for d in pop[k]]


def test_prune_keeps_essentials_and_drops_low_persistence():
    d = np.array([[0.0, np.inf],        # essential, must survive any eps
                  [1.0, 2.0],           # persistence 1
                  [1.0, 5.0],           # persistence 4
                  [1.0, 100.0]])        # persistence 99
    p2 = st.prune_diagram(d, eps=3.0)
    assert np.isinf(p2[:, 1]).sum() == 1, "essential dropped"
    finite = p2[np.isfinite(p2[:, 1])]
    assert finite.shape[0] == 2 and (finite[:, 1] - finite[:, 0] >= 3.0).all()
    # monotone: larger eps keeps fewer points
    sizes = [len(st.prune_diagram(d, e)) for e in (0.0, 3.0, 50.0, 1e9)]
    assert sizes == sorted(sizes, reverse=True)
    assert sizes[0] == 4 and sizes[-1] == 1  # eps=0 keeps all; huge eps keeps only essential


def test_frozen_grid_constant_feature_length():
    diags = _cached_real()[:40]
    pim, cap = st.make_imager(diags)
    lengths = {len(st.persistence_image(d, pim, cap)) for d in diags}
    assert len(lengths) == 1, "frozen grid must give a constant feature length"
    L = lengths.pop()
    assert L > 0, "grid collapsed to length 0 (the linear-coords birth-axis bug)"
    # pruning the input must NOT change the grid / feature length
    pruned = st.prune_diagram(diags[0], eps=5000.0)
    assert len(st.persistence_image(pruned, pim, cap)) == L


def test_log_grid_resolves_both_axes_on_heavy_tailed_data():
    # Regression for the linear-coords collapse: raw flow-accumulation diagrams have
    # births ~1e2 and deaths ~1e5, so a square-pixel linear grid sized to the death
    # axis gave the birth axis 0 pixels (feature length 0). log10 coordinates must
    # produce a genuine 2D image with both axes resolved (> 1 pixel).
    diags = _cached_real()[:40]
    pim, cap = st.make_imager(diags)
    img2d = np.asarray(pim.transform(st._capped(diags[0], cap), skew=True), float)
    assert img2d.ndim == 2 and min(img2d.shape) >= 2, f"birth axis collapsed: {img2d.shape}"
    # the cap lives in log space, comfortably below the |G| cell-count ceiling
    assert cap < 9.0, f"essential cap {cap} is implausibly large for log10-accumulation"


def test_persistence_image_finite_and_nonnegative():
    diags = _cached_real()[:10]
    pim, cap = st.make_imager(_cached_real()[:40])
    F = st.features(diags, pim, cap)
    assert np.isfinite(F).all()
    assert (F >= -1e-9).all(), "persistence image with a non-negative weight/kernel"


def test_feature_distance_matrix_matches_bruteforce():
    rng = np.random.default_rng(0)
    F = rng.normal(size=(12, 37))
    D = st.feature_distance_matrix(F)
    assert D.shape == (12, 12)
    assert np.allclose(D, D.T) and np.allclose(np.diag(D), 0.0, atol=1e-9)
    bf = np.sqrt(((F[3] - F[7]) ** 2).sum())
    assert np.isclose(D[3, 7], bf)


def test_cap_log_space_additive_convention():
    # essentials capped an ADDITIVE margin above the max finite log10-death (a
    # multiplicative 1.5x in log space would overshoot past the |G| cell ceiling)
    diags = _cached_real()
    cap = st.diagram_cap(diags)
    logfin = np.concatenate(
        [np.log10(np.maximum(d[np.isfinite(d[:, 1]), 1], 1.0)) for d in diags])
    assert np.isclose(cap, logfin.max() + st.ESS_MARGIN)
