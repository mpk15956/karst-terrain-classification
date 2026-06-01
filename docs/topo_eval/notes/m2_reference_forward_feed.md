# Forward-feeding the Phase C tiles into the Milestone 2 generator benchmark

Captured 2026-05-30. This note records why the Phase C real-DEM tile
selection is designed to feed forward into the Milestone 2 generator
benchmark by footprint rather than by raster, and the substrate confound
that drives the design. It is written to lift into the paper's
methodology and discussion sections, where the substrate-control argument
pre-empts a predictable referee objection.

## The two milestones are coupled by footprint, not by data

Phase C (the validity-demos milestone) validates the metric: it shows the
donor-graph merge tree of the flow-accumulation filtration captures real
drainage networks, by comparing the PH-derived network against NHD
flowline vectors on branching criteria. Milestone 2 (the headline) scores
generators: it compares populations of generated tiles against a real
reference via sliced-Wasserstein MMD on the H0 flow-accumulation diagram.

Phase C must run on 3DEP/CONUS, because NHD flowlines, the only external
vector ground truth, exist only for CONUS. The 20 tiles are chosen for
physiographic spread (Cumberland Plateau, Coastal Plain, Appalachian
Highlands) across NHD drainage-density quintiles, so the merge tree is
stressed across dendritic, low-gradient, and trellis regimes rather than
one. That spread is the right validation design independent of Milestone
2.

What carries forward to Milestone 2 is the tile footprint, not the 3DEP
raster.

## Why footprints and not rasters: the resolution-substrate confound

The Milestone 2 two-sample test asks whether a generator reproduces real
drainage topology. Its null hypothesis is that any divergence between the
generated and real populations is the generator's, not the data's. That
null is violated the moment the real reference and the generated samples
sit on different substrates.

The Tier-1 generators are not region-locked, so geography is not the
confound. MESA trains on Copernicus GLO-30 (Major TOM), Goslin is
Earth-scale, and Beckham and Pal train on NASA Visible Earth; all three
treat CONUS as in-distribution. The confound is resolution. The donor
graph, the channel mask, and the channelization threshold are all
grid-resolution dependent. 3DEP is roughly 10 m; MESA emits GLO-30 at
roughly 30 m. A GLO-30-generated population compared against a 3DEP real
reference confounds generator pathology with a threefold cell-size
difference in the filtration substrate. The pilot karst work already
documented that drainage extraction is resolution-sensitive across 5, 10,
and 30 m, so this is a known effect, not a hypothetical.

The resolution confound subsumes the cruder sensor-lineage objection: even
matching sensors, a resolution mismatch alone breaks the null.

## NHD drainage density is the resolution-invariant anchor

Drainage density here is computed from the NHD vectors, not from the DEM,
so it does not move when the substrate changes. That makes it the quantity
that lets the channelization threshold re-derive at any resolution: tau is
a function of (drainage density, cell size), the density is fixed by the
footprint, and the cell size is fixed by the substrate. Recording the
density and the tau rule, rather than only the tau value used at 3DEP
resolution, is what makes a substrate swap mechanical instead of a
re-derivation.

**Empirically confirmed (resolution-confound probe,
`scripts/resolution_confound_probe.py`).** On matched real-vs-real pairs, the
donor-graph channel network at the NHD-density-matched tau agrees between 3DEP
(~3612 px) and GLO-30 (3600 px) across all three provinces: net
Strahler-Wasserstein 0.009-0.023 (against the ~0.29 PH-vs-NHD scale), junction
counts within ~10%, and the GLO-30 donor graph is connected on every tile
(roots 81-283, so the whitebox-pointer fix is substrate-general). The
mitigation survives the hard case: on the flattest coastal tile (n30w083) the
raw 3DEP/GLO-30 elevation correlation is only 0.842 (small relief, so
sensor/vintage differences are a large fraction of it), yet the
density-matched networks still agree (net SW 0.021). So at matched density the
metric is resolution-invariant and the M2 cross-substrate comparison is sound;
the resolution confound is benign as long as density is matched. Result:
results/validity/teach_run_20260530/resolution_probe.json.

## The Milestone 2 reference is re-acquired, not reused verbatim

The consequence: the Milestone 2 real reference for a given generator is
the matched substrate (GLO-30 for MESA) re-acquired at the same
footprints, re-tiled to the generator's native patch grid (256 or 512),
with the donor graph and tau recomputed at that resolution. A 256-square
GLO-30 patch is about 7.7 km on a side and holds two or three Strahler
orders, so the comparison is between populations of native-size patches,
never a Phase-C-scale window against a single generator patch. The H0
flow-accumulation diagram is the robust primary at patch scale; Strahler,
Hack, and bifurcation-ratio summaries get noisy on a small crop and are
secondary.

