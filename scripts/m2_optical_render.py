"""Render the M2 real + generated DEM patches to scale-normalized RGB images.

Stage A of the optical contrast (project pixi env: rasterio + numpy; the MESA
env, which has torch, lacks rasterio, so render here and embed there). Pure
numpy/rasterio -> parallel-safe (no whitebox). Each patch is robust-normalized
by its OWN bounds (per-patch scale-invariance, the artifact guard), so the
optical metric sees terrain appearance, not the [0,1]-vs-meters scale.

Real patches = ALL non-overlapping 768px windows of every staged GLO-30 tile
(deterministic, complete; optical embedding has no whitebox failures so we use
the full real population rather than the whitebox-survivor subset -- each metric
is judged against its OWN matched-n null, so the comparable quantity is the
test/floor ratio). Generated = the 114 mesa_batch113 patches.

Writes uint8 image stacks (hillshade + geomorphic stack) + the by-tile ordering
to results/validity/m2_optical_cache/, consumed by m2_optical_embed.py.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

import sys
sys.path.insert(0, "scripts")
from render_terrain_rgb import render_hillshade_rgb, render_stack_rgb

PATCH = 768


def _render_real(spec):
    path, i, j = spec
    with rasterio.open(path) as s:
        arr = s.read(1, window=Window(j, i, PATCH, PATCH)).astype("float32")
    if arr.shape != (PATCH, PATCH):
        return None
    return render_hillshade_rgb(arr), render_stack_rgb(arr)


def _render_gen(npy):
    arr = np.load(npy).astype("float32")
    return render_hillshade_rgb(arr), render_stack_rgb(arr)


def main() -> int:
    ap = argparse.ArgumentParser(description="render M2 patches to RGB")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--mesa-dir", type=Path, default=Path("results/validity/mesa_batch113"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/m2_optical_cache"))
    ap.add_argument("--cpus", type=int, default=16)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tiles = json.loads(args.manifest.read_text())["tiles"]
    # real: all 768 windows per tile, row-major; build tile_to_idx in that order
    real_specs = []; tile_to_idx = {}; prov_by_tile = {}
    for t in tiles:
        f = args.glo30_dir / f"{t['key']}.tif"
        if not f.exists():
            continue
        prov_by_tile[t["key"]] = t["province"]
        with rasterio.open(f) as s:
            H, W = s.height, s.width
        idxs = []
        for i in range(0, H - PATCH + 1, PATCH):
            for j in range(0, W - PATCH + 1, PATCH):
                idxs.append(len(real_specs)); real_specs.append((str(f), i, j))
        tile_to_idx[t["key"]] = idxs
    gen_files = sorted(str(p) for p in args.mesa_dir.glob("*.npy"))
    gen_prov = [Path(g).name.rsplit("_", 1)[0] for g in gen_files]
    print(f"rendering real={len(real_specs)} gen={len(gen_files)} on {args.cpus} cores", flush=True)

    with mp.Pool(args.cpus) as pool:
        real = pool.map(_render_real, real_specs)
        gen = pool.map(_render_gen, gen_files)
    # filter any shape failures (shouldn't happen for full windows)
    keep = [k for k, r in enumerate(real) if r is not None]
    if len(keep) != len(real):
        remap = {old: new for new, old in enumerate(keep)}
        tile_to_idx = {t: [remap[i] for i in idxs if i in remap] for t, idxs in tile_to_idx.items()}
        real = [real[k] for k in keep]

    real_hill = np.stack([r[0] for r in real]); real_stack = np.stack([r[1] for r in real])
    gen_hill = np.stack([g[0] for g in gen]); gen_stack = np.stack([g[1] for g in gen])
    np.save(args.out / "real_hill.npy", real_hill)
    np.save(args.out / "real_stack.npy", real_stack)
    np.save(args.out / "gen_hill.npy", gen_hill)
    np.save(args.out / "gen_stack.npy", gen_stack)
    (args.out / "tile_to_idx.json").write_text(json.dumps(tile_to_idx))
    (args.out / "prov_by_tile.json").write_text(json.dumps(prov_by_tile))
    (args.out / "gen_provinces.json").write_text(json.dumps(gen_prov))
    print(f"wrote real {real_hill.shape} gen {gen_hill.shape} to {args.out}", flush=True)
    print(f"real tiles={len(tile_to_idx)}; gen province mix="
          f"{ {p: gen_prov.count(p) for p in set(gen_prov)} }", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
