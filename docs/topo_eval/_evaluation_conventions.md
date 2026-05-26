# Evaluation conventions for the topological-evaluation paper

Supplements [docs/proposal.md](../proposal.md) with operational
constraints not captured there. proposal.md states the claim, the
three tests, and the verification gates; this file states the rules
that condition how those tests are run, reported, and reused.

Per user-wide §1 and §2, these are tracked load-bearing methodology
pre-commits. Any claim conditioned on them must verify against this
file at a named HEAD commit, not against working-tree state.

## §1. Evaluation-metric and training-loss disjointness

The flow-accumulation persistence regime defined here is for
**evaluation only**. It will not be used as a training loss in the
same paper, the same model lineage, or the same author's adjacent
work (including the separate constrained-diffusion paper), without
an explicit independence argument carried in the manuscript that
uses it.

**Why.** A differentiable PH loss that trains the generator and a
PH-based metric that evaluates it are the same instrument used
twice. A model curve-fit to the scorer cannot be said to "satisfy"
drainage topology; the test has been optimized away. proposal.md
already defers training-time use to future work; this rule
upgrades that deferral to a hard lineage constraint, because
"future work" without a lineage rule lets the constraint slip the
first time it is convenient.

**How to apply.** When the constrained-diffusion paper later cites
this protocol as its evaluation regime, that is fine. When any
paper proposes using the same flow-accumulation PH construction as
a training objective, it must either (a) evaluate against a
disjoint topological metric, or (b) carry an explicit section
arguing why the dual use does not collapse to optimizing the test.

## §2. Validation on real DEMs only

Discriminative validity (the metric separates models other metrics
conflate) and construct validity (the metric tracks geomorphometric
quantities domain experts already use) are demonstrated against
real-DEM ground truth and against generators **other than** the
first author's own constrained-diffusion model. The constrained
model does not appear in the empirical core of this paper.

**Why.** A flow-accumulation filtration structurally rewards a
fluvial-erosion inductive bias, which is precisely what the
constrained-diffusion architecture encodes. Validating the metric
on the author's own generator is the maximally damaging referee
objection: "the ruler was built to measure your model as best."
The defense is sequencing plus disjointness of empirical core, not
post-hoc explanation.

**How to apply.** The empirical core stays the five Tier-1
unconditional/sketch-conditioned generators identified in
proposal.md (MESA, TerraFusion, Goslin Terrain Diffusion, Guérin
2017, Beckham & Pal 2017). The constrained-diffusion generator
does not appear in this paper's tables, figures, or appendices.
If the constrained-diffusion paper later wants to report numbers
under this protocol, it cites this paper and reports its own
numbers in its own venue.

## §3. Independence sequencing strength

This paper is preprinted or published in a venue with a public
DOI before the constrained-diffusion paper is submitted, not
merely drafted earlier. proposal.md says "sequenced first"; this
file makes "first" mean "with a citable identifier."

**Why.** The defensive value of independence is that a reviewer of
the diffusion paper can verify the metric existed and was
validated independently. A drafted-but-unposted protocol is not
verifiable; it reads as bespoke even if it was conceived first.
The minimum citable identifier is an arXiv preprint; a peer-
reviewed publication is stronger.

**How to apply.** When scoping the diffusion paper's timeline,
treat the topo-eval preprint posting as a hard upstream
dependency, not a parallel track. If the diffusion paper hits a
submission window before the topo-eval preprint is posted, the
diffusion paper either waits or evaluates with a different
regime; it does not introduce this protocol mid-paper.

## §4. Methods framing (locked 2026-05-26)

The contribution is framed as a methods paper, not a metrology
paper. The headline is the theorem stack: a Strahler-as-coarsening
result over the merge tree of the sublevel-increasing filtration of
flow accumulation restricted to the channel mask, built via
donor-based union-find on the D8 flow graph; the persistence
diagram coarsening loss characterization (what abelianizing the
merge tree forgets); and a field-level stability statement
inheriting from Cohen-Steiner-Edelsbrunner-Harer 2007. The
benchmark becomes supporting evidence.

**Why locked to methods.** Locking metrology would put the paper's
headline on the deliverable most likely to slip (the FID-blind
demonstration, which may require gradient-based adversarial DEM
construction) and would maximize the circularity exposure for the
downstream constrained-diffusion paper (a scoring metric tuned to
the same domain as the model is harder to defend than a filtration
that is generator-agnostic by construction). Methods framing also
fits the first author's research signature (by-construction-correct
methods, structural priors over spatial data) better than
metrology, which reads as "yet another generative-model evaluator"
in a genre that already has several.

**How to apply.** When drafting the paper, lead with the theorem
stack (bijection lemma, three theorems on PD coarsening / stability
/ evaluation regime); the benchmark is a validation section, not
the headline. proposal.md is rewritten to match. Target venue is
Earth Surface Dynamics (Copernicus, geomorphology methods);
backup is Remote Sensing of Environment methodology track.
Computational geometry venues are dropped because "merge tree of
superlevel filtration" is textbook CG and a pure-CG referee would
discount the contribution as applied recasting.

## §5. Hardware floor and run-scope honesty

The first author's local hardware is a 12 GB RTX 5070 desktop; a
compute-node GPU is pending. Several of the surveyed diffusion
generators will OOM at high resolution on 12 GB. The empirical
core is scoped to resolutions and sample counts that run on
available hardware; the paper reports the hardware floor
explicitly rather than implying A100-class throughput.

**Why.** Reproducibility-checklist credibility (per user-wide §6's
reproducer-audience contract) requires the reported pipeline to
actually run on the reported hardware. Underspecifying hardware
and overpromising resolution creates a reproduction gap that any
reviewer with a single-GPU workstation can flag.

**How to apply.** Per-generator resolution and sample-count
choices are documented in the experiment matrix with the GPU they
were produced on. The smoke tier (per user-wide §6) runs on the
12 GB card.

## §6. Citation hygiene for unpublished karst pilot

The karst pilot work in `docs/report/` and `docs/presentation/`
is GEOG 6591 Fall 2025 coursework, unpublished, and the first
author has not committed to publishing it. It is not cited in the
manuscript as a published precedent. Published karst/landslide-PH
precedents to cite instead are Syzdykbayev et al. (*RSE* 2020)
and Wu et al. (*Geomorphology* 2016).

This rule duplicates the corresponding item in
[the project memory](../../../../../../home/mpk15956/.claude/projects/-var-mnt-Data-Projects-karst-terrain-classification/memory/project_topo_eval_direction.md)
on purpose: the memory is a behavioral pointer for the assistant,
this file is the version-controlled paper-prose pre-commit.
