"""
DEM tile discovery and download via STAC API.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict

from pystac_client import Client
from tqdm.auto import tqdm

from geo_tda.utils.coords import get_bbox_from_key

log = logging.getLogger(__name__)


def build_dem_download_jobs_stac(
    keys_to_find: List[str],
    stac_url: str,
    collection_id: str,
    asset_key: str,
    out_dir: Path,
    gsd: int | None = None
) -> tuple[List[Dict], List[str]]:
    """
    Probe the Planetary Computer STAC API using robust, hybrid matching logic.
    """
    jobs, not_found_keys = [], []
    log.info(f"Connecting to STAC Catalog: {stac_url}")
    catalog = Client.open(stac_url)
    log.info(f"Querying STAC for {len(keys_to_find)} DEM tiles from '{collection_id}' with GSD={gsd}m...")

    for key in tqdm(keys_to_find, desc="STAC Query"):
        try:
            bbox = get_bbox_from_key(key)
            stac_query = {"gsd": {"eq": gsd}} if gsd else {}
            search = catalog.search(
                collections=[collection_id],
                bbox=bbox,
                query=stac_query,
                datetime=None
            )
            items = list(search.item_collection())

            if not items:
                log.warning(f"Tile {key}: No STAC items found in bbox for GSD={gsd}.")
                not_found_keys.append(key)
                continue

            # --- HYBRID MATCHING LOGIC ---
            matched_item = None
            # 1. Try for a perfect, exact match first.
            exact_match = next((item for item in items if item.id == key), None)
            if exact_match:
                matched_item = exact_match
                log.debug(f"Tile {key}: Found exact match: {matched_item.id}")
            else:
                # 2. If no exact match, look for items starting with the key.
                startswith_matches = [item for item in items if item.id.startswith(key)]
                if startswith_matches:
                    # 3. Prioritize suffixes: prefer '-13', then '-1', then any other.
                    for suffix in ['-13', '-1']:
                        suffixed_id = f"{key}{suffix}"
                        item = next((m for m in startswith_matches if m.id == suffixed_id), None)
                        if item:
                            matched_item = item
                            break
                    # If no prioritized suffix found, take the first available startswith match.
                    if not matched_item:
                        matched_item = startswith_matches[0]
                    log.debug(f"Tile {key}: No exact match found. Selected best available: {matched_item.id}")

            if not matched_item:
                log.warning(f"Tile {key}: Found {len(items)} items in bbox, but none had a matching ID.")
                available_ids = [item.id for item in items]
                log.debug(f"Tile {key}: Available item IDs in bbox were: {available_ids}")
                not_found_keys.append(key)
                continue
            # --- END OF LOGIC ---

            if asset_key not in matched_item.assets:
                log.warning(f"Tile {key}: Item '{matched_item.id}' missing asset '{asset_key}'.")
                not_found_keys.append(key)
                continue
            
            asset_url = matched_item.assets[asset_key].href
            # Use the original key for the filename for consistency with your requirements
            filename = f"USGS_1_{key}.tif"
            out_path = out_dir / filename
            item_bbox = matched_item.bbox if hasattr(matched_item, 'bbox') else None

            jobs.append({
                "url": asset_url,
                "out_path": out_path,
                "key": key, # Report the key we were looking for
                "source_info": {
                    "stac_url": stac_url,
                    "collection": collection_id,
                    "item_id": matched_item.id, # But record the actual ID we found
                    "asset_key": asset_key,
                    "query_gsd": gsd,
                    "original_href": asset_url,
                    "item_bbox": item_bbox
                }
            })

        except Exception as e:
            log.error(f"Failed to query STAC for key {key}: {e}")
            not_found_keys.append(key)

    if not_found_keys:
        log.warning(f"STAC query could not find suitable matches for {len(not_found_keys)} keys.")
    log.info(f"STAC query complete: {len(jobs)} jobs created, {len(not_found_keys)} keys not found.")
    return jobs, not_found_keys
