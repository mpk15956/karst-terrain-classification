---
title: "M2 optical contrast: optical metrics are not blind; the power probe adjudicates the reframe"
date: 2026-06-14
tags: [m2, optical, fid, clip, kid, contribution-1, pre-registration, both-branch]
type: result-note
---

The pre-registered both-branch outcome fired: standard optical generative
metrics are NOT blind to the MESA divergence. This note records the contrast
result (done) and PRE-REGISTERS the power-probe decision rule (three branches,
one committed sentence each) BEFORE the probe is run -- the same HARKing guard
that kept the "blind" headline from being published. Artifacts:
`results/validity/m2_optical_contrast.json` + `.log`. Code:
`scripts/m2_optical_{render,embed,contrast}.py`, `scripts/render_terrain_rgb.py`.

## Contrast result (control valid, so interpretable)

Same 768px patches as the headline (320 real windows + 114 generated), per-patch
robust-normalized then rendered (hillshade + geomorphic stack), embedded with
CLIP (512-d) and Inception (2048-d), tested with the SAME RBF-MMD + by-tile
spatial null + operating point (K=10) as the topology MMD; sigma calibrated on
the real-real block; province pairwise MMD as the positive control.

Positive control is VALID: optical separates coastal-vs-mountain
(appalachian|coastal, coastal|cumberland >> floor) but NOT the two mountainous
provinces from each other (appalachian|cumberland ~ floor) -- the instrument
tracks genuine geomorphic appearance, not noise.

gen-vs-real test/floor (topology reference = 3.12x):

| metric (render) | gen-vs-real | best province pair | KID |
|---|---|---|---|
| CLIP (hillshade) | 4.36x | 3.5x | 6.72x |
| CLIP (stack) | 4.30x | 2.6x | 5.03x |
| Inception (hillshade) | 1.70x | 3.2x | 1.40x |
| Inception (stack) | 2.68x | 3.7x | 2.10x |

(Inception 2048-d FID skipped: rank-deficient covariance at n~160, sqrtm
unstable; KID is the unbiased small-n metric and is reported instead.)

## Reading

- "Topology catches what optical misses" (the clean headline) is DEAD: every
  optical metric separates generated from real above its floor.
- CLIP (richer backbone) separates strongly (4.3x), MORE than it separates real
  provinces (2.6-3.5x); Inception (the field-standard FID backbone) is the
  WEAKEST detector (KID 1.40x, below its own province contrasts), consistent
  with Kynkaanniemi 2023 (Inception features track ImageNet classes, not terrain
  structure).
- So optical detects generated != real as an overall appearance/fidelity gap
  (MESA renders smoother/lower-fidelity), ENTANGLED with geomorphic appearance.
  Topology (3.12x) is hypothesized to isolate the drainage-organization axis.

## Do NOT lead on "FID is weakest"

The Inception-weakness result is real but is mechanism-confirmation only, NOT the
contribution. Leading on it is self-undermining: CLIP (our own richer backbone)
separates fine at 4.3x, so a referee answers "then use CLIP-FID, you don't need
topology." We cannot win a SENSITIVITY war against vision foundation models. The
claim must be about SPECIFICITY / localization, not raw detection power.

## The caveat that makes the reframe a bet (not yet earned)

CLIP separates gen-vs-real (4.3x) MORE than it separates real provinces
(2.6-3.5x). If the divergence were purely an appearance/fidelity gap entangled
with geomorphic appearance, it should sit WITHIN the range of appearance
differences CLIP already resolves between real terrains. It sits above. That is
either (a) MESA's fidelity gap is simply larger than between-province appearance
variation (innocuous, supports the reframe), or (b) CLIP is also picking up part
of the DRAINAGE divergence (then "optical cannot localize, topology isolates" is
too strong). The numbers cannot tell (a) from (b). The power probe does.

## PRE-REGISTERED power-probe decision rule (committed before f is seen)

Probe: perturb a held-out real half with randomized `_carve_trench` drainage
reroutes at increasing effect size f (mass-moved-fraction); at each f compute, in
MMD^2/floor currency (same estimator/null/operating-point as the headline), BOTH
the H0 curve AND the optical curves (CLIP primary, Inception secondary). The
f-sweep must SPAN the 3.12x topology operating point. One committed sentence per
outcome, chosen by the probe, not by us:

