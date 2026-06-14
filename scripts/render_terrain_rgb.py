"""Scale-normalized DEM -> 3-channel uint8 renderers for the optical contrast.

The optical-metric contrast must NOT see absolute elevation scale (MESA is
~[0,1], real is meters); otherwise FID/CLIP separate for a scaling reason, not a
drainage reason (a false signal). So every render is built on a robust-normalized
DEM (2-98 percentile -> [0,1]), parallel to the H0 metric's scale-invariance.

Two renders, both returned at native 768x768x3 uint8 (the embed step resizes to
224/299): hillshade (primary; gradient/relief shaded relief, the terrain texture
a vision net actually responds to) and a 3-channel geomorphic stack
(hillshade / normalized-elevation / normalized-slope) as a robustness variant.

`bounds=(lo, hi)` lets a perturbed patch be normalized with the ORIGINAL patch's
percentile bounds, so the optical metric measures the true visual delta of a
perturbation rather than a renormalization artifact (the power-probe clipping
fix). Pure numpy: no whitebox, no torch -> parallel-safe and env-agnostic.
"""
from __future__ import annotations

import numpy as np


def robust_bounds(dem: np.ndarray, lo_pct: float = 2.0, hi_pct: float = 98.0):
    """(lo, hi) robust percentile bounds of a DEM (ignoring nan)."""
    v = dem[np.isfinite(dem)]
    if v.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(v, [lo_pct, hi_pct])
    if hi <= lo:
        hi = lo + 1.0
    return float(lo), float(hi)


def robust_normalize(dem: np.ndarray, bounds=None, lo_pct: float = 2.0,
                     hi_pct: float = 98.0) -> np.ndarray:
    """DEM -> [0,1] by robust percentile clip. If bounds given, use them
    (so a perturbed patch shares the original's bounds)."""
    lo, hi = bounds if bounds is not None else robust_bounds(dem, lo_pct, hi_pct)
    out = (dem.astype("float64") - lo) / (hi - lo)
    return np.clip(out, 0.0, 1.0)


def hillshade(dem_norm: np.ndarray, azimuth: float = 315.0,
              altitude: float = 45.0, z: float = 1.0) -> np.ndarray:
    """Shaded relief in [0,1] from a normalized DEM (gradient-based, so it keys
    off relief STRUCTURE, not absolute elevation). z exaggerates relief."""
    gy, gx = np.gradient(dem_norm.astype("float64") * z)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = np.radians(360.0 - azimuth + 90.0)
    alt = np.radians(altitude)
    sh = (np.sin(alt) * np.sin(slope)
          + np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip((sh + 1.0) / 2.0, 0.0, 1.0)


def slope_norm(dem_norm: np.ndarray) -> np.ndarray:
    """Normalized gradient magnitude in [0,1] (per-patch max-scaled). Flags
    channel walls hard even when the floor is clipped flat."""
    gy, gx = np.gradient(dem_norm.astype("float64"))
    s = np.hypot(gx, gy)
    m = s.max()
    return s / m if m > 0 else s


def _u8(a: np.ndarray) -> np.ndarray:
    return np.clip(np.round(a * 255.0), 0, 255).astype("uint8")


def render_hillshade_rgb(dem: np.ndarray, bounds=None) -> np.ndarray:
    """768x768x3 uint8 hillshade (replicated to RGB)."""
    n = robust_normalize(dem, bounds=bounds)
    h = _u8(hillshade(n))
    return np.repeat(h[:, :, None], 3, axis=2)


def render_stack_rgb(dem: np.ndarray, bounds=None) -> np.ndarray:
    """768x768x3 uint8 geomorphic stack: hillshade / normalized-elevation / slope."""
    n = robust_normalize(dem, bounds=bounds)
    ch = np.stack([hillshade(n), n, slope_norm(n)], axis=2)
    return _u8(ch)
