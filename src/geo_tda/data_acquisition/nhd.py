"""NHD flowline vector acquisition (the external ground truth for Phase C).

Fetches National Hydrography Dataset flowline VECTORS by bounding box from
the USGS hydrography ArcGIS REST service. Flowlines only: the NHDPlus HR
derived RASTERS (catchment grids, flow-direction grids, flow-accumulation
grids) are deliberately NOT used as ground truth, because they descend
from the same 10 m 3DEP DEM and the same D8-style processing the metric
under test uses, which would inflate agreement through shared algorithmic
lineage. The flowline vectors descend from independently-digitized
1:24,000 hydrography (topographic-map and imagery lineage), so they are a
genuinely external criterion. See docs/topo_eval/_evaluation_conventions.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# USGS National Map hydrography service. Layer 6 of the NHD MapServer is
# the flowline feature layer (NHDFlowline). The service returns GeoJSON
# when queried with f=geojson.
NHD_FLOWLINE_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6/query"
)


def fetch_nhd_flowlines(
    bbox: tuple[float, float, float, float],
    dest_path: str | Path,
    *,
    timeout: int = 300,
) -> Path:
    """Download NHD flowline vectors intersecting a bbox as GeoJSON.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84.
        dest_path: where to write the GeoJSON FeatureCollection.
        timeout: request timeout in seconds.

    Returns:
        The path written. Raises requests.HTTPError on a failed request,
        or ValueError if the service returns no usable features.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    min_lon, min_lat, max_lon, max_lat = bbox
    params = {
        "geometry": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }
    resp = requests.get(NHD_FLOWLINE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    features = payload.get("features", [])
    if not features:
        raise ValueError(
            f"NHD service returned no flowline features for bbox {bbox}"
        )
    dest_path.write_text(resp.text)
    logger.info("wrote %d NHD flowlines to %s", len(features), dest_path)
    return dest_path


def load_flowlines(geojson_path: str | Path):
    """Load a flowline GeoJSON into a GeoDataFrame (EPSG:4326)."""
    import geopandas as gpd

    return gpd.read_file(geojson_path)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch NHD flowline vectors")
    parser.add_argument("--bbox", nargs=4, type=float, required=True)
    parser.add_argument("--dest", type=Path, default=Path("data/nhd/flowlines.geojson"))
    args = parser.parse_args()

    path = fetch_nhd_flowlines(tuple(args.bbox), args.dest)
    gdf = load_flowlines(path)
    print(f"{len(gdf)} flowlines -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
