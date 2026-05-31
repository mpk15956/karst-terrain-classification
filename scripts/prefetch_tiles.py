"""Stage Phase C tile inputs for an offline compute-node run.

GACRC compute nodes have no outbound internet; only the login node does.
This script reads a tile_manifest.json and downloads every tile's 3DEP DEM
and NHD flowline GeoJSON into data/dem and data/nhd, so the construct run
on the compute node is fully offline (validity_real_construct.py is
offline-first: it uses staged files by key and never opens the STAC
catalog when both are present).

Run on the LOGIN node, in the repo root, before sbatch. Network dependent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from geo_tda.topo_eval.pipeline import acquire_tiles


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage DEM + NHD for a tile manifest")
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()

    tiles = json.loads(args.manifest.read_text()).get("tiles", [])
    if not tiles:
        print("manifest has no tiles")
        return 1

    staged, failed = [], []
    for t in tiles:
        key = t["key"]
        got = acquire_tiles(tuple(t["bbox"]), n_tiles=1)
        if got and got[0].dem_path.exists() and got[0].nhd_path \
                and got[0].nhd_path.exists():
            staged.append(key)
            print(f"staged {key}: {got[0].dem_path.name} + {got[0].nhd_path.name}")
        else:
            failed.append(key)
            print(f"FAILED {key}")

    print(f"\nstaged {len(staged)}/{len(tiles)} tiles; failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
