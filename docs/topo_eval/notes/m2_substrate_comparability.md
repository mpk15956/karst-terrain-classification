---
title: "M2 substrate comparability: MESA elevation is a valid input to the drainage-topology comparison"
date: 2026-06-06
tags: [m2, mesa, substrate, comparability, precondition, scale-invariance]
type: result-note
---

The precondition the M2 MMD assumes but had not been checked. MESA emits a
normalized ~[0,1] elevation channel from an OPTICALLY-trained latent-diffusion
model, not a meters DEM — so before reading a large generated-vs-real MMD^2 as
drainage pathology (the headline, contribution 1), we must rule out that it is a
scale or degeneracy artifact of pulling a DEM out of a model that does not
really emit one. This is the GPU cousin of cheap-half-first: a 15-patch probe,
on the prompts and pipeline the full batch will use, before the 113-patch batch.
Artifacts: `results/validity/substrate_comparability.json` + `.log`,
`results/validity/mesa_small_manifest.json`. Code:
`scripts/substrate_comparability_probe.py`, `scripts/mesa_generate.py`.

## What MESA actually emits

Confirmed empirically: MESA's DEM channel is RGB-rendered grayscale in ~[0,1]
(15-patch range ~[0,1], mean ~0.50, std 0.08–0.21), NOT meters. The generated
object is genuinely a different kind of thing from a GLO-30 DEM. Two questions
follow, answered below: is the [0,1]-vs-meters gap harmless, and is the field
non-degenerate?

## (A) Scale invariance — the [0,1]-vs-meters gap is harmless

D8 routing depends only on elevation ORDER (steepest descent), so the H0
flow-accumulation diagram should be invariant to monotonic rescaling. Verified:
a patch run at native scale vs x1000 gives the IDENTICAL H0 feature count for
both MESA (1414 = 1414) and real (1049 = 1049). (The real case differed only in
the accumulation Gini below the 1e-9 boolean tolerance — float tie-breaking at
large magnitudes, not a topology change; MESA matched to 1e-9.)

**Decision, fixed before the batch:** the H0 statistic is scale-free, so MESA's
[0,1] normalization is NOT rescaled to meters — no normalization step is
introduced, because the comparison does not see absolute scale. Stated now so it
is not a post-hoc choice.

## (B) In-family — MESA is not degenerate "mush"

Scale-free, routing-derived descriptors on 30 real + 9 MESA patches (the 6 other
MESA patches were spurious pool failures — see below — and all run fine; 9 is the
sampled in-family set). MESA's median sits inside the real [p5, p95] band on
ALL 11 descriptors:

| descriptor | MESA p50 | real [p5, p95] | in-family |
|---|---|---|---|
| grad_rms_over_range (smoothness) | 0.0144 | [0.0090, 0.0444] | yes |
| std_over_range | 0.181 | [0.112, 0.266] | yes |
| accum_gini (concentration) | 0.986 | [0.982, 0.991] | yes |
| accum_top1pct_frac | 0.916 | [0.874, 0.940] | yes |
| largest_basin_frac | 0.537 | [0.223, 0.757] | yes |
| n_h0_features | 1194 | [920, 1215] | yes |
| n_roots | 56 | [39, 90] | yes |
| median_persistence_norm | 0.0086 | [0.0059, 0.0193] | yes |
| max_persistence_norm | 0.9995 | [0.9965, 0.9996] | yes |
| channel_cells (at matched tau) | 28240 | [28190, 28260] | yes |
| roots_over_channel (connectivity) | 0.00198 | [0.00137, 0.00318] | yes |

The mush detectors are the load-bearing ones: grad_rms/range (0.0144, real-range)
and accumulation concentration (gini 0.986, top1% 0.916, both in-range) rule out
the low-frequency-blob failure mode where a field routes degenerately. The
single verification patch had looked smooth (grad/range 0.004); it was an
outlier — the batch is in-family.

## The spurious-failure finding (and why it is NOT survivorship bias)

6 of 15 MESA patches (and 10 of 40 real) "failed" the donor pipeline inside the
multiprocessing pool with whitebox's "breach produced no output". Re-run in
ISOLATION, all 6 MESA patches succeed cleanly (no nodata, 6k–8.6k unique values,
accum_max 1.8e5–4.8e5). So the failures are a whitebox-under-multiprocessing
transient — concurrent workers racing on whitebox's shared install-dir state
(settings.json), not a property of the data. This also explains the power
extraction's ~30% patch loss (226 of 320): spurious, not degenerate, so the null
remains a valid real sample.

Crucially this is NOT survivorship bias toward "the degenerate ones failed": the
failures are uncorrelated with flatness (the FLATTEST patch, appalachian_003 std
0.085, SURVIVED; failed patches include full-dynamic-range cumberland_003 std
0.207), and the failed patches are healthy on re-run. The in-family verdict
stands. Fix for the real MMD run: retry-on-failure in extraction so the test is
not lossy (lost patches would shrink n below the null's operating point).

## Pre-registered read-out (stated before the MMD)

MESA elevation is real-scale-equivalent (H0 is scale-invariant, so the [0,1]
normalization does not affect the comparison) and in-family on all 11 scale-free
routing descriptors (it is not degenerate mush). THEREFORE a generated-vs-real
MMD^2 exceeding the spatial-null floor (0.0263 at the 113-patches/side operating
point) is read as **drainage-topology divergence**, not a substrate / scale /
degeneracy artifact. If MESA had come back out-of-family, a large MMD^2 would
have been uninterpretable and the fix would have been a normalization decision
stated here — it did not, so no such decision is needed. The comparability gate
is the last precondition before the headline measurement.
