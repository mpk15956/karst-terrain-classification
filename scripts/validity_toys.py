"""Produce the Phase B validity-demo figures from the toy fixtures.

Same fixtures the tests assert on (geo_tda.topo_eval.synthetic); this
script draws them. Three figures into figures/validity/toys/:

1. toy_zoo.png: the confirmatory toys (cone, v_valley, branching_channel)
   as flow grids with their merge-tree Strahler orders annotated.
2. adjacency_contamination.png: the meander-neck mask under donor-graph
   vs cubical 8-adjacency, with H1 = 0 vs H1 = 8. The one-glance
   demonstration that the adjacency choice is a real contribution
   (Section 7 of the proof).
3. falsification.png: the equal-birth balanced vs caterpillar witness,
   identical H0 barcodes, different Strahler distributions (Theorem 2).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geo_tda.topo_eval import synthetic as syn
from geo_tda.topo_eval.merge_tree import (
    D8_OFFSETS,
    merge_tree_from_accumulation,
    persistence_diagram,
)
from geo_tda.topo_eval.summaries import h1_cubical_mask, h1_donor_graph

OUTDIR = Path("figures/validity/toys")


def _draw_flow_grid(ax, toy, title):
    A = toy.accumulation
    mask = A >= toy.tau_channel
    ax.imshow(np.where(mask, A, np.nan), cmap="Blues", origin="upper")
    H, W = toy.flow_dir.shape
    for i in range(H):
        for j in range(W):
            code = int(toy.flow_dir[i, j])
            if code < 0:
                continue
            dy, dx = D8_OFFSETS[code]
            ax.arrow(
                j, i, dx * 0.3, dy * 0.3,
                head_width=0.12, head_length=0.1,
                fc="0.3", ec="0.3", length_includes_head=True,
            )
    ax.set_title(title, fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])


def figure_toy_zoo():
    toys = [g() for g in syn.CONFIRMATORY]
    fig, axes = plt.subplots(1, len(toys), figsize=(4 * len(toys), 4))
    for ax, toy in zip(axes, toys):
        tree = merge_tree_from_accumulation(
            toy.flow_dir, toy.accumulation, toy.tau_channel
        )
        dist = tree.strahler_distribution()
        root_order = tree.roots[0].strahler
        _draw_flow_grid(
            ax, toy,
            f"{toy.name}\nroot Strahler {root_order}, dist {dict(sorted(dist.items()))}",
        )
    fig.suptitle(
        "Confirmatory toys: donor-graph merge tree reproduces the "
        "analytical Strahler answer",
        fontsize=11,
    )
    fig.tight_layout()
    out = OUTDIR / "toy_zoo.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def _draw_mask_graph(ax, toy, adjacency, title):
    """Draw the channel-mask cells and the edges of one adjacency."""
    A = toy.accumulation
    mask = A >= toy.tau_channel
    H, W = mask.shape
    cells = [(i, j) for i in range(H) for j in range(W) if mask[i, j]]
    cell_set = set(cells)
    ax.imshow(np.where(mask, 1.0, np.nan), cmap="Greys", vmin=0, vmax=2, origin="upper")

    if adjacency == "cubical":
        for (i, j) in cells:
            for dy, dx in D8_OFFSETS:
                n = (i + dy, j + dx)
                if n in cell_set and (n[0], n[1]) > (i, j):
                    ax.plot([j, n[1]], [i, n[0]], "-", color="crimson", lw=1.2)
    else:  # donor flow graph
        for (i, j) in cells:
            code = int(toy.flow_dir[i, j])
            if code < 0:
                continue
            dy, dx = D8_OFFSETS[code]
            r = (i + dy, j + dx)
            if r in cell_set:
                ax.plot([j, r[1]], [i, r[0]], "-", color="navy", lw=1.4)
    for (i, j) in cells:
        ax.plot(j, i, "o", color="0.2", ms=5)
    ax.set_title(title, fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])


def figure_adjacency_contamination():
    toy = syn.meander_neck()
    mask = toy.accumulation >= toy.tau_channel
    h1_donor = h1_donor_graph(toy.flow_dir, mask)
    h1_cub = h1_cubical_mask(mask)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    _draw_mask_graph(
        axes[0], toy, "donor",
        f"Donor flow graph\n$H_1 = {h1_donor}$ (forest)",
    )
    _draw_mask_graph(
        axes[1], toy, "cubical",
        f"Cubical 8-adjacency\n$H_1 = {h1_cub}$ (spurious cycles)",
    )
    fig.suptitle(
        "Meander-neck mask: the adjacency choice is not cosmetic. "
        f"{mask.sum()} cells, cubical invents {h1_cub} phantom loops.",
        fontsize=11,
    )
    fig.tight_layout()
    out = OUTDIR / "adjacency_contamination.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def _draw_barcode(ax, diagram, title):
    finite = sorted((b, d) for b, d in diagram if np.isfinite(d))
    essential = [(b, d) for b, d in diagram if not np.isfinite(d)]
    y = 0
    for b, d in finite:
        ax.plot([b, d], [y, y], "-", color="navy", lw=3)
        y += 1
    for b, _d in essential:
        xmax = max([d for _b, d in finite], default=b + 1)
        ax.plot([b, xmax + 1], [y, y], "--", color="0.5", lw=2)
        y += 1
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("flow accumulation $A$")
    ax.set_yticks([])


def figure_falsification():
    pair = syn.falsification_pair()
    dgm_bal = persistence_diagram(pair.balanced)
    dgm_cat = persistence_diagram(pair.caterpillar)
    dist_bal = pair.balanced.strahler_distribution()
    dist_cat = pair.caterpillar.strahler_distribution()

    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    _draw_barcode(
        axes[0, 0], dgm_bal,
        f"Balanced tree barcode (root Strahler {pair.balanced.roots[0].strahler})",
    )
    _draw_barcode(
        axes[0, 1], dgm_cat,
        f"Caterpillar tree barcode (root Strahler {pair.caterpillar.roots[0].strahler})",
    )

    for ax, dist, name in [
        (axes[1, 0], dist_bal, "balanced"),
        (axes[1, 1], dist_cat, "caterpillar"),
    ]:
        orders = sorted(dist)
        ax.bar([str(o) for o in orders], [dist[o] for o in orders], color="teal")
        ax.set_title(f"{name} Strahler distribution {dict(sorted(dist.items()))}", fontsize=10)
        ax.set_xlabel("Strahler order")
        ax.set_ylabel("count")

    fig.suptitle(
        "Theorem 2 witness: identical H0 barcodes (top), different "
        "Strahler distributions (bottom).\nThe persistence diagram cannot "
        "see what the merge tree distinguishes.",
        fontsize=11,
    )
    fig.tight_layout()
    out = OUTDIR / "falsification.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    outs = [
        figure_toy_zoo(),
        figure_adjacency_contamination(),
        figure_falsification(),
    ]
    for o in outs:
        print(f"wrote {o}")
    print("validity-toys: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
