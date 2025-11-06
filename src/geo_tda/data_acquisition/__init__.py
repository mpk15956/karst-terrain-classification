"""
Data acquisition module for climate, soil, and DEM data.

This module provides robust, cloud-native acquisition of geospatial data
with atomic writes, authentication handling, and integrity validation.
"""

__all__ = [
    'build_dem_download_jobs_stac',
    'execute_downloads',
]

# Lazy imports to avoid dependency issues
def __getattr__(name):
    if name == 'build_dem_download_jobs_stac':
        from .dem import build_dem_download_jobs_stac
        return build_dem_download_jobs_stac
    elif name == 'execute_downloads':
        from .download_core import execute_downloads
        return execute_downloads
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")