"""Adversarial toys: the donor flow graph gives the correct tree;
cubical 8-adjacency contaminates it (phantom merges, spurious cycles).

This is the empirical backing for the donor-graph adjacency contribution
(the sharpest surviving novelty per the folklore check)."""
from __future__ import annotations

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
from geo_tda.topo_eval.summaries import (
    cubical_confluence_cells,
    h1_cubical_mask,
    h1_donor_graph,
)


def test_tributary_contact_donor_one_true_confluence():
    toy = syn.tributary_contact()
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    assert tree.num_confluences == 1
    # the single confluence is the true downstream one at (5, 2)
    assert tree.internal_nodes[0].cell == (5, 2)


def test_tributary_contact_cubical_phantom_merge_upstream():
    toy = syn.tributary_contact()
    cubical = cubical_confluence_cells(toy.accumulation, toy.tau_channel)
    # cubical 8-adjacency invents a merge somewhere other than the true
    # confluence (5, 2): the phantom contamination the donor graph removes
    assert any(c != (5, 2) for c in cubical), (
        f"expected a phantom cubical merge; got {cubical}"
    )


def test_meander_neck_donor_is_a_forest():
    toy = syn.meander_neck()
    mask = toy.accumulation >= toy.tau_channel
    tree = merge_tree_from_accumulation(
        toy.flow_dir, toy.accumulation, toy.tau_channel
    )
    assert tree.num_confluences == 0  # single chain, no merge
    assert h1_donor_graph(toy.flow_dir, mask) == 0  # forest


def test_meander_neck_cubical_has_spurious_cycles():
    toy = syn.meander_neck()
    mask = toy.accumulation >= toy.tau_channel
    h1 = h1_cubical_mask(mask)
    assert h1 > 0, (
        f"expected spurious cubical cycles on the meander neck; got H1={h1}"
    )
