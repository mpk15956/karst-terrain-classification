"""Resolution-confound probe: 3DEP vs GLO-30 channel network at matched density.

The deferred resolution confound (m2_reference_forward_feed.md): the donor
graph and tau are grid-resolution dependent, so comparing a generator on its
native substrate (GLO-30) against a 3DEP reference could read resolution, not
generator pathology. This probe isolates it on matched real-vs-real pairs.

For each tile, at the NHD-drainage-density-matched tau (the resolution-
invariant anchor) computed independently on each substrate's own grid:
- build the donor-graph channel network on 3DEP and on GLO-30;
- compare them (junction count, Strahler Wasserstein, |dR_b|) -- if they
  agree, the metric is resolution-invariant at matched density and M2 cross-
  substrate comparison is sound; if they diverge, the resolution confound is
  material and M2 must hold resolution constant (re-tile real to GLO-30).
- report donor-graph connectivity on GLO-30 (roots; confirms the whitebox
  pointer convention holds on this substrate too) and the tau-in-cells shift.
- report elevation correlation (3DEP resampled to GLO-30) as a same-ground
  sanity beyond bounds registration.

Compute (whitebox d8 per substrate); offline-first on staged 3DEP+GLO-30+NHD.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

DEM_3DEP = Path("data/dem")
DEM_GLO30 = Path("data/glo30")
NHD_DIR = Path("data/nhd")


def _network(dem_path, nhd_density, area, workdir):
    """Donor-graph network on a substrate at its NHD-density-matched tau."""
    from geo_tda.topo_eval.construct_validity import stats_from_merge_tree
    from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
    from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
    from geo_tda.topo_eval.pipeline import _cell_km, tau_for_target_density
    from geo_tda.topo_eval.summaries import h1_cubical_mask
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(dem_path) as s:
        shape = (s.height, s.width)
        b = s.bounds
        bbox = b if s.crs.to_epsg() == 4326 else transform_bounds(s.crs, "EPSG:4326", *b)
    codes, accum = d8_pointer_and_accumulation(dem_path, workdir=str(workdir))
    cell_km = _cell_km(bbox, accum.shape)
    tau = tau_for_target_density(accum, nhd_density, area, cell_km)
    tree = merge_tree_from_accumulation(codes, accum, tau)
    ph = stats_from_merge_tree(tree, area_km2=area,
                               channel_cell_count=int((accum >= tau).sum()),
                               cell_km=cell_km)
    return {"tau": float(tau), "grid": shape, "roots": len(tree.roots),
            "junctions": ph.junction_count,
            "h1_cubical": int(h1_cubical_mask(accum >= tau)),
            "drainage_density": ph.drainage_density}, ph


def _elev_corr(dep_path, glo_path):
    """Pearson correlation of 3DEP resampled onto the GLO-30 grid (same ground)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    with rasterio.open(glo_path) as g:
        gl = g.read(1).astype("float64"); dst_t, dst_crs, H, W = g.transform, g.crs, g.height, g.width
    with rasterio.open(dep_path) as d:
        dep = d.read(1).astype("float64")
        out = np.empty((H, W), "float64")
        reproject(dep, out, src_transform=d.transform, src_crs=d.crs,
                  dst_transform=dst_t, dst_crs=dst_crs, resampling=Resampling.bilinear)
    m = np.isfinite(gl) & np.isfinite(out) & (gl > -1e4) & (out > -1e4)
    if m.sum() < 100:
        return float("nan")
    return float(np.corrcoef(gl[m], out[m])[0, 1])


def main() -> int:
    import tempfile
    import shutil

    from geo_tda.topo_eval.construct_validity import compare, stats_from_flowlines
    from geo_tda.topo_eval.pipeline import _materialize_plain, _tile_area_km2, _tile_bbox_from_raster

    ap = argparse.ArgumentParser(description="Resolution-confound probe (3DEP vs GLO-30)")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--n-tiles", type=int, default=8)
    ap.add_argument("--out", type=Path, default=Path("results/validity/resolution_probe.json"))
    args = ap.parse_args()

    rows = []
    for spec in json.loads(args.manifest.read_text())["tiles"][:args.n_tiles]:
        key = spec["key"]
        dep = DEM_3DEP / f"USGS_seamless_{key}_30m.tif"
        glo = DEM_GLO30 / f"{key}.tif"
        nhd = NHD_DIR / f"{key}.geojson"
        if not (dep.exists() and glo.exists() and nhd.exists()):
            print(f"skip {key}: missing substrate"); continue
        wd = Path(tempfile.mkdtemp(prefix=f"res_{key}_"))
        try:
            dep_p = _materialize_plain(dep); glo_p = _materialize_plain(glo)
            area = _tile_area_km2(_tile_bbox_from_raster(dep_p))
            dens = stats_from_flowlines(nhd, area_km2=area).drainage_density
            d3, ph3 = _network(dep_p, dens, area, wd)
            dg, phg = _network(glo_p, dens, area, wd)
            cmp = compare(ph3, phg)  # 3DEP("ph") vs GLO-30("nhd" slot)
            corr = _elev_corr(dep_p, glo_p)
            row = {"key": key, "nhd_density": dens, "elev_corr": corr,
                   "dep": d3, "glo30": dg,
                   "net_agreement": {"junction_3dep": cmp["junction_count_ph"],
                                     "junction_glo30": cmp["junction_count_nhd"],
                                     "strahler_wasserstein": cmp["strahler_wasserstein"],
                                     "bifurcation_abs_diff": cmp["bifurcation_ratio_abs_diff"]}}
            rows.append(row)
            print(f"{key}: corr={corr:.3f} | 3DEP tau={d3['tau']:.0f} jc={d3['junctions']} roots={d3['roots']} "
                  f"| GLO30 tau={dg['tau']:.0f} jc={dg['junctions']} roots={dg['roots']} "
                  f"| net SW={cmp['strahler_wasserstein']:.3f} |dRb|={cmp['bifurcation_ratio_abs_diff']}")
        except Exception as exc:  # noqa: BLE001
            print(f"tile {key} failed: {exc}")
        finally:
            for p in (locals().get("dep_p"), locals().get("glo_p")):
                if p and Path(p).exists():
                    Path(p).unlink()
            shutil.rmtree(wd, ignore_errors=True)

    if rows:
        sw = np.nanmedian([r["net_agreement"]["strahler_wasserstein"] for r in rows])
        corr = np.nanmedian([r["elev_corr"] for r in rows])
        glo_roots = [r["glo30"]["roots"] for r in rows]
        summary = {"n_tiles": len(rows),
                   "elev_corr_median": float(corr),
                   "net_strahler_wasserstein_median": float(sw),
                   "glo30_max_roots": int(max(glo_roots)),
                   "note": "low net_strahler_wasserstein + GLO-30 roots small (connected) "
                   "=> metric resolution-invariant at matched density; high SW => resolution "
                   "confound material, M2 must hold resolution constant."}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
        print("\nSUMMARY:", json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
