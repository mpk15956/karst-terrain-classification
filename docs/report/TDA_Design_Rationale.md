# TDA Design Rationale: Why Slope, Not Aspect, Texture, or TWI?

## Introduction

This document provides a rigorous mathematical and scientific justification for the design decision to apply **Topological Data Analysis (TDA)** exclusively to **Slope** in the karst terrain classification pipeline. This decision excludes Aspect, Topographic Wetness Index (TWI), Texture metrics, and other terrain derivatives from TDA processing, despite their potential relevance to geomorphological classification.

The core research hypothesis being tested is: *"Can TDA capture multiscale information in a single pass, replacing the need for computationally expensive multi-scale derivative calculations?"* This document defends why Slope is the optimal—and sufficient—metric to test this hypothesis.

---

## Executive Summary

**Design Decision:** Topological Data Analysis (TDA) is applied **only** to Slope-derived rasters, not to Aspect, TWI, Texture, or other terrain metrics.

**Core Hypothesis:** TDA can capture multiscale topographic information in a single computational pass, potentially replacing multi-scale derivative calculations (e.g., TPI at multiple radii) that require repeated WhiteboxTools operations.

**Scope Limitation Rationale:** 
1. **Aspect** is circular data (359° adjacent to 1°), making standard persistent homology mathematically invalid
2. **Texture** is already a statistical summary; applying TDA would abstract an abstraction, losing physical interpretability
3. **TWI/Curvature** are unnecessary for hypothesis testing: if `TDA(Slope)` outperforms `Multiscale_Slope`, the scientific claim is proven without repeating the experiment on other metrics

**Implementation Status:** The current pipeline applies TDA to the DEM directly via sublevel and superlevel filtrations. The planned refactor will extract the Slope raster from `compute_whitebox_stats()` and apply TDA to it, creating `TDA(Slope)` features that can be directly compared against `Multiscale_Slope` features.

---

## Section 1: Why Not Aspect? (The Circular Data Problem)

### The Mathematical Failure

Aspect is **circular data**: it represents direction on a compass, where 359° is mathematically adjacent to 1° (both point nearly due north). In standard mathematical notation:

$$\text{Aspect} \in [0°, 360°) \text{ with } 0° \equiv 360°$$

Standard Persistent Homology uses **sublevel filtrations**, which treat data as **linear** (ordered on the real number line). When applied to circular data, the filtration algorithm sees a massive discontinuity between 359° and 0°, creating artificial topological features that represent the coordinate system boundary, not the terrain geometry.

### Why Standard TDA Fails on Aspect

Persistent Homology builds a simplicial complex by thresholding the function value. For a sublevel filtration on Aspect:

1. At threshold $t = 1°$, pixels with aspect $0° \leq \theta < 1°$ are included
2. At threshold $t = 359°$, pixels with aspect $0° \leq \theta < 359°$ are included
3. At threshold $t = 360°$, **all** pixels are included (since $360° \equiv 0°$)

The algorithm interprets the jump from $359°$ to $0°$ as a **topological boundary**, generating:
- Artificial 1-dimensional homology classes (loops) that represent the coordinate system wrap-around
- Spurious persistence pairs with high persistence values that have no physical meaning
- Topological features that correlate with the **north-south axis orientation** of the DEM, not with actual terrain structure

### The Coordinate System Artifact

Consider a terrain where aspect values are uniformly distributed around the compass. Standard TDA will generate a persistent 1-cycle (loop) with high persistence, representing the fact that "all directions are present." However, this loop is an artifact of the circular coordinate system—it does not represent a physical feature of the terrain (e.g., a circular depression or ridge).

**Example:** A perfectly flat terrain with uniform aspect distribution would generate a persistent 1-cycle in TDA, even though the terrain has no topological structure. This is a **false positive** caused by the circular nature of the data.

### Proper Alternatives (Not Used Here)

Circular statistics methods exist for handling aspect data (e.g., circular mean, von Mises distribution, directional statistics). However, these are not compatible with standard persistent homology algorithms. To apply TDA to aspect would require:
- Converting aspect to Cartesian coordinates: $(x, y) = (\cos(\theta), \sin(\theta))$
- Applying TDA to the 2D point cloud in $(x, y)$ space
- Interpreting results in terms of directional clustering, not terrain topology

This transformation changes the research question from "topological structure of terrain" to "directional clustering of slopes," which is outside the scope of this hypothesis.

