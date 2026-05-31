"""Segment-collapse the donor-graph merge tree to a NHD-comparable graph.

NHD flowlines are intrinsically segment objects: a junction is a single
geometric node connecting distinct reaches, not a run of cells. The
donor-graph merge tree's INTERNAL_NODES are already segment-comparable
(only true confluences create nodes; degree-2 extension cells silently
collapse during union-find, see merge_tree.py). But the merge-tree
representation does not expose segments as first-class objects, which the
NHD-side graph-builder needs to count junctions and Strahler order
identically on both sides.

This module materializes the segment graph from a merge tree:

- nodes: leaves (channel heads), internal nodes (confluences), roots
  (outlets). One node per merge-tree node.
- edges: parent-child links, weighted by the cell count along the
  collapsed degree-2 run.

The Strahler order at each segment-graph node equals the Strahler order
at the corresponding merge-tree node (the multiset rule depends only on
rooted-tree combinatorial type, which segment-collapse preserves), so the
Strahler distribution is invariant. Junction count IS the count of
internal segment-graph nodes; this is the metric whose comparison to NHD
needed alignment.

Horton bifurcation ratio: computed on the largest basin (root with the
most descendants), not the per-tile forest. The forest treatment
inflated R_b on real tiles where most "leaves" never merged with
anything (a sparse-mask artifact: per-tile flow accumulation has many
disconnected single-cell trees at the boundary). Restricting to the
basin reaching the dominant outlet matches NHD's per-network convention.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from geo_tda.topo_eval.merge_tree import MergeNode, MergeTree


@dataclass
class SegmentNode:
    """One node of the segment graph; mirrors a MergeNode."""

    id: int
    cell: tuple[int, int]
    strahler: int
    children: list["SegmentNode"] = field(default_factory=list)
    parent: "SegmentNode | None" = None
    edge_cells: int = 1  # cells along the degree-2 run feeding this node

    @property
    def is_leaf(self) -> bool:
        return not self.children


@dataclass
class SegmentGraph:
    roots: list[SegmentNode]

    def all_nodes(self) -> list[SegmentNode]:
        out: list[SegmentNode] = []
        stack = list(self.roots)
        while stack:
            n = stack.pop()
            out.append(n)
            stack.extend(n.children)
        return out

    @property
    def leaves(self) -> list[SegmentNode]:
        return [n for n in self.all_nodes() if n.is_leaf]

    @property
    def internal_nodes(self) -> list[SegmentNode]:
        return [n for n in self.all_nodes() if not n.is_leaf]

    @property
    def num_junctions(self) -> int:
        return len(self.internal_nodes)

    def strahler_distribution(self) -> dict[int, int]:
        dist: dict[int, int] = {}
        for n in self.all_nodes():
            dist[n.strahler] = dist.get(n.strahler, 0) + 1
        return dist

    def largest_basin(self) -> "SegmentGraph | None":
        """Single-root subgraph rooted at the basin with most descendants."""
        if not self.roots:
            return None
        best = max(self.roots, key=lambda r: len(_descendants(r)))
        return SegmentGraph(roots=[best])


def _descendants(node: SegmentNode) -> list[SegmentNode]:
    out: list[SegmentNode] = []
    stack = list(node.children)
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(n.children)
    return out


def segment_graph_from_merge_tree(tree: MergeTree) -> SegmentGraph:
    """Materialize the segment graph: one node per merge-tree node.

    The donor-graph merge tree already collapses degree-2 runs during
    union-find (extension cells join their existing component without
    creating a MergeNode), so the segment graph is structurally just a
    relabeling of the merge tree with segment-side identities.

    edge_cells is set to 1 here because the merge tree does not retain
    the lengths of the collapsed runs. A future refinement could carry
    that count from the union-find sweep; for branching-based criteria
    (junction count, Strahler distribution, R_b) it is not needed.
    """
    # Iterative build (no recursion: deep trees). Each merge node maps to a
    # segment node; strahler is read off the merge node (itself computed
    # iteratively with memoization).
    counter = 0
    sg_roots: list[SegmentNode] = []
    for r in tree.roots:
        sg_r = SegmentNode(id=counter, cell=r.cell, strahler=r.strahler, parent=None)
        counter += 1
        stack: list[tuple[MergeNode, SegmentNode]] = [(r, sg_r)]
        while stack:
            mt_node, sg_node = stack.pop()
            for c in mt_node.children:
                child = SegmentNode(
                    id=counter, cell=c.cell, strahler=c.strahler, parent=sg_node
                )
                counter += 1
                sg_node.children.append(child)
                stack.append((c, child))
        sg_roots.append(sg_r)

    return SegmentGraph(roots=sg_roots)


def bifurcation_ratio_largest_basin(tree: MergeTree) -> float:
    """Horton R_b restricted to the largest basin.

    Per-tile forests can have many stranded single-cell basins (channel
    heads whose downstream paths exit the tile before merging with
    anything else); these inflate the order-1 count and so the per-tile
    R_b across the whole forest, in a way that does not reflect the
    drainage hierarchy any single river network encodes. Computing R_b
    on the largest connected basin matches NHD's per-network convention
    (NHD reports R_b per HUC, not per tile boundary).

    Returns NaN if the largest basin has fewer than two Strahler orders.
    """
    import numpy as np

    sg = segment_graph_from_merge_tree(tree).largest_basin()
    if sg is None:
        return float("nan")
    dist = sg.strahler_distribution()
    orders = sorted(dist)
    if len(orders) < 2:
        return float("nan")
    ratios = []
    for i in range(len(orders) - 1):
        lo, hi = orders[i], orders[i + 1]
        if dist.get(hi, 0) > 0:
            ratios.append(dist[lo] / dist[hi])
    return float(np.mean(ratios)) if ratios else float("nan")
