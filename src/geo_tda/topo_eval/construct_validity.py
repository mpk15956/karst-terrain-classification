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

    Iterative post-order, not recursion: real NHD/whitebox networks have
    reach-chains thousands deep and overflow Python's recursion limit.
    Cycle-safe: NHD flowline graphs are NOT always forests (coastal tidal
    channels, canals, braided and divergent reaches form cycles), so a
    back-edge to a node already on the DFS stack is skipped rather than
    re-pushed. A naive post-order re-pushes cycle nodes forever, which is
    what made coastal tiles hang and grow memory until OOM.
    """
    order: dict[int, int] = {}
    for r in roots:
        if r in order:
            continue
        stack: list[tuple[int, object]] = [(r, iter(children_of.get(r, [])))]
        onstack: set[int] = {r}
        while stack:
            node, it = stack[-1]
            descended = False
            for child in it:
                if child in order or child in onstack:
                    continue  # finalized, or a back-edge (cycle): skip
                stack.append((child, iter(children_of.get(child, []))))
                onstack.add(child)
                descended = True
                break
            if descended:
                continue
            kids = [c for c in children_of.get(node, []) if c in order]
            if not kids:
                order[node] = 1
            else:
                co = [order[k] for k in kids]
                m = max(co)
                order[node] = m if co.count(m) == 1 else m + 1
            onstack.discard(node)
            stack.pop()
    return order


def stats_from_flowlines(
    path,
    *,
    snap_tolerance: float = 1e-4,
    area_km2: float | None = None,
    clip_bbox: tuple[float, float, float, float] | None = None,
) -> BranchingStats:
    """Build a network from flow-oriented line segments and summarize it.

    Source-agnostic: takes any flowline vector (NHD flowline GeoJSON, or
    whitebox raster_streams_to_vector output) and builds the same snapped
    directed graph, so the NHD reference side and the whitebox ceiling side
    are counted identically (per-segment Strahler on a graph, never raster
    cells). This consistency is what makes the ceiling comparison
    (whitebox-vs-NHD) commensurate with the construct comparison
    (PH-vs-NHD).

    Args:
        path: a flowline vector readable by geopandas (GeoJSON, shapefile).
        snap_tolerance: degrees within which endpoints are treated as the
            same node (1e-4 deg ~ 11 m at the equator).
        area_km2: tile area for drainage density; if None, density is NaN.
        clip_bbox: if set, (min_lon, min_lat, max_lon, max_lat) to clip the
            flowlines to before building the graph. Used when the DEM side
            was windowed, so the NHD reference covers the same extent as the
            windowed PH/whitebox network rather than the full tile.

    Returns:
        BranchingStats. Direction is inferred from vertex order: the last
        vertex of each segment is its downstream end. This holds for NHD
        (digitized upstream-to-downstream) and for whitebox stream vectors
        (oriented along the D8 pointer). If a source violates this, roots
        and hence Strahler order would be mis-assigned; both sources here
        satisfy it.
    """
    import geopandas as gpd
    from shapely.geometry import LineString, MultiLineString

    geojson_path = path

    gdf = gpd.read_file(geojson_path)
    if clip_bbox is not None and len(gdf):
        min_lon, min_lat, max_lon, max_lat = clip_bbox
        gdf = gdf.cx[min_lon:max_lon, min_lat:max_lat]

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
    """Branching summary of a PH-derived merge tree (the metric side).

    Junctions and Strahler are read off the segment graph (one node per
    merge-tree confluence; degree-2 runs already collapsed during the
    donor union-find), so they sit in the same representational units
    as the NHD-side and whitebox-side flowline-graph stats. Horton R_b
    is computed on the LARGEST basin only (see
    segment_graph.bifurcation_ratio_largest_basin for why per-tile
    forests inflate this on real tiles).
    """
    from geo_tda.topo_eval.segment_graph import (
        bifurcation_ratio_largest_basin,
        segment_graph_from_merge_tree,
    )

    sg = segment_graph_from_merge_tree(tree)
    dist = sg.strahler_distribution()
    rb = bifurcation_ratio_largest_basin(tree)
    if area_km2 and channel_cell_count and cell_km:
        total_len_km = channel_cell_count * cell_km
        density = total_len_km / area_km2
    else:
        density = float("nan")
    return BranchingStats(
        junction_count=sg.num_junctions,
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