**Conclusion:** Standard TDA on raw Aspect data produces mathematically invalid results. Aspect is excluded from TDA processing.

---

## Section 2: Why Not Texture? (The "Summary of a Summary" Problem)

### Texture as Statistical Abstraction

Texture metrics (e.g., GLCM Entropy, GLCM Contrast, GLCM Homogeneity) are **already statistical summaries** of local neighborhood properties. They quantify:
- Spatial patterns in pixel intensity (elevation) within a window
- Statistical relationships between neighboring pixels
- Second-order spatial statistics that capture texture, not raw elevation

**Example:** GLCM Entropy measures the randomness of elevation transitions within a neighborhood. A high entropy value indicates complex, irregular terrain; a low entropy value indicates smooth, uniform terrain.

### TDA as Another Abstraction Layer

Topological Data Analysis is **also** an abstraction: it converts geometric/statistical data into topological summaries (persistence diagrams, Betti curves, persistence landscapes). Applying TDA to Texture means:

$$\text{TDA}(\text{Texture}) = \text{TDA}(\text{Statistical Summary of Elevation})$$

This creates a **summary of a summary**, with two layers of abstraction between the original DEM and the final feature vector.

### Interpretation Challenges

1. **Physical Meaning Loss:** What does a "persistent 1-cycle in GLCM Entropy space" represent? It is not a physical terrain feature (e.g., a sinkhole, ridge, or valley). It is an abstract topological structure in an abstract statistical space.

2. **Double Abstraction:** The pipeline becomes: `DEM → Texture → TDA → Feature Vector`. Each step loses information and physical interpretability. By contrast, `DEM → Slope → TDA → Feature Vector` maintains a direct physical link: slope is a first derivative of elevation, and TDA captures its topological structure.

3. **Redundancy:** If Texture already captures spatial patterns, and TDA also captures spatial patterns, applying both may create redundant features without adding new information.

### The "One Proxy is Enough" Principle

The research hypothesis is: *"Can TDA capture multiscale information?"* Texture is not a multiscale metric in the same sense as Slope. Texture is computed at a fixed window size (e.g., 9×9 pixels), while Slope can be computed at multiple scales (via TPI at different radii). 

To test the hypothesis, we need a metric that:
1. Has a clear multiscale variant (Slope → Multiscale_Slope via TPI)
2. Has direct physical meaning (Slope = gradient, gravity potential)
3. Can be compared directly: `TDA(Slope)` vs. `Multiscale_Slope`

Texture does not satisfy criterion #1: there is no standard "Multiscale_Texture" that uses multiple window sizes in the same way that Multiscale_Slope uses multiple TPI radii.

**Conclusion:** Texture is excluded because applying TDA to it would create an uninterpretable "summary of a summary" without testing the core hypothesis.

---

## Section 3: Why Not TWI/Curvature? (The "One Proxy is Enough" Rule)

### Scientific Sufficiency Argument

The research hypothesis is: *"Can TDA capture multiscale information in a single pass?"*

**If `TDA(Slope)` outperforms `Multiscale_Slope`, the hypothesis is proven.** There is no scientific need to repeat the experiment on TWI, Curvature, or other metrics to make this claim.

This follows the principle of **scientific parsimony**: test the hypothesis with the minimal set of experiments required to draw a conclusion. Adding TDA to TWI or Curvature would be:
- **Redundant:** If TDA works for Slope, it likely works for other metrics too, but proving it for Slope is sufficient
- **Computationally expensive:** Each additional TDA computation adds processing time
- **Scientifically unnecessary:** The hypothesis is about TDA's ability to capture multiscale information, not about TDA's performance on every possible terrain metric

### Slope as the Optimal Candidate

Slope is the ideal metric for testing this hypothesis because:

1. **Physical Meaning:** Slope represents the gradient of elevation, directly related to gravitational potential energy and erosion processes. It is a fundamental control on geomorphological processes.

2. **Non-Circular:** Unlike Aspect, Slope is linear data (0° to 90°, or 0% to 100%), making it compatible with standard persistent homology.

3. **Multiscale Variant Exists:** `Multiscale_Slope` is well-defined via Topographic Position Index (TPI) at multiple radii (5, 15, 25 pixels), providing a clear baseline for comparison.

4. **Computational Efficiency:** Slope is computed once per tile. Applying TDA to it requires a single persistent homology computation, compared to multiple TPI calculations for Multiscale_Slope.

