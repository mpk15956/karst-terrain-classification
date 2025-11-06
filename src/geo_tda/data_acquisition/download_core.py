# src/data_acquisition/download_core.py

from __future__ import annotations
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import planetary_computer
import requests
import rasterio
from rasterio.warp import transform_bounds
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm.auto import tqdm

# Use absolute imports from the 'src' directory
from geo_tda.geoio_utils.provenance import write_provenance
from geo_tda.utils.coords import get_bbox_from_key

log = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_url_with_retry(url: str, session: requests.Session, timeout_sec: int = 60):
    """A resilient GET request wrapper using tenacity."""
    signed_url = planetary_computer.sign(url)
    response = session.get(signed_url, stream=True, timeout=timeout_sec)
    response.raise_for_status()
    return response


def _validate_geotiff_content(file_path: Path, expected_key: str) -> tuple[bool, str]:
    """
    Validates that the GeoTIFF's geographic bounds contain the expected center point.
    """
    try:
        min_lon, min_lat, max_lon, max_lat = get_bbox_from_key(expected_key)
        center_lon, center_lat = ((min_lon + max_lon) / 2, (min_lat + max_lat) / 2)

        with rasterio.open(file_path) as src:
            actual_min_lon, actual_min_lat, actual_max_lon, actual_max_lat = transform_bounds(
                src.crs, "EPSG:4326", *src.bounds
            )

            if (actual_min_lon <= center_lon <= actual_max_lon) and \
               (actual_min_lat <= center_lat <= actual_max_lat):
                return True, f"Center point validated for key {expected_key}."
            else:
                actual_bbox = (actual_min_lon, actual_min_lat, actual_max_lon, actual_max_lat)
                return (
                    False,
                    f"Center point mismatch for key {expected_key}. "
                    f"Expected center ({center_lon:.6f}, {center_lat:.6f}) "
                    f"not within actual bounds {actual_bbox}."
                )

    except Exception as e:
        return False, f"Validation failed for {file_path.name} with error: {e}"


def _download_job(job: dict, stats: dict) -> str:
    """Target function for a single download thread."""
    url = job["url"]
    out_path = Path(job["out_path"])
    key = job["key"]
    part_path = out_path.with_suffix(out_path.suffix + ".part")
    success = False

    try:
        if out_path.exists() and out_path.stat().st_size > 0:
            is_valid, _ = _validate_geotiff_content(out_path, key)
            if is_valid:
                with stats["lock"]:
                    stats["skipped"] += 1
                return f"SKIP: {out_path.name} (already exists and is valid)"

        part_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            response = _fetch_url_with_retry(url, session)
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        is_valid, msg = _validate_geotiff_content(part_path, key)
        if not is_valid:
            log.error(f"Validation failed for {out_path.name}: {msg}")
            raise ValueError(msg)

        part_path.rename(out_path)
        
        # --- FIX: Pass the missing 'parameters' argument as an empty dictionary ---
        write_provenance(out_path, job["source_info"], parameters={})
        
        success = True
        return f"OK: {out_path.name}"

    except Exception as e:
        log.error(f"Download failed for {out_path.name}: {e}")
        if part_path.exists():
            part_path.unlink()
        return f"FAIL: {out_path.name} ({e})"

    finally:
        with stats["lock"]:
            if success:
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1


def execute_downloads(jobs: list[dict], description: str, max_workers: int):
    """
    Manages a pool of threads to download a list of files concurrently.
    """
    if not jobs:
        log.info(f"No new files to download for {description}.")
        return

    stats = {
        "lock": threading.Lock(),
        "skipped": 0,
        "downloaded": 0,
        "failed": 0,
    }

    log.info(f"⬇️  Starting parallel download for {len(jobs)} {description} files...")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_job = {pool.submit(_download_job, job, stats): job for job in jobs}
        results = [
            future.result()
            for future in tqdm(
                as_completed(future_to_job),
                total=len(jobs),
                desc=description,
                unit="file",
            )
        ]

    failures = [r for r in results if r.startswith("FAIL")]
    log.info("=" * 70)
    log.info(f"Download Summary for {description}:")
    log.info(f"  Downloaded: {stats['downloaded']}")
    log.info(f"  Skipped:    {stats['skipped']} (valid files already exist)")
    log.info(f"  Failed:     {stats['failed']} (includes validation failures)")
    log.info("=" * 70)

    if failures:
        log.error("--- Download Failures ---")
        for f in failures:
            log.error(f"  - {f}")
            