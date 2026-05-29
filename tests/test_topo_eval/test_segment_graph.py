"""Segment-graph aligns PH to the NHD/whitebox representation.

Two invariants the alignment must preserve:

- Strahler distribution is invariant under segment-collapse (the multiset
  rule depends only on rooted-tree combinatorial type, which the collapse
  preserves).
- Junction count equals the merge-tree's internal-node count (degree-2
  runs were already collapsed during the donor union-find).

Plus the falsification witness still separates after collapse: this is
the Theorem 2 claim about branching, which segment-collapse preserves."""
from __future__ import annotations

import pytest

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
from geo_tda.topo_eval.segment_graph import (
    bifurcation_ratio_largest_basin,
    segment_graph_from_merge_tree,
)

ALL_GRID_TOYS = syn.CONFIRMATORY + syn.ADVERSARIAL


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_strahler_invariant_under_segment_collapse(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    sg = segment_graph_from_merge_tree(tree)
    assert sg.strahler_distribution() == tree.strahler_distribution()


@pytest.mark.parametrize("gen", ALL_GRID_TOYS, ids=lambda g: g.__name__)
def test_junction_count_equals_merge_tree_confluences(gen):
    toy = gen()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    sg = segment_graph_from_merge_tree(tree)
    assert sg.num_junctions == tree.num_confluences


def test_falsification_still_separates_after_segment_collapse():
    pair = syn.falsification_pair()
    bal = segment_graph_from_merge_tree(pair.balanced).strahler_distribution()
    cat = segment_graph_from_merge_tree(pair.caterpillar).strahler_distribution()
    assert bal == {1: 4, 2: 2, 3: 1}
    assert cat == {1: 4, 2: 3}
    assert bal != cat


def test_largest_basin_rb_finite_on_branching_toy():
    toy = syn.branching_channel()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    rb = bifurcation_ratio_largest_basin(tree)
    # balanced 4-head tree: dist {1:4, 2:2, 3:1}, ratios 4/2=2 and 2/1=2,
    # mean 2.0. A finite sensible R_b matters; the exact value is the
    # value the multiset rule produces on a balanced tree.
    assert rb == pytest.approx(2.0)


def test_largest_basin_rb_handles_single_chain():
    toy = syn.cone()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    # only Strahler order 1 -> NaN, not crash
    import math

    assert math.isnan(bifurcation_ratio_largest_basin(tree))
