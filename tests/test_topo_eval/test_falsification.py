"""Theorem 2 witness: two merge trees with identical H0 barcodes but
different Strahler distributions. The persistence diagram cannot see
Strahler order; the merge tree can.

Per the round-4 discipline, the test MEASURES bottleneck distance between
the diagrams rather than assuming the equal-birth construction delivered
d_B = 0."""
from __future__ import annotations

import numpy as np

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import persistence_diagram


def _bottleneck(dgm_a, dgm_b) -> float:
    """Bottleneck distance, finite pairs only (essential classes match by
    construction here: one per tree, both (birth, inf))."""
    import gudhi

    fa = np.array([[b, d] for b, d in dgm_a if np.isfinite(d)], dtype=float)
    fb = np.array([[b, d] for b, d in dgm_b if np.isfinite(d)], dtype=float)
    return gudhi.bottleneck_distance(fa, fb)


def test_falsification_identical_barcodes():
    pair = syn.falsification_pair()
    dgm_bal = persistence_diagram(pair.balanced)
    dgm_cat = persistence_diagram(pair.caterpillar)

    # measured, not assumed: the diagrams coincide
    db = _bottleneck(dgm_bal, dgm_cat)
    assert db < 1e-8, f"barcodes should coincide; bottleneck={db}"

    # and the finite multisets are literally equal
    fin_bal = sorted((b, d) for b, d in dgm_bal if np.isfinite(d))
    fin_cat = sorted((b, d) for b, d in dgm_cat if np.isfinite(d))
    assert fin_bal == fin_cat


def test_falsification_different_strahler():
    pair = syn.falsification_pair()
    dist_bal = pair.balanced.strahler_distribution()
    dist_cat = pair.caterpillar.strahler_distribution()

    assert dist_bal != dist_cat
    assert pair.balanced.roots[0].strahler == 3
    assert pair.caterpillar.roots[0].strahler == 2
    assert dist_bal == {1: 4, 2: 2, 3: 1}
    assert dist_cat == {1: 4, 2: 3}


def test_falsification_wasserstein_strahler_separates():
    """The Strahler distributions are separated in Wasserstein-1, the
    Phase C distributional criterion, while the barcodes are not."""
    pair = syn.falsification_pair()

    def as_samples(dist):
        out = []
        for order, count in dist.items():
            out.extend([order] * count)
        return np.array(sorted(out), dtype=float)

    a = as_samples(pair.balanced.strahler_distribution())
    b = as_samples(pair.caterpillar.strahler_distribution())
    from scipy.stats import wasserstein_distance

    w = wasserstein_distance(a, b)
    assert w > 0.1, f"Strahler distributions should separate; W1={w}"