### Why Not Test on Multiple Metrics?

While it might seem rigorous to test TDA on TWI, Curvature, and Slope, this would:
- **Dilute the research question:** The paper would become "TDA on various metrics" rather than "Can TDA replace multiscale calculations?"
- **Add unnecessary complexity:** Each additional metric requires justification, analysis, and interpretation
- **Violate parsimony:** If TDA(Slope) works, that's sufficient proof. If it doesn't work, testing on other metrics won't change the conclusion.

**Conclusion:** TWI and Curvature are excluded because Slope is sufficient to test the hypothesis. Adding them would be redundant and scientifically unnecessary.

---

## Section 4: Implementation Safety Considerations

### A. The "Hardcoded Index" Risk

**Location in Code:** `extract_core_derivatives()` function in `src/karst_tda/features.py` (lines 183-211)

**The Risk:**
The current implementation uses hardcoded slice indices to extract features from the multiscale array:
```python
# Example (pseudo-code):
core_features.append(multiscale_array[:, 0:5])   # Aspect
core_features.append(multiscale_array[:, 10:15]) # Tangential curvature
```

If the order of calculations in `compute_whitebox_stats()` changes, these hardcoded indices will silently grab the wrong data (e.g., grabbing Slope thinking it is Aspect).

**The Solution:**
The implementation uses named constants (`WBT_FEATURE_INDICES`) to prevent breakage:

```183:211:src/karst_tda/features.py
def extract_core_derivatives(multiscale_array: np.ndarray) -> np.ndarray:
    """Extract core single-scale WhiteboxTools features from multiscale array.
    
    Extracts: Aspect, Tangential curvature, Slope, TPI(radius=5), TWI, TRI
    Total: 6 features × 5 stats = 30 features
    
    Uses named constants (WBT_FEATURE_INDICES) to prevent breakage if feature order changes.
    
    Args:
        multiscale_array: Full multiscale derivatives array (n_samples, 70)
        
    Returns:
        Core derivatives array (n_samples, 30)
    """
    if multiscale_array.shape[1] != 70:
        raise ValueError(
            f"Expected multiscale_array with 70 features, got {multiscale_array.shape[1]}"
        )
    
    # Extract features using named indices for safety
    core_features = []
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['aspect'][0]:WBT_FEATURE_INDICES['aspect'][1]])
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['tangential_curvature'][0]:WBT_FEATURE_INDICES['tangential_curvature'][1]])
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['slope'][0]:WBT_FEATURE_INDICES['slope'][1]])
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['twi'][0]:WBT_FEATURE_INDICES['twi'][1]])
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['tri'][0]:WBT_FEATURE_INDICES['tri'][1]])
    core_features.append(multiscale_array[:, WBT_FEATURE_INDICES['tpi_5'][0]:WBT_FEATURE_INDICES['tpi_5'][1]])
    
    return np.concatenate(core_features, axis=1, dtype=np.float64)
```

**Alternative Approach (Future Enhancement):**
When `compute_whitebox_stats()` runs, it could return a list of feature names alongside the data. The extraction function could then find indices dynamically:

```python
def extract_core_derivatives(data, all_names):
    # Find indices where name starts with "aspect" or "slope"
    target_indices = [i for i, n in enumerate(all_names) if n in core_list]
    return data[:, target_indices]
```

**Current Status:** The implementation uses immutable named constants, which is safe as long as `WBT_FEATURE_INDICES` is maintained correctly.

---

### B. The Slope Raster Handoff

**Location in Code:** `compute_whitebox_stats()` function in `src/karst_tda/features.py` (lines 351-664)

**The Requirement:**
When `return_slope_raster=True`, the function must return the slope raster as a **NumPy array**, not as a file path. WhiteboxTools saves temporary files to disk, but these are cleaned up when the temporary directory context exits.

**Current Implementation:**
The function signature already supports this:

