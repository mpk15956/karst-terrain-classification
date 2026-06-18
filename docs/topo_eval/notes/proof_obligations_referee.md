---
title: "Proof obligations: referee-pass on the [open] items, the cardinality lemma, and the Adams/Cousty-Najman citations"
date: 2026-06-17
type: working-note
tags: [m2, proofs, cardinality-lemma, adams-2017, cousty-najman, persistence-image, stability, referee]
source: "subagent proof-research (read-only), grounded in verbatim Adams 2017 (arXiv:1507.06217) and Cousty-Bertrand-Najman-Couprie 2007/2009; verified by main session before integration"
---

This note parks the proof-research findings so the proof pass can execute from them. It is NOT yet integrated into `docs/topo_eval/proofs/strahler_merge_tree.qmd` or the manuscript Appendix; integration happens during the proof-obligations pass, after the main session verifies the MEDIUM-confidence flags against source. The cardinality lemma's PROVEN content is independent of the experiments; the stabilized-stability proposition's EMPIRICAL half still waits on Stage 1.

## Action items (for the proof pass)

To APPLY (settled, but verify the actual lines first per the verify-against-source rule):

1. §5 saddle-tie locus equation: the locus Sigma is an AFFINE HYPERPLANE carrying the D8 diagonal weights (steepest-descent tie weights diagonals by 1/sqrt(2)), not the bare `z'(a) = z'(b)` the file currently writes. The tie at cell c between neighbours a, b is `d_b * z'(a) - d_a * z'(b) + (d_a - d_b) * z'(c) = 0`. The measure-zero conclusion is unaffected, but a D8-fluent referee will catch the stated equation.
2. §5 stability wording: "Dgm_0 stable off Sigma" conflates routing-stability with diagram-stability. Restate as "off Sigma the flow graph is fixed, whence Theorem 3a applies," not as an independent stability claim.

To VERIFY myself before the lemma is final (MEDIUM-confidence flags):

3. Essential-class convention. The lemma's Step 1 assumed the infinite-persistence class (min A, infinity) is DROPPED before imaging (Adams omits infinite-persistence points). Our `stabilized.py` instead CAPS it at `diagram_cap` (1.5x max finite death), so it is included as one extra finite point. Confirm the bound still holds with the cap convention (it does: that is N+1 finite points, and the lemma's "+1" slack already absorbs it), and STATE our convention (cap, not drop) explicitly in the proof.
4. persim default weight conditions. Adams requires the weighting function to be (1) nonnegative and zero along the horizontal axis (the diagonal in birth-persistence coordinates), (2) continuous, (3) piecewise differentiable. persim's default is a persistence ramp (linear in persistence), which is zero at persistence 0, continuous, and piecewise differentiable, so it satisfies all three; confirm against the persim source and cite the exact weight we use.
5. Ground-metric constant. Adams W_p and the qmd's Theorem 3a (Cohen-Steiner/Edelsbrunner/Harer) are both L-infinity, so they compose cleanly. If any downstream step uses an L2 ground metric on the diagram plane the CONSTANT picks up a sqrt(2)/sqrt(5) factor (Adams carries exactly these in his own proof), but the N EXPONENT is unchanged. Do not double-count this against Adams' constant.

Still PENDING (blocked): the deep read of the 2019/2020 JMIV characterization paper. Its full PDF is Anubis bot-walled and absent from the corpus; the assessment below is from the bibliographic record plus abstracts only. The deep read is still required before citing it at theorem level.

## (1) Referee-pass on the three [open] items

None of the three markers is a hidden hole in a stated theorem.

