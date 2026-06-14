"""Structured-null DEMs: phase-randomized Fourier surrogates of real patches.

The zero-drainage CEILING for the H0 scale (project pixi env; pure numpy +
rasterio, parallel-safe). Each surrogate has the IDENTICAL power spectrum as its
source real patch (so it is terrain-like in roughness, NOT trivially separable
like white noise) but RANDOMIZED phase (so it has no organized drainage). H0
should reject it far above MESA's 3.12x, bracketing MESA between gross
disorganization (this null) and localized incision (the trench, ~0).

Output: results/validity/noise_batch/*.npy, consumed by m2_generated_vs_real.py
(same H0 contrast machinery) with a noise cache.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

PATCH = 768


def phase_randomize(dem: np.ndarray, rng) -> np.ndarray:
    """Fourier surrogate: keep |F|, randomize phase. rfft2/irfft2 enforce the
    Hermitian symmetry automatically and return a real field, so the power
    spectrum is preserved (terrain-like roughness) while phase -- hence all
    spatial/drainage organization -- is destroyed."""
    F = np.fft.rfft2(dem.astype("float64"))
    mag = np.abs(F)
    ph = rng.uniform(-np.pi, np.pi, size=F.shape)
    surro = np.fft.irfft2(mag * np.exp(1j * ph), s=dem.shape)
    return surro.astype("float32")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--glo30-dir", type=Path, default=Path("data/glo30"))
    ap.add_argument("--out", type=Path, default=Path("results/validity/noise_batch"))
    ap.add_argument("--n", type=int, default=114)  # match the MESA batch n
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tiles = json.loads(args.manifest.read_text())["tiles"]
    rng = np.random.default_rng(args.seed)
    # gather real windows (first few per tile, round-robin) until n surrogates
    windows = []
    for t in tiles:
        f = args.glo30_dir / f"{t['key']}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as s:
            H, W = s.height, s.width
        for i in range(0, H - PATCH + 1, PATCH):
            for j in range(0, W - PATCH + 1, PATCH):
                windows.append((str(f), i, j))
    rng.shuffle(windows)
    made = 0
    for (path, i, j) in windows:
        if made >= args.n:
            break
        with rasterio.open(path) as s:
            arr = s.read(1, window=Window(j, i, PATCH, PATCH)).astype("float32")
        if arr.shape != (PATCH, PATCH):
            continue
        surro = phase_randomize(arr, rng)
        np.save(args.out / f"noise_{made:03d}.npy", surro)
        made += 1
    print(f"wrote {made} phase-randomized surrogate DEMs to {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