```351:378:src/karst_tda/features.py
def compute_whitebox_stats(
    dem_path: Path | str,
    *,
    tpi_radii: Sequence[int] = (5, 15, 25),
    wbt_exe_path: Path | str | None = None,
    return_slope_raster: bool = False,
) -> np.ndarray | Tuple[np.ndarray, np.ndarray]:
    """Compute summary statistics for several WhiteboxTools-derived rasters.

    Currently computes: Aspect, Hillshade, Slope, TWI, TRI, TPI (multi-scale), SPI,
    Tangential Curvature, Accumulation Curvature, Topographic Openness,
    and Standard Deviation of Elevation.

    Note: Accumulation curvature and topographic openness may fail for some DEMs
    (e.g., very flat terrain, edge cases). In such cases, zero-filled statistics
    are used to maintain feature vector consistency.

    Args:
        dem_path: Path to DEM raster file
        tpi_radii: Radii for topographic position index computation
        wbt_exe_path: Path to whitebox_tools executable (optional)
        return_slope_raster: If True, return (stats, slope_raster) tuple. Slope raster
                           is read from WhiteboxTools output file before temp directory cleanup.
    
    Returns:
        If return_slope_raster=False: numpy.ndarray of summary statistics
        If return_slope_raster=True: tuple of (stats_array, slope_raster_array)
    """
```

**Memory Note:** A 256×256 float32 array is approximately 256 KB. Keeping the slope raster in memory for the TDA step is perfectly acceptable and avoids file I/O overhead.

**Implementation Checklist:**
- [ ] Verify that `compute_whitebox_stats()` reads the slope raster into a NumPy array before the temporary directory is cleaned up
- [ ] Ensure the returned slope raster has the same spatial dimensions as the input DEM
- [ ] Verify that the slope values are in degrees (not radians) for consistency with downstream processing

---

### C. Normalization Reminder

**The Issue:**
Feature arrays are concatenated from multiple sources:
- `multiscale_derivatives`: May have range [-1, 1] (if normalized) or raw values
- `persimages`: Typically has range [0, 1000] or higher (persistence image pixel values)

**The Solution:**
Raw feature arrays should be saved **without normalization** to preserve the original data distribution. Normalization (StandardScaler/Z-score) must occur **after loading** but **before** the classifier sees the data.

**Location in Code:** Model training notebook (e.g., `notebooks/final_project/quick_comparison.ipynb`)

**Implementation Checklist:**
- [ ] Verify that feature arrays are saved in raw form (no preprocessing)
- [ ] Ensure that `StandardScaler` or `RobustScaler` is applied during model training, not during feature computation
- [ ] Document the normalization strategy in the model training code

---

## Section 5: Superlevel Filtration Logic

### Mathematical Correctness

Superlevel filtrations capture **peaks** (local maxima) in the terrain. To compute superlevel persistence on a DEM, we negate the DEM:

$$\text{DEM}_{\text{negated}} = -1 \times \text{DEM}$$

This transformation converts:
- **Peaks** (high elevation) → **Basins** (low elevation in negated terrain)
- **Basins** (low elevation) → **Peaks** (high elevation in negated terrain)

Applying sublevel filtration to the negated DEM is mathematically equivalent to applying superlevel filtration to the original DEM.

### Why This Works

Persistent Homology with sublevel filtration captures the topology of the **sublevel sets**:
$$L_t = \{x \in \text{DEM} : \text{DEM}(x) \leq t\}$$

For the negated DEM:
$$L_t^{\text{neg}} = \{x \in \text{DEM} : -\text{DEM}(x) \leq t\} = \{x \in \text{DEM} : \text{DEM}(x) \geq -t\}$$

This is exactly the **superlevel set** of the original DEM at threshold $-t$.

### Physical Interpretation

- **Sublevel filtration on DEM:** Captures basins, depressions, sinkholes (features that "fill up" as the threshold increases)
- **Superlevel filtration on DEM (via negation):** Captures peaks, ridges, hilltops (features that "emerge" as the threshold decreases)

Both filtrations are necessary to capture the full topological structure of the terrain. The same logic applies to Slope:
- **Sublevel filtration on Slope:** Captures flat areas, gentle slopes (low slope values)
- **Superlevel filtration on Slope (via negation):** Captures steep areas, cliffs, escarpments (high slope values)

**Conclusion:** The negation approach (`dem_neg = -1 * dem`) is mathematically correct and computationally efficient. It is approved for use in the pipeline.

---

## Section 6: Feature Stack Architecture

### Final Feature Stack Structure

The pipeline creates the following feature stacks for model training:

**Tier 1: Baseline Features**
- `core_derivatives`: Single-scale WhiteboxTools features (Aspect, Slope, TWI, TRI, TPI, Tangential Curvature) - 30 dimensions
- `multiscale_derivatives`: Multi-scale WhiteboxTools features (all features at multiple TPI radii) - 70 dimensions
- `texture_composite`: GLCM texture + multiscale roughness + elevation entropy - 14 dimensions
- `betti`: Betti curves from TDA on DEM - 100 dimensions (50 samples × 2 homology dimensions)
- `landscapes`: Persistence landscapes from TDA on DEM - 1170 dimensions
- `persimages`: Persistence images from TDA on DEM - 5000 dimensions (50×50×2)