- **Item 1 (§4, DEM-level realization arithmetic).** Not a theorem gap; the tree-level witness is the complete proof. This is a Phase B fixture-construction obligation: build two integer cell-count layouts whose D8 accumulations realize the same three death-heights. RESOLVABLE; the file's own round-4 correction already prescribes the fix (have `test_falsification.py` MEASURE `d_B(realized)` approximately 0, never assume it). Recommend the paper cite the tree-level witness as THE proof and present the grid realization as a confirmatory artifact.
- **Item 2 (§5, generic stability remark).** The only [open] with real deferred mathematical content, honestly deferred. Sub-claims: (a) the saddle-tie locus Sigma is a finite union of hyperplanes — RESOLVABLE by elementary affine geometry (see action item 1 for the corrected weighted equation); closed, measure-zero. (b) off Sigma there is a uniform delta on compacts below which routing/A/Dgm are constant — RESOLVABLE by standard compactness (off Sigma each argmin is strict, slope-difference functions bounded away from 0 on a compact disjoint from Sigma); see action item 2 for the wording. (c) breach-and-fill does not map positive measure onto Sigma — GENUINELY HARDER, correctly deferred (breach-and-fill is itself a discontinuous piecewise map that can carve flats onto Sigma; needs a transversality argument specific to Whitebox's algorithm). VERDICT: the qualitative claim the paper actually USES (instability confined to a measure-zero saddle-tie locus, drainage-real where it occurs) is supportable by (a)+(b) alone. Keep the full generic-stability theorem as future work, labeled a remark, not a theorem.
- **Item 3 (§6, D8 vs D-infinity).** Not an open obligation; a correctly-drawn, SOUND scope boundary. Under any multiple-receiver scheme out-degree exceeds 1, Fact B's hypothesis fails, the flow graph is a DAG with non-disjoint in-trees, and the Lemma's merge-tree-to-channel-network bijection (which rests on Fact B) genuinely breaks. Optional non-required strengthening: note that sublevel-set persistence of A on the DAG is still well-defined and bottleneck-stable (Theorem 3a needs only a finite complex, not a forest), so only the Strahler-coarsening half is lost under D-infinity, not the stability half. Keep as a scope note.

## (2) Finite-diagram cardinality lemma (draft)

Notation per the qmd. Adams 2017 §3 (verbatim): `W_p(B, B') = inf over bijections gamma of (sum ||u - gamma(u)||_inf^p)^(1/p)`; the p=1 case `W_1` is a PLAIN SUM of L-infinity ground costs, no root. Bottleneck `d_B = W_inf = inf_gamma sup ||u - gamma(u)||_inf`. Diagonal points have infinite multiplicity (Adams convention).

**LEMMA (cardinality bound; bottleneck implies 1-Wasserstein for flow-accumulation H0).** Fix a flow graph G on grid G; let A, A' be two accumulation fields on it (the Theorem 3a setting: same graph). Let N be the number of off-diagonal (finite) points of `Dgm_0(A|G)`. Then

`W_1(Dgm_0(A), Dgm_0(A')) <= (N+1) * d_B(Dgm_0(A), Dgm_0(A')) <= (N+1) * ||A - A'||_inf`,

and `N = #{confluences} <= #{channel heads} - 1 < |M| <= |G|`. Hence `W_1 <= |G| * ||A - A'||_inf`.

**Proof.**
Step 1 (bottleneck to W_1 via cardinality). Let gamma* be an optimal bottleneck matching, delta = d_B. Both diagrams are finite (G finite). Under gamma* each point matches a point of the other diagram or the diagonal at L-infinity cost <= delta; diagonal-to-diagonal pairs cost 0, so only off-diagonal points contribute, at most (off-diag of A) + (off-diag of A') pairs. Reusing gamma* as a sub-optimal W_1 matching: `W_1 <= sum ||u - gamma*(u)||_inf <= (#contributing pairs) * delta`. By the qmd's Theorem 2 the elder rule gives exactly ONE finite class per merge node plus one essential class (min A, infinity); excluding the essential class from the diagram metric (Adams omits infinite-persistence points, footnote 7), each diagram has N off-diagonal finite points, N = #merge nodes. The "+1" is conservative slack for boundary bookkeeping (asymmetric counts or a capped/truncated essential class; see action item 3). Thus `W_1 <= (N+1) * delta`.
Step 2 (bottleneck to field). By Theorem 3a (CEH on the fixed finite 1-complex G), `delta <= ||A - A'||_inf`. So `W_1 <= (N+1) * ||A - A'||_inf`.
Step 3 (cardinality count). By the §2 Lemma, off-diagonal finite classes correspond to merge nodes, which correspond to confluences (branch cells with k >= 2 in-mask donors). In a forest, a rooted tree with L leaves and only arity >= 2 branchings has at most L - 1 internal branch nodes; summing over basins, `#confluences <= #heads - #basins < #heads`. Heads are leaves of G, a subset of M, so `#heads <= |M| <= |G|`. Hence `N < |M| <= |G|`, and `W_1 <= |G| * ||A - A'||_inf`. QED.

**Why the factor is N (linear), not sqrt(N).** Adams 2017 states persistence-IMAGE stability with respect to the 1-WASSERSTEIN distance W_1 (Theorems 1 and 2). For p=1 the cost is a plain SUM, so bounding each of N terms by d_B gives `W_1 <= N * d_B`, a linear factor. sqrt(N) would arise only for a W_2 bound (`W_2 = (sum cost^2)^(1/2) <= sqrt(N) * d_B`). But Adams Remark 1 PROVES the persistence-image kernel is NOT stable w.r.t. W_p for any 1 < p <= infinity, so W_2 is the wrong bridge and sqrt(N) is the wrong factor. The correct factor is N (an |G| bound). CONFIDENCE: HIGH, verified against verbatim Adams text.

**Chain to persistence-image stability (state, do not re-prove).** Composing with Adams Theorem 2:

`||I(rho_A) - I(rho_A')|| <= C_Adams * W_1(Dgm_0(A), Dgm_0(A')) <= C_Adams * |G| * ||A - A'||_inf`,

with `C_Adams = 10 * A_pix * (||f||_inf * |grad phi| + ||phi||_inf * |grad f|)` for the L-infinity image norm (A_pix = max pixel area), verbatim from Adams Theorem 2. The |G| factor is the price of the cardinality bridge and is unavoidable in the worst case (W_1 genuinely can be (#points) * bottleneck).

## (3) Citations (verbatim where quoted)

**Adams et al. 2017 (the load-bearing citation).** Henry Adams, Sofya Chepushtanova, Tegan Emerson, Eric Hanson, Michael Kirby, Francis Motta, Rachel Neville, Chris Peterson, Patrick Shipman, Lori Ziegelmeier, "Persistence Images: A Stable Vector Representation of Persistent Homology," JMLR 18(8):1-35, 2017 (arXiv:1507.06217).
- Birth-persistence transform (verbatim): "let T : R^2 -> R^2 be the linear transformation T(x, y) = (x, y - x), and let T(B) be the transformed multiset in birth-persistence coordinates." Surface `rho_B(z) = sum over u in T(B) of f(u) * phi_u(z)`, phi_u a normalized Gaussian.
- Weighting conditions (verbatim): "a nonnegative weighting function f : R^2 -> R that is zero along the horizontal axis, continuous, and piecewise differentiable." Three conditions: nonnegative and zero along the horizontal axis (the diagonal in birth-persistence coords); continuous; piecewise differentiable.
- Metric: the 1-WASSERSTEIN distance W_1 ("stability with respect to the 1-Wasserstein distance between PDs").
- Theorem 1 (surface): `||rho_B - rho_B'||_inf <= sqrt(10) * (||f||_inf*|grad phi| + ||phi||_inf*|grad f|) * W_1(B, B')`.
- Theorem 2 (image): `||I(rho_B) - I(rho_B')||_inf <= 10*A * (||f||_inf*|grad phi| + ||phi||_inf*|grad f|) * W_1(B, B')` (analogous L1 with 10*A_total, L2 with 10*sqrt(n)*A).
- Remark 1 (verbatim, the decisive corroboration of N not sqrt(N)): the kernel "is not stable with respect to W_p for any 1 < p <= infinity. That is, when 1 < p <= infinity there is no constant c such that ... ||I(rho_B) - I(rho_B')||_2 <= c * W_p(B, B')."

**Cousty/Najman watershed lineage.** J. Cousty, G. Bertrand, L. Najman, M. Couprie, "Watershed Cuts: Minimum Spanning Forests and the Drop of Water Principle," IEEE TPAMI 31(8):1362-1374, 2009 (ISMM 2007 full paper; DOI 10.1109/TPAMI.2008.173).
- Theorem 3.1 (verbatim): "Let S subset of E. The set S is a cut induced by a MSF relative to M(F) if and only if S is a watershed cut of F." Theorem 4.1 (verbatim): "The set S is a watershed of F if and only if S is a flow cut for F."
- Relevance: the canonical "watersheds ARE minimum spanning forests on an edge-weighted graph" statement, but DUAL to our object: Cousty's MSF lives on the SPATIAL edge-weighted graph and partitions by DIVIDES (the elevation/saddle side of the §7 duality), whereas our forest is the FLOW graph partitioned by CONFLUENCES. The qmd is correct to present the D8-flow-graph forest as a distinct object.

**2019/2020 characterization paper (deep read still pending; bibliographic + abstracts only).** Deise Santana Maia, Jean Cousty, Laurent Najman, Benjamin Perret, "Characterization of Graph-Based Hierarchical Watersheds: Theory and Algorithms," JMIV 62:627-658, 2020 (online 2019); DOI 10.1007/s10851-019-00936-6; HAL hal-02280023. Characterizes which hierarchies of partitions are hierarchical watersheds (nested watershed partitions induced by minimum spanning forests via extinction values on the MST / binary partition tree) and gives a quasi-linear recognition algorithm. It is the strongest existing statement that drainage-style hierarchies are EXACTLY characterized as minimum-spanning-forest sequences on an edge-weighted graph, i.e. the closest published thing to "the merge tree IS the network." Defensible distinctions to make explicit: (i) they build on the SPATIAL edge-weighted graph with a saliency/divide structure, whereas we build the merge tree on the D8 FLOW graph with the flow-ACCUMULATION scalar (the §7 elevation-vs-flow duality is exactly the gap); (ii) our Strahler coarsening (Theorems 1-2) and stability scope (Theorem 3) are not in their program. CAVEAT: confirm against the PDF before citing at theorem level.
