"""Scalar summaries of a merge tree and its persistence diagram.

Two families, mirroring the coarsening hierarchy of the proof:

- Merge-tree summaries (Theorem 1): Strahler-order distribution, Horton
  bifurcation ratio, junction count. These see branching and so can
  distinguish the falsification pair.
- Persistence-diagram summaries (Theorem 2): persistence statistics on
  the H0 barcode. These are the abelianized view and cannot see Strahler.

Plus the H1 contamination diagnostic (cubical 8-adjacency vs donor flow
graph) used in the Phase 0 spike and the Phase C real-tile sidebar.
"""
from __future__ import annotations

import numpy as np

from geo_tda.topo_eval.merge_tree import D8_OFFSETS, MergeTree

EIGHT_NEIGHBORS = D8_OFFSETS


def strahler_distribution(tree: MergeTree) -> dict[int, int]:
    return tree.strahler_distribution()


def horton_bifurcation_ratio(tree: MergeTree) -> float:
    """Mean bifurcation ratio R_b = mean over orders of N_i / N_{i+1}.

    N_i is the number of streams of Strahler order i. A "stream" of order
    i is a maximal chain of order-i nodes; here we count nodes of each
    order as a stable proxy on the merge tree (the segment-merging
    refinement is a Phase C concern). Returns NaN if fewer than two
    orders are present.
    """
    dist = tree.strahler_distribution()
    orders = sorted(dist)
    if len(orders) < 2:
        return float("nan")
    ratios = []
    for i in range(len(orders) - 1):
        lo, hi = orders[i], orders[i + 1]
        if dist.get(hi, 0) > 0:
            ratios.append(dist[lo] / dist[hi])
    return float(np.mean(ratios)) if ratios else float("nan")


def junction_count(tree: MergeTree) -> int:
    return tree.num_confluences


def persistence_statistics(diagram: list[tuple[float, float]]) -> dict[str, float]:
    """Summary stats of the finite H0 persistence pairs.

    Persistence = death - birth for finite pairs. The essential class
    (death = inf) is excluded from persistence stats and counted
    separately. These are the abelianized-view summaries; they do not
    see branching.
    """
    finite = [(b, d) for b, d in diagram if np.isfinite(d)]
    n_essential = sum(1 for _b, d in diagram if not np.isfinite(d))
    if not finite:
        return {
            "n_finite": 0,
            "n_essential": float(n_essential),
            "total_persistence": 0.0,
            "max_persistence": 0.0,
            "mean_persistence": 0.0,
        }
    pers = np.array([d - b for b, d in finite], dtype=float)
    return {
        "n_finite": float(len(finite)),
        "n_essential": float(n_essential),
        "total_persistence": float(pers.sum()),
        "max_persistence": float(pers.max()),
        "mean_persistence": float(pers.mean()),
    }


def h1_cubical_mask(mask: np.ndarray) -> int:
    """First Betti number of the channel mask under 8-adjacency.

    H1 = E - V + C (independent cycles) for the mask treated as a
    1-complex with 8-adjacency edges. The donor flow graph is a forest so
    its H1 is 0; any positive value here is spatial-adjacency
    contamination the donor-graph construction removes.
    """
    H, W = mask.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cell_set = set(cells)
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for i, j in cells:
        for dy, dx in EIGHT_NEIGHBORS:
            n = (i + dy, j + dx)
            if n in cell_set:
                edges.add(tuple(sorted([(i, j), n])))

    parent: dict[tuple[int, int], tuple[int, int]] = {c: c for c in cells}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    components = len({find(c) for c in cells})
    return len(edges) - len(cells) + components


def cubical_confluence_cells(
    accumulation: np.ndarray, tau_channel: float
) -> list[tuple[int, int]]:
    """Confluence cells found by cubical 8-adjacency union-find.

    The negative-control construction: process channel-mask cells in
    ascending A, joining each to its already-processed 8-neighbours. A
    cell whose already-present 8-neighbours span >= 2 distinct components
    is a (possibly phantom) confluence. Used by the adjacency test to show
    cubical adjacency invents merges the donor graph does not.
    """
    mask = accumulation >= tau_channel
    H, W = accumulation.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cells.sort(key=lambda c: (accumulation[c[0], c[1]], c[0], c[1]))

    parent: dict[tuple[int, int], tuple[int, int]] = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    processed: set[tuple[int, int]] = set()
    confluences: list[tuple[int, int]] = []
    for c in cells:
        i, j = c
        parent[c] = c
        present = []
        for dy, dx in EIGHT_NEIGHBORS:
            n = (i + dy, j + dx)
            if n in processed:
                present.append(n)
        comps = {find(n) for n in present}
        if len(comps) >= 2:
            confluences.append(c)
        for n in present:
            parent[find(n)] = c
        parent[c] = c
        processed.add(c)
    return confluences


def h1_donor_graph(flow_dir: np.ndarray, mask: np.ndarray) -> int:
    """First Betti number of the donor flow graph on the mask. Always 0
    (the flow graph is a forest); provided as an explicit cross-check.
    """
    H, W = flow_dir.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cell_set = set(cells)
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for i, j in cells:
        code = int(flow_dir[i, j])
        if code < 0:
            continue
        dy, dx = D8_OFFSETS[code]
        r = (i + dy, j + dx)
        if r in cell_set:
            edges.add(tuple(sorted([(i, j), r])))

    parent: dict[tuple[int, int], tuple[int, int]] = {c: c for c in cells}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    components = len({find(c) for c in cells})
    return len(edges) - len(cells) + components
