# Implementation Timeline & Checklist
## GEOG 6591 Final Presentation - Michael Kerr

**Target Completion:** Before presentation date  
**Estimated Total Time:** 6-8 hours  
**Current Status:** 7.0/10 projected score  
**Target Score:** 9.5-10/10

---

## Day 1 (2-3 hours): Critical Fixes

### Morning Session (1.5 hours)

#### ✅ Task 1: Revise Title & Research Question (15 min)
- [ ] Change title from "Classifying Karst Terrain with Persistent Homology" to:
  - **Recommended:** "When TDA Works: Combining Topological and Traditional Features for Karst Classification"
- [ ] Update research question slide to reflect "enhancement" not "replacement"
- [ ] Add "spoiler" statement: "TDA can't replace—but combining gives best results"

**Files to modify:**
- `presentation.qmd`: Line 2 (title)
- Slide 3 (problem definition)

**Expected Impact:** +0.5 points (Problem Definition criterion)

---

#### ✅ Task 2: Simplify TDA Section (45 min)

**Current:** 4 slides with heavy math  
**Target:** 2 slides with visual intuition

**Action items:**
- [ ] **Slide 6 (New): TDA in One Sentence**
  - One sentence definition
  - One filtration animation
  - Remove: Betti numbers, simplicial complexes, math notation
  
- [ ] **Slide 7 (New): Why Three Filtrations?**
  - Side-by-side comparison: elevation, slope, superlevel
  - Caption: "Different filtrations capture different morphology"
  
- [ ] **Move to Backup Slides:**
  - Current Slides 9-10 (Simplicial complexes, Betti numbers)
  - Current Slide 11 (Geometric realizations)

**Files to modify:**
- `presentation.qmd`: Slides 9-12

**Expected Impact:** +0.75 points (Methodology criterion)

---

#### ✅ Task 3: Add "So What?" Content (30 min)

**Create new slide after current Slide 18:**

- [ ] Create translation table (see VISUALIZATION_GUIDE.md for template)
- [ ] Add real-world impact statements:
  - 66% accuracy → 10,000 tiles need review (out of 30k)
  - 10× speedup → 100 km² in 2 hrs vs 20 hrs
  - Cost savings → $1,800 per 100 km² @ $100/hr

**Files to modify:**
- `presentation.qmd`: Add new slide after results

**Expected Impact:** +0.5 points (Results/Evaluation criterion)

---

### Afternoon Session (1 hour)

#### ✅ Task 4: Create Study Area Context Map (30 min)

**What you need:**
1. Inset map: USA → Kentucky → Study area
2. Highlight Warren & Hardin Counties
3. Show Mammoth Cave National Park
4. Add coordinate grid

**Implementation:**
- [ ] Use code template from VISUALIZATION_GUIDE.md (Priority 1)
- [ ] Save as `study_area_context_map.png`
- [ ] Add to presentation: Replace current Slide 6

**Data sources:**
- Kentucky counties: KyGovMaps or Census TIGER
- Mammoth Cave boundary: NPS Data Store

**Expected Impact:** +0.25 points (Visual Presentation criterion)

---

#### ✅ Task 5: Create Performance Bar Charts (30 min)

**Replace tables with visualizations:**

- [ ] Top 5 methods bar chart (Spatial CV)
- [ ] Color code by category (Hybrid=green, Traditional=blue)
- [ ] Add error bars (standard deviation)
- [ ] Include TDA Alone for contrast (red bar)

**Implementation:**
- [ ] Use code template from VISUALIZATION_GUIDE.md (Priority 3)
- [ ] Save as `performance_bar_chart_spatial.png`
- [ ] Replace current Slides 15, 17

**Expected Impact:** +0.5 points (Visual Presentation criterion)

---

## Day 2 (2-3 hours): Important Enhancements

### Morning Session (1.5 hours)

#### ✅ Task 6: Create Sample Tile Grid (45 min)

