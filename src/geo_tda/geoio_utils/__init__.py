"""
I/O utilities for raster, vector, and provenance tracking.
"""

from .provenance import write_provenance, get_git_commit
from .raster import safe_union_all, ensure_crs, fix_invalid
from .vector import read_vector, write_vector, detect_name_column, load_and_standardize

__all__ = [
    # Provenance
    'write_provenance',
    'get_git_commit',
    # Raster/geometry utilities
    'safe_union_all',
    'ensure_crs',
    'fix_invalid',
    # Vector I/O
    'read_vector',
    'write_vector',
    'detect_name_column',
    'load_and_standardize',
]
