"""Embed the rendered M2 patches with Inception + CLIP (MESA conda env, GPU).

Stage B of the optical contrast. Loads the uint8 RGB stacks from
m2_optical_render.py and produces feature matrices for two backbones x two
renders x {real, gen}. Inception = the field-standard FID backbone (ImageNet
features, ~one affine transform from ImageNet logits -> expected to be
drainage-insensitive, Kynkaanniemi 2023); CLIP = the richer/general backbone
(the load-bearing one: if CLIP is also insensitive, that is the strong result).

Offline: weights pre-staged in ~/.cache by prefetch_embeddings.py.
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import argparse
import json
from pathlib import Path

import numpy as np
import torch

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def _inception():
    from torchvision.models import inception_v3, Inception_V3_Weights
    m = inception_v3(weights=Inception_V3_Weights.IMAGENET1K_V1,
                     transform_input=False, aux_logits=True)
    m.fc = torch.nn.Identity()  # -> 2048-d pooled features
    return m.eval().cuda()


def _embed_inception(model, imgs, bs=32):
    out = []
    mean = IMAGENET_MEAN.cuda(); std = IMAGENET_STD.cuda()
    for k in range(0, len(imgs), bs):
        x = torch.from_numpy(imgs[k:k + bs]).float().cuda().permute(0, 3, 1, 2) / 255.0
        x = torch.nn.functional.interpolate(x, size=(299, 299), mode="bilinear",
                                            align_corners=False)
        x = (x - mean) / std
        with torch.no_grad():
            out.append(model(x).cpu().numpy())
    return np.concatenate(out)


def _embed_clip(model, proc, imgs, bs=32):
    out = []
    for k in range(0, len(imgs), bs):
        batch = [imgs[m] for m in range(k, min(k + bs, len(imgs)))]
        inp = proc(images=batch, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out.append(model.get_image_features(**inp).cpu().numpy())
    return np.concatenate(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="embed rendered patches")
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_optical_cache"))
    args = ap.parse_args()

    print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)
    incep = _inception()
    from transformers import CLIPModel, CLIPProcessor
    clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval().cuda()
    cproc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    print("backbones loaded", flush=True)

    for render in ("hill", "stack"):
        for which in ("real", "gen"):
            imgs = np.load(args.cache / f"{which}_{render}.npy")
            fi = _embed_inception(incep, imgs)
            fc = _embed_clip(clip, cproc, list(imgs))
            np.save(args.cache / f"{which}_incep_{render}.npy", fi)
            np.save(args.cache / f"{which}_clip_{render}.npy", fc)
            print(f"{which}_{render}: incep {fi.shape} clip {fc.shape}", flush=True)
    print("DONE embedding", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
