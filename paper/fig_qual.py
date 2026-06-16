"""Whitebox-dependent manuscript figures: Fig 1 (pipeline on a real patch) and
Fig 7 (real vs MESA, "looks fine, routes wrong").

Local recompute on elis (WhiteboxTools v2.4.0): a real GLO-30 patch and a MESA
sample patch -> D8 flow accumulation -> donor-graph merge tree -> H0 diagram, at
the common target density. Faithful to the analysis (same pipeline, same density);
this is figure-input recompute, not a new experiment. Reuses scripts/render_terrain_rgb
and src/geo_tda/topo_eval. Seconds per patch.

Run from the repo root: .pixi/envs/cpu/bin/python paper/fig_qual.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from render_terrain_rgb import robust_bounds, render_hillshade_rgb  # noqa: E402
from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation  # noqa: E402
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation, persistence_diagram  # noqa: E402
from geo_tda.topo_eval.pipeline import (  # noqa: E402
    _cell_km, _tile_area_km2, _tile_bbox_from_raster, tau_for_target_density,
)

import whitebox  # noqa: E402
whitebox.WhiteboxTools().set_max_procs(1)

PATCH = 768
CELL_DEG = 1.0 / 3600
FIGS = ROOT / "paper" / "figures"
VAL = ROOT / "results" / "validity"
TARGET_DENSITY = float(json.loads((VAL / "m2_power.json").read_text())["target_density"])


def process(dem: np.ndarray) -> dict:
    """DEM patch -> (hillshade rgb, accumulation, channel mask, H0 diagram, tau)."""
    wd = Path(tempfile.mkdtemp(prefix="fig_"))
    try:
        tif = wd / "p.tif"
        prof = dict(driver="GTiff", height=PATCH, width=PATCH, count=1, dtype="float32",
                    crs="EPSG:4326", transform=from_origin(-85, 36, CELL_DEG, CELL_DEG),
                    compress="none", tiled=False)
        with rasterio.open(tif, "w", **prof) as d:
            d.write(dem.astype("float32"), 1)
        bbox = _tile_bbox_from_raster(tif)
        area = _tile_area_km2(bbox)
        codes, accum = d8_pointer_and_accumulation(tif, workdir=str(wd))
        tau = tau_for_target_density(accum, TARGET_DENSITY, area, _cell_km(bbox, (PATCH, PATCH)))
        tree = merge_tree_from_accumulation(codes, accum, tau)
        dgm = [(b, d) for (b, d) in persistence_diagram(tree)
               if d is not None and np.isfinite(d) and np.isfinite(b)]
        mask = accum >= tau
        return {"hill": render_hillshade_rgb(dem, bounds=robust_bounds(dem)),
                "accum": accum, "mask": mask, "dgm": dgm, "tau": tau}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def pick_real_patch() -> np.ndarray:
    """Highest-relief 768 window of a locally-available mountainous (cumberland) tile."""
    tm = json.loads((VAL / "teach_run_20260530" / "tile_manifest.json").read_text())["tiles"]
    glo = ROOT / "data" / "glo30"
    cand = [t["key"] for t in tm if t["province"] == "cumberland_plateau" and (glo / f"{t['key']}.tif").exists()]
    cand = cand or [t["key"] for t in tm if (glo / f"{t['key']}.tif").exists()]
    key = cand[0]
    best, best_g = None, -1.0
    with rasterio.open(glo / f"{key}.tif") as s:
        H, W = s.height, s.width
        for i in range(0, H - PATCH + 1, PATCH):
            for j in range(0, W - PATCH + 1, PATCH):
                arr = s.read(1, window=Window(j, i, PATCH, PATCH)).astype("float32")
                if arr.shape != (PATCH, PATCH) or not np.isfinite(arr).all():
                    continue
                gy, gx = np.gradient(arr)
                g = float(np.sqrt(gy ** 2 + gx ** 2).mean())
                if g > best_g:
                    best_g, best = g, arr
    print(f"  real patch: tile {key}, gradient-rms {best_g:.3f}")
    return best


def plot_pd(ax, dgm, title):
    if not dgm:
        ax.text(0.5, 0.5, "no finite features", ha="center"); return
    b = np.array([x[0] for x in dgm], float)
    d = np.array([x[1] for x in dgm], float)
    fin = np.isfinite(b) & np.isfinite(d) & (b > 0) & (d > 0)
    b, d = b[fin], d[fin]
    if b.size == 0:
        ax.text(0.5, 0.5, "no finite features", ha="center"); return
    ax.scatter(b, d, s=6, alpha=0.5, color="#0072B2", edgecolors="none")
    lo = max(1.0, float(min(b.min(), d.min())) * 0.8)
    hi = float(max(b.max(), d.max())) * 1.2
    lim = [lo, hi]
    ax.plot(lim, lim, "k-", lw=0.6)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("birth (accumulation)"); ax.set_ylabel("death")
    ax.set_title(f"{title}  (n={len(dgm)} H0 features)", fontsize=8.5)


def overlay_network(ax, hill, mask, title):
    ax.imshow(hill)
    over = np.zeros((*mask.shape, 4))
    over[mask] = (0.85, 0.10, 0.10, 0.9)  # red channels
    ax.imshow(over)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=8.5)


def fig_pipeline(real):
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.6))
    axes[0].imshow(real["hill"]); axes[0].set_xticks([]); axes[0].set_yticks([])
    axes[0].set_title("(a) DEM hillshade\n(a physical ridgeline)", fontsize=8.5)
    la = np.log10(real["accum"].astype(float) + 1)
    im = axes[1].imshow(la, cmap="cividis"); axes[1].set_xticks([]); axes[1].set_yticks([])
    axes[1].set_title("(b) D8 flow accumulation\n(log scale)", fontsize=8.5)
    fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    overlay_network(axes[2], real["hill"], real["mask"],
                    "(c) channel network at\nmatched NHD density")
    plot_pd(axes[3], real["dgm"], "(d) H0 persistence diagram")
    fig.suptitle("From physical terrain to drainage topology: the donor-graph merge tree of flow accumulation",
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"fig-pipeline.{ext}")
    plt.close(fig)
    print("  wrote figures/fig-pipeline.pdf/.png")


def fig_qualitative(real, mesa):
    fig, axes = plt.subplots(2, 3, figsize=(10, 6.6))
    for row, (d, lab) in enumerate([(real, "real (GLO-30)"), (mesa, "MESA-generated")]):
        axes[row, 0].imshow(d["hill"]); axes[row, 0].set_xticks([]); axes[row, 0].set_yticks([])
        axes[row, 0].set_ylabel(lab, fontsize=10)
        axes[row, 0].set_title("hillshade (looks like terrain)" if row == 0 else "", fontsize=8.5)
        overlay_network(axes[row, 1], d["hill"], d["mask"],
                        "channel network" if row == 0 else "")
        plot_pd(axes[row, 2], d["dgm"], "H0 diagram" if row == 0 else "")
    fig.suptitle("Looks fine, routes wrong: comparable appearance, different drainage topology", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"fig-qualitative.{ext}")
    plt.close(fig)
    print("  wrote figures/fig-qualitative.pdf/.png")


def main():
    print("=== whitebox figures ===")
    real = process(pick_real_patch())
    mesa_npy = sorted((VAL / "mesa_batch113").glob("cumberland_plateau_*.npy"))[0]
    print(f"  mesa patch: {mesa_npy.name}")
    mesa = process(np.load(mesa_npy).astype("float32"))
    fig_pipeline(real)
    fig_qualitative(real, mesa)
    print("done.")


if __name__ == "__main__":
    main()
