"""Phase C tile selection: physiographic spread by NHD flowline density.

Builds a tile_manifest.json for the construct-validity run. Scores candidate
1-degree tiles in three physiographic provinces (Cumberland Plateau,
Coastal Plain, Appalachian Highlands) by NHD flowline density, then picks
tiles per province whose densities span the corpus rather than cluster, so
the donor-graph merge tree is stressed across dendritic, low-gradient, and
trellis drainage regimes.

Scoring uses only NHD flowline vectors (no DEM download): cheap. Each
selected tile carries the forward-feed metadata that lets Milestone 2
re-acquire the SAME footprint on a generator-matched substrate (Copernicus
GLO-30 etc.) at native patch size; see
docs/topo_eval/notes/m2_reference_forward_feed.md. The resolution-invariant
anchor is NHD drainage density, which fixes the tau rule at any resolution.

Network dependent (NHD service). --quick scores a small candidate subset.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# Candidate 1-degree tile SW corners (lon, lat) per province. Chosen inland
# of the coast so 3DEP/NHD coverage is land, with enough candidates that the
# scorer can drop ocean/empty tiles and still span the density range.
CANDIDATES: dict[str, list[tuple[int, int]]] = {
    "cumberland_plateau": [
        (-85, 35), (-86, 35), (-85, 36), (-86, 36), (-84, 35),
        (-87, 34), (-85, 34), (-84, 36), (-87, 35), (-86, 34),
    ],
    "coastal_plain": [
        (-83, 31), (-82, 31), (-84, 32), (-82, 32), (-83, 32),
        (-85, 31), (-84, 31), (-81, 32), (-86, 31), (-83, 30),
    ],
    "appalachian_highlands": [
        (-82, 36), (-81, 36), (-83, 36), (-82, 37), (-80, 37),
        (-83, 37), (-81, 35), (-82, 35), (-80, 36), (-81, 37),
    ],
}

PICKS_PER_PROVINCE = {
    "cumberland_plateau": 7,
    "appalachian_highlands": 7,
    "coastal_plain": 6,
}

TAU_RULE = {
    "method": "match channel density to NHD drainage density",
    "target_cells": "round(nhd_drainage_density * area_km2 / cell_km)",
    "tau": "accumulation value with target_cells cells at or above it",
    "density_source": "NHD flowline vectors (resolution-invariant)",
    "note": "re-derives at any substrate resolution by swapping cell_km; "
    "sensitivity sweep is +/-10% around the matched tau",
}


def _tile_area_km2(bbox: tuple[float, float, float, float]) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lat = math.radians((min_lat + max_lat) / 2)
    km_per_deg_lon = 111.32 * math.cos(mid_lat)
    return abs((max_lon - min_lon) * km_per_deg_lon) * abs(
        (max_lat - min_lat) * 110.57
    )


def _key(lon: int, lat: int) -> str:
    ns, ew = ("n" if lat >= 0 else "s"), ("w" if lon < 0 else "e")
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def _footprint(bbox: tuple[float, float, float, float]) -> dict:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat],
            [min_lon, max_lat], [min_lon, min_lat],
        ]],
    }


def _score_tile(lon: int, lat: int, nhd_dir: Path) -> dict | None:
    """Fetch NHD flowlines for a 1-degree tile and score its density."""
    import geopandas as gpd

    from geo_tda.data_acquisition.nhd import fetch_nhd_flowlines

    bbox = (float(lon), float(lat), float(lon + 1), float(lat + 1))
    key = _key(lon, lat)
    dest = nhd_dir / f"{key}.geojson"
    try:
        if not dest.exists():
            fetch_nhd_flowlines(bbox, dest)
        gdf = gpd.read_file(dest)
    except Exception as exc:  # noqa: BLE001 - ocean/empty/service tiles dropped
        logger.warning("drop %s: %s", key, exc)
        return None
    if gdf.empty:
        return None
    total_len_km = float(gdf.geometry.length.sum()) * 111.0
    area = _tile_area_km2(bbox)
    density = total_len_km / area if area else float("nan")
    return {
        "key": key,
        "bbox": list(bbox),
        "footprint": _footprint(bbox),
        "nhd_flowline_count": int(len(gdf)),
        "nhd_total_length_km": total_len_km,
        "area_km2": area,
        "nhd_drainage_density": density,
        "tau_rule": TAU_RULE,
        "source": {"product": "USGS 3DEP seamless", "gsd_m": 30},
    }


def _quintile_edges(values: list[float]) -> list[float]:
    import numpy as np

    return [float(np.quantile(values, q)) for q in (0.2, 0.4, 0.6, 0.8)]


def _quintile_of(value: float, edges: list[float]) -> int:
    q = 1
    for e in edges:
        if value > e:
            q += 1
    return q  # 1..5


def _spread_pick(scored: list[dict], n: int) -> list[dict]:
    """Pick n tiles spanning the density range by evenly spaced rank."""
    if len(scored) <= n:
        return scored
    ordered = sorted(scored, key=lambda s: s["nhd_drainage_density"])
    if n <= 1:
        return [ordered[len(ordered) // 2]]
    idx = [round(i * (len(ordered) - 1) / (n - 1)) for i in range(n)]
    seen, picks = set(), []
    for i in idx:
        while i in seen and i < len(ordered) - 1:
            i += 1
        seen.add(i)
        picks.append(ordered[i])
    return picks


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Phase C tile manifest builder")
    today = datetime.date.today().strftime("%Y%m%d")
    ap.add_argument("--out", type=Path,
                    default=Path(f"results/validity/teach_run_{today}/tile_manifest.json"))
    ap.add_argument("--nhd-dir", type=Path, default=Path("data/nhd"))
    ap.add_argument("--quick", action="store_true",
                    help="score 3 candidates per province, pick 1 each")
    args = ap.parse_args()
    args.nhd_dir.mkdir(parents=True, exist_ok=True)

    all_scored: list[dict] = []
    by_province: dict[str, list[dict]] = {}
    for province, corners in CANDIDATES.items():
        cands = corners[:3] if args.quick else corners
        scored = []
        for lon, lat in cands:
            s = _score_tile(lon, lat, args.nhd_dir)
            if s is not None:
                s["province"] = province
                scored.append(s)
                print(f"{s['key']} [{province}]: density={s['nhd_drainage_density']:.3f} "
                      f"km/km2, n_flowlines={s['nhd_flowline_count']}")
        by_province[province] = scored
        all_scored.extend(scored)

    if not all_scored:
        print("no tiles scored (NHD service or coverage issue)")
        return 1

    edges = _quintile_edges([s["nhd_drainage_density"] for s in all_scored])
    tiles: list[dict] = []
    for province, scored in by_province.items():
        n = 1 if args.quick else PICKS_PER_PROVINCE[province]
        for pick in _spread_pick(scored, n):
            pick["quintile"] = _quintile_of(pick["nhd_drainage_density"], edges)
            tiles.append(pick)

    manifest = {
        "selection": {
            "created": today,
            "provinces": list(CANDIDATES),
            "n_candidates_scored": len(all_scored),
            "n_selected": len(tiles),
            "density_metric": "NHD total flowline length (km) / tile area (km2)",
            "corpus_quintile_edges": edges,
            "rationale": "physiographic spread across NHD drainage-density "
            "quintiles; footprints forward-feed Milestone 2 (see "
            "docs/topo_eval/notes/m2_reference_forward_feed.md)",
        },
        "tiles": tiles,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2))
    print(f"\nselected {len(tiles)} tiles across {len(CANDIDATES)} provinces")
    print(f"quintile edges (km/km2): {[round(e, 3) for e in edges]}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
