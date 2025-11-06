"""
Organize DEM files by physiographic province.

This script:
1. Reads the province boundary shapefile
2. For each DEM file, determines which province(s) it intersects
3. Copies (duplicates) the DEM to data/processed/{province_name}/ subdirectories
4. Optionally renames files with province prefix for clarity
"""

import shutil
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import rasterio
from shapely.geometry import box
from tqdm import tqdm


def get_dem_bounds(dem_path: Path) -> box:
    """Get the bounding box of a DEM file."""
    with rasterio.open(dem_path) as src:
        bounds = src.bounds
        return box(bounds.left, bounds.bottom, bounds.right, bounds.top)


def find_intersecting_provinces(
    dem_bounds: box, provinces_gdf: gpd.GeoDataFrame
) -> List[str]:
    """
    Find all provinces that intersect with the DEM bounds.

    Args:
        dem_bounds: Shapely box representing DEM extent
        provinces_gdf: GeoDataFrame with province boundaries

    Returns:
        List of province names that intersect the DEM
    """
    intersecting = provinces_gdf[provinces_gdf.intersects(dem_bounds)]
    return intersecting["PROVINCE"].tolist()


def sanitize_province_name(name: str) -> str:
    """Convert province name to valid directory name."""
    return name.lower().replace(" ", "_").replace("&", "and")


def organize_dems(
    raw_dem_dir: Path,
    province_shapefile: Path,
    output_base_dir: Path,
    add_prefix: bool = True,
    dry_run: bool = False,
):
    """
    Organize DEMs by province.

    Args:
        raw_dem_dir: Directory containing raw DEM .tif files
        province_shapefile: Path to province boundary shapefile
        output_base_dir: Base directory for organized DEMs (e.g., data/processed)
        add_prefix: If True, add province prefix to filename
        dry_run: If True, only print what would be done without copying
    """
    # Read province boundaries
    print(f"Reading province boundaries from {province_shapefile}...")
    provinces = gpd.read_file(province_shapefile)

    # Print province info
    print(f"\nFound {len(provinces)} provinces:")
    for idx, row in provinces.iterrows():
        print(f"  - {row['PROVINCE']}")

    # Get all DEM files
    dem_files = list(raw_dem_dir.glob("*.tif"))
    print(f"\nFound {len(dem_files)} DEM files to organize")

    # Track statistics
    stats: Dict[str, int] = {}
    duplicate_count = 0

    # Process each DEM
    print("\nProcessing DEMs...")
    for dem_path in tqdm(dem_files, desc="Organizing DEMs"):
        try:
            # Get DEM bounds
            dem_bounds = get_dem_bounds(dem_path)

            # Find intersecting provinces
            intersecting_provinces = find_intersecting_provinces(dem_bounds, provinces)

            if not intersecting_provinces:
                print(f"Warning: {dem_path.name} does not intersect any province")
                continue

            # Track if this is a duplicate (intersects multiple provinces)
            if len(intersecting_provinces) > 1:
                duplicate_count += 1

            # Copy to each intersecting province
            for province_name in intersecting_provinces:
                # Update statistics
                stats[province_name] = stats.get(province_name, 0) + 1

                # Create output directory
                province_dir_name = sanitize_province_name(province_name)
                output_dir = output_base_dir / province_dir_name

                if not dry_run:
                    output_dir.mkdir(parents=True, exist_ok=True)

                # Determine output filename
                if add_prefix:
                    output_filename = f"{province_dir_name}_{dem_path.name}"
                else:
                    output_filename = dem_path.name

                output_path = output_dir / output_filename

                # Copy file
                if dry_run:
                    print(
                        f"  Would copy: {dem_path.name} -> {output_dir.name}/{output_filename}"
                    )
                else:
                    shutil.copy2(dem_path, output_path)

        except Exception as e:
            print(f"Error processing {dem_path.name}: {e}")
            continue

    # Print summary statistics
    print("\n" + "=" * 60)
    print("ORGANIZATION SUMMARY")
    print("=" * 60)
    print(f"Total DEMs processed: {len(dem_files)}")
    print(f"DEMs intersecting multiple provinces: {duplicate_count}")
    print("\nDEMs per province:")
    for province_name in sorted(stats.keys()):
        print(f"  {province_name}: {stats[province_name]} files")

    if dry_run:
        print("\n** DRY RUN - No files were actually copied **")
    else:
        print(f"\nFiles organized in: {output_base_dir}")


if __name__ == "__main__":
    # Define paths
    project_root = Path(__file__).parent.parent.parent
    raw_dem_dir = project_root / "data" / "raw" / "dem_30m"
    province_shapefile = (
        project_root / "data" / "raw" / "boundaries" / "study_provinces.shp"
    )
    output_base_dir = project_root / "data" / "processed" / "dem_30m_by_province"

    # First do a dry run to see what would happen
    print("RUNNING DRY RUN FIRST...")
    print("=" * 60)
    organize_dems(
        raw_dem_dir=raw_dem_dir,
        province_shapefile=province_shapefile,
        output_base_dir=output_base_dir,
        add_prefix=True,
        dry_run=True,
    )

    # Ask user to confirm
    print("\n" + "=" * 60)
    response = input("\nProceed with actual file organization? (y/n): ")

    if response.lower() == "y":
        print("\nProceeding with file organization...")
        organize_dems(
            raw_dem_dir=raw_dem_dir,
            province_shapefile=province_shapefile,
            output_base_dir=output_base_dir,
            add_prefix=True,
            dry_run=False,
        )
        print("\nDone!")
    else:
        print("\nCancelled.")