**Create 2×2 grid showing:**
- Pure Qal (Alluvium) tile
- Pure Qr (Residuum) tile
- Multi-label tile (Qal + Qc)
- Hard case (model confusion)

**Implementation:**
- [ ] Identify representative tiles from dataset
- [ ] Use code template from VISUALIZATION_GUIDE.md (Priority 2)
- [ ] Save as `sample_tile_grid.png`
- [ ] Add to presentation: New slide after dataset overview (Slide 7)

**Expected Impact:** +0.25 points (Visual Presentation + Problem Definition)

---

#### ✅ Task 7: Create Spatial CV Comparison Visual (45 min)

**Side-by-side maps:**
- Left: Random CV (scattered tiles)
- Right: Spatial CV (regional blocks)
- Annotations showing performance drop

**Implementation:**
- [ ] Use code template from VISUALIZATION_GUIDE.md (Priority 4)
- [ ] Save as `cv_strategy_comparison.png`
- [ ] Replace current Slide 13

**Expected Impact:** +0.25 points (Methodology criterion)

---

### Afternoon Session (1 hour)

#### ✅ Task 8: Create Feature Importance Plot (45 min)

**Extract from trained model:**

- [ ] Load best model (multiscale_betti Random Forest)
- [ ] Extract `feature_importances_`
- [ ] Create horizontal bar chart (top 20 features)
- [ ] Color code by category (TDA, Traditional, Texture)

**Implementation:**
- [ ] Use code template from VISUALIZATION_GUIDE.md (Priority 5)
- [ ] Save as `feature_importance_plot.png`
- [ ] Add as new slide after "Why Hybrid Works" (after Slide 21)

**Expected Impact:** +0.25 points (Results/Evaluation criterion)

---

#### ✅ Task 9: Trim Presentation to 10 Minutes (15 min)

**Content audit:**

- [ ] Count slides: Target 15 slides max (currently 24)
- [ ] Move to backup:
  - Evidence tier hierarchy detail
  - Limitations section (mention briefly in conclusion)
  - Future directions (Q&A only)
- [ ] Practice timing: 30-45 seconds per slide

**Expected Impact:** +0.5 points (Delivery criterion)

---

## Day 3 (1-2 hours): Polish & Practice

### Morning Session (1 hour)

#### ✅ Task 10: Add Missing Context (30 min)

**Study area slide enhancements:**
- [ ] Add bullet points:
  - "1000+ sinkholes/km² in some areas"
  - "Type locality for covered karst"
  - "High-quality 1m LiDAR captures micro-topography"

**Problem definition enhancements:**
- [ ] Add impact statements:
  - "Karst aquifers provide 25% global drinking water"
  - "Sinkholes cause $300M+ annual US infrastructure damage"

**Files to modify:**
- `presentation.qmd`: Slides 2-3, 6

**Expected Impact:** +0.25 points (Problem Definition criterion)

---

#### ✅ Task 11: Final Visual Quality Check (30 min)

**For each figure:**
- [ ] Resolution: 300 DPI minimum
- [ ] Font sizes: ≥10pt, readable at distance
- [ ] Color contrast: Test with color blindness simulator
- [ ] File size: <2MB each
- [ ] Consistency: Same color scheme across all figures

