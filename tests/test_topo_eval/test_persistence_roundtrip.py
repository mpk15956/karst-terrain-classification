"""The persistence diagram is the abelianization of the merge tree
(Theorem 2): every confluence contributes one finite pair, and each
basin contributes one essential class. Checks the elder-rule
bookkeeping on the confirmatory toys."""
from __future__ import annotations

import numpy as np
import pytest

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import (
    merge_tree_from_accumulation,
    persistence_diagram,
)

ALL_GRID_TOYS = syn.CONFIRMATORY + syn.ADVERSARIAL


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_finite_pairs_equal_confluence_count(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    diagram = persistence_diagram(tree)
    n_finite = sum(1 for _b, d in diagram if np.isfinite(d))
    assert n_finite == tree.num_confluences


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_one_essential_class_per_basin(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    diagram = persistence_diagram(tree)
    n_essential = sum(1 for _b, d in diagram if not np.isfinite(d))
    assert n_essential == len(tree.roots)


def test_v_valley_exact_diagram():
    toy = syn.v_valley()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    diagram = sorted(persistence_diagram(tree), key=lambda p: (p[0], p[1]))
    # two heads born at A=1; one dies at the confluence (A=7), one survives
    finite = [(b, d) for b, d in diagram if np.isfinite(d)]
    assert finite == [(1.0, 7.0)]
    essential = [(b, d) for b, d in diagram if not np.isfinite(d)]
    assert essential == [(1.0, float("inf"))]
