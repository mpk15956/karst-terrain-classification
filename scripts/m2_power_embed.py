"""Power probe stage 2: embed the base + perturbed renders (MESA env, GPU).

Same backbones as the contrast (CLIP primary, Inception secondary). Loads
base_/pert_ {hill,stack}.npy from stage 1, saves feature matrices for stage 3.
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import argparse
from pathlib import Path

import numpy as np
import torch

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def _inception():
    from torchvision.models import inception_v3, Inception_V3_Weights
    m = inception_v3(weights=Inception_V3_Weights.IMAGENET1K_V1,
                     transform_input=False, aux_logits=True)
    m.fc = torch.nn.Identity()
    return m.eval().cuda()


def _embed_incep(model, imgs, bs=32):
    out = []; mean = IMAGENET_MEAN.cuda(); std = IMAGENET_STD.cuda()
    for k in range(0, len(imgs), bs):
        x = torch.from_numpy(imgs[k:k + bs]).float().cuda().permute(0, 3, 1, 2) / 255.0
        x = torch.nn.functional.interpolate(x, size=(299, 299), mode="bilinear", align_corners=False)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("results/validity/m2_power_probe"))
    args = ap.parse_args()
    print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)
    incep = _inception()
    from transformers import CLIPModel, CLIPProcessor
    clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval().cuda()
    cproc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    for which in ("base", "pert"):
        for render in ("hill", "stack"):
            imgs = np.load(args.cache / f"{which}_{render}.npy")
            np.save(args.cache / f"{which}_incep_{render}.npy", _embed_incep(incep, imgs))
            np.save(args.cache / f"{which}_clip_{render}.npy", _embed_clip(clip, cproc, list(imgs)))
            print(f"{which}_{render}: {len(imgs)} embedded", flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
