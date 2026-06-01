"""Pull Copernicus GLO-30 DEM at the locked teach_run footprints.

GLO-30 is MESA's training substrate. Pulling it at the SAME footprints as the
3DEP tiles gives matched real-vs-real 3DEP/GLO-30 pairs, which are (a) the
input to the deferred resolution-confound probe and (b) the substrate-matched
M2 real reference. This is the cheap half of M2 step 1: network only, no GPU.

Covering-item selection guards the corner-touching-neighbor failure (bug 1):
pick the STAC item with maximum bbox overlap, not just any intersecting tile.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
GLO30_COLLECTION = "cop-dem-glo-30"


def _overlap(bbox, ib) -> float:
    if not ib:
        return 0.0
    ox = max(0.0, min(bbox[2], ib[2]) - max(bbox[0], ib[0]))
    oy = max(0.0, min(bbox[3], ib[3]) - max(bbox[1], ib[1]))
    return ox * oy


def pull_glo30(bbox, dest: Path) -> Path | None:
    import planetary_computer
    import requests
    from pystac_client import Client

    cat = Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)
    items = list(cat.search(collections=[GLO30_COLLECTION], bbox=bbox).item_collection())
    if not items:
        return None
    item = max(items, key=lambda it: _overlap(bbox, getattr(it, "bbox", None)))
    if _overlap(bbox, getattr(item, "bbox", None)) <= 0:
        return None
    asset = item.assets.get("data")
    if asset is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with requests.get(asset.href, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull GLO-30 at teach_run footprints")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("data/glo30"))
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text())["tiles"]
    ok, failed = [], []
    for t in tiles:
        dest = args.out_dir / f"{t['key']}.tif"
        if dest.exists():
            ok.append(t["key"])
            print(f"have {t['key']}")
            continue
        try:
            r = pull_glo30(tuple(t["bbox"]), dest)
        except Exception as exc:  # noqa: BLE001
            r, exc_s = None, str(exc)
            print(f"FAILED {t['key']}: {exc_s}")
        if r:
            ok.append(t["key"])
            print(f"pulled {t['key']}")
        elif t["key"] not in [x for x in ok]:
            failed.append(t["key"])
    print(f"\nGLO-30: {len(ok)}/{len(tiles)} staged; failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
