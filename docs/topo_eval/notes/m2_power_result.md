---
title: "M2 power analysis result: the spatial-split null is tight, and the test must be run at the null's patch-n"
date: 2026-06-06
tags: [m2, power-analysis, distributional-gate, spatial-null, mmd, n-matching]
type: result-note
---

The free half of the headline experiment, run before any GPU-hour. The
pre-registered spatial-split (by-tile) real-vs-real null
([[m2_distributional_gate]]) was measured on the 20 staged GLO-30 tiles, and it
answers two questions before generation: **is the experiment powered, and at
what sample size must the generated-vs-real test be run?**

Artifacts: `results/validity/m2_power.json` (curve + operating point + generation
target), `results/validity/m2_power_28644.log`, `results/validity/m2power.sbatch`.
Driver: `scripts/m2_power_analysis.py`; null/MMD:
`src/geo_tda/topo_eval/distributional.py`.

## Setup

226 valid 768x768 patches over the 20 tiles, every patch's H0
flow-accumulation diagram built at a COMMON target density (median real NHD
density, 1.732 km/km2) so the comparison is density-controlled and reflects
branching, not density. Statistic: sliced-Wasserstein-kernel MMD^2 with a
globally-fixed sigma (median off-diagonal SW distance, 7.2e6). The null draws
two DISJOINT groups of whole tiles and computes MMD^2 between their pooled
patches; the split is by tile so the two real subpopulations are as independent
as the generated-vs-real comparison will be (the load-bearing autocorrelation
guard — random patch splits would deflate the band).

## The curve, expressed in PATCHES (the MMD unit)

The MMD's unit is the per-patch H0 diagram, so the null is reported in patches
per side, not tiles, and the sweep runs to the MAX balanced split the 20-tile
corpus supports (10+10), not an arbitrary cap.

| tiles/side | patches/side | null MMD^2 median | p95 (the floor) | max |
|---|---|---|---|---|
| 2 | ~22 | 0.0160 | 0.116 | 0.201 |
| 3 | ~34 | 0.0192 | 0.092 | 0.146 |
| 4 | ~45 | 0.0095 | 0.059 | 0.090 |
| 5 | ~56 | 0.0074 | 0.047 | 0.089 |
| 6 | ~68 | 0.0049 | 0.052 | 0.096 |
| 7 | ~79 | 0.0041 | 0.030 | 0.047 |
| 8 | ~90 | 0.0058 | 0.031 | 0.063 |
| 9 | ~102 | 0.0030 | 0.028 | 0.054 |
| **10** | **~113** | **0.0042** | **0.0263** | **0.041** |

The p95 band tightens monotonically (modulo sampling noise at 120 reps) and does
NOT plateau wide — pooling more real footprints keeps shrinking the floor.
**The design is powered.** Operating point: the largest balanced split, 10
tiles/side ≈ 113 patches/side, floor p95 = **0.0263**.

## N is set in PATCHES, and test-n must equal null-n (the n-matching fix)

A near-miss caught at greenlight: the first pass capped the sweep at 7 tiles and
reported the floor there (0.034), then would have tested generated-vs-real at a
different sample size. MMD^2 bias AND variance are n-dependent — the dry-fire
shows the O(1/n) bias directly — so a test statistic computed at one n, judged
against a null band measured at another n, clears a floor set at the wrong
sample size (a favorable-direction lie, cousin to the autocorrelation deflation).

Fix, built into the protocol:

- the null is swept to the max balanced split (10+10) and reported per-side in
  PATCHES;
- the operating point is that split, ~113 patches/side;
- the generated-vs-real test is run at the SAME per-side patch count: 113
  generated patches vs 113 real patches, both spatial. test-n ≡ null-n by
  construction, so the floor (0.0263) is the honest bar.

A MESA call emits exactly one 768px patch, so the generation target is a PATCH
count, not a tile count (the earlier "N=20 tiles" framing was a category error —
generated patches and real-tile patches need not have the same per-footprint
yield, so the comparison is counted in patches).

## Generation target (recorded before generation)

**113 generated patches**, drawn in the real reference corpus's province mix:
cumberland_plateau 40, appalachian_highlands 40, coastal_plain 34.

The 7:7:6 (≈40:40:34) mix is NOT a chosen sample-size design — it is the FORCED
mirror of the real reference population's province proportions. The two-sample
MMD compares whole distributions, so if the generated mix differed from the real
mix, the test would read province-mix as topology. Mirroring the reference mix
is a constraint, not a free parameter; stated that way it answers "why these
proportions?" directly. (It is explicitly NOT power-justified per province: the
null pools provinces, and per-province null widths almost certainly differ —
coastal-plain vs trellis drainage — so no per-province power claim is made.)

## Dry-fire reading: the null is not "zero", and that is correct

Real-vs-real MMD^2 medians are small but positive (0.016 -> 0.004), shrinking
with patch-n. This is the O(1/n) positive bias of the biased MMD^2 estimator,
NOT a leak: the test compares the generated-vs-real MMD^2 against the p95 of THIS
empirical null at the same n, not against 0, so the bias is absorbed by
construction. The monotone shrink with n is the signature of a clean,
bias-dominated null. Worth stating in the paper: the spatial null is the
reference distribution, not a point mass at zero.

## How we got here (the diagnostic path — five jobs, cheap because cached)

The result is one number-table, but the path is the methods-paper lesson that
the cheap half can still hide expensive bugs:

- **28556** — serial extraction finished, but the first-cut `power_curve`
  recomputed pairwise sliced-Wasserstein from scratch on every rep x size
  (millions of redundant evals) and timed out at 2h. Fix: SW matrix ONCE,
  every MMD an index lookup with a globally-fixed sigma.
- **28639** — parallelized extraction, but WhiteboxTools defaults to ALL cores,
  so 24 workers each spawned an all-cores whitebox and the node thrashed (stuck
  >25 min). Fix: cap whitebox to 1 core ONCE in the parent (`set_max_procs(1)`,
  persists via the shared settings.json the forked workers read — per-worker
  calls would race on that file). Extraction completed and cached.
- **28641** — SW matrix still single-threaded while 24 cores idled, and Python
  block-buffered stdout to the log so progress was invisible. Fix: parallel SW
  matrix (fork-shared diagrams, row-interleaved) + `python -u`.
- **28642** — cached load + parallel matrix -> curve in ~10 min. But the sweep
  was capped at 7 tiles and the floor reported at the wrong (sub-test) n.
- **28644** — n-matching redesign: sweep to the max balanced split, report in
  patches, set the generation target = the operating-point patch count so
  test-n ≡ null-n. Loaded both caches; ran in under a minute.

The caching (`diagrams.pkl` + `sw_matrix.npy`) made five iterations affordable:
the expensive whitebox extraction ran exactly once; every later fix — including
the n-matching redesign — re-ran only the cheap tail. The reproducibility lesson
for the paper: separate the expensive deterministic stage (per-patch H0
extraction) from the cheap re-tunable stage (kernel + null + power), cache the
boundary, and the analysis becomes iterable instead of a multi-hour gamble.
