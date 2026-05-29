"""End-to-end filtration: DEM (or flow grids) to merge tree and diagram.

Ties the pieces together. From a real DEM, run whitebox to get the D8
pointer and accumulation (hydrology), translate, build the donor-graph
merge tree (merge_tree), and read off the persistence diagram. From toy
flow grids, skip whitebox and go straight to the merge tree.

The cubical-complex persistence wrapper for the elevation-sublevel
baseline lives in geo_tda.persistence, NOT here; this module is the
flow-accumulation channel construction only.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from geo_tda.topo_eval.merge_tree import (
    MergeTree,
    merge_tree_from_accumulation,
    persistence_diagram,
)


def filtration_from_flow_grids(
    flow_dir: np.ndarray,
    accumulation: np.ndarray,
    tau_channel: float,
) -> tuple[MergeTree, list[tuple[float, float]]]:
    """Merge tree + persistence diagram from precomputed flow grids.

    The toy path (no whitebox): callers supply D8 receiver codes and an
    accumulation field directly.
    """
    tree = merge_tree_from_accumulation(flow_dir, accumulation, tau_channel)
    diagram = persistence_diagram(tree)
    return tree, diagram


def filtration_from_dem(
    dem_path: str | Path,
    *,
    tau_channel: float,
    condition: str = "breach",
    workdir: str | Path | None = None,
) -> tuple[MergeTree, list[tuple[float, float]], np.ndarray]:
    """Merge tree + persistence diagram + accumulation field from a DEM.

    The real path: runs whitebox conditioning + D8 pointer + accumulation,
    then builds the donor-graph merge tree. Returns the accumulation field
    too so callers can compute the channel mask and the H1 diagnostic.
    """
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation

    receiver_codes, accumulation = d8_pointer_and_accumulation(
        dem_path, condition=condition, workdir=workdir
    )
    tree = merge_tree_from_accumulation(receiver_codes, accumulation, tau_channel)
    diagram = persistence_diagram(tree)
    return tree, diagram, accumulation