**Tier 2: Hypothesis Test Combinations**
- `multiscale_betti`: Multiscale derivatives + Betti curves - 170 dimensions
- `multiscale_landscapes`: Multiscale derivatives + Persistence landscapes - 1240 dimensions
- `multiscale_persimages`: Multiscale derivatives + Persistence images - 5070 dimensions
- `multiscale_texture_betti`: Multiscale + Texture + Betti - 184 dimensions
- `multiscale_texture_landscapes`: Multiscale + Texture + Landscapes - 1254 dimensions
- `multiscale_texture_persimages`: Multiscale + Texture + PersImages - 5084 dimensions

**Planned Addition (Post-Refactor):**
- `tda_slope_persimages`: TDA applied to Slope raster (not DEM) - 5000 dimensions
- `multiscale_tda_slope_persimages`: Multiscale derivatives + TDA(Slope) - 5070 dimensions

### Array Shape Verification

Before saving feature arrays, the pipeline must verify that all arrays have the same number of samples (rows):

```python
# Pseudo-code verification
assert feature_arrays['multiscale_derivatives'].shape[0] == feature_arrays['betti'].shape[0]
assert feature_arrays['multiscale_derivatives'].shape[0] == feature_arrays['persimages'].shape[0]
# ... repeat for all feature arrays
```

**Location in Code:** `notebooks/final_project/compute_features.ipynb`, before saving feature arrays (around line 1240)

### Concatenation Logic

Feature stacks are created by concatenating arrays along axis=1 (columns):

```python
# Example: multiscale_persimages
multiscale_persimages = np.concatenate([
    feature_arrays['multiscale_derivatives'],  # (n_samples, 70)
    feature_arrays['persimages']                # (n_samples, 5000)
], axis=1)  # Result: (n_samples, 5070)
```

**Implementation Checklist:**
- [ ] Verify that all feature arrays have the same number of samples (rows)
- [ ] Ensure concatenation occurs along axis=1 (columns)
- [ ] Verify that feature dimensions match expected values (e.g., persimages = 5000)
- [ ] Add shape assertions before saving to catch dimension mismatches early

---

## Section 7: Code References

### Key Functions and Locations

1. **`compute_whitebox_stats()`**: `src/karst_tda/features.py`, lines 351-664
   - Computes WhiteboxTools-derived terrain metrics
   - Returns summary statistics (mean, std, min, max, median) for each metric
   - Supports `return_slope_raster=True` to return slope raster array

2. **`extract_core_derivatives()`**: `src/karst_tda/features.py`, lines 183-211
   - Extracts core single-scale features from multiscale array
   - Uses named constants (`WBT_FEATURE_INDICES`) for safe indexing

3. **TDA Pipeline**: `notebooks/final_project/compute_features.ipynb`, lines ~1073-1120
   - Computes persistent homology on DEM tiles using `cripser.computePH()`
   - Vectorizes persistence diagrams into Betti curves, landscapes, and persistence images
   - Includes error handling for topological "explosions"

4. **Feature Stack Creation**: `scripts/reorganize_feature_stacks.py`
   - Combines baseline features into hypothesis test combinations
   - Creates multiscale + TDA composite features

### Implementation Checklist

- [ ] **Modify `compute_whitebox_stats`:** Ensure it extracts and returns the `slope` numpy array when `return_slope_raster=True`
- [ ] **Implement `extract_core`:** Verify that named constants (`WBT_FEATURE_INDICES`) are used for robust indexing
- [ ] **Add `negated_dem` logic:** Implement `dem_neg = -1 * dem` for superlevel filtration (if not already present)
- [ ] **Verify Array Shapes:** Before saving, add assertions to ensure all feature arrays have matching row dimensions
- [ ] **Document Normalization:** Ensure that normalization occurs during model training, not during feature computation

---

## Conclusion

This document provides rigorous justification for applying TDA exclusively to Slope, excluding Aspect, Texture, and TWI/Curvature. The decision is based on:

