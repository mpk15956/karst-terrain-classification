---
title: "Pre-registration: the saddle-stable statistic, its validation gate, and the branch claim-sentences"
date: 2026-06-16
type: pre-registration
tags: [m2, saddle, stabilized, persistence-image, ensemble, pre-registration, contribution-1]
---

This note fixes the constants, the validation gate, the non-vacuity controls, and
the exact manuscript claim-sentences for the saddle-stable statistic BEFORE any
stabilized result is computed. It follows the project's constants discipline (any
change is made in an open commit, before checking whether it flips a pass) and the
two referee passes of 2026-06-16. Committing it is the gate that licenses the
Stage-0.5 sweep and the Stage-1 build. The full design lives in the approved plan
(`~/.claude/plans/polished-giggling-rossum.md`).

## Why this exists (the diagnostic path, briefly)

The base headline (MESA-vs-real test median MMD^2 0.0885 / spatial-null p95 floor
0.0283 = 3.12x, near-non-overlapping) is statistically clean, but its MAGNITUDE in
raw diagram-distance units (mean generated-vs-real sliced-Wasserstein H0 1.012e7 /
mean real-vs-real 7.97e6 = 1.27x) sits where heavy D8 saddle rerouting can also
reach (`saddle_probe_A.json`: high-flip bins rr_h0 1.21-1.35; `stability_p95_rr_h0`
2.79). Attribution to macro-scale drainage reorganization versus the metric's known
saddle sensitivity (Theorem 3b) is unresolved. The saddle-stable statistic is built
to make that separation. Three reviewer claims were over-reaches that dissolved on
checking source and are recorded here so they are not re-litigated: the "~79%
saddle" decomposition (1.27 is a raw SW movement ratio, not a saddle fraction, and
does not decompose the 3.12 MMD-tail ratio); the "vacuous non-vacuity guard" (the
saddle-probe control is a large-watershed-capture megachannel the base metric
responds to at Spearman 0.80, not the localized trench it ignores); and the "mask
drift" (the channel mask is recomputed per realization at the frozen tau threshold,
`merge_tree.py:181`, which is the correct behavior, not a defect). The underlying
concerns are real and are addressed by the constants below.

## Posture (decided)

The base paper ships regardless; the saddle-stable statistic is upside. The
construct-validity spine and the theorem stack are independent of the MESA
attribution. Every stage below has a fallback to the base paper; a stall triggers
the fallback, not a stuck submission.

## Pre-registered constants

- **Ensemble size J = 16.** Validated against J = 32 on a handful of patches in the
  Stage-1 smoke (the ensemble feature is a Monte-Carlo mean of bounded
  persistence-image vectors; variance falls as 1/J). If J = 16 and J = 32 features
  differ by more than the inter-patch spread on the smoke set, raise J before the
  headline.
- **Perturbation = a pre-registered amplitude model, not a calibrated estimate.**
  Base correlated-noise amplitudes are swept over the physically-motivated grid
  `{0.25, 0.5, 1.0, 2.0}` metres (sub-metre LiDAR-grade through coarse-product
  scale). Spatial correlation reuses the existing `gaussian_filter` machinery
  (`CORR_LEN_PX = 4`). Each base amplitude is LOCALLY scaled: the per-cell amplitude
  is `a_base * (gap_local / median(gap))`, where `gap_local` is the local
  steepest-descent elevation gap, because saddle ambiguity is local and a single
  global amplitude is indefensible. The perturbation is applied in physical metres
  on the conditioned DEM before any normalization; generated [0,1] patches are
  rescaled to the median real-patch relief first (scale-consistency).
- **Conservative-pick rule (Stage 0.5).** Among the swept amplitudes, identify the
  range where (a) the non-vacuity controls still elicit a stabilized response (power
  retained) and (b) the stabilization frontier has taken effect (saddle movement
  reduced / plateaued). Pick the LARGEST such amplitude (the most marginalization
  that still preserves power), so the macro-attribution claim is made under the most
  conservative stabilization. Pre-register the picked amplitude before any
  real-vs-real null is computed. Timebox the sweep at three working days; if no
  clear frontier plateau emerges, fall back to the 1.0 m base amplitude and declare
  it a pre-registered choice (not a calibrated estimate). Product LE90 figures and
  the 3DEP-vs-GLO-30 overlap are a discussion-section cross-check only, not the
  instrument (the overlap conflates resolution, registration, and genuine error and
  is not a clean vertical-error field).
