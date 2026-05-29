"""Synthetic toy DEMs with analytical drainage answers.

Each generator returns a flow-direction grid (D8 receiver codes per
merge_tree.D8_OFFSETS), its accumulation field, a channel threshold, and
the expected merge-tree facts. The toys serve double duty as pytest
fixtures (known-answer assertions) and as figure sources for the paper.

Three families:

- Confirmatory (cone, V-valley, branching-channel): hierarchy
  correctness. The construction reproduces the analytical Strahler answer.
- Adversarial (tributary-contact, meander-neck): adjacency correctness.
  The donor graph gives the right tree; cubical 8-adjacency would
  contaminate it. These are the Phase 0 spike toys promoted to fixtures.
- Falsification (equal-birth balanced vs caterpillar): the PD
  coarsening-loss witness of Theorem 2. Same H0 barcode, different
  Strahler distribution.

Accumulation is computed from the flow-direction grid by the same
topological sweep the proof uses (Kahn over the flow DAG), so the toys
need no whitebox.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from geo_tda.topo_eval.merge_tree import D8_OFFSETS, MergeNode, MergeTree


@dataclass
class Toy:
    """A synthetic toy and its analytical answers."""

    name: str
    flow_dir: np.ndarray
    accumulation: np.ndarray
    tau_channel: float
    expected_leaves: int
    expected_confluences: int
    expected_root_strahler: int
    expected_strahler_dist: dict[int, int] = field(default_factory=dict)
    notes: str = ""


def accumulation_from_flowdir(flow_dir: np.ndarray) -> np.ndarray:
    """D8 accumulation by topological sweep over the flow DAG.

    Each cell with a defined receiver (or that receives flow) contributes
    1 to itself; accumulation flows downstream. Cells with code -1 and no
    inflow get 0 so the channel mask isolates the network.
    """
    H, W = flow_dir.shape
    A = np.zeros((H, W), dtype=np.int64)
    recv: dict[tuple[int, int], tuple[int, int]] = {}
    indeg = np.zeros((H, W), dtype=np.int64)
    chan = np.zeros((H, W), dtype=bool)

    for i in range(H):
        for j in range(W):
            code = int(flow_dir[i, j])
            if code < 0:
                continue
            chan[i, j] = True
            dy, dx = D8_OFFSETS[code]
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W:
                recv[(i, j)] = (ni, nj)
                indeg[ni, nj] += 1
                chan[ni, nj] = True

    A[chan] = 1
    work = indeg.copy()
    q = deque(
        (i, j)
        for i in range(H)
        for j in range(W)
        if chan[i, j] and work[i, j] == 0
    )
    while q:
        c = q.popleft()
        if c in recv:
            r = recv[c]
            A[r] += A[c]
            work[r] -= 1
            if work[r] == 0:
                q.append(r)
    return A


# Confirmatory toys


def cone() -> Toy:
    """Single radial basin: one head reaching one outlet, no confluence."""
    H, W = 6, 3
    fd = np.full((H, W), -1, dtype=np.int8)
    for i in range(5):
        fd[i, 1] = 4  # S, straight column to outlet at (5,1)
    A = accumulation_from_flowdir(fd)
    return Toy(
        name="cone",
        flow_dir=fd,
        accumulation=A,
        tau_channel=1,
        expected_leaves=1,
        expected_confluences=0,
        expected_root_strahler=1,
        expected_strahler_dist={1: 1},
        notes="degenerate single chain; one H0 class, no merge",
    )


def v_valley() -> Toy:
    """Two heads merging once: the canonical Y, root Strahler order 2."""
    H, W = 9, 5
    fd = np.full((H, W), -1, dtype=np.int8)
    fd[1, 1] = 4; fd[2, 1] = 4; fd[3, 1] = 3  # arm A -> (4,2)
    fd[1, 3] = 4; fd[2, 3] = 4; fd[3, 3] = 5  # arm B -> (4,2)
    fd[4, 2] = 4; fd[5, 2] = 4; fd[6, 2] = 4  # trunk to outlet (7,2)
    A = accumulation_from_flowdir(fd)
    return Toy(
        name="v_valley",
        flow_dir=fd,
        accumulation=A,
        tau_channel=1,
        expected_leaves=2,
        expected_confluences=1,
        expected_root_strahler=2,
        expected_strahler_dist={1: 2, 2: 1},
        notes="two order-1 streams meet -> order 2",
    )


def branching_channel() -> Toy:
    """Four heads, balanced binary merges: root Strahler order 3.

    Two Y sub-confluences (each two order-1 heads -> order-2) whose
    order-2 streams meet at a main confluence -> order-3. Confirms the
    generalized Strahler rule on a balanced tree.

    Layout (row, col), outlet at (5, 3):
        (0,0) (0,2)        (0,4) (0,6)      heads
            \\ /                \\ /
           (1,1)=2            (1,5)=2        sub-confluences
              \\                  /
            (2,1)->(3,2)    (2,5)->(3,4)
                   \\        /
                    (3,3)=3                  main confluence
                      |
                  (4,3)->(5,3)               trunk to outlet
    """
    H, W = 6, 7
    fd = np.full((H, W), -1, dtype=np.int8)
    # left Y -> (1,1)
    fd[0, 0] = 3; fd[0, 2] = 5            # SE, SW -> (1,1)
    fd[1, 1] = 4; fd[2, 1] = 3            # S -> (2,1); SE -> (3,2)
    # right Y -> (1,5)
    fd[0, 4] = 3; fd[0, 6] = 5            # SE, SW -> (1,5)
    fd[1, 5] = 4; fd[2, 5] = 5            # S -> (2,5); SW -> (3,4)
    # main confluence (3,3)
    fd[3, 2] = 2; fd[3, 4] = 6            # E, W -> (3,3)
    fd[3, 3] = 4; fd[4, 3] = 4            # trunk to outlet (5,3)
    A = accumulation_from_flowdir(fd)
    return Toy(
        name="branching_channel",
        flow_dir=fd,
        accumulation=A,
        tau_channel=1,
        expected_leaves=4,
        expected_confluences=3,
        expected_root_strahler=3,
        expected_strahler_dist={1: 4, 2: 2, 3: 1},
        notes="balanced binary tree: 4 heads -> 2 order-2 -> 1 order-3",
    )


# Adversarial toys (Phase 0 spike toys, promoted)


def tributary_contact() -> Toy:
    """Two flow-distinct arms 8-adjacent along their length; true
    confluence well downstream. Donor graph sees one merge at the true
    confluence; cubical 8-adjacency would merge them upstream.
    """
    H, W = 8, 4
    fd = np.full((H, W), -1, dtype=np.int8)
    fd[0, 1] = 4; fd[1, 1] = 4; fd[2, 1] = 4; fd[3, 1] = 4; fd[4, 1] = 3  # arm A -> (5,2)
    fd[2, 2] = 4; fd[3, 2] = 4; fd[4, 2] = 4                              # arm B -> (5,2)
    fd[5, 2] = 4; fd[6, 2] = 4                                            # trunk -> (7,2)
    A = accumulation_from_flowdir(fd)
    return Toy(
        name="tributary_contact",
        flow_dir=fd,
        accumulation=A,
        tau_channel=1,
        expected_leaves=2,
        expected_confluences=1,
        expected_root_strahler=2,
        expected_strahler_dist={1: 2, 2: 1},
        notes="adjacency toy: donor->1 merge at true confluence (5,2); "
        "cubical would phantom-merge upstream",
    )


def meander_neck() -> Toy:
    """Single channel snaking within an 8-neighbourhood of itself. Donor
    graph: a chain, no merges, H1=0. Cubical 8-adjacency: spurious cycles.
    """
    H, W = 5, 4
    fd = np.full((H, W), -1, dtype=np.int8)
    fd[0, 1] = 4   # S -> (1,1)
    fd[1, 1] = 4   # S -> (2,1)
    fd[2, 1] = 2   # E -> (2,2)
    fd[2, 2] = 2   # E -> (2,3)
    fd[2, 3] = 4   # S -> (3,3)
    fd[3, 3] = 6   # W -> (3,2)
    fd[3, 2] = 6   # W -> (3,1)
    fd[3, 1] = 4   # S -> (4,1) outlet
    A = accumulation_from_flowdir(fd)
    return Toy(
        name="meander_neck",
        flow_dir=fd,
        accumulation=A,
        tau_channel=1,
        expected_leaves=1,
        expected_confluences=0,
        expected_root_strahler=1,
        expected_strahler_dist={1: 1},
        notes="adjacency toy: donor->single chain, H1=0; cubical mask H1=8",
    )


# Falsification witness (Theorem 2): abstract merge trees, exact by
# construction. The grid realization of exactly-matched death multisets
# is the [open] arithmetic flagged in the proof; the tree-level witness
# is complete and is what the proof rests on, so we build it directly as
# MergeNode structures rather than via fragile grid routing.


@dataclass
class FalsificationPair:
    """Two merge trees with identical H0 barcodes, different Strahler dists.

    Both have four heads born at the common height ``birth`` (equal-birth
    construction) and three confluences at heights ``heights`` (a strictly
    increasing triple). The balanced tree pairs heads (h,h)->order2,
    (h,h)->order2, then (order2,order2)->order3. The caterpillar tree
    absorbs heads one at a time, staying order 2. Both yield the barcode
    {(birth, h1), (birth, h2), (birth, h3), (birth, inf)}; their Strahler
    distributions differ ({1:4,2:2,3:1} vs {1:4,2:3}).
    """

    balanced: MergeTree
    caterpillar: MergeTree
    birth: float
    heights: tuple[float, float, float]


def _balanced_tree(birth: float, h: tuple[float, float, float]) -> MergeTree:
    h1, h2, h3 = h
    l1 = MergeNode(cell=(0, 0), birth=birth, death=h1)
    l2 = MergeNode(cell=(0, 1), birth=birth, death=h1)
    c1 = MergeNode(cell=(1, 0), birth=h1, death=h3, children=[l1, l2])
    l3 = MergeNode(cell=(0, 2), birth=birth, death=h2)
    l4 = MergeNode(cell=(0, 3), birth=birth, death=h2)
    c2 = MergeNode(cell=(1, 2), birth=h2, death=h3, children=[l3, l4])
    root = MergeNode(cell=(2, 0), birth=h3, death=None, children=[c1, c2])
    return MergeTree(roots=[root])


def _caterpillar_tree(birth: float, h: tuple[float, float, float]) -> MergeTree:
    h1, h2, h3 = h
    l1 = MergeNode(cell=(0, 0), birth=birth, death=h1)
    l2 = MergeNode(cell=(0, 1), birth=birth, death=h1)
    c1 = MergeNode(cell=(1, 0), birth=h1, death=h2, children=[l1, l2])
    l3 = MergeNode(cell=(0, 2), birth=birth, death=h2)
    c2 = MergeNode(cell=(1, 1), birth=h2, death=h3, children=[c1, l3])
    l4 = MergeNode(cell=(0, 3), birth=birth, death=h3)
    root = MergeNode(cell=(2, 0), birth=h3, death=None, children=[c2, l4])
    return MergeTree(roots=[root])


def falsification_pair(
    birth: float = 1.0, heights: tuple[float, float, float] = (3.0, 5.0, 7.0)
) -> FalsificationPair:
    """The Theorem 2 witness: identical barcodes, different Strahler.

    Exact by construction at the tree level (the regime the proof's
    witness lives in). The test still MEASURES bottleneck distance rather
    than assuming it, per the round-4 discipline.
    """
    return FalsificationPair(
        balanced=_balanced_tree(birth, heights),
        caterpillar=_caterpillar_tree(birth, heights),
        birth=birth,
        heights=heights,
    )


CONFIRMATORY = [cone, v_valley, branching_channel]
ADVERSARIAL = [tributary_contact, meander_neck]
