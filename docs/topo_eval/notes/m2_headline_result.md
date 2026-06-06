---
title: "M2 headline: MESA-generated drainage topology is distributionally distinguishable from real terrain"
date: 2026-06-06
tags: [m2, headline, mmd, mesa, distributional-gate, contribution-1, saddle]
type: result-note
---

The contribution-1 measurement: at matched drainage density, the population of
H0 flow-accumulation persistence diagrams from MESA-generated terrain is
distributionally distinguishable from real terrain, by a sliced-Wasserstein-
kernel MMD tested against a spatial (by-tile) real-vs-real null. Run only after
every precondition cleared. Artifacts: the result JSON and log under
`results/validity/m2_generated_vs_real.*`; generation manifest
`results/validity/mesa_batch113_manifest.json`. Code:
`scripts/m2_generated_vs_real.py`, `scripts/mesa_generate.py`.

## Result

- **Reject H0.** Test MMD^2 median = **0.0885**; spatial-null p95 floor =
  **0.0283**; ratio **3.12x**; ALL 200 real-half draws above the floor;
  one-sided p = 0.
- n-matched and mix-mirrored: **114 generated** (40 cumberland : 40 appalachian
  : 34 coastal, the pre-registered forced mirror) vs ~113 real (10-tile spatial
  halves), sigma FIXED to the null's value (7.2e6) so the kernel and floor are
  comparable.
- Density-controlled: both populations' diagrams built at the common target
  density (median real NHD density, 1.732 km/km2), so the MMD reflects
  branching/topology, not density.

## Why the read is trustworthy (the precondition chain)

Each gate was cleared and committed before this number was computed, so a
significant MMD is interpretable rather than confounded:

1. **Saddle confound characterized** — H0's sensitivity to D8 saddle flips is a
   graded curve (not a binary failure); read against the operating point below.
2. **Resolution confound** — the metric is resolution-invariant at matched
   density (3DEP vs GLO-30), so GLO-30 generated/real is fair.
3. **Power** — the spatial null is tight (floor 0.0263-0.0283 at the operating
   point) and the design is powered; N set in patches with test-n == null-n.
4. **Substrate comparability** — MESA's [0,1] elevation is H0-scale-invariant
   and in-family on 11/11 scale-free routing descriptors, so a large MMD is
   drainage divergence, not a scale/degeneracy artifact.

## Robustness: the correction went AGAINST the favorable direction

First pass lost 55/114 generated patches to a whitebox-under-pool concurrency
race (retry-in-pool does not help; the race persists), leaving 59 patches with a
cumberland-skewed mix (46:31:24) and n unmatched (59 vs 113) -- both would have
inflated the MMD in the favorable direction (smaller-n bias + mix confound).
Caught before reporting. Serial extraction recovered ALL 114 (err=0), restoring
the 40:40:34 mirror and n-matching. The corrected MMD^2 is LARGER, not smaller
(0.089 vs 0.071): the over-represented cumberland patches were the ones closest
to real, so fixing the bias strengthened the rejection. The headline is
conservative w.r.t. the bug, not propped up by it.

## Saddle operating-point read (the honest qualifier)

The divergence is statistically unambiguous, but its MAGNITUDE must be read
against H0's saddle-instability (Theorem 3: D8 routing is discontinuous at
saddles, so H0-of-accumulation is bottleneck-unstable in the DEM; the saddle
probe confirmed stability_pass=false).

- Mean gen-vs-real SW = 1.012e7; mean real-vs-real SW = 7.97e6 -> H0 **movement
  ratio = 1.27x** the real baseline (gen-gen internal spread 1.34x).
- On the saddle curve, rr_h0 = 1.27 sits in the high-flip regime (2.8M-10M
  flips, rr 1.21-1.35); the real-vs-real baseline itself is ~2.5M-flip-equivalent
  movement.

So generated terrain differs from real by MORE than real differs from itself,
but at a magnitude in the saddle-reorganization regime. The defensible claim is
therefore **distributional distinguishability** of generated drainage topology
from real -- NOT a proven gross drainage-network failure, because part of the
H0 movement is attributable to saddle-level routing differences that Theorem 3
makes the metric sensitive to. Separating "macro-structure divergence" from
"saddle-instability sensitivity" requires the saddle-STABLE metric variant
(the Theorem-3-stable construction) -- the natural follow-up.

## What remains for the full contribution-1 claim

- **FID / CLIP-FID contrast** (pending): the claim's other half is that this
  divergence exists where optical generative metrics do NOT detect it. FID needs
  the optical image channel (real Sentinel-2 + generated) and an Inception/CLIP
  embedding; not yet computed. The topological half (this result) is in.
- **Saddle-stable variant** to upgrade "distinguishable" toward "structurally
  divergent" if it survives.

## The near-miss worth keeping

The result was nearly reported at 2.52x on a silently-lossy, mix-skewed sample.
The same n-matching and forced-mirror discipline that was built into the design
is what flagged that the extraction loss had broken both -- the guard caught its
own pipeline, not just the statistic. The lesson: a gate is only as good as the
n and the covariate balance it is actually computed at; verify those held at
RUN time, not just design time.
