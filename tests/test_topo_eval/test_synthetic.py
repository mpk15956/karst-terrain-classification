"""Confirmatory toys: the donor-graph merge tree reproduces the
analytical drainage answer (Lemma + Theorem 1)."""
from __future__ import annotations

import pytest

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation


@pytest.mark.parametrize("gen", syn.CONFIRMATORY, ids=lambda g: g.__name__)
def test_confirmatory_toy_matches_analytical_answer(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    assert len(tree.leaves) == toy.expected_leaves, toy.name
    assert tree.num_confluences == toy.expected_confluences, toy.name
    assert len(tree.roots) == 1, f"{toy.name}: single-basin toy"
    assert tree.roots[0].strahler == toy.expected_root_strahler, toy.name
    assert tree.strahler_distribution() == toy.expected_strahler_dist, toy.name
