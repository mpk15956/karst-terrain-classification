# Phase C construct-validity run: milestone post-mortem

Archival narrative for the 20-tile real-DEM construct-validity run on GACRC
teach (2026-05-30/31). Records the result, the debugging arc, and the
reflective answers, for the methodology and discussion sections and for
future-work memory. The conventions and result tables are in
`results/validity/teach_run_20260530/construct.json`.

## What the milestone was

Phase C is not the paper's headline. It is the prerequisite that makes the
Milestone 2 generator benchmark non-circular: the donor-graph merge tree of
the flow-accumulation filtration must be shown to capture real drainage
networks against an external reference (NHD flowline vectors) before it can
score generated terrain. The run validates the metric on 20 full 1-degree
3DEP tiles spanning three physiographic provinces (Cumberland Plateau,
Coastal Plain, Appalachian Highlands), with whitebox's own field-standard
extraction as the agreement ceiling.

## The result (corrected, n=20)

| criterion | PH vs NHD | whitebox vs NHD | gap | verdict |
|---|---|---|---|---|
| junction-count correlation | +0.936 | +0.935 | +0.001 | pass |
| Strahler Wasserstein-1 (lower better) | 0.287 | 0.287 | +0.000 | pass |
| bifurcation ratio \|dR_b\| (lower better) | 0.185 | 0.375 | -0.190 | pass |

All three pre-registered verdicts (PH within 95% of the ceiling) pass. The
cubical-vs-donor H1 sidebar: median 48,498 spurious 8-adjacency cycles per
tile (range 14,825 to 100,195) removed by construction (donor H1 = 0). Every
tile ran full-tile (no windowing), zero tiles missed their dominant basin.
The bifurcation-ratio gap is favorable but is one criterion at n=20 on a
basin-scoped scalar, so it is a comparative-advantage seed, not a finding;
the A-vs-B framing is deferred to dedicated analysis.

## The debugging arc: six bugs, all at seams

The run took several cluster attempts. Every bug lived at an untested
boundary between WhiteboxTools and the pipeline, which the hand-built toy
tests could not reach. The pattern is the lesson.

1. **Corner-touching tile acquisition.** The STAC search for a 1-degree
   footprint returned a neighbor that shared only a corner; the DEM and the
   NHD reference were spatially disjoint. Found by reading a per-tile JSON
   and noticing the DEM bbox was a degree off. Fixed by ranking candidate
   items by overlap area with the requested tile.

2. **Whitebox cannot read the 3DEP COG.** breach silently produced no output
   on the raw cloud-optimized GeoTIFF but worked on a plain rewrite. Found by
   running breach directly with verbose on the raw file vs a rewrite. Fixed
   by always rematerializing a plain single-band GeoTIFF before any whitebox
   call.

3. **Recursion-depth overflow.** Strahler and segment-graph traversals were
   recursive; real reach chains are thousands deep and overflowed Python's
   1000-frame limit. Fixed by converting all traversals to iterative.

4. **h1_cubical_mask O(huge) Python sets.** The cubical Betti-1 diagnostic
   built per-cell tuple sets and a Python union-find; on million-cell masks
   that was hours of runtime and the memory blowup that swamped the node.
   Fixed by vectorizing: edges via shifted-array AND-reductions, components
   via one scipy.ndimage.label pass. E - V + C unchanged.

5. **Unbounded-stack hang on cyclic NHD graphs.** After (3), coastal tiles
   hung for hours, growing memory until OOM. Found with a per-stage timer:
   stats_from_flowlines never returned while every other stage was fast.
   Coastal NHD has cyclic flowline graphs (tidal channels, canals, braided
   and divergent reaches), and the naive iterative post-order re-pushed cycle
   nodes forever. Fixed with a cycle-safe DFS that skips back-edges.

6. **Rotated D8 pointer convention (the decisive one).** See below.

## The decisive pivot: the junction-count anomaly

