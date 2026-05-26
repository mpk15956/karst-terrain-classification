# Novelty-collision check: merge tree of flow accumulation

Targeted search 2026-05-26 for prior art on the methods paper's
load-bearing claim. The claim:

> The merge tree of the flow accumulation field A on a DEM, built
> by donor-based union-find on the D8 flow graph (restricted to the
> channel mask {A ≥ τ_channel}, swept in ascending A), recovers the
> watershed/channel-network hierarchy. Horton-Strahler stream order
> is a coarsening of this merge tree via the equal-vs-unequal-
> confluence rule.

The check was run as a parallel literature-search agent task while
the Phase 0 spike was being written. Three questions, three
findings.

## (a) Does any published paper state this merge-tree / watershed bijection?

**No explicit statement located.** The closest analogs all use
**elevation** as the scalar field whose merge tree gives a watershed
hierarchy, not flow accumulation:

- **TerraStream** (Danner, Mølhave, Yi, Agarwal, Arge, Mitasova,
  *ACM GIS 2007*). §3: "topological persistence … induces a merge
  tree on the sinks of T," where T is the elevation height-graph.
  The "watershed hierarchy" in §5 is the Pfafstetter recursive
  decomposition (Verdin & Verdin 1999; Arge et al. 2007),
  constructed downstream of flow accumulation but NOT as a merge
  tree of it. Persistence here ranks sinks by elevation depth, not
  by accumulation.
- **Agarwal, Arge, Yi**, "I/O-Efficient Batched Union-Find and Its
  Applications to Terrain Analysis" (*SoCG 2006*). Union-find on
  the height-graph (elevation, spatial adjacency) to compute
  persistence and contour trees. Not flow accumulation.
- **Cousty, Bertrand, Najman, Couprie**, "Watershed cuts: MSF and
  the drop of water principle" (*IEEE PAMI 2009*) plus the
  hierarchical-watershed line (Cousty-Najman ISMM 2011; JMIV 2019).
  Proves the watershed = MSF cut equivalence on edge-weighted
  graphs under spatial adjacency, scalar field is elevation or
  generic image gradient. The Horton-Strahler / channel-network
  interpretation is absent.
- **Fill-Spill-Merge** (Barnes et al.; Agarwal et al. *CACM 2023*).
  Depression/merge-tree of elevation for flood routing through
  depression hierarchies. Not flow accumulation, not Horton-
  Strahler.

## (b) Does any paper use flow-graph adjacency (rather than spatial-grid adjacency) to construct a topological invariant of a DEM's drainage network?

**No clean match.** Standard fast flow-accumulation algorithms
(Su et al. 2013 basin-tree-index; Zhou et al. *Frontiers of Earth
Science* 2018) use tree structures for COMPUTING accumulation
efficiently, not as topological invariants. Zhang & Jia 2020
"Watershed Merging" merges watersheds using neighboring-watershed
information as a depression-handling heuristic for flow direction
assignment in DAFAs, but not as the construction of a merge tree of
A. The bijection on the D8 flow graph (channel-restricted,
ascending-A sweep) appears unstated.

## (c) Does any paper apply persistent homology under a flow-accumulation filtration to a DEM at all?

**No**, confirming the May 2026 lit review at
[docs/literature/052626/1.md](../../literature/052626/1.md) §3.4
and the parallel content in the May 11 compass artifact.

## Implications for paper framing

The methods paper's contribution stack (as locked in
[_evaluation_conventions.md](../_evaluation_conventions.md) §4)
holds, with one refinement: the bijection itself, while not in the
literature as stated, is dense enough in the surrounding scaffolding
(TerraStream's elevation-persistence + Pfafstetter pipeline; Cousty
et al.'s watershed-as-MSF; Horton-Strahler's tree-pruning
combinatorics) that a reviewer who knows that scaffolding will see
the headline as "obvious in hindsight" unless the prose preempts
them.

**Concrete reframing for Phase A (light, not a contribution
downgrade):**

1. **Cite the bijection as formalizing a folklore correspondence**
   that prior work has approached from three sides (TerraStream's
   elevation-persistence + Pfafstetter pipeline; Cousty et al.'s
   watershed-as-MSF; Horton-Strahler's tree-pruning combinatorics)
   without uniting them on the flow-accumulation scalar.

2. **The donor-graph adjacency choice is the sharpest surviving
   novelty point.** None of the cited prior work constructs the
   merge tree on the D8 flow graph (donor adjacency); all use
   spatial-grid adjacency on the underlying height-graph or
   edge-weighted graph. This is a smaller methodological move than
   "fresh bijection" but a sharper one to defend. The Phase 0 spike
   provides empirical evidence that this choice matters: cubical
   8-adjacency produces phantom merges and spurious H₁ cycles on
   degenerate toys that the donor-graph construction removes.

3. **Lead with the evaluation regime as the headline** (already
   independently novel per the May 2026 scan); position the
   merge-tree / Horton-Strahler bijection as a clarifying lemma
   that makes the regime's outputs interpretable, citing
   TerraStream and Agarwal-Arge-Yi as the nearest prior work on
   terrain merge-trees.

The proposal.md rewrite picks this up. The paper's contributions in
order of novelty strength:

1. Evaluation regime (no prior PH-based eval of generative terrain;
   no prior flow-accumulation filtration on a DEM).
2. Donor-graph adjacency for the merge-tree construction (no prior
   terrain merge-tree built on flow-graph rather than spatial-grid
   adjacency).
3. PD coarsening loss characterization (what abelianizing the merge
   tree forgets; falsification toy as empirical companion).
4. Field-level stability with honest scope (CEH 2007 on A;
   honest framing of DEM→A instability as drainage property).

The bijection lemma sits between (2) and (3) as the
folklore-formalization step that makes the rest interpretable.

## Caveat: one deep read before final submission

The Cousty-Najman hierarchical-watershed line is large. Specifically,
**"Characterization of Graph-Based Hierarchical Watersheds"**
(Cousty, Najman, et al., *Journal of Mathematical Imaging and
Vision* 2019) formalizes hierarchical watersheds in graph-theoretic
language closest to this paper's claim. A deep read before final
submission would catch any near-overlap that the agent search did
not surface from abstracts alone. Add to the Phase A pre-submission
checklist.
