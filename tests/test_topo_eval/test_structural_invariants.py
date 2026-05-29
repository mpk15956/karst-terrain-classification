"""Structural invariants that must hold on every generated merge tree:
the donor graph is a forest, every confluence has >= 2 donor components,
and no merges occur between flow-disconnected cells (guaranteed by the
donor construction). Regression guard for the Lemma's hypotheses."""
from __future__ import annotations

import pytest

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
from geo_tda.topo_eval.summaries import h1_donor_graph

ALL_GRID_TOYS = syn.CONFIRMATORY + syn.ADVERSARIAL


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_donor_graph_is_forest(gen):
    toy = gen()
    mask = toy.accumulation >= toy.tau_channel
    assert h1_donor_graph(toy.flow_dir, mask) == 0


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_every_confluence_has_at_least_two_children(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    for node in tree.internal_nodes:
        assert len(node.children) >= 2, (
            f"{toy.name}: confluence {node.cell} has "
            f"{len(node.children)} children"
        )


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_leaf_count_equals_strahler_order_one_count(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    dist = tree.strahler_distribution()
    assert dist.get(1, 0) == len(tree.leaves)
