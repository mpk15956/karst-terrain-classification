"""Throwaway: donor-precondition check on a generated MESA DEM (project env).

"MESA ran right" must mean the generated surface satisfies the metric's
preconditions, not just that a heightmap appeared. Run the saved MESA DEM
through the SAME donor pipeline real DEMs used and confirm it yields a
connected, sane channel network (few roots, confluences > 0) -- otherwise the
generated surface breaks an assumption the pipeline relied on, and that must
be known BEFORE the gate, not discovered as a confusing H0 number during it.
"""
import numpy as np
import rasterio
from rasterio.transform import from_origin

from geo_tda.topo_eval.hydrology import d8_pointer_and_accumulation
from geo_tda.topo_eval.merge_tree import merge_tree_from_accumulation
from geo_tda.topo_eval.summaries import h1_cubical_mask

dem = np.load("/home/mpk15956/mesa/out/dem_verify.npy").astype("float32")
H, W = dem.shape
tif = "/home/mpk15956/mesa/out/dem_verify.tif"
with rasterio.open(tif, "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="float32", crs="EPSG:4326",
                   transform=from_origin(-85.0, 36.0, 1 / 3600, 1 / 3600)) as ds:
    ds.write(dem, 1)

codes, accum = d8_pointer_and_accumulation(tif)
# no NHD anchor for a generated patch: percentile tau (top ~5% of accumulation)
tau = float(np.percentile(accum, 95))
mask = accum >= tau
chan = int(mask.sum())
tree = merge_tree_from_accumulation(codes, accum, tau)
roots = len(tree.roots); leaves = len(tree.leaves); internal = len(tree.internal_nodes)
h1c = int(h1_cubical_mask(mask))

print("dem %dx%d range [%.3f, %.3f]" % (H, W, float(dem.min()), float(dem.max())))
print("channel_cells=%d tau=%.1f" % (chan, tau))
print("DONOR NETWORK: roots=%d leaves=%d confluences=%d h1_cubical=%d" % (roots, leaves, internal, h1c))
connected = roots < max(1, chan) * 0.2
sanenet = internal > 0
print("PRECONDITION connected=%s (roots/chan=%.3f)  sane_network=%s" % (
    "OK" if connected else "SHATTERED", roots / max(1, chan), "OK" if sanenet else "DEGENERATE"))
print("VERDICT:", "PASS" if (connected and sanenet) else "FAIL -- generated surface violates donor preconditions")
