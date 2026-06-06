---
title: "M2 power analysis result: the spatial-split null is tight and the design is powered"
date: 2026-06-06
tags: [m2, power-analysis, distributional-gate, spatial-null, mmd]
type: result-note
---

# M2 power analysis result

The free half of the headline experiment, run before any GPU-hour. The
pre-registered spatial-split (by-tile) real-vs-real null
([[m2_distributional_gate]]) was measured on the 20 staged GLO-30 tiles, and it
answers the one question that had a real answer before generation: **is the
experiment powered, and how many generated tiles does it take?**

Artifacts: `results/validity/m2_power.json` (curve), `results/validity/m2_power_28642.log`
(run log), `results/validity/m2power.sbatch` (job). Driver:
`scripts/m2_power_analysis.py`; null/MMD: `src/geo_tda/topo_eval/distributional.py`.

## Setup

226 valid 768x768 patches over the 20 tiles (16 attempted per tile minus a
handful where breach produced no output), every patch's H0 flow-accumulation
diagram built at a COMMON target density (median real NHD density,
1.732 km/km2) so the comparison is density-controlled and reflects branching,
not density. Statistic: sliced-Wasserstein-kernel MMD^2 with a globally-fixed
sigma (median off-diagonal SW distance, 7.2e6). The null draws two DISJOINT
groups of whole tiles and computes MMD^2 between their pooled patches; the split
is by tile so the two real subpopulations are as independent as the
generated-vs-real comparison will be (the load-bearing guard — random patch
splits would deflate the band).

## The curve (greenlight criterion)

| tiles/group | null MMD^2 median | p95 (the floor) | max |
|---|---|---|---|
| 2 | 0.0146 | 0.131 | 0.201 |
| 3 | 0.0185 | 0.082 | 0.113 |
| 4 | 0.0101 | 0.063 | 0.098 |
| 5 | 0.0081 | 0.058 | 0.071 |
| 6 | 0.0050 | 0.049 | 0.092 |
| 7 | 0.0040 | 0.034 | 0.047 |

The p95 band tightens monotonically and does NOT plateau wide — pooling more
real footprints keeps shrinking the floor. **The design is powered.** At the
largest balanced split the 20 real tiles allow (7+7, leaving 6), the floor a
generated-vs-real MMD^2 must EXCEED to reject H0 is ~0.034; at 6/group it is
~0.049. Given the unit checks (same distribution -> MMD^2 ~ 0; shifted -> ~1),
any genuine drainage-topology divergence — which contribution 1 posits exists
where FID does not see it — should clear a 0.03-0.05 floor comfortably.

## N for the generation batch

Generate in the pre-registered 7:7:6 province proportions
(cumberland:appalachian:coastal). N = 20 (exact 7:7:6) sits at the tight end of
the measured curve (floor <= 0.034) and is cheap on an A30 (a few min/tile), so
there is no reason to under-generate; N ~ 10-14 (band ~0.04-0.05) is an
acceptable cost compromise. N = 2-3 would be underpowered (floor 0.08-0.13) and
is disqualified. The greenlight criterion in the gate pre-registration is met.

## Dry-fire reading: the null is not "zero", and that is correct

Real-vs-real MMD^2 medians are small but positive (0.015 -> 0.004), shrinking
monotonically with group size. This is the O(1/n) positive bias of the biased
MMD^2 estimator, NOT a leak: the within-block diagonal is removed but the
cross-term still carries finite-sample bias. The test does not compare the
generated-vs-real MMD^2 against 0 — it compares against the p95 of THIS
empirical null, so the bias is absorbed by construction. The monotone shrink
with N is exactly the signature of a clean, bias-dominated null. This is a
methodological subtlety worth stating in the paper: the spatial null is the
reference distribution, not a point mass at zero.

## How we got here (the diagnostic path — four jobs, cheap because cached)

The result is one number-table, but the path to it is the methods-paper lesson
that the cheap half can still hide expensive bugs:

- **28556** — serial extraction finished all 20 tiles, but the first-cut
  `power_curve` recomputed the pairwise sliced-Wasserstein distances from
  scratch on every rep x size (millions of redundant SW evals) and timed out at
  2h with no output. Fix: compute the SW matrix ONCE, do every MMD by index
  lookup with a globally-fixed sigma (`mmd2_from_matrix`, `power_curve_indexed`).
- **28639** — parallelized extraction across 24 cores, but WhiteboxTools
  defaults to ALL cores, so 24 workers each spawned an all-cores whitebox and
  the node thrashed (stuck "extracting" >25 min). Fix: cap whitebox to 1 core
  ONCE in the parent (`set_max_procs(1)`), which persists via the shared
  settings.json the forked workers read — calling it per-worker would race on
  that file. Extraction then completed and cached (`diagrams.pkl`).
- **28641** — the SW matrix was still single-threaded while 24 cores sat idle,
  and Python block-buffered stdout to the log file so progress was invisible
  (an empty log read as "hung" when it was working). Fix: parallel SW matrix
  (fork-shared diagram list, row-interleaved for balanced triangular load) +
  `python -u`.
- **28642** — loaded the cached diagrams, built the matrix on 24 cores in ~10
  min, wrote the curve.

The caching (`diagrams.pkl` + `sw_matrix.npy`) is what made four iterations
affordable: extraction (the genuinely expensive whitebox step) ran exactly once;
every later fix re-ran only the cheap tail. The lesson for the paper's
reproducibility section: separate the expensive deterministic stage (per-patch
H0 extraction) from the cheap re-tunable stage (kernel + null), cache the
boundary, and the analysis becomes iterable instead of a multi-hour gamble.
