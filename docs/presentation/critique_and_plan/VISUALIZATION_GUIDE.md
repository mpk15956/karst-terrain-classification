# Missing Visualizations: Implementation Guide
## GEOG 6591 Final Presentation

This document provides specific guidance and code templates for creating the missing critical visualizations identified in the presentation review.

---

## Priority 1: Study Area Context Map

### What You Need
An inset map showing:
1. Kentucky state outline
2. Mammoth Cave National Park location
3. Warren & Hardin Counties highlighted
4. Study area extent with coordinate grid

### Why It Matters
- Provides geographic context for non-local audience
- Shows the spatial scale of your analysis
- Demonstrates you understand regional geography

### Implementation (Python + Matplotlib)

```python
import matplotlib.pyplot as plt
import geopandas as gpd
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

fig, ax = plt.subplots(figsize=(12, 8))

# Main map: Kentucky with counties
kentucky = gpd.read_file('path/to/kentucky_counties.shp')
kentucky.plot(ax=ax, color='lightgray', edgecolor='black', linewidth=0.5)

# Highlight Warren & Hardin counties
study_counties = kentucky[kentucky['NAME'].isin(['Warren', 'Hardin'])]
study_counties.plot(ax=ax, color='#2E7D32', alpha=0.5, edgecolor='black', linewidth=1.5)

# Add Mammoth Cave National Park boundary
park = gpd.read_file('path/to/mammoth_cave_boundary.shp')
park.plot(ax=ax, color='none', edgecolor='red', linewidth=2, linestyle='--')

# Add study area bounding box
study_bbox = Rectangle((min_x, min_y), width, height, 
                       fill=False, edgecolor='blue', linewidth=2)
ax.add_patch(study_bbox)

# Labels
ax.text(warren_x, warren_y, 'Warren\nCounty', fontsize=10, ha='center')
ax.text(hardin_x, hardin_y, 'Hardin\nCounty', fontsize=10, ha='center')
ax.text(park_x, park_y, 'Mammoth Cave\nNational Park', 
        fontsize=9, ha='center', color='red')

# Inset map: USA with Kentucky highlighted
inset_ax = inset_axes(ax, width="25%", height="25%", loc='upper right')
usa = gpd.read_file('path/to/usa_states.shp')
usa.plot(ax=inset_ax, color='lightgray', edgecolor='black', linewidth=0.3)
usa[usa['NAME'] == 'Kentucky'].plot(ax=inset_ax, color='#2E7D32')
inset_ax.axis('off')

# Styling
ax.set_xlabel('Longitude', fontsize=12)
ax.set_ylabel('Latitude', fontsize=12)
ax.set_title('Study Area: Karst Terrain in South-Central Kentucky', 
             fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('study_area_context_map.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Data Sources
- Kentucky counties: [KyGovMaps](https://kygeonet.ky.gov/)
- Mammoth Cave boundary: [NPS Data Store](https://irma.nps.gov/DataStore/)
- If shapefiles unavailable, use web services:
  ```python
  import contextily as ctx
  # Add basemap
  ctx.add_basemap(ax, crs=study_counties.crs.to_string(), 
                  source=ctx.providers.Stamen.Terrain)
  ```

---

## Priority 2: Sample Tile Grid (4 Examples)

### What You Need
A 2×2 grid showing:
- Top-left: Clean Qal (Alluvium) tile
- Top-right: Clean Qr (Residuum) tile  
- Bottom-left: Multi-label tile (Qal + Qc)
- Bottom-right: "Hard case" that models struggled with

### Why It Matters
- Makes abstract labels concrete
- Shows visual differences between classes
- Demonstrates understanding of geomorphology

### Implementation

```python
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# Load sample tiles (you need to identify these from your dataset)
sample_tiles = {
    'Qal_pure': 'path/to/alluvium_tile.tif',
    'Qr_pure': 'path/to/residuum_tile.tif',
    'Multi_label': 'path/to/multi_label_tile.tif',
    'Hard_case': 'path/to/confused_tile.tif'
}

fig, axes = plt.subplots(2, 2, figsize=(12, 12))
axes = axes.flatten()

titles = [
    'Qal (Alluvium)\nFlat valley, recent deposition',
    'Qr (Residuum)\nWeathered bedrock, gentle slopes',
    'Multi-label (Qal + Qc)\nValley with colluvial fans',
    'Hard Case\nModel Confusion: Qr vs Qc'
]

