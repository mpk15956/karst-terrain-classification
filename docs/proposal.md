# Topological evaluation of generative terrain models

**Status (2026-05-26):** Framing locked to methods after four rounds
of plan revision against referee-style review. Filtration locked to
sublevel-increasing on the channel mask, donor-based union-find on
the D8 flow graph. Phase 0 spike PASS (9/9 toy assertions per
[docs/topo_eval/notes/orientation_spike.md](topo_eval/notes/orientation_spike.md)).
Novelty-collision check cleared per
[docs/topo_eval/notes/folklore_check.md](topo_eval/notes/folklore_check.md).
Operational pre-commits in [docs/topo_eval/_evaluation_conventions.md](topo_eval/_evaluation_conventions.md).
Phase A drafting (proof) can begin.

## The contribution stack

Four contributions, ordered by novelty strength:

1. **Evaluation regime.** No published paper applies persistence-
   based distributional tests as an evaluation regime for generative
   DEM/terrain models, and no paper uses flow accumulation as the
   filtration function for sublevel-set PH on a DEM. Both novelty
   claims stack independently per the May 2026 literature scans at
   [docs/literature/052626/1.md](literature/052626/1.md) and the
   parallel May 11 compass artifact.

2. **Donor-graph adjacency for the merge-tree construction.** No
   prior terrain merge-tree built on the D8 flow graph (donor
   relation) rather than spatial-grid adjacency. Closest analogs
   (TerraStream, Agarwal-Arge-Yi *SoCG 2006*, Cousty et al.
   *PAMI 2009* watershed cuts) all use spatial adjacency on the
   underlying height-graph or edge-weighted graph. The Phase 0
   spike provides empirical evidence that this choice matters:
   cubical 8-adjacency produces a phantom merge four cells upstream
   of the true confluence on the tributary-contact toy and spurious
   H₁ = 8 cycles on a 9-cell meander-neck mask. The donor-graph
   construction removes both contamination modes.

3. **Persistence diagram coarsening-loss characterization.**
   Explicit statement of what the PD of the filtration forgets
   relative to the merge tree: branch permutations at confluences.
   The PD is the abelianization of the merge tree; Horton-Strahler
   stream order depends on the branching pairing the abelianization
   discards. Companion: a falsification toy (two DEMs with identical
   H₀ barcodes and different Strahler distributions via equal-birth
   construction).

4. **Field-level stability with honest scope.** Cohen-Steiner,
   Edelsbrunner, Harer (2007) applied directly to the accumulation
   field gives $d_B(\text{Dgm}(A_1), \text{Dgm}(A_2)) \le \|A_1 - A_2\|_\infty$.
   No global Lipschitz claim from input DEM to A: D8 flow direction
   is discontinuous at saddles, so ε perturbation can reroute
   O(catchment) accumulation. DEM→A instability is framed as a
   property of drainage (small divide migrations genuinely reroute
   basins; a faithful drainage metric reflects that), not a defect
   of the metric. Optional generic-stability statement off a
   measure-zero saddle-tied set.

