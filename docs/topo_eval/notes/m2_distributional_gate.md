# Milestone 2 distributional gate: pre-registration

Pre-registered BEFORE any generated-vs-real MMD is computed, so the prompt set
and the null are fixed by rule, not tuned to the result (the HARKing guard,
same discipline as freezing tau and the probe constants). Committed before the
MESA generation batch runs.

## Formal hypothesis

H0: the real and generated populations of H0 flow-accumulation persistence
diagrams (at matched drainage density) are samples from the same distribution
(population sliced-Wasserstein-kernel MMD = 0 in expectation). Reject H0
(generated drainage topology diverges from real) iff the generated-vs-real MMD
exceeds the spatial-split real-vs-real null band (95th percentile). Statistic:
sliced-Wasserstein kernel (Carriere-Cuturi-Oudot 2017) MMD (Gretton 2012). The
contribution-1 claim is that this divergence exists where FID does not detect
it; FID/CLIP-FID are computed and reported alongside.

## Prompt set: province-matched by pre-registered proportion

The generated conditioning distribution is fixed to mirror the real
population's province proportions, taken from the manifest province labels
(NOT tuned against MESA output):

- cumberland_plateau: 7/20
- appalachian_highlands: 7/20
- coastal_plain: 6/20

so N generated tiles are drawn in 7:7:6 across three fixed province prompts
(stated here before generation; the exact prompt strings are recorded with the
generation run). Generic (un-province-matched) prompts are disqualified: they
make H0 false for a trivial reason (the conditioning distributions differ), so
a rejection could not separate "prompted a different distribution" from
"generated drainage is pathological."

## Scope: the text-conditioning confound (part of the claim, not a defect)

MESA conditions on text captions learned from Copernicus training data; its
caption semantics are NOT identical to the NHD-flowline-density province
definition used here. So "province-matched" matches OUR province semantics to
MESA's CAPTION semantics, which can diverge. The honest, and stronger, claim is
therefore scoped to the generator AS USED: "MESA, prompted to produce terrain
of a given geomorphic character, produces drainage topology that diverges from
real terrain of that character, a divergence FID does not detect." The
conditioning is part of the claim, which is what a practitioner deploys.

## The null is SPATIAL, not random (the load-bearing guard)

768x768 patches cut from the same 1-degree tile are spatially autocorrelated
(adjacent patches share drainage). The karst-era pilot already measured this
(spatial CV stricter than random CV, ~6 F1 points of autocorrelation
inflation). If the real-vs-real null splits patches RANDOMLY, the two halves
are artificially similar, the null band is artificially tight, and
generated-vs-real clears a floor that is too low: a false-positive headline.
So the null splits by TILE (whole tiles to a side), and any permutation
respects tile blocks, so the two real subpopulations are as independent as the
generated-vs-real comparison will be. This is the single most likely way the
headline goes artifactually positive; it is built spatial from the first line.

## N is set by power, not by feel

Before generating, the spatial-split null is run on the real GLO-30 patches at
varying subpopulation size, giving the null-band-width-vs-size curve. N is the
size at which the band is tight enough to resolve a difference worth caring
about. If the band is too wide even pooling all real patches, the experiment
is underpowered and the fix is a design change (more real footprints, a
different statistic), learned from free real-data resampling, not after a GPU
batch. The power analysis is the greenlight criterion for the generation batch.

> Result (2026-06-06, `docs/topo_eval/notes/m2_power_result.md`): the
> spatial-split null tightens monotonically (in PATCHES, the MMD unit) to a p95
> floor of **0.0263 MMD^2** at the max balanced split, 10 tiles/side ≈ 113
> patches/side — the design is powered. N is set in patches, not tiles: generate
> **113 patches** (one per MESA call) so the generated-vs-real test runs at the
> SAME per-side patch count as the null (test-n ≡ null-n). The 7:7:6 (≈40:40:34)
> mix is the FORCED mirror of the real reference corpus, not a chosen N.
> Greenlight criterion MET.

## Density control

Both populations' H0 diagrams are built at a COMMON target drainage density
(the median real NHD density), tau derived per patch via the resolution-
invariant anchor. This holds density constant across real and generated, so
the MMD reflects branching/topology, not density (which is mechanically set by
tau; see the resolution-confound result). The saddle gate still applies: H0's
saddle-sensitivity at MESA's actual flip-magnitude must be read before the MMD
is trusted.
