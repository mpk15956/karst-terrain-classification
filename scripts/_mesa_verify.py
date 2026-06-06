"""Throwaway: MESA franklin_gpu verification + in-distribution stats.

Runs in the MESA conda env on a GPU node (offline; node has no internet).
Confirms the GPU is used and weights load, generates one (image, dem), saves
the dem as .npy for the donor-precondition check (run separately in the
project env, which has whitebox/rasterio), and prints in-distribution stats.
"""
import os
import sys

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
MESA = "/home/mpk15956/mesa"
sys.path.insert(0, MESA)

import numpy as np
import torch

print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0))

from pipeline_terrain import TerrainDiffusionPipeline

pipe = TerrainDiffusionPipeline.from_pretrained(f"{MESA}/weights", torch_dtype=torch.float16)
pipe.to("cuda")
print("pipeline loaded")

prompt = "A sentinel-2 image of montane forests and mountains with dendritic river valleys"
out = pipe(prompt, num_inference_steps=50, guidance_scale=7.5)
print("output type:", type(out))

# README: image, dem = pipe(...). Be defensive about the container/format.
if isinstance(out, (tuple, list)) and len(out) == 2:
    image, dem = out
else:
    image, dem = None, out

d = np.asarray(dem, dtype=np.float64)
print("dem type", type(dem), "shape", d.shape)
while d.ndim > 3 and d.shape[0] == 1:   # squeeze batch
    d = d[0]
if d.ndim == 3 and d.shape[-1] in (3, 4):  # RGB-rendered depth -> scalar
    ch = d[..., :3]
    chdev = float(np.abs(ch - ch.mean(axis=-1, keepdims=True)).max())
    print("3-channel dem; max channel deviation from mean %.4f (near 0 => grayscale depth)" % chdev)
    d2 = ch.mean(axis=-1)
elif d.ndim == 3:
    d2 = d[0]
else:
    d2 = d
print("scalar dem shape", d2.shape)
print("dem range [%.4f, %.4f] mean %.4f std %.4f" % (
    float(np.nanmin(d2)), float(np.nanmax(d2)), float(np.nanmean(d2)), float(np.nanstd(d2))))
# terrain-like proxy: gradient energy relative to range (flat noise -> high; real terrain -> structured)
gy, gx = np.gradient(d2.astype(float))
grad_rms = float(np.sqrt((gx**2 + gy**2).mean()))
rng = float(np.nanmax(d2) - np.nanmin(d2)) or 1.0
print("grad_rms %.5f  grad_rms/range %.5f" % (grad_rms, grad_rms / rng))

os.makedirs(f"{MESA}/out", exist_ok=True)
np.save(f"{MESA}/out/dem_verify.npy", d2.astype("float32"))
print("saved", f"{MESA}/out/dem_verify.npy", "shape", d2.shape)