for idx, (label, path) in enumerate(sample_tiles.items()):
    with rasterio.open(path) as src:
        dem = src.read(1)
        
    # Create hillshade for visualization
    from matplotlib.colors import LightSource
    ls = LightSource(azdeg=315, altdeg=45)
    hillshade = ls.hillshade(dem, vert_exag=2, dx=1, dy=1)
    
    # Plot
    im = axes[idx].imshow(hillshade, cmap='gray', vmin=0, vmax=1)
    axes[idx].imshow(dem, cmap='terrain', alpha=0.4)
    
    axes[idx].set_title(titles[idx], fontsize=12, fontweight='bold')
    axes[idx].axis('off')
    
    # Add elevation colorbar
    cbar = plt.colorbar(im, ax=axes[idx], fraction=0.046, pad=0.04)
    cbar.set_label('Elevation (m)', rotation=270, labelpad=15)

plt.suptitle('Example DEM Tiles by Surficial Geology Class', 
             fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('sample_tile_grid.png', dpi=300, bbox_inches='tight')
plt.show()
```

### How to Select Tiles
```python
# Find representative tiles from your dataset
import pandas as pd

# Assuming you have tile metadata
metadata = pd.read_csv('tile_metadata.csv')

# Pure Qal (single class, high confidence)
qal_tiles = metadata[(metadata['Qal'] == 1) & 
                     (metadata['n_classes'] == 1) &
                     (metadata['prediction_confidence'] > 0.9)]
qal_sample = qal_tiles.sample(1).iloc[0]['tile_path']

# Pure Qr (single class, high confidence)
qr_tiles = metadata[(metadata['Qr'] == 1) & 
                    (metadata['n_classes'] == 1) &
                    (metadata['prediction_confidence'] > 0.9)]
qr_sample = qr_tiles.sample(1).iloc[0]['tile_path']

# Multi-label (Qal + Qc)
multi_tiles = metadata[(metadata['Qal'] == 1) & 
                       (metadata['Qc'] == 1) &
                       (metadata['n_classes'] == 2)]
multi_sample = multi_tiles.sample(1).iloc[0]['tile_path']

# Hard case (low confidence, frequently misclassified)
hard_tiles = metadata[(metadata['prediction_confidence'] < 0.5) |
                      (metadata['cross_val_std'] > 0.3)]
hard_sample = hard_tiles.sample(1).iloc[0]['tile_path']
```

---

## Priority 3: Performance Bar Chart (Replace Tables)

### What You Need
Clean bar chart showing:
- Top 5 methods only
- F1-macro scores for Spatial CV
- Error bars (standard deviation)
- Clear ranking

### Why It Matters
- Tables are unreadable in presentations
- Bar charts show ranking at a glance
- Audience can focus on key comparisons

### Implementation

```python
import matplotlib.pyplot as plt
import numpy as np

# Data from your results (Spatial CV)
methods = [
    'Hybrid\n(Multi+Betti)',
    'Traditional\n(Multi-scale)',
    'Hybrid\n(Multi+Texture+Betti)',
    'Hybrid\n(Multi+Betti Slope)',
    'Traditional\n(Multi+Texture)'
]

f1_scores = [0.663, 0.659, 0.662, 0.660, 0.658]
f1_stds = [0.149, 0.148, 0.138, 0.152, 0.127]

# Color by category
colors = ['#2E7D32', '#1976D2', '#2E7D32', '#2E7D32', '#1976D2']
# Green for Hybrid with TDA, Blue for Traditional

fig, ax = plt.subplots(figsize=(10, 6))

x = np.arange(len(methods))
bars = ax.bar(x, f1_scores, yerr=f1_stds, 
              color=colors, alpha=0.7, capsize=5,
              edgecolor='black', linewidth=1.5)

# Add value labels on bars
for i, (score, std) in enumerate(zip(f1_scores, f1_stds)):
    ax.text(i, score + std + 0.01, f'{score:.3f}', 
            ha='center', va='bottom', fontsize=10, fontweight='bold')

# Styling
ax.set_ylabel('F1-Macro Score', fontsize=12, fontweight='bold')
ax.set_xlabel('Method', fontsize=12, fontweight='bold')
ax.set_title('Top 5 Methods: Spatial Cross-Validation Performance', 
             fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(methods, fontsize=10)
ax.set_ylim(0, 0.9)
ax.axhline(y=0.659, color='gray', linestyle='--', linewidth=1, 
           label='Baseline (Multi-scale)')
ax.grid(axis='y', alpha=0.3)
ax.legend()

plt.tight_layout()
plt.savefig('performance_bar_chart_spatial.png', dpi=300, bbox_inches='tight')
plt.show()
```

### Variation: Add TDA Alone for Contrast

```python
# Extended comparison including failures
methods_extended = methods + ['TDA Alone\n(Betti)', 'Deep Learning\n(ResNet-50)']
f1_extended = f1_scores + [0.561, 0.647]
f1_stds_extended = f1_stds + [0.118, 0.192]
colors_extended = colors + ['#D32F2F', '#FF6F00']  # Red for failures, Orange for DL

# Same plotting code but with extended data
```

---

## Priority 4: Spatial CV Comparison Visual

### What You Need
Side-by-side maps showing:
- Left: Random CV (tiles scattered)
- Right: Spatial CV (regions held out)
- Annotation showing performance drop

### Why It Matters
- Explains why spatial CV is harder
- Shows spatial autocorrelation visually
- Justifies your methodology choice

### Implementation

```python
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Create mock study area grid (replace with actual coordinates)
n_regions = 8
region_colors = plt.cm.tab10(np.arange(n_regions))

# Random CV: scatter tiles randomly
np.random.seed(42)
random_fold_assignment = np.random.randint(0, 5, size=100)
random_colors = plt.cm.Set3(random_fold_assignment)

# Spatial CV: group by region
spatial_regions = np.repeat(np.arange(8), 12)  # 8 regions, ~12 tiles each
np.random.shuffle(spatial_regions[:60])  # Mix some, but keep clusters
spatial_fold_assignment = spatial_regions % 5
spatial_colors = plt.cm.Set3(spatial_fold_assignment)

# Plot random CV
ax1.scatter(np.random.rand(100), np.random.rand(100), 
           c=random_colors, s=50, alpha=0.7, edgecolors='black', linewidth=0.5)
ax1.set_title('Random Cross-Validation\nF1 = 0.731 ± 0.008', 
             fontsize=12, fontweight='bold')
ax1.set_xlabel('Easting', fontsize=10)
ax1.set_ylabel('Northing', fontsize=10)
ax1.text(0.5, 0.95, '❌ Spatial leakage\nTraining & test tiles intermixed', 
         transform=ax1.transAxes, ha='center', va='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# Plot spatial CV (create clear regions)
region_x = [0, 0.33, 0.66, 0, 0.33, 0.66, 0, 0.33]
region_y = [0, 0, 0, 0.33, 0.33, 0.33, 0.66, 0.66]

for i in range(8):
    fold = i % 5
    color = plt.cm.Set3(fold)
    rect = Rectangle((region_x[i], region_y[i]), 0.3, 0.3, 
                     facecolor=color, edgecolor='black', linewidth=2, alpha=0.7)
    ax2.add_patch(rect)
    ax2.text(region_x[i] + 0.15, region_y[i] + 0.15, f'R{i+1}\nF{fold+1}',
            ha='center', va='center', fontsize=9, fontweight='bold')

ax2.set_xlim(-0.05, 1.05)
ax2.set_ylim(-0.05, 1.05)
ax2.set_title('Spatial Cross-Validation\nF1 = 0.663 ± 0.149', 
             fontsize=12, fontweight='bold')
ax2.set_xlabel('Easting', fontsize=10)
ax2.set_ylabel('Northing', fontsize=10)
ax2.text(0.5, 0.95, '✅ Geographic separation\nEntire regions held out', 
         transform=ax2.transAxes, ha='center', va='top',
         bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

# Add legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=plt.cm.Set3(i), label=f'Fold {i+1}') 
                   for i in range(5)]
fig.legend(handles=legend_elements, loc='upper center', ncol=5, 
          bbox_to_anchor=(0.5, -0.05), frameon=False)

plt.suptitle('Cross-Validation Strategy Comparison', 
            fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('cv_strategy_comparison.png', dpi=300, bbox_inches='tight')
plt.show()
```

---

## Priority 5: Feature Importance Plot

### What You Need
Bar chart showing:
- Top 15-20 most important features
- From your best model (Random Forest)
- Categorized by feature type (Traditional, TDA, Texture)

### Why It Matters
- Shows model interpretability
- Reveals what geomorphic patterns matter
- Answers "what did the model learn?"

### Implementation

```python
import pandas as pd
import matplotlib.pyplot as plt

# Extract from trained Random Forest
# Assuming you have: model, feature_names
importances = model.feature_importances_
indices = np.argsort(importances)[-20:]  # Top 20

# Create dataframe
feature_importance_df = pd.DataFrame({
    'feature': [feature_names[i] for i in indices],
    'importance': importances[indices]
})

# Categorize features
def categorize_feature(name):
    if 'betti' in name.lower() or 'persistence' in name.lower():
        return 'TDA'
    elif 'texture' in name.lower() or 'glcm' in name.lower():
        return 'Texture'
    elif 'slope' in name.lower() or 'curvature' in name.lower() or 'tpi' in name.lower():
        return 'Traditional'
    else:
        return 'Other'

feature_importance_df['category'] = feature_importance_df['feature'].apply(categorize_feature)

# Plot
fig, ax = plt.subplots(figsize=(10, 8))

colors = {'TDA': '#2E7D32', 'Traditional': '#1976D2', 'Texture': '#F57C00', 'Other': 'gray'}
bar_colors = [colors[cat] for cat in feature_importance_df['category']]

ax.barh(range(len(feature_importance_df)), feature_importance_df['importance'],
        color=bar_colors, alpha=0.7, edgecolor='black', linewidth=0.5)

ax.set_yticks(range(len(feature_importance_df)))
ax.set_yticklabels(feature_importance_df['feature'], fontsize=9)
ax.set_xlabel('Feature Importance (Gini Impurity Reduction)', fontsize=11, fontweight='bold')
ax.set_title('Top 20 Most Important Features\n(Hybrid Model: Multi-scale + Betti)', 
            fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)

# Add legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=colors[cat], label=cat) 
                   for cat in ['TDA', 'Traditional', 'Texture']]
ax.legend(handles=legend_elements, loc='lower right')

plt.tight_layout()
plt.savefig('feature_importance_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

---

## Priority 6: Computational Cost Scatter Plot

### What You Need
2D scatter plot showing:
- X-axis: Time per tile (seconds)
- Y-axis: F1-macro score (Spatial CV)
- Points labeled by method
- Pareto frontier highlighted

### Why It Matters
- Shows efficiency vs accuracy trade-off
- Identifies "sweet spot" methods
- Practical guidance for method selection

### Implementation

```python
import matplotlib.pyplot as plt
import numpy as np

# Data from your timing results + performance results
methods_data = [
    {'name': 'Traditional\n(Multi-scale)', 'time': 0.981, 'f1': 0.659, 'category': 'Traditional'},
    {'name': 'TDA\n(Betti)', 'time': 0.071, 'f1': 0.561, 'category': 'TDA'},
    {'name': 'Hybrid\n(Multi+Betti)', 'time': 0.527, 'f1': 0.663, 'category': 'Hybrid'},
    {'name': 'Deep Learning\n(ResNet)', 'time': 0.102, 'f1': 0.647, 'category': 'AI'},
    {'name': 'Texture', 'time': 0.204, 'f1': 0.640, 'category': 'Traditional'},
    # Add more methods...
]

# Convert to arrays
times = [d['time'] for d in methods_data]
f1s = [d['f1'] for d in methods_data]
names = [d['name'] for d in methods_data]
categories = [d['category'] for d in methods_data]

# Color mapping
color_map = {'Traditional': '#1976D2', 'TDA': '#D32F2F', 
             'Hybrid': '#2E7D32', 'AI': '#FF6F00'}
colors = [color_map[cat] for cat in categories]

# Plot
fig, ax = plt.subplots(figsize=(12, 8))

scatter = ax.scatter(times, f1s, c=colors, s=200, alpha=0.7, 
                    edgecolors='black', linewidth=1.5)

# Label points
for i, name in enumerate(names):
    ax.annotate(name, (times[i], f1s[i]), 
               xytext=(10, 5), textcoords='offset points',
               fontsize=9, ha='left')

# Pareto frontier (methods that are not dominated)
pareto_indices = []
for i in range(len(times)):
    dominated = False
    for j in range(len(times)):
        if i != j:
            # Method j dominates i if: faster AND more accurate
            if times[j] <= times[i] and f1s[j] >= f1s[i] and (times[j] < times[i] or f1s[j] > f1s[i]):
                dominated = True
                break
    if not dominated:
        pareto_indices.append(i)

# Draw Pareto frontier
pareto_times = [times[i] for i in sorted(pareto_indices, key=lambda x: times[x])]
pareto_f1s = [f1s[i] for i in sorted(pareto_indices, key=lambda x: times[x])]
ax.plot(pareto_times, pareto_f1s, 'k--', linewidth=2, alpha=0.5, label='Pareto Frontier')

# Styling
ax.set_xlabel('Computation Time per Tile (seconds)', fontsize=12, fontweight='bold')
ax.set_ylabel('F1-Macro Score (Spatial CV)', fontsize=12, fontweight='bold')
ax.set_title('Performance vs Computational Cost Trade-off', fontsize=14, fontweight='bold')
ax.set_xscale('log')  # Log scale for time
ax.grid(True, alpha=0.3)

# Add legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=color_map[cat], label=cat) 
                   for cat in color_map.keys()]
legend_elements.append(plt.Line2D([0], [0], color='black', linestyle='--', 
                                 linewidth=2, label='Pareto Frontier'))
ax.legend(handles=legend_elements, loc='lower right')

# Annotate "sweet spot"
best_hybrid_idx = [i for i, cat in enumerate(categories) if cat == 'Hybrid'][0]
ax.annotate('Sweet Spot:\nBest F1 at\n2× speedup', 
           xy=(times[best_hybrid_idx], f1s[best_hybrid_idx]),
           xytext=(times[best_hybrid_idx]*2, f1s[best_hybrid_idx]-0.05),
           arrowprops=dict(arrowstyle='->', lw=2, color='green'),
           fontsize=11, fontweight='bold', color='green',
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

plt.tight_layout()
plt.savefig('performance_vs_cost_scatter.png', dpi=300, bbox_inches='tight')
plt.show()
```

---

## Priority 7: "So What?" Impact Translation Slide

### What You Need
Table or infographic showing:
- Metric values translated to real-world meaning
- Computational savings translated to practical impact
- Accuracy translated to operational use cases

### Implementation (Design in PowerPoint/Keynote)

**Slide Content:**

```
┌─────────────────────────────────────────────────────────────────┐
│          What These Numbers Mean in Practice                    │
├─────────────────┬───────────┬─────────────────────────────────────┤
│ Metric          │ Value     │ Real-World Translation             │
├─────────────────┼───────────┼─────────────────────────────────────┤
│ F1 = 0.663      │ Best      │ • 66% of 30k tiles classified      │
│ (Hybrid)        │ Hybrid    │   correctly (all 7 classes)        │
│                 │           │ • ~10,000 tiles need expert review │
├─────────────────┼───────────┼─────────────────────────────────────┤
│ F1 = 0.561      │ TDA       │ • 56% accuracy—WORSE than baseline │
│ (TDA Alone)     │ Alone     │ • 13,500 errors = unacceptable     │
│                 │           │   for operational use              │
├─────────────────┼───────────┼─────────────────────────────────────┤
│ Δ = 0.10 F1     │ Improve-  │ • ~3,000 fewer errors compared to  │
│ (vs TDA alone)  │ ment      │   TDA alone                        │
│                 │           │ • Reduces manual review by 30%     │
├─────────────────┼───────────┼─────────────────────────────────────┤
│ 10× speedup     │ TDA vs    │ • 100 km² mapped in 2 hours        │
│                 │ Tradition │   instead of 20 hours              │
│                 │           │ • $1,800 labor cost savings per    │
│                 │           │   100 km² @ $100/hr analyst rate   │
└─────────────────┴───────────┴─────────────────────────────────────┘

KEY TAKEAWAY:
Hybrid approach achieves professional-grade accuracy (66%) with 2× speedup
→ Viable for first-pass automated mapping requiring expert review
  only for ambiguous cases (34% of tiles)
```

### Alternative: Infographic Style

Create visual showing:
- 100 tile icons
- 66 colored green (correct classification)
- 34 colored yellow (needs review)
- Clock icon showing "2 hrs" vs "20 hrs"
- Dollar sign showing "$1,800 saved per 100 km²"

---

## Priority 8: Error Analysis / Confusion Elements

### What You Need
One of:
1. Confusion matrix (simplified)
2. Per-class F1 scores
3. Examples of misclassifications

### Why It Matters
- Shows you understand model limitations
- Demonstrates geographic insight
- Provides honest assessment

### Implementation: Per-Class F1 Scores

```python
import matplotlib.pyplot as plt
import numpy as np

# Per-class F1 scores from your multilabel classifier
classes = ['Qal', 'Qr', 'Qls', 'Qc', 'Qe', 'Qp', 'Qm']
f1_scores = [0.78, 0.69, 0.54, 0.71, 0.42, 0.38, 0.65]  # Example values
prevalence = [0.35, 0.28, 0.08, 0.22, 0.03, 0.02, 0.12]  # Class prevalence

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: F1 by class
colors = ['#2E7D32' if f1 > 0.65 else '#FF6F00' if f1 > 0.5 else '#D32F2F' 
          for f1 in f1_scores]
ax1.barh(classes, f1_scores, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
ax1.axvline(x=0.65, color='gray', linestyle='--', linewidth=1, label='Target (0.65)')
ax1.set_xlabel('F1 Score', fontsize=11, fontweight='bold')
ax1.set_title('Per-Class Performance', fontsize=13, fontweight='bold')
ax1.set_xlim(0, 1)
ax1.legend()
ax1.grid(axis='x', alpha=0.3)

# Plot 2: F1 vs Prevalence (scatter)
ax2.scatter(prevalence, f1_scores, s=200, alpha=0.7, edgecolors='black', linewidth=1.5)
for i, cls in enumerate(classes):
    ax2.annotate(cls, (prevalence[i], f1_scores[i]), 
                xytext=(5, 5), textcoords='offset points', fontsize=10)
ax2.set_xlabel('Class Prevalence (% of tiles)', fontsize=11, fontweight='bold')
ax2.set_ylabel('F1 Score', fontsize=11, fontweight='bold')
ax2.set_title('Performance vs Class Frequency', fontsize=13, fontweight='bold')
ax2.grid(alpha=0.3)

# Add annotation
ax2.text(0.02, 0.42, 'Rare classes\n(Qe, Qp)\nunderperform', 
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
        fontsize=10)

plt.tight_layout()
plt.savefig('per_class_performance.png', dpi=300, bbox_inches='tight')
plt.show()
```

---

## Testing & Validation Checklist

Before finalizing any visualization:

- [ ] **Resolution check**: All images saved at 300 DPI
- [ ] **Font sizes**: Readable at presentation scale (min 10pt)
- [ ] **Color blindness**: Use [ColorBrewer](https://colorbrewer2.org/) safe palettes
- [ ] **Contrast**: Check readability on projector (white background preferred)
- [ ] **File format**: PNG for presentations (not PDF, to avoid scaling issues)
- [ ] **Aspect ratio**: Match presentation dimensions (16:9 or 4:3)
- [ ] **File size**: Keep under 2MB each (compress if needed)

---

## Quick References

### Color Palettes (Consistent Across All Figures)

```python
# Category colors
CATEGORY_COLORS = {
    'Traditional': '#1976D2',  # Blue
    'TDA': '#D32F2F',          # Red  
    'Hybrid': '#2E7D32',        # Green
    'AI': '#FF6F00',            # Orange
}

# Performance tiers
PERFORMANCE_COLORS = {
    'excellent': '#2E7D32',     # Green (F1 > 0.70)
    'good': '#1976D2',          # Blue (0.60 < F1 ≤ 0.70)
    'acceptable': '#FF6F00',    # Orange (0.50 < F1 ≤ 0.60)
    'poor': '#D32F2F',          # Red (F1 ≤ 0.50)
}
```

### Standard Figure Sizes

```python
# For full-slide images
FULL_SLIDE = (12, 6.75)  # 16:9 aspect ratio

# For half-slide images
HALF_SLIDE = (6, 6)      # Square

# For small insets
INSET = (4, 3)           # 4:3 aspect ratio
```

---

## Troubleshooting Common Issues

### Issue: Figures look blurry in presentation
**Solution:** 
```python
plt.savefig('figure.png', dpi=300, bbox_inches='tight')
# NOT: dpi=72 (screen resolution)
```

### Issue: Text too small to read
**Solution:**
```python
plt.rcParams['font.size'] = 12        # Base size
plt.rcParams['axes.titlesize'] = 14   # Title
plt.rcParams['axes.labelsize'] = 12   # Axis labels
plt.rcParams['legend.fontsize'] = 10  # Legend
```

### Issue: Colors look different on projector
**Solution:** Test on actual presentation hardware, or use high-contrast safe palettes

### Issue: File size too large (>5MB)
**Solution:**
```python
from PIL import Image

img = Image.open('figure.png')
img.save('figure_compressed.png', optimize=True, quality=85)
```

---

*Generated: December 4, 2024*  
*For: GEOG 6591 Final Presentation*  
*Next: Implement Priority 1-3 first, then reassess*
