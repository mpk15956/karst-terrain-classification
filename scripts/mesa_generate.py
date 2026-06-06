"""Generate MESA terrain patches for the M2 distributional gate.

Runs in the MESA conda env on a GPU node (offline; node has no internet). Emits
one 768x768 DEM per inference call -- the MMD unit is the per-patch H0 diagram,
so N is counted in PATCHES, not tiles. Province prompts are the PRE-REGISTERED
strings (docs/topo_eval/notes/m2_distributional_gate.md): scene/relief/geology
only, with the drainage pattern (the dependent variable) deliberately NOT named,
so a topology match cannot be circular.

MESA's DEM channel is RGB-rendered grayscale in ~[0,1] (NOT meters); we decode
to a scalar by averaging channels and save float32. D8 routing is invariant to
monotonic elevation rescaling, so the [0,1] scale is fine for the H0
flow-accumulation statistic -- the comparability probe verifies this empirically
before any MMD is trusted.

Usage (on a GPU node, MESA conda env):
  python mesa_generate.py --out <dir> --counts cumberland_plateau=5,...
Writes <dir>/<province>_<i>.npy and <dir>/manifest.json (prompt, province, seed).
"""
import argparse
import json
import os
import sys

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
MESA = "/home/mpk15956/mesa"
sys.path.insert(0, MESA)

import numpy as np
import torch

# PRE-REGISTERED province prompts (scene/relief/geology only; no drainage words).
PROMPTS = {
    "cumberland_plateau":
        "A Sentinel-2 image of a forested dissected sandstone plateau with deep steep-walled valleys",
    "appalachian_highlands":
        "A Sentinel-2 image of forested parallel mountain ridges and intervening valleys",
    "coastal_plain":
        "A Sentinel-2 image of low-relief coastal plain with forests and wetlands",
}


def _decode_dem(dem) -> np.ndarray:
    """MESA dem -> single-band float32, mirroring _mesa_verify's decoding."""
    d = np.asarray(dem, dtype=np.float64)
    while d.ndim > 3 and d.shape[0] == 1:
        d = d[0]
    if d.ndim == 3 and d.shape[-1] in (3, 4):
        d = d[..., :3].mean(axis=-1)   # RGB-rendered depth -> scalar
    elif d.ndim == 3:
        d = d[0]
    return d.astype("float32")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate MESA patches for M2")
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", required=True,
                    help="province=N comma list, e.g. cumberland_plateau=5,appalachian_highlands=5,coastal_plain=5")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--guidance", type=float, default=7.5)
    ap.add_argument("--seed0", type=int, default=1000)
    args = ap.parse_args()

    counts = {}
    for tok in args.counts.split(","):
        k, v = tok.split("=")
        if k not in PROMPTS:
            raise SystemExit(f"unknown province {k!r}; known: {list(PROMPTS)}")
        counts[k] = int(v)

    os.makedirs(args.out, exist_ok=True)
    print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)
    if torch.cuda.is_available():
        print("device", torch.cuda.get_device_name(0), flush=True)

    from pipeline_terrain import TerrainDiffusionPipeline
    pipe = TerrainDiffusionPipeline.from_pretrained(f"{MESA}/weights", torch_dtype=torch.float16)
    pipe.to("cuda")
    print("pipeline loaded", flush=True)

    manifest = []
    seed = args.seed0
    for province, n in counts.items():
        prompt = PROMPTS[province]
        for i in range(n):
            gen = torch.Generator(device="cuda").manual_seed(seed)
            out = pipe(prompt, num_inference_steps=args.steps,
                       guidance_scale=args.guidance, generator=gen)
            image, dem = (out if isinstance(out, (tuple, list)) and len(out) == 2
                          else (None, out))
            d = _decode_dem(dem)
            fn = f"{province}_{i:03d}.npy"
            np.save(os.path.join(args.out, fn), d)
            manifest.append({"file": fn, "province": province, "prompt": prompt,
                             "seed": seed, "steps": args.steps,
                             "guidance": args.guidance,
                             "dem_min": float(d.min()), "dem_max": float(d.max()),
                             "dem_mean": float(d.mean()), "dem_std": float(d.std())})
            print(f"  {fn}: range [{d.min():.4f},{d.max():.4f}] mean {d.mean():.4f}", flush=True)
            seed += 1

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump({"prompts": PROMPTS, "patches": manifest}, f, indent=2)
    print(f"wrote {len(manifest)} patches + manifest to {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
