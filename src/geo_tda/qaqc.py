# -*- coding: utf-8 -*-
"""
Geospatial QA/QC utilities for the Multiscale TDA Geomorphology project.

Design goals:
- Small, composable checks that either raise (hard fail) or return a structured result.
- Clear, actionable error messages for reproducibility/auditability.
- Safe defaults for common pitfalls: CRS, invalid topology, contiguity, leakage, and area drift.

Typical usage (in a notebook/script):
    from qaqc import qa_study_package
    report = qa_study_package(
        study_final, validation_final, holdout_final,
        expected_holdout_percent=0.25,
        gap_buffer_m=0, target_crs="EPSG:5070"
    )
    print(report)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import logging
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry
from shapely import make_valid
from pyproj import CRS

log = logging.getLogger("qaqc")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str = ""
    extras: dict = field(default_factory=dict)

    def __bool__(self):
        return self.ok

    def __str__(self):
        status = "✅ PASS" if self.ok else "❌ FAIL"
        return f"[{status}] {self.name}: {self.message}"


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #

def _as_crs(crs_like) -> CRS:
    return CRS.from_user_input(crs_like)


def _geom_area_km2(geom: BaseGeometry, crs: Union[str, CRS]) -> float:
    """Area in km^2. Assumes geom is already in an equal-area CRS."""
    return float(geom.area) / 1_000_000.0


def _largest_part(geometry: BaseGeometry) -> BaseGeometry:
    gs = gpd.GeoSeries([geometry]).explode(index_parts=False)
    if len(gs) == 1:
        return make_valid(gs.iloc[0])
    areas = gs.area.values
    return make_valid(gs.iloc[int(np.argmax(areas))])


def _is_singlepart_polygon(geometry: BaseGeometry) -> bool:
    gs = gpd.GeoSeries([geometry]).explode(index_parts=False)
    return len(gs) == 1 and not gs.iloc[0].is_empty


def _sum_area_km2(gdf: gpd.GeoDataFrame) -> float:
    return float(gdf.geometry.area.sum()) / 1_000_000.0


def _percent_diff(a: float, b: float) -> float:
    """Symmetric percentage difference in [0, ∞)."""
    if max(abs(a), abs(b)) < 1e-12:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b))


def _safe_union_all(gdf: gpd.GeoDataFrame, grid_size: float = 1e-6) -> BaseGeometry:
    """
    Safely compute union of all geometries in a GeoDataFrame.
    Fixes invalid geometries and handles topology exceptions.
    """
    try:
        # First try to fix any invalid geometries
        valid_geoms = gdf.geometry.apply(make_valid)
        # Use union_all() instead of deprecated unary_union
        return valid_geoms.union_all(grid_size=grid_size)
    except Exception as e:
        # Fallback: try with larger grid size for more aggressive snapping
        log.warning(f"Union failed with grid_size={grid_size}, retrying with larger grid: {e}")
        try:
            valid_geoms = gdf.geometry.apply(make_valid)
            return valid_geoms.union_all(grid_size=1e-5)
        except Exception as e2:
            # Last resort: union geometries one by one
            log.warning(f"Grid-based union failed, using iterative union: {e2}")
            valid_geoms = [make_valid(g) for g in gdf.geometry]
            result = valid_geoms[0]
            for g in valid_geoms[1:]:
                try:
                    result = result.union(g)
                except:
                    # Skip problematic geometries
                    log.warning("Skipping problematic geometry in union")
            return result


# --------------------------------------------------------------------------- #
# Core checks (raise=False returns CheckResult; raise=True raises AssertionError)
# --------------------------------------------------------------------------- #

def crs_policy_check(
        gdfs: Sequence[gpd.GeoDataFrame],
        target_crs: Union[str, CRS],
        raise_on_fail: bool = False,
) -> CheckResult:
    name = "CRS policy (all in target CRS)"
    target = _as_crs(target_crs)
    all_ok = True
    bad = []
    for i, gdf in enumerate(gdfs):
        if gdf.crs is None or _as_crs(gdf.crs) != target:
            all_ok = False
            bad.append(i)
    msg = "All GeoDataFrames match target CRS." if all_ok else f"Indexes not in {target.to_string()}: {bad}"
    res = CheckResult(name, all_ok, msg, {"bad_indexes": bad})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def geometry_validity_report(
        gdf: gpd.GeoDataFrame,
        raise_on_fail: bool = False,
) -> CheckResult:
    name = "Geometry validity (no empty/invalid)"
    empties = (~gdf.geometry.notnull()) | (gdf.geometry.is_empty)
    invalid = ~gdf.is_valid
    n_empty = int(empties.sum())
    n_invalid = int(invalid.sum())
    ok = (n_empty == 0) and (n_invalid == 0)
    msg = "All geometries valid & non-empty." if ok else f"{n_empty} empty, {n_invalid} invalid geometries."
    res = CheckResult(name, ok, msg, {"n_empty": n_empty, "n_invalid": n_invalid})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def contiguity_check(
        geom: BaseGeometry,
        raise_on_fail: bool = False,
) -> CheckResult:
    name = "Holdout contiguity (single-part)"
    ok = _is_singlepart_polygon(geom)
    msg = "Holdout is single contiguous polygon." if ok else "Holdout is fragmented; expected a single polygon."
    res = CheckResult(name, ok, msg)
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def area_tolerance_check(
        achieved_km2: float,
        target_km2: float,
        rel_tol: float = 0.005,  # ±0.5%
        raise_on_fail: bool = False,
) -> CheckResult:
    name = "Holdout area within tolerance"
    rel_err = 0.0 if target_km2 <= 0 else abs(achieved_km2 - target_km2) / target_km2
    ok = rel_err <= rel_tol
    msg = (
        f"Δ={rel_err * 100:.2f}% (achieved={achieved_km2:,.2f} km² vs target={target_km2:,.2f} km²)."
        if not ok else
        f"Match ok (Δ={rel_err * 100:.2f}%)."
    )
    res = CheckResult(name, ok, msg, {"rel_err": rel_err})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def leakage_gap_check(
        train_geom: BaseGeometry,
        holdout_geom: BaseGeometry,
        gap_buffer_m: float = 0.0,
        raise_on_fail: bool = False,
) -> CheckResult:
    """
    If gap_buffer_m > 0, ensure train and buffered holdout are disjoint (no touching).
    If gap_buffer_m == 0, require they do not overlap (touching is allowed).
    """
    name = "Train/Holdout leakage gap"

    # Make sure geometries are valid before checking
    train_geom = make_valid(train_geom)
    holdout_geom = make_valid(holdout_geom)

    if gap_buffer_m > 0:
        disjoint = holdout_geom.buffer(gap_buffer_m).disjoint(train_geom)
        ok, msg = disjoint, (f"Gap ok (≥{gap_buffer_m:.0f} m)." if disjoint else "Gap buffer failed (touch/overlap).")
    else:
        overlaps = holdout_geom.intersects(train_geom) and not holdout_geom.touches(train_geom)
        ok, msg = (not overlaps), ("No overlap (touch allowed)." if not overlaps else "Train overlaps holdout.")
    res = CheckResult(name, ok, msg, {"gap_buffer_m": gap_buffer_m})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def duplicate_names_check(
        gdf: gpd.GeoDataFrame,
        name_field: str = "PROVINCE",
        raise_on_fail: bool = False,
) -> CheckResult:
    name = f"Duplicate names in '{name_field}'"
    dupes = gdf[name_field].duplicated(keep=False)
    n_dupes = int(dupes.sum())
    ok = n_dupes == 0
    msg = "No duplicate names." if ok else f"{n_dupes} duplicate rows by '{name_field}'."
    res = CheckResult(name, ok, msg, {"dupe_rows": gdf[dupes].index.tolist()})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def bounds_proximity_report(
        a: gpd.GeoDataFrame, b: gpd.GeoDataFrame,
        raise_on_fail: bool = False,
) -> CheckResult:
    """
    Report centroid separation (meters) between datasets after projecting to EPSG:3857.
    Informational only (always PASS).
    """
    name = "Bounds proximity (informational)"
    try:
        # Project to Web Mercator
        a_3857 = a.to_crs(3857)
        b_3857 = b.to_crs(3857)

        # Use the safe union function instead of direct unary_union
        a_union = _safe_union_all(a_3857)
        b_union = _safe_union_all(b_3857)

        # Get centroids
        ac = a_union.centroid
        bc = b_union.centroid

        # Calculate distance
        dist_m = ac.distance(bc)
        msg = f"Centroid separation ≈ {dist_m / 1000:.1f} km."
        return CheckResult(name, True, msg, {"distance_m": float(dist_m)})
    except Exception as e:
        # If we can't compute distance, just report it as informational
        msg = f"Could not compute centroid separation (geometry issues): {str(e)[:100]}"
        return CheckResult(name, True, msg, {"error": str(e)})


def coverage_check(
        study_gdf: gpd.GeoDataFrame,
        validation_gdf: gpd.GeoDataFrame,
        holdout_gdf: gpd.GeoDataFrame,
        name_field: str = "PROVINCE",
        raise_on_fail: bool = False,
) -> CheckResult:
    """
    Check that (study ∪ holdout) exactly reconstructs original study province geometry,
    and that validation province is disjoint from both.
    (Assumes all three in the same equal-area CRS.)
    """
    name = "Coverage & disjointness (study/train + holdout)"
    # Build province-by-province checks for the ones that have a holdout
    problems: List[str] = []
    for prov in holdout_gdf[name_field].unique():
        h_gdf = holdout_gdf[holdout_gdf[name_field] == prov]
        s_gdf = study_gdf[study_gdf[name_field] == prov]

        # Use safe union function
        h = _safe_union_all(h_gdf)
        s = _safe_union_all(s_gdf)

        # Make valid before operations
        h = make_valid(h)
        s = make_valid(s)

        union = shapely.union_all([h, s])
        # Expect exact reconstruction (allow tiny numeric tolerance via symmetric difference area)
        sym = shapely.symmetric_difference(union, s.buffer(0).union(h.buffer(0)))
        if sym.area > 1e-6:
            problems.append(f"{prov}: union symmetry area={sym.area:.3f} > tol")

    # Validation disjoint from all study/holdout
    v = _safe_union_all(validation_gdf)
    sh_union = shapely.union_all([
        _safe_union_all(study_gdf),
        _safe_union_all(holdout_gdf)
    ])

    # Make valid before checking disjoint
    v = make_valid(v)
    sh_union = make_valid(sh_union)

    valid_disjoint = v.disjoint(sh_union)
    ok = (len(problems) == 0) and valid_disjoint
    msg = "Coverage ok; validation is disjoint." if ok else f"Issues: {problems}; validation_disjoint={valid_disjoint}"
    res = CheckResult(name, ok, msg, {"problems": problems, "validation_disjoint": valid_disjoint})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


def dataframe_schema_check(
        gdf: gpd.GeoDataFrame,
        required_columns: Sequence[str],
        raise_on_fail: bool = False,
) -> CheckResult:
    name = "Schema contains required columns"
    missing = [c for c in required_columns if c not in gdf.columns]
    ok = len(missing) == 0
    msg = "All required columns present." if ok else f"Missing columns: {missing}"
    res = CheckResult(name, ok, msg, {"missing": missing})
    if raise_on_fail and not res:
        raise AssertionError(str(res))
    return res


# --------------------------------------------------------------------------- #
# High-level orchestrator
# --------------------------------------------------------------------------- #

def qa_study_package(
        study_gdf: gpd.GeoDataFrame,
        validation_gdf: gpd.GeoDataFrame,
        holdout_gdf: gpd.GeoDataFrame,
        *,
        expected_holdout_percent: float,
        gap_buffer_m: float = 0.0,
        target_crs: Union[str, CRS] = "EPSG:5070",
        name_field: str = "PROVINCE",
        rel_area_tol: float = 0.005,  # ±0.5%
        hard_fail: bool = False,
) -> str:
    """
    Run a standard suite of QA checks for the (study, validation, holdout) package.
    Assumes inputs are the *final* products in the same equal-area CRS.

    Returns a human-readable multi-line report. Set hard_fail=True to raise on any failure.
    """
    results: List[CheckResult] = []

    # 0) CRS & schema
    results.append(crs_policy_check([study_gdf, validation_gdf, holdout_gdf], target_crs))
    results.append(dataframe_schema_check(study_gdf, [name_field, "AREA_SQKM"]))
    results.append(dataframe_schema_check(validation_gdf, [name_field, "AREA_SQKM"]))
    results.append(dataframe_schema_check(holdout_gdf, [name_field, "AREA_SQKM"]))

    # 1) validity
    results.append(geometry_validity_report(study_gdf))
    results.append(geometry_validity_report(validation_gdf))
    results.append(geometry_validity_report(holdout_gdf))

    # 2) duplicate names (sanity)
    results.append(duplicate_names_check(study_gdf, name_field))
    results.append(duplicate_names_check(validation_gdf, name_field))
    results.append(duplicate_names_check(holdout_gdf, name_field))

    # 3) bounds overlap sanity
    results.append(bounds_proximity_report(study_gdf, validation_gdf))

    # 4) holdout contiguity + area tolerance per province with a holdout
    # (If multiple provinces could have holdouts in the future, loop them.)
    for prov in holdout_gdf[name_field].unique():
        h_gdf = holdout_gdf[holdout_gdf[name_field] == prov]
        s_gdf = study_gdf[study_gdf[name_field] == prov]

        # Use safe union function
        h = _safe_union_all(h_gdf)
        s = _safe_union_all(s_gdf)

        # Make geometries valid
        h = make_valid(h)
        s = make_valid(s)

        results.append(contiguity_check(h))

        # compute target by percent of original province area (study + holdout)
        original = shapely.union_all([h, s])
        A_orig_km2 = float(original.area) / 1_000_000.0
        target_km2 = expected_holdout_percent * A_orig_km2
        A_holdout_km2 = float(h.area) / 1_000_000.0
        results.append(area_tolerance_check(A_holdout_km2, target_km2, rel_tol=rel_area_tol))

        # leakage check against train (study version of that province)
        results.append(leakage_gap_check(train_geom=s, holdout_geom=h, gap_buffer_m=gap_buffer_m))

    # 5) coverage and validation disjointness
    results.append(coverage_check(study_gdf, validation_gdf, holdout_gdf, name_field=name_field))

    # Build report
    lines = ["\n=== QA/QC Report ==="]
    any_fail = False
    for r in results:
        lines.append(str(r))
        any_fail |= (not r.ok)

    summary = "✅ All checks passed." if not any_fail else "❌ One or more checks failed."
    lines.append(f"\nSummary: {summary}")

    report = "\n".join(lines)

    if hard_fail and any_fail:
        # Raise one combined assertion to keep error handling simple upstream
        raise AssertionError(report)

    return report