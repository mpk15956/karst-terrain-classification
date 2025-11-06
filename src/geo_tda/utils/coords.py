"""
Coordinate and tile key utilities for DEM processing.
"""

import re


def get_key_from_sw_corner(lon: int, lat: int) -> str:
    """
    Generate standard USGS 1x1 degree DEM tile key from SW corner coordinates.

    Example: (lon=-85, lat=33) -> 'n34w085'

    Args:
        lon: Longitude (western edge of tile)
        lat: Latitude (southern edge of tile)

    Returns:
        Tile key string
    """
    ns = 'n' if lat >= 0 else 's'
    ew = 'w' if lon < 0 else 'e'
    # The key uses the northern latitude and western longitude bounds
    lat_key = abs(lat) + 1 if ns == 'n' else abs(lat)
    lon_key = abs(lon) if ew == 'w' else abs(lon) - 1

    return f"{ns}{int(lat_key):02d}{ew}{int(lon_key):03d}"


def get_bbox_from_key(key: str) -> tuple[float, float, float, float]:
    """
    Calculate bounding box from USGS 1x1 degree DEM tile key.

    The key represents the NW corner of the tile.

    Example: 'n34w085' -> (-85.0, 33.0, -84.0, 34.0)

    Args:
        key: Tile key (e.g., 'n34w085')

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat)
    """
    match = re.match(r"(n|s)(\d{2})(w|e)(\d{3})", key)
    if not match:
        raise ValueError(f"Invalid DEM key format: {key}")

    ns, lat_str, ew, lon_str = match.groups()
    lat_bound = int(lat_str)
    lon_bound = int(lon_str)

    if ns == 'n':
        max_lat = float(lat_bound)
        min_lat = float(lat_bound - 1)
    else:  # ns == 's'
        max_lat = float(-lat_bound + 1)
        min_lat = float(-lat_bound)

    if ew == 'w':
        min_lon = float(-lon_bound)
        max_lon = float(-lon_bound + 1)
    else:  # ew == 'e'
        min_lon = float(lon_bound)
        max_lon = float(lon_bound + 1)

    return (min_lon, min_lat, max_lon, max_lat)
