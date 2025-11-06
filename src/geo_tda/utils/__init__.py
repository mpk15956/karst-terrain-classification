"""
General utility functions for logging, coordinates, and system resources.
"""

from .coords import get_bbox_from_key, get_key_from_sw_corner
from .logging import setup_colored_logging
from .gpu_detection import (
    detect_gpu_config,
    get_compute_backend,
    check_cupy_available,
    get_system_compute_resources,
    print_compute_summary,
)

__all__ = [
    # Logging
    'setup_colored_logging',
    # Coordinates
    'get_bbox_from_key',
    'get_key_from_sw_corner',
    # GPU Detection
    'detect_gpu_config',
    'get_compute_backend',
    'check_cupy_available',
    'get_system_compute_resources',
    'print_compute_summary',
]