**Tools:**
- [Color Oracle](https://colororacle.org/) for color blindness testing
- ImageOptim or similar for compression

**Expected Impact:** +0.25 points (Visual Presentation criterion)

---

### Afternoon Session (1 hour)

#### ✅ Task 12: Practice Presentation (1 hour)

**Rehearsal checklist:**
- [ ] Time yourself: Target 9-10 minutes
- [ ] Record yourself (video or audio)
- [ ] Identify weak transitions
- [ ] Note where you hesitate or over-explain
- [ ] Practice Q&A responses

**Key transitions to practice:**
- "Now that we've seen the problem..." → Study area
- "Before showing results, I need to explain TDA..." → TDA section
- "Here's the key finding..." → Results summary
- "Why does this work?" → Interpretation

**Expected Impact:** +0.5 points (Delivery criterion)

---

## Optional Enhancements (If Time Permits)

### Nice-to-Have Visualizations

#### ⭐ Computational Cost Scatter Plot (45 min)
- F1 vs Time per tile
- Pareto frontier highlighted
- See VISUALIZATION_GUIDE.md Priority 6

#### ⭐ Per-Class Performance Analysis (30 min)
- Bar chart: F1 by class
- Scatter: F1 vs prevalence
- See VISUALIZATION_GUIDE.md Priority 8

#### ⭐ Error Map (1 hour)
- Spatial distribution of errors
- Color-coded accuracy
- Requires spatial join with tile locations

---

## Pre-Presentation Checklist (30 min before)

### Technical Setup
- [ ] Test presentation on actual hardware
- [ ] Check projector resolution and colors
- [ ] Have backup USB drive with presentation
- [ ] Test clicker/remote (if using)
- [ ] Load backup slides (in case of questions)

### Content Final Check
- [ ] All figures rendering correctly
- [ ] No placeholder text remaining
- [ ] Citations complete (if required)
- [ ] Title slide has correct date

### Personal Preparation
- [ ] Review key findings one more time
- [ ] Rehearse opening and closing
- [ ] Prepare for likely questions:
  - "Why didn't TDA alone work?"
  - "How would this scale to other regions?"
  - "What about deep learning?"
  - "Can you explain persistent homology more?"

---

## Quick Reference: Files to Modify

### Primary Files
```
presentation.qmd                     # Main presentation file
├── Slides 2-3    → Problem definition (add context)
├── Slides 6-7    → Study area (add map)
├── Slides 9-12   → TDA section (simplify)
├── Slide 13      → CV strategy (add visual)
├── Slides 15,17  → Results (replace with charts)
└── New slide     → "So what?" translation

presentation_visuals.ipynb           # Generate figures
├── Add: study_area_context_map
├── Add: sample_tile_grid
├── Add: performance_bar_chart
├── Add: cv_strategy_comparison
└── Add: feature_importance_plot
```

### Images Directory
```
docs/presentation/images/
├── study_area_context_map.png           [NEW]
├── sample_tile_grid.png                 [NEW]
├── performance_bar_chart_spatial.png    [NEW]
├── cv_strategy_comparison.png           [NEW]
├── feature_importance_plot.png          [NEW]
└── (existing images remain)
```

---

## Progress Tracking

### Completion Status

| Task | Priority | Est. Time | Status | Impact |
|------|----------|-----------|--------|--------|
| 1. Revise title/RQ | 🔴 Critical | 15 min | ⬜ | +0.5 pts |
| 2. Simplify TDA | 🔴 Critical | 45 min | ⬜ | +0.75 pts |
| 3. Add "so what?" | 🔴 Critical | 30 min | ⬜ | +0.5 pts |
| 4. Study area map | 🔴 Critical | 30 min | ⬜ | +0.25 pts |
| 5. Performance charts | 🔴 Critical | 30 min | ⬜ | +0.5 pts |
| 6. Sample tile grid | 🟡 Important | 45 min | ⬜ | +0.25 pts |
| 7. CV comparison | 🟡 Important | 45 min | ⬜ | +0.25 pts |
| 8. Feature importance | 🟡 Important | 45 min | ⬜ | +0.25 pts |
| 9. Trim to 10 min | 🟡 Important | 15 min | ⬜ | +0.5 pts |
| 10. Add context | 🟢 Polish | 30 min | ⬜ | +0.25 pts |
| 11. Quality check | 🟢 Polish | 30 min | ⬜ | +0.25 pts |
| 12. Practice | 🟢 Polish | 60 min | ⬜ | +0.5 pts |
| **TOTAL** | | **6-8 hrs** | 0/12 | **+5.0 pts** |

**Current trajectory:** 7.0/10  
**After critical tasks:** 9.0/10  
**After all tasks:** 10.0/10 (with practice)

---

## Emergency Triage (If Time-Constrained)

### If you only have 2 hours:
1. ✅ Revise title/RQ (15 min)
2. ✅ Simplify TDA (45 min)
3. ✅ Add "so what?" (30 min)
4. ✅ Performance charts (30 min)

**Expected score:** 8.0/10

### If you only have 4 hours:
Add to above:
5. ✅ Study area map (30 min)
6. ✅ Sample tile grid (45 min)
7. ✅ Trim to 10 min (15 min)
8. ✅ Practice (1 hour)

**Expected score:** 9.0/10

### If you have full 8 hours:
Complete all tasks in order.

**Expected score:** 10.0/10

---

## Post-Presentation (For Future Reference)

### What Went Well
- [ ] Note questions that were asked
- [ ] Identify which slides resonated
- [ ] Record any "aha!" moments from audience

### What to Improve
- [ ] Which slides took too long?
- [ ] Where did you stumble?
- [ ] What questions were you unprepared for?

### For Written Report
- [ ] Expand on verbal explanations that worked well
- [ ] Address questions that came up in Q&A
- [ ] Add visualizations that audience requested

---

## Support Resources

### Documentation
- **CRITICAL_REVIEW.md**: Full rubric analysis
- **VISUALIZATION_GUIDE.md**: Code templates for all figures
- **final_project_summary.qmd**: Statistical analysis reference
- **PresentationCriterion.md**: Official rubric

### Code Resources
- `presentation_visuals.ipynb`: Base code for figure generation
- `src/karst_tda/features.py`: Feature extraction reference
- `notebooks/final_project/quick_comparison.ipynb`: Model training

### External Resources
- ColorBrewer: https://colorbrewer2.org/ (color palettes)
- Color Oracle: https://colororacle.org/ (color blindness simulator)
- KyGovMaps: https://kygeonet.ky.gov/ (Kentucky GIS data)
- NPS Data Store: https://irma.nps.gov/ (Mammoth Cave boundary)

---

## Motivation & Perspective

### Remember
You have **exceptional statistical rigor** (3 ultra-robust methods with p < 0.0002). Most ML papers can't make claims this strong. The content is publication-ready.

### The Only Issues
1. **Framing**: Title doesn't match findings (easy fix)
2. **Pedagogy**: TDA explanation too technical for geography audience (30 min fix)
3. **Translation**: Results need "so what?" context (30 min fix)
4. **Visuals**: Tables instead of charts, missing context (2 hours fix)
5. **Time**: 24 slides won't fit in 10 minutes (15 min triage)

### Total Fix Time
6-8 hours of focused work transforms a 7/10 presentation into 10/10.

### Your Competitive Advantage
Most students will present:
- Generic ML results
- No spatial validation
- No statistical rigor
- No geographic insight

You have:
- ✅ Spatial CV (honest performance)
- ✅ Bonferroni correction (ultra-conservative)
- ✅ Evidence hierarchy (nuanced)
- ✅ Geographic context (karst morphology)

**You're 90% there. Just need polish.**

---

## Questions? Stuck?

### If code doesn't work:
1. Check Python environment (packages installed?)
2. Verify file paths (absolute vs relative)
3. Check data availability (do you have shapefiles?)
4. Ask for help (TA, classmates, office hours)

### If time is running short:
1. Focus on critical tasks first (Tasks 1-5)
2. Use simpler visuals (stock photos, sketches, screenshots)
3. Practice verbal explanations to compensate for missing visuals

### If presentation is tomorrow:
1. Emergency triage mode (2-hour version above)
2. Focus on content clarity, not visual perfection
3. Prepare good answers for predictable questions
4. Confidence and clarity > perfect slides

---

**You've got this. Your research is solid. Now make the presentation match the quality of your work.**

*Generated: December 4, 2024*  
*Last Updated: [Update after each work session]*  
*Next Review: After Day 1 tasks complete*
