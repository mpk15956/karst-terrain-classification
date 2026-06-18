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

## Amendment (2026-06-18): persistence-image coordinates are log10-accumulation

This amends the constants above BEFORE any stabilized real-vs-real null is computed
(it precedes the Stage-0.5 sweep), per the constants discipline. It was forced by a
hard failure and verified by three adversarial subagents (one theory, one data
geometry, one gate-robustness); the advisor input that prompted it is corrected where
it overreached.

**Why.** On real flow-accumulation H0 diagrams the births cluster near tau (~115-512)
while finite deaths reach ~530,000 (a ~1000x dynamic range; deaths span ~3.5 log10
decades). A square-pixel persistence-image grid sized to the death/persistence axis
gives the birth axis zero pixels, so the image collapsed to length 0. This affects
ONLY the stabilized/ensemble persistence-image statistic; the base sliced-Wasserstein
MMD headline operates on raw diagrams and is scale-tolerant, so it is untouched.

**Decision.** Image in log10-accumulation COORDINATES: map each diagram point
`(b, d) -> (log10 b, log10 d)`, image on the resulting (birth, persistence') plane.
NOT the persistence value: `log(d - b)` sends the diagonal to minus infinity and
breaks the Adams "weight vanishes on the diagonal" condition (in Adams' post-transform
birth-persistence plane); logging the coordinates keeps the diagonal at
`persistence' = log(d/b) = 0` where the weight correctly vanishes.

**Justification is distributional, not a power law.** The deaths are heavy-tailed
(coefficient of variation 2.6, p99/p50 ~ 99, top 1% hold ~19% of death-mass) and span
~3.5 log decades, so a linear grid buries ~85% of features in one pixel. They are NOT
a clean power law (Hill alpha drifts 0.6 -> 3.8 down the tail) and NOT near the Hack
exponent 0.43 (that is the exponent on the accumulation field A, not on diagram
deaths). Justify log by heavy-tailedness and the log-decade span, never by Hack's law.

**Grid and kernel.** Essential cap = max finite log10-death over the pooled corpus
PLUS an additive margin (`ESS_MARGIN = 0.5`), not a multiplicative 1.5x (which in log
space would place essentials at 10^(1.5 max) accumulation, far past the |G| cell
ceiling). Pixels are sized to the PERSISTENCE span (PI_PIXELS across the persistence
axis), giving pixel_size ~ 0.14 log10-units on the real corpus; the Gaussian kernel
covariance is one pixel (within-patch log-persistence spread ~ 0.74, so one pixel does
not wash out). Grid, cap, and tau remain frozen once over the pooled real+generated
corpus.

**Stability (the proof survives, with a better constant).** log10 is strictly
monotone, so the merge-tree combinatorics, the heads/confluences bijection, and the
cardinality exponent N are unchanged (filtering on log A equals computing the diagram
on A and log-transforming its coordinates; merge_tree.py is untouched). On the masked
range A >= tau the transform is a `1/(tau ln 10)`-Lipschitz CONTRACTION, so the
Theorem-3a -> cardinality-lemma -> Adams chain gives `C_Adams |G| / (tau ln 10)`,
strictly tighter than the raw bound. See docs/topo_eval/notes/proof_obligations_referee.md.

**Gate robustness (the differential-compression hazard is refuted in direction).** A
controlled high-death-vs-mid-death perturbation test found that log makes the saddle
term RELATIVELY LARGER, not smaller (R_log / R_fair-linear ~ 4-9x): log gives every
decade equal axis room, so equal-relative saddle and signal kicks get equal pixel
budgets. Log is therefore the CONSERVATIVE choice for the attribution gate (it lets
Theorem-3b saddle movement register more, making the macro-attribution claim harder,
not easier). Consequently: do NOT add a linear-normalized-grid persistence image as a
co-equal gate comparator (the linear grid is degenerate at this dynamic range). If a
referee belt is wanted, report ONE robustness line under a quantile (rank) coordinate,
which pushes the saddle term even smaller (gate even harder), confirming log is
conservative; flag that the quantile coordinate is a one-off sensitivity cross-check,
NOT a valid frozen statistic (it is non-Lipschitz and corpus-coupled, which would also
contaminate the spatial-split null).

**Representation (2D image stays primary; 1D is a documented contingency).** The log
diagram point cloud is empirically near rank-1 (PCA PC1 = 98.5% pooled, 99.1-99.6% in
every patch; births contribute under 0.2% to the base sliced-Wasserstein distance; the
birth spread is mostly tau drifting across patches). The pre-registered 2D log10
persistence image stays the PRIMARY stabilized statistic (Adams-backed, locked). A 1D
log-persistence representation (a persistence landscape, Bubenik 2015 stability) is a
documented contingency, to be adopted only if the Stage-1 J=16-vs-J=32 smoke shows the
near-degenerate birth axis materially inflates finite-J variance.

**Corrections folded in (do not repeat in the writeup).** The advisor framing that
independent per-axis linear scaling "breaks the math" is OVERSTATED: a frozen linear
rescale is fully Adams-valid and stable (the diagonal still maps to the horizontal
axis where the weight vanishes); the real defect is distributional degeneracy. And the
power-law / Hack-exponent justification does not apply to the diagram deaths.
