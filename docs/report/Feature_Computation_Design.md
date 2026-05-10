# Feature Computation Design: Error Handling Rationale

## Introduction

In an ideal world, code is deterministic: if it works for one $224 \times 224$ matrix, it should work for all of them. However, in **geospatial data science**, "similar" data often hides invisible edge cases that crash algorithms. The error handling implemented in `compute_features.ipynb` is not a sign of flawed code, but rather a necessary defense against data that violates mathematical assumptions.

This document explains why comprehensive error handling (try-except blocks with fallback values) is essential for the feature computation pipeline, even when processing seemingly uniform DEM tiles.

## The Three "Silent Killers" in DEM Processing

### 1. Divide-by-Zero Errors in Deep Learning Pre-processing

**Location in Code:** `prepare_3channel_input()` function, `normalize_channel()` helper (lines ~757-765 in `compute_features.ipynb`)

**The Edge Case:**
A tile that falls entirely within a lake, a flat parking lot, or a large building roof might have **zero variance** (every pixel is identical).

**The Mathematical Problem:**
The normalization logic uses z-score standardization:
```python
normalized = (channel - mean) / std
```

If all pixels are identical, `std = 0`. Division by zero creates `NaN` (Not a Number) or `Inf` values.

**The Impact:**
- ResNet-50 and ViT models will ingest these `NaN` values
- Model outputs become `NaN` features
- This effectively poisons that row of the dataset, causing downstream Random Forest models to fail silently or produce unreliable predictions

**The Solution:**
The `normalize_channel()` function includes an explicit check:
```python
if std == 0:
    return np.zeros_like(channel)
```

This prevents `NaN` propagation by returning a zero-filled channel when variance is zero, allowing the pipeline to continue processing with a valid (though information-poor) feature vector.

**Real-World Examples:**
- Flat agricultural fields (rice paddies, tilled fields)
- Large bodies of water (lakes, reservoirs)
- Urban infrastructure (parking lots, building roofs)
- Artificially filled areas (construction sites, landfills)

---

### 2. NoData Propagation from Edge Tiles

**Location in Code:** WhiteboxTools calls throughout the feature computation loop (lines ~1529-1583) and TDA pipeline (lines ~1625-1667)

**The Edge Case:**
The dataset covers Warren and Hardin Counties, Kentucky. Real-world raster datasets have irregular boundaries, meaning square tiles at the very edge of the county will be partially filled with valid elevation data and partially filled with `NoData` values (often represented as `-9999`, `NaN`, or `-3.4e+38`).

**The Mathematical Problem:**
Many algorithms cannot handle `NoData` values gracefully:

- **WhiteboxTools:** When curvature, slope, or aspect algorithms encounter `NoData` values, they may:
  - Return garbage values (e.g., `-3.4e+38`) for the entire tile
  - Fail silently and produce invalid outputs
  - Crash the computation entirely

- **Topological Data Analysis (TDA):** The `cripser.computePH()` function expects finite values:
  - If `NaN` values are present, the filtration may fail to build
  - The persistence diagram may be empty or contain invalid entries
  - Downstream vectorization (Betti curves, persistence landscapes, persistence images) will fail

**The Impact:**
- Edge tiles produce invalid feature vectors
- Without error handling, the entire pipeline crashes on the first problematic tile
- Silent failures (garbage values) are worse than crashes because they corrupt the dataset without warning

**The Solution:**
All WhiteboxTools and TDA computations are wrapped in try-except blocks:
```python
try:
    baseline_vector = compute_traditional_baseline(...)
except Exception as e:
    tqdm.write(f"  ⚠ Traditional+WBT failed: {e}")
    baseline_vector = np.zeros(220, dtype=np.float64)
```

When failures occur, the pipeline:
1. Logs the error for debugging
2. Returns a zero-filled feature vector of the correct dimensionality
3. Continues processing the remaining tiles

This ensures that edge cases don't halt the entire batch processing job.

**Real-World Examples:**
- Tiles at county boundaries
- Tiles overlapping with data collection boundaries
- Tiles containing masked areas (protected lands, private property)
- Tiles with sensor artifacts or data gaps

