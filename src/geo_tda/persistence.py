"""Cubical-complex persistent homology on 2D scalar fields.

The elevation-sublevel-set baseline that the flow-accumulation channel
construction is contrasted against (Section 7 of the proof). This is
spatial-grid (cubical) persistence on the raw scalar field, used ONLY
for the baseline comparison; the channel merge tree is built by
geo_tda.topo_eval.merge_tree on the D8 flow graph, NOT here.

Promoted from notebooks/minimal_exploration/compute_features.ipynb,
reduced to the diagram-computation core (the notebook also had
giotto-tda vectorization for the karst classifier, which the methods
paper does not need).
"""
from __future__ import annotations

import numpy as np


def sanitize_field(field: np.ndarray) -> np.ndarray:
    """Coerce a raster to a finite float64 field fit for cubical PH.

    NaN/inf are replaced by the field's finite max (so nodata does not
    create spurious deep sublevel components). Returns a contiguous
    float64 copy.
    """
    arr = np.asarray(field, dtype=np.float64)
    finite = np.isfinite(arr)
    if not finite.any():
        raise ValueError("field has no finite values")
    fill = arr[finite].max()
    out = np.where(finite, arr, fill)
    return np.ascontiguousarray(out)


def sublevel_diagram(
    field: np.ndarray, *, maxdim: int = 1
) -> dict[int, np.ndarray]:
    """Sublevel-set cubical persistence diagram of a 2D scalar field.

    Uses cripser (Cubical Ripser), which computes sublevel-set
    persistence on the lower-star filtration of the grid. Returns a dict
    mapping homology degree -> (n, 2) array of (birth, death) pairs.

    Args:
        field: 2D scalar field (e.g. a DEM elevation tile).
        maxdim: maximum homology degree to compute (0 and 1 by default).

    Returns:
        {degree: array of (birth, death)} for degree in 0..maxdim.
        Infinite deaths are represented as np.inf.
    """
    import cripser

    arr = sanitize_field(field)
    # cripser returns rows: dim, birth, death, x1, y1, z1, x2, y2, z2
    raw = cripser.computePH(arr, maxdim=maxdim)
    out: dict[int, np.ndarray] = {}
    for d in range(maxdim + 1):
        rows = raw[raw[:, 0] == d]
        pairs = rows[:, 1:3].astype(np.float64)
        # cripser encodes essential deaths as a large sentinel; map to inf
        sentinel = arr.max() + 1.0
        pairs[pairs[:, 1] >= sentinel, 1] = np.inf
        out[d] = pairs
    return out


def superlevel_diagram(
    field: np.ndarray, *, maxdim: int = 1
) -> dict[int, np.ndarray]:
    """Superlevel-set cubical persistence by negating the field.

    Superlevel persistence of f is sublevel persistence of -f with the
    birth/death heights negated back. Provided for completeness; the
    elevation baseline in the paper uses sublevel by default.
    """
    arr = sanitize_field(field)
    neg = sublevel_diagram(-arr, maxdim=maxdim)
    out: dict[int, np.ndarray] = {}
    for d, pairs in neg.items():
        flipped = -pairs[:, ::-1]  # (birth,death) of -f -> (death,birth) negated
        out[d] = flipped
    return out


def total_persistence(diagram: np.ndarray) -> float:
    """Sum of (death - birth) over finite pairs of one degree's diagram."""
    if diagram.size == 0:
        return 0.0
    finite = diagram[np.isfinite(diagram[:, 1])]
    if finite.size == 0:
        return 0.0
    return float((finite[:, 1] - finite[:, 0]).sum())