- **Pruning diagnostic epsilon (Stage 0).** Not a single value: sweep epsilon over
  the finite-persistence percentiles `{10, 25, 50, 75, 90}` of the real corpus and
  report the test/floor ratio as a function of epsilon. Pruning is a DIAGNOSTIC that
  informs the Stage-1 amplitude prior, never a program gate. Low persistence is not
  synonymous with saddle (a generator can differ in real fine-channel branching), so
  pruning surviving only rules out "all low-persistence dust"; pruning collapsing
  only raises skepticism and tightens the amplitude prior.
- **Stabilized feature.** Per realization, the H0 persistence image on a fixed
  global grid with a Gaussian weight that vanishes on the diagonal (the Adams 2017
  conditions); the essential-class cap and the grid are frozen once over the pooled
  real+generated corpus and identical for every patch and realization. The patch
  feature is the mean of the J realization images. The two-sample machinery runs on
  the pairwise L2 distance matrix of these features; the kernel sigma is re-derived
  in this feature space (the SW sigma 7.2e6 does NOT transfer).
- **Tau and mask.** Tau is frozen per patch on the unperturbed DEM and reused across
  all J draws; the channel mask `{A >= tau}` is recomputed on each realization's
  perturbed accumulation at that frozen threshold (the correct behavior, stated
  explicitly and unit-tested for support consistency).

## Validation gate (graded, relative, single-currency)

All quantities are computed on the stabilized statistic, in the stabilized
persistence-image L2 currency. Let `M_signal` be the stabilized generated-vs-real
movement and `M_saddle` the stabilized saddle movement under the validation stress
perturbation (the existing probe stress, distinct from the marginalization
perturbation). Define the dimensionless `rho = M_saddle / M_signal` (scale-free, so
the bands below are defensible independent of the absolute stabilized scale).

- **HARD STOP -> fallback:** the top flip bin's stabilized saddle movement is not
  materially flattened (remains a large fraction of `M_signal`, operationally
  `> 0.5`), i.e. the bimodal high-flip Theorem-3b case is not stabilized. The
  divergence cannot be attributed; ship the base paper.
- **WEAK PASS (qualified):** `0.2 < rho <= 0.5` and the stabilized headline clears
  its pre-registered floor. Residual saddle is a non-trivial minority of the signal.
- **CLEAN PASS:** `rho <= 0.2` and the stabilized headline clears its floor.

Non-vacuity guard (the statistic must still RESPOND to genuine reorganization, or
"stability" is vacuous): keep the megachannel control (verified base response,
Spearman 0.80) AND add a pervasive re-branching control (a calibrated merge-height
shift on the diagram). The stabilized statistic must respond to both; a statistic
flat against the controls fails the gate regardless of `rho`.

## Pre-registered branch claim-sentences (the shape is locked here)

Each placeholder is filled post-Stage-1 by an explicit computation in the stabilized
currency; filling them cannot change the claim shape, only its numbers. The branch
is selected by the gate above.

- **HARD STOP:** "Under the saddle-stable statistic the generated population still
  diverges from real at <R> times the stabilized null floor, with residual saddle
  movement <Y> percent of the stabilized signal, so the divergence is macro-scale
  drainage reorganization rather than a routing artifact."
- **WEAK PASS:** "Under the saddle-stable statistic the generated population diverges
  at <R> times the stabilized null floor, with residual saddle movement <Y> percent
  of the stabilized signal, so we attribute the majority but not all of the
  divergence to macro-scale reorganization."
- **CLEAN PASS:** "Under the saddle-stable statistic generated and real terrain are
  indistinguishable (<R> times the stabilized floor, within margin), so the
  base-metric divergence was predominantly saddle-routing sensitivity, and the
  attribution claim is withdrawn in favor of the base-metric distributional result."

Placeholder definitions: `<R>` = stabilized test median feature-distance divided by
the pre-registered stabilized null p95 floor (`m2_pi_power.json`, committed before
the headline). `<Y>` = `100 * rho` rounded, both terms in the stabilized
persistence-image L2 currency. No quantity mixes the base SW-MMD currency with the
stabilized currency.

## Ordering commitments

1. This note is committed before any stabilized result.
2. The stabilized null floor (`m2_pi_power.json`) is committed before the stabilized
   headline.
3. The amplitude pick (Stage 0.5) is committed before any real-vs-real stabilized
   null.
4. The branch is read only after Stage 2, and the sentence is the template above.
