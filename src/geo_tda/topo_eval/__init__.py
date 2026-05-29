"""Topological evaluation of terrain: flow-accumulation merge trees.

The headline construction of the topo-eval methods paper. The merge tree
of a DEM's flow-accumulation field, built on the D8 flow graph (donor
adjacency, not spatial-grid adjacency), restricted to a channel mask.
Horton-Strahler stream order is a coarsening of this merge tree; the
persistence diagram is a strictly lossier coarsening (its abelianization).

See docs/topo_eval/proofs/strahler_merge_tree.qmd for the theory and
docs/topo_eval/notes/orientation_spike.md for the empirical validation
of the construction choices (donor vs cubical adjacency; sublevel-
increasing vs superlevel-decreasing direction).
"""
from __future__ import annotations

from geo_tda.topo_eval.merge_tree import (
    MergeNode,
    MergeTree,
    merge_tree_from_accumulation,
    persistence_diagram,
)

__all__ = [
    "MergeNode",
    "MergeTree",
    "merge_tree_from_accumulation",
    "persistence_diagram",
]