The first clean run reported PH losing to the whitebox ceiling on all three
criteria, with PH junction counts 25 to 40 times below NHD's. The tempting
narrative was "topological abstraction: the merge tree is a coarser, valid
network." We refused it. The discriminating diagnostic counted the merge-tree
anatomy on one tile: of 235,332 channel cells, 231,954 (98.6%) had zero
in-mask donors and the tree had 232,529 roots with 31 confluences. That is
not a coarse network, it is a graph shattered into one component per cell,
in direct violation of the Lemma (the donor merge tree is the channel
network, i.e. connected).

Rather than trust the WhiteboxTools docs, we recovered the pointer convention
empirically from the raster: the true receiver always has strictly higher
flow accumulation, so for each pointer value the correct offset is the one
where the neighbor's accumulation exceeds the cell's for ~100% of cells. The
recovery was unambiguous: WhiteboxTools uses 1=NE, 2=E, 4=SE, 8=S, 16=SW,
32=W, 64=NW, 128=N (grid 64-128-1 / 32-0-2 / 16-8-4). The code had assumed
the ESRI 1=E convention, a one-step (45-degree) rotation. Every receiver was
mis-routed 45 degrees, which on a thin channel mask sent it into a
non-channel cell, so almost no cell found its in-mask donor. After the fix,
the same tile went from 31 to 2,155 confluences and from 232,529 to 85 roots,
and PH junction counts came to match whitebox almost exactly. The entire
prior results table was a rotated-pointer artifact.

## Reflective answers

**What was the critical pivot that identified the cycles (bug 5)?** Not
guessing from the symptom. OOM and timeout are non-specific; many things
produce them. The per-stage timer localized the hang to one function on one
class of tile (coastal), and from there the reasoning was about what is
special about coastal NHD: its flowline graph is not a tree. The general
lesson: when a symptom is non-specific (hang, OOM), instrument to localize
the stage before forming a hypothesis, then ask what is special about the
inputs that fail.

**What do real-world cycles say about the topological approach?** Real
drainage data is not clean. The NHD reference graph carries cycles
(divergent, tidal, canal, braided reaches); the raw cubical mask carries tens
of thousands of spurious 8-adjacency cycles. The donor-graph construction is
a forest by D8 single-receiver definition, so it is H1 = 0 by construction.
The empirical cyclicity of the inputs is exactly what makes a
by-construction-acyclic channel-network metric worth having. The 48k-cycles
sidebar is the quantified version of that argument and it is independent of
every bug above.

**Was the 25-40x junction deficit a feature (topological abstraction)?**
No. This question came with the wrong premise. The diagnostic showed the
deficit was a 99%-disconnected graph, not a coarsening. After the fix, PH and
whitebox produce essentially identical junction counts (both ~2-3x NHD, as
two DEM-derived methods at the same threshold should, both denser than the
photo-digitized reference). There is no abstraction-driven reduction to
claim. The real topological advantages are elsewhere: H1 = 0 by construction,
and the favorable bifurcation-ratio gap. Recording this because the
near-miss is instructive: a favorable-sounding narrative was available for a
broken instrument, and only the mechanical check (count the roots) killed it.

**Claim A vs Claim B (candidate framing, for ratification, not settled).**
The corrected data supports Claim A (construct validity) cleanly: the
donor-graph merge tree ties the field-standard whitebox extraction on
junction-correlation and Strahler agreement with NHD, so it is a valid
channel-network representation, and it requires no claim of superiority to
establish that. Claim B (comparative advantage) has two seeds: the favorable
\|dR_b\| gap, which is one criterion at n=20 on a basin-scoped scalar with
known scoping sensitivity and so needs the dedicated comparative-advantage
analysis before it is a finding; and the H1 = 0 property, which is robust and
bug-independent. The honest synthesis the data buys is "A is met; B is a
favorable hint plus one robust structural property, pending analysis." The
final framing decision is the first author's and is deliberately not encoded
in the commit or ordained here.

