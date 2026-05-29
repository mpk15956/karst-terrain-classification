"""Branching-based construct-validity comparison against NHD flowlines.

Phase C compares the PH-derived channel network (the donor-graph merge
tree) against NHD flowline vectors on three BRANCHING criteria, not on
drainage density (which is set by tau_channel and so mechanically
reproducible; it is a controlled covariate, not a criterion):

- junction count: confluences in the network;
- Strahler-order distribution: compared by Wasserstein-1 distance;
- Horton bifurcation ratio R_b.

The NHD network is built from flowline geometry by snapping shared
endpoints into a directed graph, then Strahler order is computed on that
graph with the SAME arity convention as the merge tree (a node where k
upstream reaches meet is one confluence of arity k, per Theorem 1's
convention in the proof). This keeps both sides method-consistent.

Thresholds in Phase C are pre-registered RELATIVE to the whitebox-vs-NHD
agreement ceiling, not against absolute targets, because DEM-extracted
and photo-digitized networks disagree for epoch and cartographic-
convention reasons unrelated to metric quality.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BranchingStats:
    """Branching summary of a channel network (PH or NHD side)."""

    junction_count: int
    strahler_distribution: dict[int, int]
    bifurcation_ratio: float
    drainage_density: float  # covariate, not a criterion


def _strahler_on_digraph(
    children_of: dict[int, list[int]], roots: list[int]
) -> dict[int, int]:
    """Strahler order per node of a rooted forest given children adjacency.

    Uses the generalized multiset rule (Theorem 1): leaf -> 1; internal
    node with child-order maximum m attained by n children -> m if n == 1
    else m + 1.
    """
    order: dict[int, int] = {}

    def visit(node: int) -> int:
        kids = children_of.get(node, [])
        if not kids:
            order[node] = 1
            return 1
        child_orders = [visit(k) for k in kids]
        m = max(child_orders)
        n = child_orders.count(m)
        order[node] = m if n == 1 else m + 1
        return order[node]

    for r in roots:
        visit(r)
    return order


def stats_from_nhd_flowlines(
    geojson_path, *, snap_tolerance: float = 1e-4, area_km2: float | None = None
) -> BranchingStats:
    """Build a network from NHD flowlines and summarize its branching.

    Args:
        geojson_path: path to an NHD flowline GeoJSON (EPSG:4326).
        snap_tolerance: degrees within which endpoints are treated as the
            same node (1e-4 deg ~ 11 m at the equator).
        area_km2: tile area for drainage density; if None, density is NaN.

    Returns:
        BranchingStats for the NHD network. Direction is inferred from
        flowline vertex order (NHD digitizes upstream-to-downstream), so
        each flowline's last vertex is its downstream end.
    """
    import geopandas as gpd
    from shapely.geometry import LineString, MultiLineString

    gdf = gpd.read_file(geojson_path)

    def snap(pt):
        return (round(pt[0] / snap_tolerance), round(pt[1] / snap_tolerance))

    # build node ids and directed edges (upstream_node -> downstream_node)
    node_id: dict[tuple[int, int], int] = {}
    edges: list[tuple[int, int]] = []
    total_len_deg = 0.0

    def add_node(pt) -> int:
        key = snap(pt)
        if key not in node_id:
            node_id[key] = len(node_id)
        return node_id[key]

    def handle_line(line: LineString) -> None:
        nonlocal total_len_deg
        coords = list(line.coords)
        if len(coords) < 2:
            return
        up = add_node(coords[0])
        down = add_node(coords[-1])
        if up != down:
            edges.append((up, down))
        total_len_deg += line.length

    for geom in gdf.geometry:
        if geom is None:
            continue
        if isinstance(geom, LineString):
            handle_line(geom)
        elif isinstance(geom, MultiLineString):
            for part in geom.geoms:
                handle_line(part)

    # children_of[downstream] = [upstream donors]
    children_of: dict[int, list[int]] = {}
    indeg: dict[int, int] = {}
    outdeg: dict[int, int] = {}
    nodes = set()
    for up, down in edges:
        children_of.setdefault(down, []).append(up)
        indeg[down] = indeg.get(down, 0) + 1
        outdeg[up] = outdeg.get(up, 0) + 1
        nodes.add(up)
        nodes.add(down)

    # roots = nodes with no downstream edge (outlets)
    roots = [n for n in nodes if outdeg.get(n, 0) == 0]
    order = _strahler_on_digraph(children_of, roots)

    # junctions = nodes with >= 2 upstream donors
    junction_count = sum(1 for n in children_of if len(children_of[n]) >= 2)

    dist: dict[int, int] = {}
    for n in nodes:
        s = order.get(n, 1)
        dist[s] = dist.get(s, 0) + 1

    rb = _bifurcation_ratio(dist)

    # crude degree->km: 1 degree ~ 111 km; this is the covariate only
    total_len_km = total_len_deg * 111.0
    density = (
        total_len_km / area_km2 if area_km2 not in (None, 0) else float("nan")
    )

    return BranchingStats(
        junction_count=junction_count,
        strahler_distribution=dist,
        bifurcation_ratio=rb,
        drainage_density=density,
    )


def stats_from_merge_tree(tree, *, area_km2: float | None = None,
                          channel_cell_count: int | None = None,
                          cell_km: float | None = None) -> BranchingStats:
    """Branching summary of a PH-derived merge tree (the metric side)."""
    dist = tree.strahler_distribution()
    rb = _bifurcation_ratio(dist)
    if area_km2 and channel_cell_count and cell_km:
        total_len_km = channel_cell_count * cell_km
        density = total_len_km / area_km2
    else:
        density = float("nan")
    return BranchingStats(
        junction_count=tree.num_confluences,
        strahler_distribution=dist,
        bifurcation_ratio=rb,
        drainage_density=density,
    )


def _bifurcation_ratio(dist: dict[int, int]) -> float:
    orders = sorted(dist)
    if len(orders) < 2:
        return float("nan")
    ratios = []
    for i in range(len(orders) - 1):
        lo, hi = orders[i], orders[i + 1]
        if dist.get(hi, 0) > 0:
            ratios.append(dist[lo] / dist[hi])
    return float(np.mean(ratios)) if ratios else float("nan")


def strahler_wasserstein(a: dict[int, int], b: dict[int, int]) -> float:
    """Wasserstein-1 distance between two Strahler-order distributions."""
    from scipy.stats import wasserstein_distance

    def samples(dist):
        out = []
        for order, count in dist.items():
            out.extend([order] * count)
        return np.array(out, dtype=float) if out else np.array([0.0])

    return float(wasserstein_distance(samples(a), samples(b)))


def compare(ph: BranchingStats, nhd: BranchingStats) -> dict[str, float]:
    """Per-tile agreement on the three branching criteria."""
    return {
        "junction_count_ph": ph.junction_count,
        "junction_count_nhd": nhd.junction_count,
        "strahler_wasserstein": strahler_wasserstein(
            ph.strahler_distribution, nhd.strahler_distribution
        ),
        "bifurcation_ratio_ph": ph.bifurcation_ratio,
        "bifurcation_ratio_nhd": nhd.bifurcation_ratio,
        "bifurcation_ratio_abs_diff": abs(
            ph.bifurcation_ratio - nhd.bifurcation_ratio
        )
        if np.isfinite(ph.bifurcation_ratio) and np.isfinite(nhd.bifurcation_ratio)
        else float("nan"),
        "drainage_density_ph": ph.drainage_density,
        "drainage_density_nhd": nhd.drainage_density,
    }