## The caveat that the manifest cannot resolve

Footprint re-acquisition is clean only for the three global generators.
TerraFusion's training substrate is not named in the available survey, and
Guerin is sketch-conditioned with no locked geography, so neither has a
well-defined matched real reference. Each likely needs a held-out slice of
its own training corpus as reference, or separate treatment, which means
Milestone 2 will not be uniform across the Tier-1 set. This is an open
Milestone 2 design item, flagged rather than papered over; the tile
manifest cannot resolve it.

## A second, finer confound: routing discontinuity at saddles

Theorem 3 states the construction is bottleneck-stable in the accumulation
field A but not stable in the DEM, because D8 flow routing is discontinuous
at saddles. The rotated-pointer defect found during the Phase C run is an
empirical instance of exactly this: a change confined to the routing layer
(the whitebox pointer convention) produced a large, non-continuous change in
the merge tree, a 25-40x junction shift and near-total disconnection. The
theorem demonstrated itself in debugging.

This adds a Milestone 2 confound finer than the resolution one above.
Generated tiles carry different saddle structure than real DEMs, and the
routing-discontinuity sensitivity means the two-sample distributional test
can register routing-layer differences that are not drainage-topology
differences. The resolution match controls the grid-scale substrate; this is
a saddle-level confound on the same comparison. Mitigations to weigh:
condition the real reference and the generated tiles through the identical
breach-and-route step before building the filtration, so any routing
artifact is applied to both sides symmetrically; and report the H0
flow-accumulation diagram as primary (it is the bottleneck-stable summary),
with the saddle-sensitive merge-tree branching summaries as secondaries.

## Saddle-stability probe: yield and the Milestone 2 step-1 gate

The probe (`scripts/saddle_stability_probe.py`) tested the saddle confound on
real tiles before any generator is involved. Its design and the dead ends are
in [phase_c_postmortem.md](phase_c_postmortem.md). What it yielded:

- A monotonic flip-count to H0-movement **sensitivity curve** in the
  generator-like (spatially correlated) regime, with a consistent constant-f
  control as the unit. rr_h0 (H0 movement over a constant reroute) by flip
  quartile across 5 tiles: 0.21, 0.48, 1.35, 1.21. H0 response is graded in
  routing change, not a cliff: the Theorem 3 mechanism, confirmed.
- At the generator-relevant end (gentle correlated perturbation; smoothing),
  H0 is moderately stable (rr_h0 ~0.21 at the lowest flip bin; smoothing
  ~0.40). At the high-flip end (millions of receivers flipped) H0 moves as
  much as a real reroute (rr_h0 > 1). Whether the confound is benign or
  material is therefore a function of where real-vs-generated differences sit
  on this curve.
- White additive noise was rejected as unrepresentative: sub-meter white
  noise flips millions of receivers (wholesale rerouting); generator-vs-real
  differences are spatially correlated.
- The pooled stability/asymmetry pass-fail gates are **superseded by design**:
  they average the stable low-flip end with the unstable high-flip end of a
  graded response, so they are meaningless once the response is known to be
  graded. The result JSON carries them only as machine fields; do not quote
  "stability gate: fail" bare. The curve is the artifact and the operating
  point (below) is where the verdict is rendered.

**Milestone 2 step-1 gate (named, not someday).** M2 step 1 measures, on
matched real-vs-generated pairs, the actual H0 movement (plus its flip-count
and spatial structure for context). The saddle-confound go/no-go is read
THERE, from the measured H0 response, before any two-sample drainage claim is
trusted. The synthetic curve is the interpretive frame only; flip-count is
NOT assumed a sufficient statistic, because a generator's spatially structured
differences can land at the same flip-count yet move H0 differently. No
distributional comparison is trusted until this gate is read.

**Scope.** This probe isolates the saddle-routing confound under correlated
perturbation. It does not test the resolution confound (the next probe:
downsample a real tile to GLO-30 cell size, check tau-matching) nor
texture/spectral generated-vs-real gaps (Milestone 2 proper). "Smoothing moves
H0 ~0.40" means the saddle confound looks moderate in the generator regime,
NOT that the metric is validated against generators.

## What this does not block

The headline arm of Milestone 2 is itself undecided: the distributional
MMD test versus the FID-blind paired demonstration (matched-FID,
divergent-drainage pairs), which `validity_real_probe.py` is meant to
adjudicate by testing whether natural pairs suffice or adversarial DEM
construction is needed. If the headline ends up carried by the paired demo
rather than the distributional test, the substrate-matched reference
matters less. The forward-feed hooks are cheap metadata, so they go in the
manifest now regardless, but Milestone 2 reference design is post-run and
does not gate the Phase C launch.
