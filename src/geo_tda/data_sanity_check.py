"""
Comprehensive data sanity check utilities for downloaded geospatial data.

This module provides functions to verify:
- DEM data completeness, coverage, and validity
- Climate data (Daymet) integrity and spatial/temporal coverage
- Soil data (gNATSGO) completeness and data quality
- Visualization of data coverage against study areas
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rioxarray as rxr
from shapely.geometry import box
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from tqdm.auto import tqdm

log = logging.getLogger(__name__)


class DataQualityReport:
    """Container for data quality check results."""

    def __init__(self, data_type: str):
        self.data_type = data_type
        self.checks = []
        self.warnings = []
        self.errors = []
        self.summary = {}

    def add_check(self, name: str, passed: bool, message: str, details: Optional[Dict] = None):
        """Add a check result."""
        self.checks.append({
            'name': name,
            'passed': passed,
            'message': message,
            'details': details or {}
        })
        if not passed:
            self.errors.append(f"{name}: {message}")

    def add_warning(self, message: str):
        """Add a warning."""
        self.warnings.append(message)

    def __str__(self):
        """Generate human-readable report."""
        lines = [f"\n{'='*60}"]
        lines.append(f"{self.data_type} DATA QUALITY REPORT")
        lines.append(f"{'='*60}\n")

        # Summary
        if self.summary:
            lines.append("SUMMARY:")
            for key, value in self.summary.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        # Checks
        lines.append("CHECKS:")
        for check in self.checks:
            status = "✅ PASS" if check['passed'] else "❌ FAIL"
            lines.append(f"  {status} {check['name']}: {check['message']}")

        # Warnings
        if self.warnings:
            lines.append("\nWARNINGS:")
            for warning in self.warnings:
                lines.append(f"  ⚠️  {warning}")

        # Overall status
        lines.append(f"\n{'='*60}")
        all_passed = all(c['passed'] for c in self.checks)
        if all_passed and not self.errors:
            lines.append("✅ ALL CHECKS PASSED")
        else:
            lines.append(f"❌ {len(self.errors)} CHECK(S) FAILED")
        lines.append(f"{'='*60}\n")

        return '\n'.join(lines)


def check_dem_data(dem_dir: Path, aoi_gdf: gpd.GeoDataFrame,
                   expected_crs: str = "EPSG:4326") -> DataQualityReport:
    """
    Comprehensive DEM data quality checks.
    """
    report = DataQualityReport("DEM")
    log.info("Starting DEM data quality checks...")

    dem_files = sorted(dem_dir.glob("*.tif"))
    report.summary['Total Files'] = len(dem_files)
    report.add_check(
        "File Existence",
        len(dem_files) > 0,
        f"Found {len(dem_files)} DEM tile(s)"
    )

    if not dem_files:
        return report

    # Check for file size and corruption
    corrupted = []
    small_files = []
    size_threshold = 1024  # 1 KB is a more reasonable threshold

    for dem_file in dem_files:
        file_size = dem_file.stat().st_size
        if file_size == 0:
            corrupted.append(dem_file.name)
        elif file_size < size_threshold:
            small_files.append((dem_file.name, file_size))

    report.add_check(
        "File Integrity",
        not corrupted,
        f"{len(corrupted)} corrupted (0 bytes) file(s)" if corrupted else "All files have non-zero size",
        {'corrupted_files': corrupted}
    )

    if small_files:
        report.add_warning(
            f"{len(small_files)} suspiciously small file(s) (< {size_threshold} bytes): "
            f"{[f[0] for f in small_files[:5]]}"
        )

    # Check 3: Raster readability and metadata
    readable_count = 0
    crs_issues = []
    nodata_issues = []
    elevation_stats = []
    tile_bounds = []

    log.info("Checking individual DEM tiles...")
    for dem_file in tqdm(dem_files, desc="Checking DEM tiles", unit="file"):
        try:
            da = rxr.open_rasterio(dem_file).squeeze()
            readable_count += 1

            # Check CRS
            if da.rio.crs is None:
                crs_issues.append(f"{dem_file.name}: No CRS")
            elif str(da.rio.crs) != expected_crs:
                # Actually many DEM tiles might be in their native CRS, so this is informational
                pass

            # Check NoData
            nodata = da.rio.nodata
            if nodata is None:
                nodata_issues.append(f"{dem_file.name}: No NoData value defined")

            # Check elevation range (sanity)
            valid_data = da.values[da.values != nodata] if nodata is not None else da.values
            if len(valid_data) > 0:
                elev_min, elev_max = float(valid_data.min()), float(valid_data.max())
                elevation_stats.append({
                    'file': dem_file.name,
                    'min': elev_min,
                    'max': elev_max,
                    'mean': float(valid_data.mean())
                })

                # Flag suspicious elevations (likely in meters)
                if elev_min < -500 or elev_max > 9000:
                    report.add_warning(
                        f"{dem_file.name}: Unusual elevation range [{elev_min:.1f}, {elev_max:.1f}]"
                    )
            else:
                report.add_warning(f"{dem_file.name}: Contains only NoData values")

            # Store bounds for coverage check
            bounds = da.rio.bounds()
            tile_bounds.append(box(*bounds))

            da.close()

        except Exception as e:
            report.add_warning(f"Cannot read {dem_file.name}: {str(e)[:100]}")

    report.add_check(
        "Raster Readability",
        readable_count == len(dem_files),
        f"{readable_count}/{len(dem_files)} files readable",
        {'readable': readable_count, 'total': len(dem_files)}
    )

    if crs_issues:
        report.add_warning(f"{len(crs_issues)} file(s) with CRS issues")

    if nodata_issues:
        report.add_warning(f"{len(nodata_issues)} file(s) without NoData value")

    # Check 4: Spatial coverage
    if tile_bounds:
        tiles_gdf = gpd.GeoDataFrame(geometry=tile_bounds, crs=expected_crs)
        aoi_wgs84 = aoi_gdf.to_crs(expected_crs)

        # Calculate coverage
        tiles_union = tiles_gdf.unary_union
        aoi_geom = aoi_wgs84.unary_union

        coverage_area = tiles_union.intersection(aoi_geom).area
        aoi_area = aoi_geom.area
        coverage_pct = (coverage_area / aoi_area * 100) if aoi_area > 0 else 0

        report.summary['Coverage'] = f"{coverage_pct:.1f}%"
        report.add_check(
            "Spatial Coverage",
            coverage_pct > 95,
            f"DEM tiles cover {coverage_pct:.1f}% of AOI",
            {'coverage_pct': coverage_pct}
        )

        if coverage_pct < 100:
            report.add_warning(f"AOI coverage is {coverage_pct:.1f}% (< 100%)")

    # Check 5: Elevation statistics summary
    if elevation_stats:
        all_mins = [s['min'] for s in elevation_stats]
        all_maxs = [s['max'] for s in elevation_stats]
        report.summary['Elevation Range'] = f"[{min(all_mins):.1f}, {max(all_maxs):.1f}] m"

    return report


def check_climate_data(climate_dir: Path, aoi_gdf: gpd.GeoDataFrame,
                       expected_vars: List[str] = ['prcp', 'tmin', 'tmax'],
                       expected_date_range: Tuple[str, str] = ('2018-01-01', '2022-12-31')) -> DataQualityReport:
    """
    Comprehensive climate data (Daymet) quality checks.

    Checks:
    - Zarr store existence and readability
    - Required variables present
    - Temporal coverage (date range)
    - Spatial coverage against AOI
    - Data value ranges (climate sanity checks)
    - Missing data percentage

    Parameters
    ----------
    climate_dir : Path
        Directory containing climate data
    aoi_gdf : gpd.GeoDataFrame
        Area of Interest geometry
    expected_vars : List[str]
        Expected variable names
    expected_date_range : Tuple[str, str]
        Expected (start, end) date range

    Returns
    -------
    DataQualityReport
    """
    report = DataQualityReport("CLIMATE")
    log.info("Starting climate data quality checks...")

    # Check 1: Zarr store existence
    zarr_path = climate_dir / "daymet_daily_subset.zarr"
    report.add_check(
        "Zarr Store Exists",
        zarr_path.exists(),
        f"Zarr store found at {zarr_path}" if zarr_path.exists() else "Zarr store not found"
    )

    if not zarr_path.exists():
        return report

    # Check 2: Zarr readability
    try:
        # Handle NumPy 2.0 compatibility issue
        import warnings
        with warnings.catch_warnings():
            # Suppress the np.PINF deprecation warning
            warnings.filterwarnings('ignore', message='.*PINF.*')

            # Temporarily monkey-patch np.PINF for NumPy 2.0+ compatibility
            if not hasattr(np, 'PINF'):
                np.PINF = np.inf
                np.NINF = -np.inf
                patched_numpy = True
            else:
                patched_numpy = False

            try:
                ds = xr.open_zarr(zarr_path)
                report.add_check("Zarr Readable", True, "Successfully opened Zarr store")

                # Add note if we had to patch NumPy
                if patched_numpy:
                    report.add_warning(
                        "Zarr file contains deprecated NumPy references (np.PINF). "
                        "Consider re-downloading climate data with current NumPy version."
                    )
            finally:
                # Clean up the monkey-patch if we added it
                if patched_numpy:
                    delattr(np, 'PINF')
                    delattr(np, 'NINF')

    except Exception as e:
        report.add_check("Zarr Readable", False, f"Cannot read Zarr: {str(e)[:100]}")
        return report

    # Check 3: Variables present
    missing_vars = [v for v in expected_vars if v not in ds.data_vars]
    report.add_check(
        "Variables Present",
        len(missing_vars) == 0,
        f"All expected variables found" if not missing_vars else f"Missing: {missing_vars}",
        {'expected': expected_vars, 'found': list(ds.data_vars), 'missing': missing_vars}
    )

    report.summary['Variables'] = ', '.join(ds.data_vars)

    # Check 4: Temporal coverage
    if 'time' in ds.dims:
        time_range = (str(ds.time.min().values)[:10], str(ds.time.max().values)[:10])
        n_timesteps = len(ds.time)

        report.summary['Time Range'] = f"{time_range[0]} to {time_range[1]}"
        report.summary['Timesteps'] = n_timesteps

        # Check if it covers expected range
        expected_start = pd.to_datetime(expected_date_range[0])
        expected_end = pd.to_datetime(expected_date_range[1])
        actual_start = pd.to_datetime(ds.time.min().values)
        actual_end = pd.to_datetime(ds.time.max().values)

        covers_range = (actual_start <= expected_start) and (actual_end >= expected_end)
        report.add_check(
            "Temporal Coverage",
            covers_range,
            f"Covers expected range" if covers_range else f"Range mismatch: expected {expected_date_range}, got {time_range}"
        )
    else:
        report.add_check("Temporal Coverage", False, "No 'time' dimension found")

    # Check 5: Spatial coverage
    if hasattr(ds, 'rio'):
        try:
            ds_crs = ds.rio.crs
            bounds = ds.rio.bounds()

            # Create bounding box of climate data
            climate_bbox = gpd.GeoDataFrame(
                geometry=[box(*bounds)],
                crs=ds_crs
            ).to_crs(aoi_gdf.crs)

            aoi_geom = aoi_gdf.unary_union
            climate_geom = climate_bbox.unary_union

            coverage_area = climate_geom.intersection(aoi_geom).area
            aoi_area = aoi_geom.area
            coverage_pct = (coverage_area / aoi_area * 100) if aoi_area > 0 else 0

            report.summary['Spatial Coverage'] = f"{coverage_pct:.1f}%"
            report.add_check(
                "Spatial Coverage",
                coverage_pct > 95,
                f"Climate data covers {coverage_pct:.1f}% of AOI"
            )
        except Exception as e:
            report.add_warning(f"Could not check spatial coverage: {str(e)[:100]}")

    # Check 6: Data value ranges and missing data
    for var in expected_vars:
        if var not in ds.data_vars:
            continue

        try:
            data = ds[var]

            # Sample statistics (avoid loading full array)
            sample = data.isel(time=slice(0, min(10, len(ds.time))))

            # Check for all NaN
            if np.all(np.isnan(sample.values)):
                report.add_warning(f"{var}: All sampled values are NaN")
                continue

            # Basic statistics
            valid_data = sample.values[~np.isnan(sample.values)]
            if len(valid_data) > 0:
                var_min, var_max = float(valid_data.min()), float(valid_data.max())
                var_mean = float(valid_data.mean())

                # Sanity checks based on variable type
                if var == 'prcp':  # precipitation in mm/day
                    if var_min < 0 or var_max > 500:
                        report.add_warning(f"{var}: Unusual range [{var_min:.1f}, {var_max:.1f}]")
                elif var in ['tmin', 'tmax']:  # temperature in Celsius
                    if var_min < -60 or var_max > 60:
                        report.add_warning(f"{var}: Unusual temperature range [{var_min:.1f}, {var_max:.1f}]")

                report.summary[f'{var} range'] = f"[{var_min:.1f}, {var_max:.1f}]"

        except Exception as e:
            report.add_warning(f"Could not check {var}: {str(e)[:100]}")

    ds.close()
    return report


def check_soil_data(soils_dir: Path, aoi_gdf: gpd.GeoDataFrame) -> DataQualityReport:
    """
    Comprehensive soil data (gNATSGO) quality checks.

    Checks for NEW workflow (1.2 updated):
    - Merged CSV file existence
    - Row counts and completeness
    - Required columns present
    - MUKEY counts
    - Data value ranges

    Also checks for OLD workflow files (for backwards compatibility):
    - Raster tiles
    - Individual table files

    Parameters
    ----------
    soils_dir : Path
        Directory containing soil data
    aoi_gdf : gpd.GeoDataFrame
        Area of Interest geometry

    Returns
    -------
    DataQualityReport
    """
    report = DataQualityReport("SOIL (gNATSGO)")
    log.info("Starting soil data quality checks...")

    # Check 1: NEW WORKFLOW - Merged CSV file (primary output from updated 1.2)
    csv_files = sorted(soils_dir.glob("*_gnatsgo_data.csv"))
    report.summary['CSV Files'] = len(csv_files)

    if csv_files:
        # Found merged CSV - this is the new workflow
        csv_file = csv_files[0]  # Use first/only CSV
        report.add_check(
            "Merged CSV Exists",
            True,
            f"Found merged soil data: {csv_file.name}"
        )

        try:
            soil_df = pd.read_csv(csv_file)
            n_rows = len(soil_df)
            n_mukeys = soil_df['mukey'].nunique() if 'mukey' in soil_df.columns else 0
            n_components = soil_df['cokey'].nunique() if 'cokey' in soil_df.columns else 0

            report.summary['Total Rows'] = f"{n_rows:,}"
            report.summary['Unique MUKEYs'] = f"{n_mukeys:,}"
            report.summary['Components'] = f"{n_components:,}"

            report.add_check(
                "CSV Readable",
                True,
                f"Successfully loaded {n_rows:,} soil records"
            )

            # Check required columns for WEPP
            required_cols = ['mukey', 'cokey', 'hzdept_r', 'hzdepb_r',
                           'sandtotal_r', 'silttotal_r', 'claytotal_r']
            missing_cols = [c for c in required_cols if c not in soil_df.columns]

            report.add_check(
                "Required Columns Present",
                len(missing_cols) == 0,
                f"All WEPP-required columns present" if not missing_cols else f"Missing: {missing_cols}"
            )

            # Check for empty/null data
            if n_rows > 0:
                null_pct = (soil_df[required_cols].isnull().sum().sum() /
                           (n_rows * len(required_cols)) * 100)
                report.summary['Null Data'] = f"{null_pct:.1f}%"

                if null_pct > 10:
                    report.add_warning(f"{null_pct:.1f}% of required column values are null")

        except Exception as e:
            report.add_check("CSV Readable", False, f"Cannot read CSV: {str(e)[:100]}")

    else:
        # No CSV found - check for old workflow files
        report.add_check("Merged CSV Exists", False, "No merged CSV found (expected from new 1.2 workflow)")

        # Check 2: OLD WORKFLOW - Raster tiles (backwards compatibility)
        raster_dir = soils_dir / "mukey_tiles"
        if not raster_dir.exists() or len(list(raster_dir.glob("gnatsgo_mukey_*.tif"))) == 0:
            raster_dir = soils_dir

        raster_files = sorted(raster_dir.glob("gnatsgo_mukey_*.tif"))
        report.summary['Raster Tiles'] = len(raster_files)
    report.add_check(
        "Raster Tiles Exist",
        len(raster_files) > 0,
        f"Found {len(raster_files)} raster tile(s)"
    )

    if len(raster_files) > 0:
        # Check for corruption
        corrupted = []
        readable_count = 0
        tile_bounds = []
        tile_crs = None

        for raster_file in tqdm(raster_files, desc="Checking soil rasters", unit="file"):
            file_size = raster_file.stat().st_size
            if file_size == 0:
                corrupted.append(raster_file.name)
                continue

            try:
                da = rxr.open_rasterio(raster_file).squeeze()
                readable_count += 1

                # Store CRS from first valid file
                if tile_crs is None and da.rio.crs is not None:
                    tile_crs = da.rio.crs

                # Store bounds (will be reprojected later for coverage calculation)
                bounds = da.rio.bounds()
                tile_bounds.append((box(*bounds), da.rio.crs))

                da.close()
            except Exception as e:
                report.add_warning(f"Cannot read {raster_file.name}: {str(e)[:100]}")

        report.add_check(
            "Raster Integrity",
            len(corrupted) == 0,
            f"{len(corrupted)} corrupted file(s)" if corrupted else "All raster files readable",
            {'corrupted': corrupted}
        )

        # Spatial coverage - handle CRS reprojection properly
        if tile_bounds:
            try:
                # Create GeoDataFrame with proper CRS handling
                geometries = []
                for geom, crs in tile_bounds:
                    if crs is not None:
                        # Reproject to WGS84 for comparison with AOI
                        gdf_temp = gpd.GeoDataFrame(geometry=[geom], crs=crs)
                        gdf_wgs84 = gdf_temp.to_crs("EPSG:4326")
                        geometries.append(gdf_wgs84.geometry.iloc[0])
                    else:
                        # Assume WGS84 if no CRS
                        geometries.append(geom)

                if geometries:
                    tiles_gdf = gpd.GeoDataFrame(geometry=geometries, crs="EPSG:4326")
                    aoi_wgs84 = aoi_gdf.to_crs("EPSG:4326")

                    tiles_union = tiles_gdf.unary_union
                    aoi_geom = aoi_wgs84.unary_union

                    coverage_area = tiles_union.intersection(aoi_geom).area
                    aoi_area = aoi_geom.area
                    coverage_pct = (coverage_area / aoi_area * 100) if aoi_area > 0 else 0

                    report.summary['Raster Coverage'] = f"{coverage_pct:.1f}%"
                    report.add_check(
                        "Raster Spatial Coverage",
                        coverage_pct > 95,
                        f"Soil rasters cover {coverage_pct:.1f}% of AOI"
                    )
                else:
                    report.add_warning("Could not determine spatial coverage: no valid geometries")
            except Exception as e:
                report.add_warning(f"Error calculating spatial coverage: {str(e)[:100]}")
    else:
        report.add_check("Raster Tiles Exist", False, f"No raster tiles found in {raster_dir}")

    # Check 2: Mukey manifest
    mukey_manifest = soils_dir / "mukeys_aoi.csv"
    if mukey_manifest.exists():
        try:
            mukeys_df = pd.read_csv(mukey_manifest)
            n_mukeys = len(mukeys_df)
            report.summary['Unique MUKEYs'] = n_mukeys
            report.add_check(
                "MUKEY Manifest",
                n_mukeys > 0,
                f"Found {n_mukeys:,} unique mukey(s)"
            )
        except Exception as e:
            report.add_check("MUKEY Manifest", False, f"Cannot read manifest: {str(e)[:100]}")
    else:
        report.add_check("MUKEY Manifest", False, "MUKEY manifest not found")

    # Check 3: Tabular data
    tables_dir = soils_dir / "tables_aoi"
    if tables_dir.exists():
        component_file = tables_dir / "component_aoi.parquet"
        horizon_file = tables_dir / "chorizon_aoi.parquet"

        # Component table
        if component_file.exists():
            try:
                comp_df = pd.read_parquet(component_file)
                report.summary['Component Rows'] = f"{len(comp_df):,}"
                report.add_check(
                    "Component Table",
                    len(comp_df) > 0,
                    f"{len(comp_df):,} component records"
                )

                # Check for required columns
                required_cols = ['mukey', 'cokey', 'compname']
                missing_cols = [c for c in required_cols if c not in comp_df.columns]
                if missing_cols:
                    report.add_warning(f"Component table missing columns: {missing_cols}")

            except Exception as e:
                report.add_check("Component Table", False, f"Cannot read: {str(e)[:100]}")
        else:
            report.add_check("Component Table", False, "Component table not found")

        # Horizon table
        if horizon_file.exists():
            try:
                horiz_df = pd.read_parquet(horizon_file)
                report.summary['Horizon Rows'] = f"{len(horiz_df):,}"
                report.add_check(
                    "Horizon Table",
                    len(horiz_df) > 0,
                    f"{len(horiz_df):,} horizon records"
                )
            except Exception as e:
                report.add_check("Horizon Table", False, f"Cannot read: {str(e)[:100]}")
        else:
            report.add_check("Horizon Table", False, "Horizon table not found")
    else:
        report.add_warning(f"Tables directory not found: {tables_dir}")

    return report


def create_coverage_visualization(dem_dir: Path, climate_dir: Path, soils_dir: Path,
                                  aoi_gdf: gpd.GeoDataFrame, output_path: Path):
    """
    Create a comprehensive visualization showing data coverage.

    Creates a multi-panel figure showing:
    - DEM tile coverage
    - Climate data extent
    - Soil raster tile coverage
    - Overall combined coverage

    Parameters
    ----------
    dem_dir : Path
        DEM data directory
    climate_dir : Path
        Climate data directory
    soils_dir : Path
        Soils data directory
    aoi_gdf : gpd.GeoDataFrame
        Area of Interest
    output_path : Path
        Where to save the figure
    """
    log.info("Creating coverage visualization...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    aoi_wgs84 = aoi_gdf.to_crs("EPSG:4326")

    # Panel 1: DEM Coverage
    ax = axes[0, 0]
    aoi_wgs84.boundary.plot(ax=ax, color='black', linewidth=2, zorder=3)

    dem_files = sorted(dem_dir.glob("*.tif"))
    if dem_files:
        tile_bounds = []
        for dem_file in dem_files:
            try:
                da = rxr.open_rasterio(dem_file).squeeze()
                tile_bounds.append(box(*da.rio.bounds()))
                da.close()
            except:
                pass

        if tile_bounds:
            tiles_gdf = gpd.GeoDataFrame(geometry=tile_bounds, crs="EPSG:4326")
            tiles_gdf.plot(ax=ax, facecolor='green', edgecolor='white', alpha=0.6, zorder=2)

    ax.set_title(f"DEM Coverage ({len(dem_files)} tiles)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Panel 2: Climate Coverage
    ax = axes[0, 1]
    aoi_wgs84.boundary.plot(ax=ax, color='black', linewidth=2, zorder=3)

    zarr_path = climate_dir / "daymet_daily_subset.zarr"
    if zarr_path.exists():
        try:
            # Handle NumPy 2.0 compatibility
            if not hasattr(np, 'PINF'):
                np.PINF = np.inf
                np.NINF = -np.inf
                patched = True
            else:
                patched = False

            try:
                ds = xr.open_zarr(zarr_path)
                if hasattr(ds, 'rio'):
                    bounds = ds.rio.bounds()
                    climate_bbox = gpd.GeoDataFrame(
                        geometry=[box(*bounds)],
                        crs=ds.rio.crs
                    ).to_crs("EPSG:4326")
                    climate_bbox.plot(ax=ax, facecolor='blue', edgecolor='darkblue',
                                     alpha=0.4, zorder=2, label='Climate Data Extent')
                ds.close()
            finally:
                if patched:
                    delattr(np, 'PINF')
                    delattr(np, 'NINF')
        except:
            pass

    ax.set_title("Climate Data Coverage", fontsize=14, fontweight='bold')
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Panel 3: Soil Coverage
    ax = axes[1, 0]
    aoi_wgs84.boundary.plot(ax=ax, color='black', linewidth=2, zorder=3)

    # Check both old and new locations for soil files
    raster_dir = soils_dir / "mukey_tiles"
    if not raster_dir.exists() or len(list(raster_dir.glob("gnatsgo_mukey_*.tif"))) == 0:
        raster_dir = soils_dir

    soil_files = sorted(raster_dir.glob("gnatsgo_mukey_*.tif"))
    if soil_files:
        tile_bounds = []
        for soil_file in soil_files:
            try:
                da = rxr.open_rasterio(soil_file).squeeze()
                bounds = da.rio.bounds()
                tile_crs = da.rio.crs

                # Reproject bounds to WGS84 if needed
                if tile_crs is not None and str(tile_crs) != "EPSG:4326":
                    bbox_geom = box(*bounds)
                    gdf_temp = gpd.GeoDataFrame(geometry=[bbox_geom], crs=tile_crs)
                    gdf_wgs84 = gdf_temp.to_crs("EPSG:4326")
                    tile_bounds.append(gdf_wgs84.geometry.iloc[0])
                else:
                    tile_bounds.append(box(*bounds))

                da.close()
            except:
                pass

        if tile_bounds:
            tiles_gdf = gpd.GeoDataFrame(geometry=tile_bounds, crs="EPSG:4326")
            # Only plot if tiles_gdf has valid bounds
            if not tiles_gdf.empty and tiles_gdf.total_bounds is not None:
                try:
                    tiles_gdf.plot(ax=ax, facecolor='brown', edgecolor='white', alpha=0.6, zorder=2)
                except ValueError as e:
                    # Handle cases where plotting fails due to invalid aspect ratio
                    log.warning(f"Could not plot soil coverage: {str(e)[:100]}")

    ax.set_title(f"Soil Data Coverage ({len(soil_files)} tiles)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Panel 4: Combined Summary
    ax = axes[1, 1]
    ax.axis('off')

    summary_text = "DATA COVERAGE SUMMARY\n\n"
    summary_text += f"DEM Tiles: {len(dem_files)}\n"
    summary_text += f"Climate Data: {'✅' if zarr_path.exists() else '❌'}\n"
    summary_text += f"Soil Raster Tiles: {len(soil_files)}\n"
    summary_text += f"\nStudy Area: {len(aoi_gdf)} province(s)\n"

    ax.text(0.1, 0.9, summary_text, transform=ax.transAxes,
            fontsize=12, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Legend
    legend_elements = [
        Line2D([0], [0], color='black', linewidth=2, label='AOI Boundary'),
        Rectangle((0, 0), 1, 1, facecolor='green', alpha=0.6, label='DEM Tiles'),
        Rectangle((0, 0), 1, 1, facecolor='blue', alpha=0.4, label='Climate Data'),
        Rectangle((0, 0), 1, 1, facecolor='brown', alpha=0.6, label='Soil Tiles')
    ]
    ax.legend(handles=legend_elements, loc='center', fontsize=11)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    log.info(f"Saved coverage visualization to {output_path}")
    plt.close()


def run_full_sanity_check(project_root: Path, config: dict) -> Dict[str, DataQualityReport]:
    """
    Run complete sanity check on all downloaded data.

    Parameters
    ----------
    project_root : Path
        Project root directory
    config : dict
        Configuration dictionary from config.yml

    Returns
    -------
    Dict[str, DataQualityReport]
        Reports for each data type
    """
    log.info("="*60)
    log.info("STARTING COMPREHENSIVE DATA SANITY CHECK")
    log.info("="*60)

    # Load AOI
    study_areas = project_root / config['paths']['study_areas']
    holdout = project_root / config['paths']['external_holdout']

    gdf_cv = gpd.read_file(study_areas, layer='cv_provinces')
    gdf_holdout = gpd.read_file(holdout, layer='external_holdout')
    aoi_gdf = pd.concat([gdf_cv, gdf_holdout], ignore_index=True)

    # Run checks
    reports = {}

    # DEM check
    dem_dir = project_root / config['paths']['dem_dir']
    reports['dem'] = check_dem_data(dem_dir, aoi_gdf)
    print(reports['dem'])

    # Climate check
    climate_dir = project_root / config['paths']['climate_dir']
    reports['climate'] = check_climate_data(
        climate_dir, aoi_gdf,
        expected_vars=config['data_sources']['daymet']['daily_variables'],
        expected_date_range=config['data_sources']['daymet']['date_range']
    )
    print(reports['climate'])

    # Soil check
    soils_dir = project_root / config['paths']['soils_dir']
    reports['soil'] = check_soil_data(soils_dir, aoi_gdf)
    print(reports['soil'])

    # Create visualization
    viz_path = project_root / config['paths']['reports_data_acquisition'] / "data_coverage_overview.png"
    create_coverage_visualization(dem_dir, climate_dir, soils_dir, aoi_gdf, viz_path)

    log.info("="*60)
    log.info("SANITY CHECK COMPLETE")
    log.info("="*60)

    return reports
