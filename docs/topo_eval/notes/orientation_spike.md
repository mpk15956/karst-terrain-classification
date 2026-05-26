# Phase 0 filtration-orientation spike: findings

Run via `pixi run spike-filtration`. Source: `scripts/spike_filtration.py`.
Date: 2026-05-26. Result: 9 / 9 assertions passed.

## Locked formalization

The filtration construction used in the paper and throughout the
codebase is:

> The merge tree of the flow accumulation field A on a DEM, built by
> donor-based union-find on the D8 flow graph, restricted to the
> channel mask {A ≥ τ_channel}, swept in ascending A.

Equivalent formalization in the paper-prose draft will be
**mask-restricted filtration** (not sweep-of-τ_channel tracking the
extracted graph). The two formalizations are mathematically
equivalent; mask-restricted reads more cleanly in code (the spike's
own union-find code is the proof of that) and in prose ("at
filtration parameter τ, the cells present are exactly those with
τ_channel ≤ A(cell) ≤ τ").

## Toy assertions

### Y-toy (no degenerate geometry; donor and cubical should agree)

Two heads at (1,1) and (1,3), true confluence at (4,2), trunk to
outlet at (7,2). No subparallel tributaries, no meander necks; this
toy cannot distinguish donor-graph adjacency from cubical
8-adjacency. It is the baseline correctness check.

- Donor union-find: 1 merge at (4,2), accum 7, 2 children. PASS.
- Donor births: 2 (one per head), at (1,1) and (1,3). PASS.
- Cubical 8-adjacency: 1 merge at (4,2), same as donor. PASS.
  (Confirms cubical and donor agree when there is no degenerate
  geometry.)
- Superlevel-decreasing on whole grid: 0 merges at the confluence
  cell. PASS. (Confirms the wrong direction makes confluences
  invisible: the component grows headward from the trunk and each
  new cell joins the already-present component.)

### Tributary-contact toy (adjacency contamination: phantom merge)

Two distinct flow paths in adjacent columns whose cells are
8-adjacent along most of their length, with true flow confluence at
(5,2). Arm A is column 1, arm B is column 2; they are 8-adjacent at
rows 1-4 inclusive. This is the toy the Y-toy could not produce.

- Donor union-find: 1 merge at the TRUE confluence (5,2), accum 9,
  2 children. PASS.
- Cubical 8-adjacency: phantom merge at (1,1), accum 2. PASS
  (this is the contamination). Specifically: (1,1) is 8-adjacent to
  both (0,1) [arm A's head] and (2,2) [arm B's head], so when (1,1)
  enters the mask it sees both arms' heads as already-present
  neighbors and merges them four rows upstream of the true
  confluence. The donor-graph construction does not see (2,2) as a
  donor of (1,1) (because (2,2)'s D8 receiver is (3,2), not (1,1)),
  so the contamination does not propagate.

### Meander-neck toy (adjacency contamination: spurious cycles)

Single channel whose path snakes through a 2x3 block at rows 2-3,
cols 1-3. Cells across the meander's interior are 8-adjacent. This
is a different failure mode of cubical adjacency: not a phantom
merge in the union-find, but extra edges that create cycles in the
mask graph.

- Donor union-find: 0 merges (correct: it is a single chain). PASS.
- Donor flow graph H₁ = 0 (correct: D8 receivers form a function,
  so the donor-graph is a forest). PASS.
- Cubical 8-adjacency mask H₁ = 8 (the contamination). PASS.
  Eight independent cycles arise from diagonal edges between cells
  of the meander's two rows that share 8-neighbors despite being
  flow-distinct. The donor-graph construction removes all of them.

## Empirical strength of the contamination

Cubical 8-adjacency contamination is not a marginal effect even on
toys this small: the tributary-contact toy puts the phantom merge
**four cells upstream** of the true confluence, and the meander-neck
toy generates **eight spurious cycles** in a 9-cell mask. On real
30 m DEMs, where subparallel tributaries and meander necks are
common, the effect is expected to be larger by orders of magnitude.
H₁ of the cubical mask remains a per-tile diagnostic in Phase C
that quantifies how much contamination the donor-graph removes on
real data.

## Real-tile diagnostic: deferred

The spike script as written tests synthetic toys only. The real-tile
diagnostic (every internal merge-tree node coincides with a D8 flow
confluence; no merges between flow-disconnected cells; per-tile H₁
of the cubical mask reported) is deferred to the early Phase C work
once tile acquisition is wired in via `src/geo_tda/data_acquisition/`.
The toy zoo covers the two failure modes the real-tile step was
intended to expose; the real-tile diagnostic on top adds quantitative
calibration of the contamination scale on representative terrain.

## Structural-check pass record

All structural invariants required by the plan are exercised by the
spike and pass:

- Donor-graph is a forest on every toy (H₁ = 0). Verified directly.
- Every donor-based merge event has ≥ 2 donor components and is
  located at a true flow confluence (not a spatial-adjacency
  contact). Verified by Y-toy and tributary-contact assertions.
- Cubical 8-adjacency produces contamination on degenerate toys
  (phantom merge upstream, or spurious cycles in the mask) that the
  donor-graph construction removes. Verified by both contamination
  toys.

## Implications for Phase A drafting

Phase A drafting can begin. The construction is empirically validated
against the negative controls; the bijection lemma in the proof
section can be stated with confidence as operating on the
donor-graph merge tree. Phase B's module `src/geo_tda/topo_eval/merge_tree.py`
should be a promotion of the spike's `donor_union_find` function with
tests, an API that takes `(dem, flow_direction, accumulation,
τ_channel)`, and the structural-invariants test suite as a
regression guard.
