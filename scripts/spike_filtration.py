"""Phase 0 filtration-orientation spike for the topological-evaluation paper.

Tests the locked filtration construction on synthetic toys before any proof
or production code is written. The construction under test:

    Merge tree of the flow accumulation field A on a DEM, built by
    donor-based union-find on the D8 flow graph, restricted to the
    channel mask {A >= tau_channel}, swept in ascending A.

Two negative controls run alongside:

    1. Cubical 8-adjacency union-find under the same direction. Same as
       donor-based on the Y-toy (no degenerate geometry); diverges on the
       tributary-contact and meander-neck toys where spatial adjacency
       creates phantom confluences or cycles the flow graph cannot have.

    2. Superlevel-decreasing on the whole grid (the wrong direction).
       Confluences become invisible because the component grows headward
       from the trunk and each new cell joins the already-present component.

Plus an H_1 diagnostic on the meander-neck toy: cubical 8-adjacency on a
self-touching channel mask creates cycles (H_1 > 0); the donor-graph is a
forest (H_1 = 0). Quantifies the spatial-adjacency contamination the
donor-graph construction removes.

This spike is throwaway. Its output is the orientation_spike.md note.
Phase A drafting starts after the note exists.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# D8 offsets indexed 0..7 = N, NE, E, SE, S, SW, W, NW
D8_OFFSETS: list[tuple[int, int]] = [
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
]
EIGHT_NEIGHBORS = D8_OFFSETS  # alias; cubical 8-adjacency uses same offsets


def compute_accumulation(flow_dir: np.ndarray) -> np.ndarray:
    """D8 flow accumulation from a flow-direction grid.

    flow_dir[i, j] in 0..7 is the D8 receiver index per D8_OFFSETS;
    -1 means no receiver (outlet or non-channel hillslope).

    Every cell with flow_dir >= 0 OR that receives flow contributes 1 to
    itself. Non-channel cells (flow_dir == -1 AND no in-flow) are assigned
    accumulation 0 here so the channel mask can isolate the network from
    the background.
    """
    H, W = flow_dir.shape
    accum = np.zeros((H, W), dtype=np.int64)

    receivers: dict[tuple[int, int], tuple[int, int]] = {}
    in_degree = np.zeros((H, W), dtype=np.int64)
    is_channel = np.zeros((H, W), dtype=bool)

    for i in range(H):
        for j in range(W):
            code = int(flow_dir[i, j])
            if code < 0:
                continue
            is_channel[i, j] = True
            dy, dx = D8_OFFSETS[code]
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W:
                receivers[(i, j)] = (ni, nj)
                in_degree[ni, nj] += 1
                is_channel[ni, nj] = True

    # Initialize accumulation to 1 for every channel cell
    accum[is_channel] = 1

    # Topological sweep (Kahn's algorithm) over the flow DAG
    queue: deque[tuple[int, int]] = deque()
    in_degree_work = in_degree.copy()
    for i in range(H):
        for j in range(W):
            if is_channel[i, j] and in_degree_work[i, j] == 0:
                queue.append((i, j))
    while queue:
        c = queue.popleft()
        if c in receivers:
            r = receivers[c]
            accum[r] += accum[c]
            in_degree_work[r] -= 1
            if in_degree_work[r] == 0:
                queue.append(r)

    return accum


@dataclass
class UnionFind:
    parent: dict[tuple[int, int], tuple[int, int]] = field(default_factory=dict)

    def add(self, x: tuple[int, int]) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: tuple[int, int]) -> tuple[int, int]:
        # iterative path compression
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[ra] = rb
        return True


@dataclass
class FiltrationResult:
    name: str
    births: list[tuple[int, int]] = field(default_factory=list)
    merges: list[dict] = field(default_factory=list)
    final_components: int = 0


def donor_union_find(
    flow_dir: np.ndarray, accum: np.ndarray, tau_channel: int
) -> FiltrationResult:
    """Donor-based union-find on D8 flow graph, mask-restricted, ascending A."""
    H, W = flow_dir.shape
    mask = accum >= tau_channel

    # Receivers and donors over channel cells only
    donors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for i in range(H):
        for j in range(W):
            if not mask[i, j]:
                continue
            donors[(i, j)] = []
    for i in range(H):
        for j in range(W):
            if int(flow_dir[i, j]) < 0:
                continue
            dy, dx = D8_OFFSETS[int(flow_dir[i, j])]
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W and mask[ni, nj]:
                donors[(ni, nj)].append((i, j))

    channel_cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    channel_cells.sort(key=lambda c: (accum[c[0], c[1]], c[0], c[1]))

    uf = UnionFind()
    res = FiltrationResult(name="donor")
    processed: set[tuple[int, int]] = set()

    for c in channel_cells:
        uf.add(c)
        in_mask_processed = [d for d in donors[c] if d in processed]
        if not in_mask_processed:
            res.births.append(c)
        else:
            components = {uf.find(d) for d in in_mask_processed}
            if len(components) >= 2:
                res.merges.append(
                    {
                        "cell": c,
                        "accum": int(accum[c]),
                        "num_children": len(components),
                    }
                )
            for d in in_mask_processed:
                uf.union(c, d)
        processed.add(c)

    roots = {uf.find(c) for c in channel_cells}
    res.final_components = len(roots)
    return res


def cubical_union_find(
    accum: np.ndarray, tau_channel: int
) -> FiltrationResult:
    """Cubical 8-adjacency union-find on the channel mask, ascending A."""
    H, W = accum.shape
    mask = accum >= tau_channel

    channel_cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    channel_cells.sort(key=lambda c: (accum[c[0], c[1]], c[0], c[1]))

    uf = UnionFind()
    res = FiltrationResult(name="cubical")
    processed: set[tuple[int, int]] = set()

    for c in channel_cells:
        i, j = c
        uf.add(c)
        in_mask_processed_neighbors: list[tuple[int, int]] = []
        for dy, dx in EIGHT_NEIGHBORS:
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W and mask[ni, nj] and (ni, nj) in processed:
                in_mask_processed_neighbors.append((ni, nj))
        if not in_mask_processed_neighbors:
            res.births.append(c)
        else:
            components = {uf.find(n) for n in in_mask_processed_neighbors}
            if len(components) >= 2:
                res.merges.append(
                    {
                        "cell": c,
                        "accum": int(accum[c]),
                        "num_children": len(components),
                    }
                )
            for n in in_mask_processed_neighbors:
                uf.union(c, n)
        processed.add(c)

    roots = {uf.find(c) for c in channel_cells}
    res.final_components = len(roots)
    return res


def superlevel_decreasing_8adj(accum: np.ndarray) -> FiltrationResult:
    """Negative control: whole-grid superlevel filtration, descending A,
    cubical 8-adjacency. Demonstrates that confluences are invisible
    under this orientation because the component grows from the trunk
    headward and each new cell joins the already-present trunk component.
    """
    H, W = accum.shape
    # Process only cells with A > 0; A=0 cells aren't part of any drainage.
    cells = [(i, j) for i in range(H) for j in range(W) if accum[i, j] > 0]
    cells.sort(key=lambda c: (-int(accum[c[0], c[1]]), c[0], c[1]))

    uf = UnionFind()
    res = FiltrationResult(name="superlevel-decreasing")
    processed: set[tuple[int, int]] = set()

    for c in cells:
        i, j = c
        uf.add(c)
        already_present: list[tuple[int, int]] = []
        for dy, dx in EIGHT_NEIGHBORS:
            ni, nj = i + dy, j + dx
            if 0 <= ni < H and 0 <= nj < W and (ni, nj) in processed:
                already_present.append((ni, nj))
        if not already_present:
            res.births.append(c)
        else:
            components = {uf.find(n) for n in already_present}
            if len(components) >= 2:
                res.merges.append(
                    {
                        "cell": c,
                        "accum": int(accum[c]),
                        "num_children": len(components),
                    }
                )
            for n in already_present:
                uf.union(c, n)
        processed.add(c)

    return res


def h1_of_mask_under_cubical(mask: np.ndarray) -> int:
    """First Betti number of the channel mask treated as a 1-complex
    under 8-adjacency: H_1 = E - V + C where C is number of connected
    components. Counts independent cycles. The donor-graph adjacency
    cannot produce cycles (it is a forest by D8 single-receiver
    construction), so a positive value here quantifies spatial-adjacency
    contamination the donor-graph removes.
    """
    H, W = mask.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cell_set = set(cells)

    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for c in cells:
        i, j = c
        for dy, dx in EIGHT_NEIGHBORS:
            ni, nj = i + dy, j + dx
            n = (ni, nj)
            if n in cell_set:
                edges.add(tuple(sorted([c, n])))

    uf = UnionFind()
    for c in cells:
        uf.add(c)
    for a, b in edges:
        uf.union(a, b)
    components = len({uf.find(c) for c in cells})

    return len(edges) - len(cells) + components


def h1_of_donor_graph(flow_dir: np.ndarray, mask: np.ndarray) -> int:
    """First Betti number of the donor-graph restricted to the mask.
    Should always be 0 because the D8 receiver relation is a function,
    so its donor-graph is a forest.
    """
    H, W = flow_dir.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cell_set = set(cells)

    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for i in range(H):
        for j in range(W):
            if (i, j) not in cell_set:
                continue
            code = int(flow_dir[i, j])
            if code < 0:
                continue
            dy, dx = D8_OFFSETS[code]
            r = (i + dy, j + dx)
            if r in cell_set:
                edges.add(tuple(sorted([(i, j), r])))

    uf = UnionFind()
    for c in cells:
        uf.add(c)
    for a, b in edges:
        uf.union(a, b)
    components = len({uf.find(c) for c in cells})

    return len(edges) - len(cells) + components


# Toy DEM constructors. Each returns (flow_dir, accum, tau_channel, label).

def make_y_toy() -> tuple[np.ndarray, np.ndarray, int, str]:
    """Y: two heads, one true confluence at (4,2), trunk to outlet at (7,2)."""
    H, W = 9, 5
    fd = np.full((H, W), -1, dtype=np.int8)
    # Arm A: (1,1)->(2,1)->(3,1)->(4,2)
    fd[1, 1] = 4  # S
    fd[2, 1] = 4  # S
    fd[3, 1] = 3  # SE -> (4,2)
    # Arm B: (1,3)->(2,3)->(3,3)->(4,2)
    fd[1, 3] = 4  # S
    fd[2, 3] = 4  # S
    fd[3, 3] = 5  # SW -> (4,2)
    # Trunk: (4,2)->(5,2)->(6,2)->(7,2)
    fd[4, 2] = 4
    fd[5, 2] = 4
    fd[6, 2] = 4
    # outlet (7,2) has fd = -1
    accum = compute_accumulation(fd)
    return fd, accum, 1, "Y-toy"


def make_tributary_contact_toy() -> tuple[np.ndarray, np.ndarray, int, str]:
    """Two distinct flow paths in adjacent columns whose cells are 8-adjacent
    along most of their length, with true confluence well downstream at (5,2).
    Arm A is column 1, arm B is column 2 from row 2 onward. They are
    8-adjacent at rows 2..4 inclusive. Both reach (5,2) via S/SE.

    Cubical adjacency joins them early (phantom merge somewhere upstream of
    (5,2)). Donor adjacency only sees the true merge at (5,2).
    """
    H, W = 8, 4
    fd = np.full((H, W), -1, dtype=np.int8)
    # Arm A: (0,1)->(1,1)->(2,1)->(3,1)->(4,1)->(5,2) via SE
    fd[0, 1] = 4
    fd[1, 1] = 4
    fd[2, 1] = 4
    fd[3, 1] = 4
    fd[4, 1] = 3  # SE -> (5,2)
    # Arm B: (2,2)->(3,2)->(4,2)->(5,2)
    fd[2, 2] = 4
    fd[3, 2] = 4
    fd[4, 2] = 4
    # Trunk: (5,2)->(6,2)->(7,2)
    fd[5, 2] = 4
    fd[6, 2] = 4
    # outlet (7,2) has fd = -1
    accum = compute_accumulation(fd)
    return fd, accum, 1, "tributary-contact-toy"


def make_meander_neck_toy() -> tuple[np.ndarray, np.ndarray, int, str]:
    """Single channel whose path snakes through a 2x3 block, creating cells
    that are 8-adjacent across the meander's interior. Flow path is:
    (0,1)->(1,1)->(2,1)->(2,2)->(2,3)->(3,3)->(3,2)->(3,1)->(4,1)->outlet.

    Donor adjacency: a single chain, H_1 = 0.
    Cubical 8-adjacency: the 2x3 block at rows 2-3 cols 1-3 contains
    diagonal edges that create cycles, H_1 > 0.
    """
    H, W = 5, 4
    fd = np.full((H, W), -1, dtype=np.int8)
    fd[0, 1] = 4  # S -> (1,1)
    fd[1, 1] = 4  # S -> (2,1)
    fd[2, 1] = 2  # E -> (2,2)
    fd[2, 2] = 2  # E -> (2,3)
    fd[2, 3] = 4  # S -> (3,3)
    fd[3, 3] = 6  # W -> (3,2)
    fd[3, 2] = 6  # W -> (3,1)
    fd[3, 1] = 4  # S -> (4,1)
    # outlet (4,1) has fd = -1
    accum = compute_accumulation(fd)
    return fd, accum, 1, "meander-neck-toy"


# Assertion runner

@dataclass
class AssertionResult:
    name: str
    passed: bool
    detail: str


def run_y_toy_assertions() -> list[AssertionResult]:
    fd, accum, tau, label = make_y_toy()
    mask = accum >= tau
    donor = donor_union_find(fd, accum, tau)
    cubical = cubical_union_find(accum, tau)
    superlvl = superlevel_decreasing_8adj(accum)

    results: list[AssertionResult] = []

    # Donor: exactly 1 merge at the confluence (4,2)
    ok = (
        len(donor.merges) == 1
        and donor.merges[0]["cell"] == (4, 2)
        and donor.merges[0]["num_children"] == 2
    )
    results.append(
        AssertionResult(
            f"{label} / donor: 1 merge at confluence (4,2) with 2 children",
            ok,
            f"merges={donor.merges}, births={len(donor.births)}",
        )
    )

    # Donor: 2 channel-head births
    ok = len(donor.births) == 2
    results.append(
        AssertionResult(
            f"{label} / donor: 2 channel-head births", ok,
            f"births={donor.births}",
        )
    )

    # Cubical agrees on Y-toy (no degenerate geometry)
    cubical_merge_cells = {m["cell"] for m in cubical.merges}
    ok = cubical_merge_cells == {(4, 2)} and len(cubical.merges) == 1
    results.append(
        AssertionResult(
            f"{label} / cubical agrees with donor on Y-toy (no degenerate geom)",
            ok,
            f"cubical merges={cubical.merges}",
        )
    )

    # Superlevel-decreasing: zero merges at the confluence (the bug)
    superlvl_merge_cells = {m["cell"] for m in superlvl.merges}
    ok = (4, 2) not in superlvl_merge_cells
    results.append(
        AssertionResult(
            f"{label} / superlevel-decreasing: zero merges at confluence "
            f"(confluences invisible under wrong direction)",
            ok,
            f"superlevel merges={superlvl.merges}",
        )
    )

    return results


def run_tributary_contact_assertions() -> list[AssertionResult]:
    fd, accum, tau, label = make_tributary_contact_toy()
    donor = donor_union_find(fd, accum, tau)
    cubical = cubical_union_find(accum, tau)

    results: list[AssertionResult] = []

    # Donor: exactly 1 merge at the true confluence (5,2)
    ok = (
        len(donor.merges) == 1
        and donor.merges[0]["cell"] == (5, 2)
        and donor.merges[0]["num_children"] == 2
    )
    results.append(
        AssertionResult(
            f"{label} / donor: 1 merge at TRUE confluence (5,2)",
            ok,
            f"merges={donor.merges}",
        )
    )

    # Cubical: at least one phantom merge somewhere upstream of (5,2),
    # OR the merge is at the wrong cell. Either is the contamination.
    cubical_merge_cells = [m["cell"] for m in cubical.merges]
    has_phantom_upstream = any(c != (5, 2) for c in cubical_merge_cells)
    ok = has_phantom_upstream and len(cubical.merges) >= 1
    results.append(
        AssertionResult(
            f"{label} / cubical: phantom merge upstream of true confluence "
            f"(the adjacency-bug contamination)",
            ok,
            f"cubical merges={cubical.merges}",
        )
    )

    return results


def run_meander_neck_assertions() -> list[AssertionResult]:
    fd, accum, tau, label = make_meander_neck_toy()
    mask = accum >= tau
    donor = donor_union_find(fd, accum, tau)
    cubical = cubical_union_find(accum, tau)
    h1_donor = h1_of_donor_graph(fd, mask)
    h1_cubical = h1_of_mask_under_cubical(mask)

    results: list[AssertionResult] = []

    # Donor: no merges (single chain)
    ok = len(donor.merges) == 0
    results.append(
        AssertionResult(
            f"{label} / donor: no merges (single chain, no spurious confluence)",
            ok,
            f"merges={donor.merges}",
        )
    )

    # Donor flow graph: H_1 = 0 (it's a forest)
    ok = h1_donor == 0
    results.append(
        AssertionResult(
            f"{label} / donor flow graph: H_1 = 0 (forest, no cycles)",
            ok,
            f"h1_donor={h1_donor}",
        )
    )

    # Cubical 8-adjacency mask: H_1 > 0 (the meander loop)
    ok = h1_cubical > 0
    results.append(
        AssertionResult(
            f"{label} / cubical mask: H_1 > 0 "
            f"(spatial-adjacency contamination the donor-graph removes)",
            ok,
            f"h1_cubical={h1_cubical}",
        )
    )

    return results


def print_results(label: str, results: list[AssertionResult]) -> tuple[int, int]:
    print(f"\n=== {label} ===")
    passed = 0
    for r in results:
        marker = "[PASS]" if r.passed else "[FAIL]"
        print(f"  {marker} {r.name}")
        print(f"         {r.detail}")
        if r.passed:
            passed += 1
    return passed, len(results)


def main() -> int:
    print(
        "Phase 0 filtration-orientation spike\n"
        "Testing: donor-based union-find on D8 flow graph, mask-restricted, "
        "sublevel-increasing in A\n"
        "Negative controls: cubical 8-adjacency, superlevel-decreasing on whole grid"
    )
    total_passed = 0
    total = 0

    for label, runner in [
        ("Y-toy (no degenerate geometry; donor and cubical should agree)",
         run_y_toy_assertions),
        ("Tributary-contact toy (adjacency contamination: phantom merge upstream)",
         run_tributary_contact_assertions),
        ("Meander-neck toy (adjacency contamination: cycles via 8-adj across neck)",
         run_meander_neck_assertions),
    ]:
        p, t = print_results(label, runner())
        total_passed += p
        total += t

    print(f"\n--- summary: {total_passed} / {total} assertions passed ---")
    if total_passed == total:
        print(
            "Spike PASS: filtration construction (sublevel-increasing on channel mask, "
            "donor-based union-find on D8 flow graph) is empirically validated against "
            "the negative controls on the toy zoo."
        )
        return 0
    print(
        "Spike FAIL: at least one assertion failed. Fix the construction before "
        "drafting the proof."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
