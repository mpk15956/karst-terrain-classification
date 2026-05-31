"""Donor-graph merge tree of a flow-accumulation field.

The construction proved in docs/topo_eval/proofs/strahler_merge_tree.qmd
and empirically validated in scripts/spike_filtration.py. Given a D8
flow-direction grid and its accumulation field, build the merge tree of
the channel network by donor-based union-find on the D8 flow graph,
restricted to the channel mask {A >= tau_channel}, swept in ascending A.

Donor adjacency, not spatial-grid adjacency: a cell's children in the
merge tree are the cells that flow INTO it (its D8 donors), not its
spatial 8-neighbours. The Phase 0 spike shows this distinction is not
cosmetic: cubical 8-adjacency produces phantom confluences on
subparallel tributaries and spurious H_1 cycles on meander necks that
the donor graph (a forest by D8 single-receiver construction) cannot
have.

The persistence diagram is the abelianization of the merge tree
(Theorem 2 of the proof): the multiset of (birth, death) heights
produced by the elder rule, which forgets the branching pairing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# D8 receiver codes 0..7 = N, NE, E, SE, S, SW, W, NW. -1 = no receiver.
D8_OFFSETS: list[tuple[int, int]] = [
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
]

Cell = tuple[int, int]


@dataclass
class MergeNode:
    """A node of the merge tree.

    A leaf is a channel head (no in-mask donors). An internal node is a
    confluence (>= 2 in-mask donor components merging). The root is the
    basin outlet.
    """

    cell: Cell
    birth: float
    death: float | None  # None for the essential (surviving) class
    children: list["MergeNode"] = field(default_factory=list)
    _strahler: int | None = field(default=None, repr=False, compare=False)

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def strahler(self) -> int:
        """Horton-Strahler order via the generalized confluence rule.

        Leaf -> 1. Internal node with child orders having maximum m
        attained by n children: m if n == 1, else m + 1. Reduces to the
        classical binary rule (two equal orders i give i+1; unequal give
        the larger). See Theorem 1 of the proof.

        Computed by an iterative post-order with per-node memoization, not
        recursion: real channel chains are thousands of confluences deep
        and overflow Python's recursion limit.
        """
        if self._strahler is not None:
            return self._strahler
        stack: list[tuple[MergeNode, bool]] = [(self, False)]
        while stack:
            node, ready = stack.pop()
            if node._strahler is not None:
                continue
            if ready or not node.children:
                if not node.children:
                    node._strahler = 1
                else:
                    co = [c._strahler for c in node.children]
                    m = max(co)
                    node._strahler = m if co.count(m) == 1 else m + 1
            else:
                stack.append((node, True))
                stack.extend((c, False) for c in node.children)
        return self._strahler  # type: ignore[return-value]


@dataclass
class MergeTree:
    """A forest of merge trees, one rooted tree per basin reaching the mask.

    Multi-outlet tiles produce a forest (Lemma + Fact B of the proof);
    single-basin inputs produce a one-element forest.
    """

    roots: list[MergeNode]

    def _iter_nodes(self):
        """Iterative pre-order over the forest (no recursion: deep trees)."""
        stack = list(self.roots)
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node.children)

    @property
    def leaves(self) -> list[MergeNode]:
        return [n for n in self._iter_nodes() if n.is_leaf]

    @property
    def internal_nodes(self) -> list[MergeNode]:
        return [n for n in self._iter_nodes() if not n.is_leaf]

    def all_nodes(self) -> list[MergeNode]:
        return list(self._iter_nodes())

    @property
    def num_confluences(self) -> int:
        return len(self.internal_nodes)

    def strahler_distribution(self) -> dict[int, int]:
        """Count of nodes at each Strahler order across the forest."""
        dist: dict[int, int] = {}
        for node in self.all_nodes():
            s = node.strahler
            dist[s] = dist.get(s, 0) + 1
        return dist


def _donors_from_pointer(
    flow_dir: np.ndarray, mask: np.ndarray
) -> dict[Cell, list[Cell]]:
    """In-mask donors of each in-mask cell: cells whose D8 receiver is it."""
    H, W = flow_dir.shape
    donors: dict[Cell, list[Cell]] = {
        (i, j): [] for i in range(H) for j in range(W) if mask[i, j]
    }
    for i in range(H):
        for j in range(W):
            if not mask[i, j]:
                continue
            code = int(flow_dir[i, j])
            if code < 0:
                continue
            dy, dx = D8_OFFSETS[code]
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W and mask[ni, nj]:
                donors[(ni, nj)].append((i, j))
    return donors


def merge_tree_from_accumulation(
    flow_dir: np.ndarray,
    accumulation: np.ndarray,
    tau_channel: float,
) -> MergeTree:
    """Build the donor-graph merge tree (Lemma of the proof).

    Args:
        flow_dir: D8 receiver-code grid, values 0..7 per D8_OFFSETS, -1 for
            no receiver (outlet / off-grid). Shape (H, W).
        accumulation: flow accumulation field A, same shape.
        tau_channel: channelization threshold; mask is {A >= tau_channel}.

    Returns:
        MergeTree (a forest; one rooted tree per outlet basin reaching the
        mask). Each node carries its cell, birth height (A at the
        component's founding head), death height (A at the confluence that
        absorbs it; None for the surviving root class), and its children
        (the donor components it merged).

    The sweep is in ascending A. By Fact A of the proof, every cell is
    processed strictly after all its donors, so when a cell is added its
    in-mask donors are already placed; their distinct components are this
    cell's children if there are >= 2, the single extended component if 1,
    and a new birth if 0.
    """
    if flow_dir.shape != accumulation.shape:
        raise ValueError("flow_dir and accumulation must share shape")

    mask = accumulation >= tau_channel
    donors = _donors_from_pointer(flow_dir, mask)

    H, W = flow_dir.shape
    channel_cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    # Ascending A; ties broken by position for determinism. Ties only
    # coincide numerical heights; combinatorial structure is unaffected
    # (tie-robustness, Lemma).
    channel_cells.sort(key=lambda c: (accumulation[c[0], c[1]], c[0], c[1]))

    # union-find over component representatives, each rep an active MergeNode
    parent: dict[Cell, Cell] = {}
    rep_node: dict[Cell, MergeNode] = {}

    def find(x: Cell) -> Cell:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    processed: set[Cell] = set()

    for c in channel_cells:
        a_c = float(accumulation[c[0], c[1]])
        in_donors = [d for d in donors[c] if d in processed]
        parent[c] = c

        if not in_donors:
            # channel head: a new component is born here
            node = MergeNode(cell=c, birth=a_c, death=None)
            rep_node[c] = node
        else:
            comps = {find(d) for d in in_donors}
            if len(comps) == 1:
                # extend the single existing component; c joins it
                (only,) = comps
                parent[c] = only
            else:
                # confluence: merge >= 2 distinct components at height a_c
                child_nodes = [rep_node[r] for r in comps]
                for ch in child_nodes:
                    ch.death = a_c
                merged = MergeNode(
                    cell=c, birth=a_c, death=None, children=child_nodes
                )
                # union all donor components plus c under c's root
                for r in comps:
                    parent[r] = c
                for d in in_donors:
                    parent[find(d)] = c
                parent[c] = c
                rep_node[c] = merged
        processed.add(c)

    # roots: the surviving component representative per basin
    roots: list[MergeNode] = []
    seen_reps: set[Cell] = set()
    for c in channel_cells:
        r = find(c)
        if r not in seen_reps:
            seen_reps.add(r)
            roots.append(rep_node[r])
    return MergeTree(roots=roots)


def persistence_diagram(tree: MergeTree) -> list[tuple[float, float]]:
    """Degree-0 persistence diagram: the abelianization of the merge tree.

    Elder rule (Theorem 2 of the proof): process merges in increasing
    height; at each confluence the younger merging components die at the
    confluence height and the oldest survives. Returns the multiset of
    (birth, death) pairs; the surviving class per basin has death = +inf.

    The diagram retains birth/death heights but forgets the branching
    pairing, which is why it cannot recover Strahler order.
    """
    pairs: list[tuple[float, float]] = []
    # Iterative post-order (deep trees overflow recursion): oldest[node] is
    # the birth height of the oldest leaf under node.
    oldest: dict[int, float] = {}
    for root in tree.roots:
        stack: list[tuple[MergeNode, bool]] = [(root, False)]
        while stack:
            node, ready = stack.pop()
            if node.is_leaf:
                oldest[id(node)] = node.birth
                continue
            if ready:
                child_births = sorted(oldest[id(c)] for c in node.children)
                oldest[id(node)] = child_births[0]
                for younger_birth in child_births[1:]:
                    pairs.append((younger_birth, node.birth))
            else:
                stack.append((node, True))
                stack.extend((c, False) for c in node.children)
        pairs.append((oldest[id(root)], float("inf")))

    return pairs
