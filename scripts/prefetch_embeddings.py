"""Pre-download embedding weights for the optical contrast (INTERNET node only).

Compute nodes have no internet, so the CLIP + Inception weights must be cached
first (none are, verified). Run this on the teach TRANSFER node (txfer), which
has internet + the shared home filesystem, in the MESA conda env (has
torch/torchvision/transformers). The GPU embed job then loads them offline
(HF_HUB_OFFLINE=1, TORCH_HOME set to the same cache).

Downloads (~700 MB total):
  - InceptionV3 ImageNet weights (torchvision) -> TORCH_HOME / torch hub cache
  - CLIP ViT-B/32 (openai/clip-vit-base-patch32) -> HF hub cache
"""
import os


def main() -> int:
    print("downloading InceptionV3 (torchvision)...", flush=True)
    import torchvision
    from torchvision.models import inception_v3, Inception_V3_Weights
    m = inception_v3(weights=Inception_V3_Weights.IMAGENET1K_V1)
    print("  inception_v3 weights cached; torch hub:",
          os.environ.get("TORCH_HOME", "~/.cache/torch"), flush=True)
    del m

    print("downloading CLIP ViT-B/32 (transformers)...", flush=True)
    from transformers import CLIPModel, CLIPProcessor
    CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    print("  CLIP cached; HF hub:",
          os.environ.get("HF_HOME", "~/.cache/huggingface"), flush=True)

    print("DONE: embedding weights staged for offline use.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