---

### 3. Topological "Explosions" in Persistent Homology

**Location in Code:** `cripser.computePH()` call (line ~1626) and downstream TDA vectorization (lines ~1634-1667)

**The Edge Case:**
While rare, extremely noisy terrain can create a "worst-case scenario" for homology computation. Examples include:
- Dense forest canopy that wasn't filtered out of the DEM
- Highly eroded karst terrain with thousands of small sinkholes
- Urban areas with complex building geometries
- Artificially modified terrain (mining operations, construction)

**The Mathematical Problem:**
Persistent homology builds a simplicial complex from the DEM data. The number of simplices in the filtration grows with terrain complexity:

- **Normal terrain:** Hundreds to thousands of simplices
- **Pathological terrain:** Tens of thousands to millions of simplices

When the number of simplices grows exponentially, `cripser` (despite being optimized) can:
- Hit memory limits (causing `MemoryError`)
- Exceed computation timeouts (causing the kernel to hang)
- Produce invalid persistence diagrams that crash downstream vectorization

**The Impact:**
- A single pathological tile can crash the entire batch processing job
- Without error handling, hours of computation can be lost
- The failure is non-deterministic: it depends on the specific terrain geometry

**The Solution:**
The TDA pipeline includes comprehensive error handling:
```python
try:
    pd = cripser.computePH(dem_tile.astype(np.float64), maxdim=1)
except Exception as e:
    tqdm.write(f"  ⚠ PH Computation failed: {e}")
    pd = None

# Downstream vectorization checks for None
if pd is None:
    raise ValueError("PH computation failed, cannot compute Betti curves")
```

When persistent homology computation fails:
1. The error is logged
2. `pd` is set to `None`
3. Downstream vectorization functions detect `None` and return zero-filled feature vectors
4. Processing continues for remaining tiles

**Real-World Examples:**
- Karst terrain with dense sinkhole networks (relevant to Mammoth Cave National Park study area)
- Urban areas with complex building footprints
- Forested areas where LiDAR penetrated canopy inconsistently
- Mining or construction sites with artificial terrain modifications

---

## Summary: The 1% Edge Case Problem

You are not coding for the 99% of tiles that are normal hills and valleys. You are adding error handling for the **1% of tiles** that are:
- Perfectly flat lakes (Divide by Zero)
- Edge-of-map artifacts (NoData)
- Noisy glitches or pathological terrain (Topological Explosions)

### Why This Matters for Model Performance

If you don't track and handle these failures:
1. **Silent Data Corruption:** `NaN` values propagate through the feature matrix, causing Random Forest models to produce unreliable predictions
2. **Mystery Poor Performance:** Models trained on corrupted data will underperform, but you won't know why
3. **Non-Reproducible Results:** Different runs may process tiles in different orders, leading to inconsistent failures

### Implementation Strategy

The error handling strategy follows a consistent pattern:

1. **Try the computation** with the actual data
2. **Catch any exception** (broad catch to handle all failure modes)
3. **Log the error** for debugging and analysis
4. **Return a zero-filled feature vector** of the correct dimensionality
5. **Continue processing** the remaining tiles

This approach ensures:
- **Robustness:** The pipeline completes even when individual tiles fail
- **Transparency:** Errors are logged so you can identify problematic tiles
- **Consistency:** Failed tiles produce valid (though information-poor) feature vectors, maintaining matrix dimensions

### Code References

- **Normalization with zero-variance check:** `notebooks/final_project/compute_features.ipynb`, lines ~757-765
- **WhiteboxTools error handling:** `notebooks/final_project/compute_features.ipynb`, lines ~1529-1583
- **TDA error handling:** `notebooks/final_project/compute_features.ipynb`, lines ~1625-1667
- **Deep learning feature extraction error handling:** `notebooks/final_project/compute_features.ipynb`, lines ~1685-1712

---

## Conclusion

Implementing comprehensive error handling takes minimal time (the try-except blocks add ~5 minutes of coding) but saves hours of debugging "mystery" poor performance later. In geospatial data science, edge cases are not bugs—they are features of real-world data that must be anticipated and handled gracefully.