A **bijection lemma** sits between contributions (2) and (3): the
donor-graph merge tree, restricted to the channel mask and swept in
ascending A, is in bijection with the channel network produced by
the standard hydrology workflow (threshold A → extract channels).
Per the folklore check, the bijection is unstated in the literature
but the surrounding scaffolding is dense (TerraStream's
elevation-persistence + Pfafstetter pipeline; Cousty et al.'s
watershed-as-MSF; Horton-Strahler's tree-pruning combinatorics).
The lemma formalizes a folklore correspondence that prior work has
approached from three sides without uniting on the flow-accumulation
scalar. Reviewers familiar with the cited prior work will see the
lemma as "obvious in hindsight"; the contribution sits in the
contributions above and the lemma is the clarifying step that
makes them interpretable.

## Why this paper stands alone

The first author has a separate constrained-diffusion paper
(Helmholtz decomposition, by-construction mass conservation,
FastScape-integration evaluation). If the topological-evaluation
protocol were introduced in that paper, the obvious reviewer
critique is circularity: the metric was designed to favor the
proposed model. Even when the metric is well-motivated independently,
the appearance of circularity weakens both contributions.

Sequencing the protocol paper first, on a benchmark that does not
feature the constrained generator as protagonist, establishes the
protocol as community infrastructure. The diffusion paper later
cites the protocol as the field's evaluation regime without anyone
wondering whether the metric was cooked. Heusel et al. ran the same
play with FID.

The independence sequencing rule in [_evaluation_conventions.md](topo_eval/_evaluation_conventions.md) §3
tightens "sequenced first" to "preprint posted first." A drafted-
but-unposted protocol is not verifiable and reads as bespoke even
if conceived first.

## The filtration

Let $M$ be a DEM after whitebox's breach-and-fill conditioning. Let
$A$ be the D8 flow accumulation field on $M$ (single-receiver
routing; each cell contributes 1 to itself plus its donors). Fix a
channelization threshold $\tau_\text{channel}$. The channel mask is
$\{A \ge \tau_\text{channel}\}$; the channel network is the
donor-graph restricted to this mask.

The filtration of interest is:

- **Direction:** sublevel-increasing in $A$.
- **Domain:** restricted to the channel mask.
- **Adjacency:** D8 donor relation, NOT cubical 8-neighbor.

Construction. Channel-mask cells are processed in ascending $A$
order; each cell joins the components of its already-processed
in-mask donors via union-find. A cell with no in-mask donors is a
channel-head birth. A cell with ≥ 2 donors in distinct components
is a confluence (merge event), and the merge tree records the
branching pairing. The persistence diagram of the filtration is the
abelianization of the merge tree.

Both filtration choices (orientation and adjacency) are empirically
validated by the Phase 0 spike on three toys:

- **Y-toy** (no degenerate geometry): donor and cubical agree, 1
  merge at the true confluence under each. Superlevel-decreasing on
  the whole grid produces 0 merges at the confluence (the
  wrong-direction failure mode: the component grows headward from
  the trunk and each new cell joins the already-present component).
- **Tributary-contact toy** (subparallel flow paths 8-adjacent
  along most of their length): donor produces 1 merge at the true
  confluence; cubical produces a phantom merge four cells upstream.
- **Meander-neck toy** (single channel snaking through a 2x3 block
  with 8-adjacency across the neck): donor produces 0 merges and
  $H_1 = 0$ (forest); cubical produces 0 merges but $H_1 = 8$
  (spurious cycles in the mask graph).

The orientation-spike note records the per-assertion pass details
and the locked formalization.

## The three theorems

Stated here in compressed form; full statements and proofs go in
`docs/topo_eval/proofs/strahler_merge_tree.md` (Phase A).

**Theorem 1 (Strahler as merge-tree coarsening).** Horton-Strahler
stream order is a coarsening of the donor-graph merge tree of $A$
via the equal-vs-unequal-confluence rule applied to merge-tree
branching. Many standard hydrology summaries (Horton bifurcation
ratios, Hack's exponent derived from channel networks) factor
through the merge tree as further coarsenings.

**Theorem 2 (PD coarsening loss).** The persistence diagram of the
filtration is the abelianization of the merge tree, discarding the
branching pairing at confluences. There exist pairs of DEMs whose
H₀ barcodes coincide and whose Strahler distributions differ; the
falsification toy (equal-birth construction, four heads at common
birth $\tau$, balanced tree giving Strahler root order 3 vs
caterpillar tree giving Strahler root order 2 with the same death
multiset) is the minimal witness.

**Theorem 3 (field-level stability).** $d_B(\text{Dgm}(A_1),
\text{Dgm}(A_2)) \le \|A_1 - A_2\|_\infty$ via CEH 2007 applied to
the accumulation field directly. No global Lipschitz bound from
input DEM to $A$ exists because D8 flow direction is discontinuous
at saddles; this is a property of drainage, not a defect of the
metric. Optional generic-stability statement: DEMs off a measure-
zero set of saddle-tied configurations have stable $A$ under
sufficiently small perturbations.

## What this filtration sees that elevation-sublevel-set conflates

Elevation-sublevel-set persistence on a DEM conflates ridge
topology with basin merger topology (ridges of equal height
produce H₀ classes that merge at the saddle between them, which is
fine for ridge counting but blind to drainage hierarchy). The
flow-accumulation filtration with donor-graph adjacency captures
drainage basin merger structure, channel-network hierarchy, and
divide-vs-channel asymmetry directly. Phase A's proof section
contains worked elevation-vs-flow-accumulation contrast examples.
The cubical PH wrapper in `src/geo_tda/persistence.py` (promoted
from the existing notebook) is used in this contrast section to
compute the elevation-sublevel baseline; it is NOT used for the
channel merge tree itself.

## Three validity demonstrations

The validity-demos milestone (the first implementation milestone)
delivers three demonstrations, scoped to the Phase B + Phase C
structure of the plan at `~/.claude/plans/great-it-seems-like-streamed-honey.md`.

### Test 1: confirmatory toys (Phase B)

Three synthetic DEMs with analytical drainage answers: cone (single
basin), V-valley (two basins merging at the bottom), branching
channel (binary tree with controlled Strahler order). The
construction reproduces the analytical answers within pre-registered
tolerance, asserted in pytest fixtures.

### Test 2: adversarial toys (Phase B)

Two adversarial toys exercising the cubical-vs-donor adjacency
distinction (tributary-contact, meander-neck; already validated by
the Phase 0 spike), plus the equal-birth falsification toy
demonstrating the PD coarsening loss. The adversarial toys confirm
that cubical adjacency would have produced the contamination the
construction explicitly avoids; the falsification toy provides
empirical companion to Theorem 2.

### Test 3: real-DEM construct validity (Phase C)

Per-tile PH-derived channel network compared against NHD flowline
vectors (1:24,000 USGS lineage) on roughly 100 tiles across two or
three physiographic provinces. NHDPlus HR derived rasters
(catchment polygons, accumulation grids, flow-direction grids) are
off-limits because they share algorithmic lineage with the metric.

Branching-based criteria (junction count via Spearman ρ across
tiles, Strahler-order distribution via per-tile Wasserstein-1
distance, Horton bifurcation ratio via per-tile $|R_b(\text{PH}) -
R_b(\text{NHD})|$). Drainage density is a controlled covariate, not
a criterion: it is set by $\tau_\text{channel}$ and would be
mechanically reproducible by any thresholding without testing the
branching contribution.

τ_channel is chosen per-tile to match NHD's drainage density on that
tile; sensitivity analysis sweeps ±10% around the matched value.
Pre-registered thresholds for the three criteria are RELATIVE to the
whitebox-vs-NHD agreement ceiling estimated by a separate calibration
step, not against absolute targets: DEM-extracted networks and
photo-digitized vectors disagree for epoch and cartographic-
convention reasons unrelated to any specific metric's correctness.

The per-tile H₁-of-cubical-mask diagnostic is reported as a sidebar
showing how much spatial-adjacency contamination the donor-graph
construction removes on real data.

## Verification status

The three pre-implementation gates are cleared.

### Gate 1, generator availability: cleared

Of 16 surveyed generative terrain models, 7 have confirmed runnable
code and weights (≈ 44 %). The five Tier-1
unconditional/sketch-conditioned generators (MESA, TerraFusion,
Goslin Terrain Diffusion, Guérin 2017, Beckham & Pal 2017) span
GAN, DCGAN, latent diffusion, and hierarchical DDPM. They form the
empirical core for the eventual benchmark (Milestone 2+), not for
the validity-demos milestone.

### Gate 2, prior art (PH + terrain generation): cleared

No paper applies persistence-based distributional tests as an
evaluation regime for generative DEM/terrain models. Separately, no
paper uses flow accumulation as the filtration function for
sublevel-set PH on a DEM. Both novelty claims survive the targeted
search per [docs/literature/052626/1.md](literature/052626/1.md).

### Gate 3, filtration spike: PASS 9/9

The Phase 0 filtration-orientation spike (`scripts/spike_filtration.py`)
empirically validates the locked construction against two negative
controls (cubical 8-adjacency; superlevel-decreasing on whole grid)
on three toys (Y, tributary-contact, meander-neck). All nine
assertions pass; the negative controls produce the predicted
contamination on the degenerate toys, removed under the locked
construction. Findings recorded in [docs/topo_eval/notes/orientation_spike.md](topo_eval/notes/orientation_spike.md).

### Gate 4, folklore-collision check: cleared with refinement

The targeted novelty-collision search (recorded at
[docs/topo_eval/notes/folklore_check.md](topo_eval/notes/folklore_check.md))
confirms no exact prior art on (a) merge-tree-of-flow-accumulation
recovers the watershed hierarchy as stated, (b) flow-graph adjacency
for terrain merge-tree construction, or (c) PH under flow-accumulation
filtration on a DEM. Closest analogs all use elevation rather than
flow accumulation; the bijection lemma is positioned as
folklore-formalization. One follow-up read flagged for pre-submission:
Cousty-Najman, "Characterization of Graph-Based Hierarchical
Watersheds," *Journal of Mathematical Imaging and Vision* 2019.

## Target venue

**Earth Surface Dynamics** (Copernicus, open-access, methods-friendly
geomorphology audience). The readership has the mathematical
literacy to engage with the merge-tree coarsening and the domain
expertise to care about D8 routing limitations and NHD baseline
conventions.

**Backup:** Remote Sensing of Environment methodology track.

**Not** SoCG or JoCG: the "merge tree of superlevel filtration"
object is textbook computational geometry; a pure-CG referee would
discount the contribution as applied recasting of standard
machinery. The contribution after the folklore-check refinement is
"rigorous correspondence between a known topological invariant and
a domain-specific evaluation regime not yet in the literature,"
which is a geomorphology-methods contribution, not a CG
contribution.

## What this repository already contains

The karst-terrain-classification work in `docs/report/` and
`docs/presentation/` is GEOG 6591 Fall 2025 coursework. It
contributes:

- `src/geo_tda/`: raster IO, QA/QC, plotting, DEM acquisition.
  Reusable as the TDA harness for the new direction.
- Persistence computation via gudhi and cripser, validated on
  synthetic and real DEMs (cubical-complex pipeline; promoted to a
  module in Phase B for the elevation-sublevel baseline, NOT for
  the channel merge tree).
- Patch extraction and per-tile feature pipelines, adaptable to
  generator-output evaluation.

The karst classification result is not the headline of this
directory. It is pilot data and infrastructure validation. The
original framing (TDA versus pretrained DL on karst classification)
was deprecated by the first author as methodologically weak;
training cost was a sunk cost under frozen features, removing the
intended asymmetry. The karst pilot is unpublished and is NOT cited
as published precedent in any manuscript; published karst /
landslide-topology precedents to use instead are Syzdykbayev et al.
*RSE* 2020 (PH on LiDAR for landslides) and Wu et al. *Geomorphology*
2016 (LiDAR sinkhole delineation).

## Composition with the broader portfolio

| Project | Role | Active in this repo? |
|---|---|---|
| MS thesis: 3DGS topology-preserving pruning for CubeSat edge (Mishra/MOCI) | PhD methods signal, edge engineering | No, separate repo |
| Topological evaluation of generative terrain (this paper) | Methods + benchmark, standalone | Yes, primary |
| Constrained diffusion (Helmholtz, mass-conservation by construction) | Methods, "structural priors over spatial data" | No, separate repo |
| Spatial fairness | In progress | No, separate repo |

The four projects share one research identity: structural priors
over spatial data. This paper's role in the portfolio is to give
the diffusion paper a non-circular evaluation regime to plug into
later. The eval-metric / training-loss disjointness rule in
[_evaluation_conventions.md](topo_eval/_evaluation_conventions.md) §1
governs that integration.

## Project-level conventions

Reproducibility stack follows user-wide §5: `Containerfile` as
canonical install record, pixi for dependencies, `pixi.lock`
committed alongside `pyproject.toml`. README structure follows
user-wide §6: one labeled section per audience, no chained-command
setup.

Per user-wide §3, prose in deliverables (.qmd, .md, paper draft)
uses no em dashes, no AI-tell hedge openers, no tricolons of three,
no trailing summaries.

Per user-wide §1 and §2, claims of work landed in tracked
methodology files must include the git diff hunk in the agent
report, and pre-commits to tracked methodology files must be
committed before agent handoffs. The validity-demos milestone has
Phase 0 commits (this proposal's rewrite, the methodology
conventions, the spike, the spike note, the folklore note) all in
HEAD before any Phase B implementation work begins.