1. **Mathematical validity:** Aspect is circular data, making standard TDA invalid
2. **Physical interpretability:** Texture is already an abstraction; applying TDA would create an uninterpretable "summary of a summary"
3. **Scientific sufficiency:** If `TDA(Slope)` outperforms `Multiscale_Slope`, the hypothesis is proven without needing to test other metrics

The implementation includes safety considerations for hardcoded indices, slope raster handoff, and normalization strategy. The feature stack architecture supports direct comparison between `TDA(Slope)` and `Multiscale_Slope`, enabling rigorous hypothesis testing.

This design is **technically sound, highly efficient, and research-ready.** The architecture avoids redundant calculations, creates exactly the datasets needed for the paper, and provides a defensible scientific foundation for the research claims.

---

## Section 8: Post-Experiment Analysis - The Right Tool for the Wrong Job

It is completely normal to feel disappointed, but don't let the "hype" fool you—your result is a classic case of **"The Right Tool for the Wrong Job."**

TDA is not "snake oil," but it is highly specialized. The reason it is failing in your specific application (supervised classification of high-quality DEMs) highlights exactly where its true strengths lie.

Here is the breakdown of why TDA is hyped, why it failed here, and where it actually wins.

### 1. Why TDA Failed Here (The "Mismatch")

You are working with **Digital Elevation Models (DEMs)**, which are structured, high-quality grids.

* **The "Grid" Advantage:** Because your data is a perfect grid, you can calculate **Derivatives** (Slope, Curvature) instantly using neighboring pixels. These are mathematically precise descriptions of local shape. TDA is a "blunt instrument" compared to a derivative on a grid.

* **The "Invariance" Problem:** TDA is designed to be **deformation invariant**. If you stretch a rubber sheet, the topology (number of holes) stays the same, but the slope changes completely.

    * *In Geography:* **Geometry matters.** A steep slope is different from a shallow one. TDA sees them both as "connected components." It effectively "throws away" the metric information (steepness/rigidity) that is critical for classifying landforms.

* **Local vs. Global:** Your task (classifying a sinkhole or a ridge) is often defined by **local texture**. TDA is designed to capture **global connectivity**. You are using a telescope to read a book.

### 2. Where is TDA Actually Useful? (The "Hype" Use Cases)

TDA shines in scenarios where traditional methods (like derivatives or standard statistics) break down completely.

* **Messy Point Clouds (LiDAR):** If you don't have a grid, you can't calculate slope. TDA works natively on unstructured "clouds" of points, finding shape where no surface exists.

* **High-Dimensional "Noise":** In **Drug Discovery**, molecules are complex 3D shapes. TDA can fingerprint "binding pockets" (holes) in proteins regardless of how the molecule is rotated.

* **Cosmology:** Analyzing the "Cosmic Web" of galaxies. Derivatives mean nothing in empty space, but TDA can measure the "filament" structures of the universe.

* **Time-Series Analysis:** Detecting "loops" in stock market data or chaotic biological rhythms (like heart arrhythmias) where standard frequency analysis fails.

### 3. The "Unfair" Fight

In your study, you pitted TDA against **Texture (GLCM)** and **Derivatives**.

* **Derivatives** are the "native language" of physics (gravity, flow).

* **Texture** is the "native language" of statistical patterns.

* **Topology** is the "native language" of connectivity.

**The Verdict:** Your landscapes are defined more by **gravity and statistics** than by connectivity. A sinkhole is a "hole," yes, but it's also a specific *shape* of hole. TDA just says "there is a hole." Derivatives say "there is a hole with 45-degree walls and a flat bottom." The latter is more predictive.

### Summary: Your Result is Valid

You haven't shown that TDA is useless; you have shown that **High-Quality Geomorphometry is already solved by Derivatives.**

This is a valuable contribution. It tells future researchers: *"If you have a good DEM, don't waste compute on TDA. Use derivatives and texture."* That is a publishable, money-saving insight.

---

## References

- **Persistent Homology Theory:** Edelsbrunner & Harer (2010). *Computational Topology: An Introduction*. American Mathematical Society.
- **Circular Statistics:** Fisher (1993). *Statistical Analysis of Circular Data*. Cambridge University Press.
- **Geomorphometry:** Hengl & Reuter (2009). *Geomorphometry: Concepts, Software, Applications*. Elsevier.
- **TDA in Geomorphology:** See `docs/topological-fingerprinting-literature/` for comprehensive literature review.

---

*Document Version: 1.1*  
*Last Updated: 2025-01-XX*  
*Author: Research Team*

