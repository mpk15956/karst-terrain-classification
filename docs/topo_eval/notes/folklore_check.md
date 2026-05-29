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

## Caveat resolved 2026-05-29: Cousty-Najman 2019 remains disjoint

A targeted second-pass read of Santana Maia, Cousty, Najman, Perret,
"Characterization of Graph-Based Hierarchical Watersheds," *JMIV*
2019/2020 (HAL hal-02280023v2; Springer 10.1007/s10851-019-00936-6),
plus its surrounding line (Cousty-Bertrand 2012 on edge/node-weight
equivalence, Najman-Cousty-Perret ISMM 2013, Perret-Cousty *TIP*
2018, and the authors' own Higra reference implementation), confirms
the framework is structurally disjoint from this paper's lemma.

**Structural distinctions.**

- *Scalar field.* Their framework ranks **edge weights** (or
  equivalent vertex weights via the Cousty-Bertrand 2012
  flooding-graph transform). The field is a dissimilarity/contrast,
  i.e. local. Our scalar is **flow accumulation $A$**, a vertex-valued
  *global* integral (drainage area). $A$ is neither a dissimilarity
  nor an edge weight; it does not reduce to either form.
- *Graph.* Their framework operates on any **undirected
  edge-weighted graph**; the imaging instances use spatial 4/8-grids
  with gradient/colour weights. Our graph is the **D8 flow graph**, a
  *directed* functional graph (each non-pit vertex points to its
  steepest receiver). The flow graph is the graph of a discrete vector
  field, not an edge-weighted graph in their sense.
- *Central construction.* Their key object is the **binary partition
  hierarchy by altitude ordering** (BPH): a Kruskal-style sequential
  union of edge endpoints in ascending edge-weight order, equivalent
  to MST construction; the hierarchical watershed is a pruning of the
  BPH by an attribute (area, volume, dynamics) of regional minima.
  Our object is the merge tree of a vertex sublevel filtration of $A$
  on the donor graph, swept by elder rule. BPH-by-edge-rank and
  merge-tree-by-vertex-sublevel are different filtrations even if the
  underlying graph were the same.
- *Hydrology vocabulary absent.* Their "watershed" is Beucher-Meyer
  flooding on a dissimilarity surface, used for image segmentation.
  Flow accumulation, drainage networks, and Horton-Strahler do not
  appear in the JMIV 2019 paper, its surrounding line, or Higra.

**Why the obvious unification attempt fails.** If one tried to
recover our lemma by setting their edge weights to $\max(A_u, A_v)$
on the D8 flow graph, two structural mismatches remain: (i) the
framework requires an undirected (or flooding-graph-symmetrizable)
graph and the D8 graph is directed; (ii) their hierarchy is built by
edge-rank Kruskal merges, so its leaves are individual pixels rather
than channel heads, and it does not equal the merge tree of $A$.

**Verdict.** Disjoint. The existing positioning in this note ("scalar
field is elevation or generic image gradient," "spatial adjacency,"
"Horton-Strahler/channel-network interpretation absent") survives.
No reframe is needed. The bijection lemma's framing as
folklore-formalization on a *directed* donor graph with a
*vertex-valued integral* scalar is the genuinely novel posture
relative to this body of work, and the donor-graph adjacency choice
is the sharpest surviving novelty point.

**Access caveat (pre-submission action, not blocking).** The verdict
above rests on the consistent abstract across multiple aggregators,
the surrounding-paper definitions (Cousty-Bertrand 2012 arXiv:1204.2837;
Najman-Cousty-Perret 2013; Perret-Cousty 2018), and the Higra reference
implementation by the same authors. The full JMIV PDF was 403-gated by
Anubis access control during the second-pass read. The residual risk
that the paper buries a directed-graph or vertex-integral
generalization outside its abstract and framework commitments is low,
but a 30-minute targeted skim of §§2–3 (definitions) and §6
(algorithms) on a campus-library copy before manuscript submission
will close it. Add to the pre-submission checklist.