## Cost finding (the implementation half of the motto)

The run was CPU-bound, full-tile at field resolution, no GPU, no windowing,
within a 4-hour wallclock on commodity cluster CPU. That is a real usefulness
claim for a methods paper: the evaluation is cheap enough to run on every
generator output without GPU. The same run also showed the pure-Python donor
union-find is the bottleneck (slow-karst/coastal breach starvation under
concurrency, two tiles needing serial reruns). Milestone 2 multiplies tiles
by generators by samples, so the numba/Cython port of the union-find is a
Milestone 2 prerequisite, not a wishlist item.

## What worked methodologically

Refusing to rationalize the anomaly; pausing before the framing call because
framing is downstream of whether the instrument is sound; verifying the
pointer convention empirically against the data rather than from docs; and
writing the regression test at the seam the toys could not reach (a
connectivity assertion on real whitebox output that fails on the pre-fix
code, verified by reverting the fix). The recurring failure shape
(untested whitebox-to-pipeline seams) is now recorded in memory
([[whitebox-d8-pointer-convention]]) and guarded by a test. The saddle-level
confound this surfaced for Milestone 2 is in
[m2_reference_forward_feed.md](m2_reference_forward_feed.md).

## Decided framing (ratified 2026-05-31)

Supersedes the candidate paragraph above. The Phase C validation section is
written as construct validity carried by parity, with the comparative
advantage carried by a structural guarantee rather than a scalar margin. The
weighting is set by whether each result was predicted in advance, which is
the hygiene mechanism (predicted = confirmatory and load-bearing; unpredicted
= exploratory and demoted), not by which result is more favorable.

1. **Primary, pre-registered: construct validity.** The donor-graph merge
   tree matches the WhiteboxTools agreement ceiling with NHD on junction
   correlation (0.936 vs 0.935) and Strahler Wasserstein (0.287 vs 0.287),
   and is within the pre-registered 95% bound on R_b. The metric recovers
   real channel networks. This is the correctly-scoped result, not a timid
   one: the paper's novelty is upstream (the theorem stack, flow-accumulation
   as the filtration, the generative-model evaluation regime), so the
   validation section does not need to carry novelty and should not try to.

2. **Comparative advantage, structural and predicted: H1 = 0 by
   construction.** The D8 donor relation is a function, so the donor-graph
   channel network is acyclic by construction. Spatial 8-adjacency stream
   extraction admits phantom confluences on subparallel tributaries and
   spurious loops on meander necks; the donor graph cannot. Predicted by the
   Phase 0 spike (cubical H1 = 8 vs donor 0) and the proof, confirmed at scale
   (median ~48,500 cycles per tile removed across 20 tiles). This is a
   structural guarantee, not a statistical claim, so it carries the advantage
   without needing n or significance testing. This is the load-bearing
   adjacency contribution.

3. **Favorable hint, exploratory: the R_b gap (0.185 vs 0.375).** One
   criterion, n = 20, a basin-scoped scalar from the family that produced the
   pointer-bug artifact. Reported, not leaned on, explicitly flagged for
   dedicated comparative-advantage analysis. It carries nothing it cannot
   bear.

Analogy that fixes the weighting (Osher-Sethian level sets, 1988): level sets
did not win by beating explicit meshes on static-droplet accuracy; they won
because they handle topological change by construction with no heuristic
surgery. The donor graph's claim has the same shape, an acyclic channel
network by construction with no phantom cycles, which is why validity parity
is sufficient and the structural guarantee is the contribution rather than a
scalar margin. Size the analogy to what it does: it illuminates the
contribution shape (parity plus a by-construction guarantee is a legitimate
result), not the magnitude. Level sets earned that framing across a large
body of topology-change problems; here the guarantee is one property
(acyclicity) shown on one toy and twenty tiles. Borrow the logic, not the
stature.