- BRANCH 1 -- optical flat (inside its null) while H0 fires across f: the reframe
  holds cleanly. Sentence: "Optical generative metrics detect that generated
  terrain differs but cannot localize the difference; the flow-accumulation
  metric isolates the drainage-organization axis, detecting a structural reroute
  the optical metrics do not register until it becomes an overwhelming visual
  scar."
- BRANCH 2 -- optical rises with f but H0 rises earlier/faster: it is a
  SENSITIVITY-PROFILE claim, not isolation. Sentence: "Both optical and
  topological metrics respond to drainage reorganization, but the
  flow-accumulation metric is markedly more sensitive per unit structural change
  and is the only one expressed on a named, NHD-validated drainage axis."
- BRANCH 3 -- optical rises with f comparably to H0: no drainage-specific
  superiority. Sentence: "Optical metrics can track drainage reorganization
  under controlled perturbation; the flow-accumulation metric's distinct value
  is INTERPRETABILITY -- it reports the difference as a geomorphically meaningful
  drainage quantity rather than an unlocalized embedding distance."

The durable framing across branches is INTERPRETABILITY / LOCALIZATION: every
metric can say generated != real; only the flow-accumulation metric says the
difference is in drainage organization specifically, validated against NHD. This
is robust to CLIP being a strong detector (we concede detection, claim
localization) and to the geomorphology venue. The abstract is NOT written until
the probe's f is in and the branch is known.

## Power-probe RESULT (2026-06-14): none of the three branches fired

Artifacts: `results/validity/m2_power_curve.json` + `.log`, stage outputs under
`results/validity/m2_power_probe/`. Code: `scripts/m2_power_{perturb,embed,curve}.py`.

The probe produced a FOURTH, unanticipated outcome: the trench is the wrong
perturbation. Across the f-sweep (mean f 0.05->0.14), in MMD^2/floor currency:

| metric | curve (ratio by level) |
|---|---|
| H0 | 0.03, 0.02, -0.05, 0.01, 0.06, -0.13 (flat at ~0) |
| CLIP / stack | 0.32, 0.56, 0.90, 1.65, 1.41, 1.34 (rises) |
| Inception / stack | 0.0, 0.44, 1.53, 2.99, 2.74, 2.19 (rises) |
| CLIP / hill, Incep / hill | <= 0.77 (hillshade weak for thin features) |

H0 does NOT register the trench; optical (stack render) does. The per-pair
diagnostic confirms it is not a bug: the trench moves a patch's H0 by 0.2-1.2e6
vs the natural inter-patch SW spread of 7.8e6 (~3-15%). So at matched density H0
is genuinely INVARIANT to a localized megachannel and responds to PERVASIVE
branching reorganization (what MESA exhibits, 3.12x) -- a characterization of the
instrument, not an adjudication of branches 1-3 (all of which assumed H0 fires).

This is ADVERSE to "topology catches what optical misses": we now have a drainage
change (the trench) optical catches and H0 does not, and NO case of the reverse.
So orthogonality/complementarity is NOT claimed (the missing quadrant is unmet),
and the "isolation" reframe is dead. Searching for a new perturbation that fires
H0-not-optical AFTER seeing this would be post-hoc forking-paths (rejected).

## RESOLUTION: contribution 1 = interpretability, probe = honest limitation

Committed contribution-1 sentence (interpretability-only, needs no probe):
"Every evaluated metric distinguishes MESA-generated terrain from real, but only
the flow-accumulation persistence metric NAMES the axis of difference -- it
reports the divergence as drainage-network organization, validated against NHD
flowlines, where optical generative metrics give an unlocalized embedding
distance. Among optical metrics the field-standard Inception-FID is the weakest
detector (Kynkaanniemi 2023); a richer CLIP detects the gap strongly but as
overall appearance/fidelity, entangled with geomorphic style (it separates real
provinces comparably)."

The probe is reported as a LIMITATION / characterization, not hidden: "the
flow-accumulation metric at matched density is sensitive to pervasive
drainage-network reorganization and INVARIANT to localized channel incision (the
trench probe: optical metrics flag the gouge at up to 3x their floor while H0
stays at its floor)." An adverse, reported stress-test strengthens credibility.

Optical's role is recast from "foil we beat" to "baseline we contextualize":
detects-but-does-not-localize; gives a number without a meaning. The contribution
is the number WITH a meaning. This is smaller than the original "topology beats
optical" but it is unassailable and true, and it is what feeds the diffusion
paper (which needs a physics-grading, not pixel-realism, evaluator).
