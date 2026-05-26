# Topological evaluation of generative terrain models

**Status (2026-05-11):** Verification gates cleared per literature review in
[docs/literature/](literature/compass_artifact_wf-00716190-ad42-4c87-a495-27efa3a64aa4_text_markdown.md).
Two positioning reads remain (PTRM, TFDM); neither blocks implementation.

## The claim

Generative terrain models published since 2023 (eight or more, spanning
diffusion, flow matching, and GANs) evaluate primarily on FID, aggregate
elevation statistics, and qualitative renderings. These metrics are
insensitive to drainage-network topological pathology. A generator can
match scalar geomorphometric summaries while producing tiles with
disconnected basins, phantom loops, or broken watershed hierarchies.

This project proposes persistence-based distributional evaluation under
flow-accumulation filtration, benchmarks existing generators against it,
and reports findings about the field. The protocol stacks two moves
that are each individually absent from the surveyed literature (per
lit review 2026-05-11). First, persistence-based distributional testing
applied to generative *terrain*; closest priors are Khrulkov-Oseledets
Geometry Score (ICML 2018) and Horak et al. Topology Distance (AAAI
2021), both in generic image domains. Second, flow accumulation as the
filtration function for sublevel-set PH on a DEM; closest priors are
Sousbie (2010), Pranav et al. (MNRAS 2021), and Biagetti-Cole-Shiu
(2020), which use density-field filtrations on cosmic webs. The
contribution is the protocol and the benchmark, generator-agnostic.

## Why this paper stands alone

The first author has a separate constrained-diffusion paper (Helmholtz
decomposition, by-construction mass conservation, FastScape-integration
evaluation). If the topological-evaluation protocol were introduced in
that paper, the obvious reviewer critique is circularity: the metric was
designed to favor the proposed model. Even when the metric is
well-motivated independently, the appearance of circularity weakens both
contributions.

Sequencing the protocol paper first, on a benchmark that does not
feature the constrained generator as protagonist, establishes the
protocol as community infrastructure. The diffusion paper later cites
the protocol as the field's evaluation regime without anyone wondering
whether the metric was cooked. Heusel et al. ran the same play with FID.

## The three tests

### Test 1, per-tile topological pathology

For each generated tile, compute persistence diagrams under sublevel
filtration on elevation. Flag tiles whose topological features violate
hard physical constraints:

- H₀ classes with infinite persistence (disconnected components,
  impossible in continuous terrain).
- H₁ classes in regions where flow accumulation indicates no closed
  loop should exist.
- Basin counts outside the empirical distribution for the matched
  physiographic class.

Output is a per-generator defect rate.

### Test 2, distributional comparison

Compute persistence images (Adams et al., *JMLR* 2017) on a held-out
set of real tiles and on a matched set of generated tiles. Two-sample
test via the sliced-Wasserstein kernel (Carrière-Cuturi-Oudot, ICML
2017), significance via the Robinson-Turner permutation test
(*J. Applied & Computational Topology* 2017), and bootstrap
confidence bands per Fasy et al. (*Annals of Statistics* 2014).
Reports a $p$-value for "are the generated and real tile
distributions topologically distinguishable." Population-level analog
of Test 1; the headline metric. All required statistical machinery is
off-the-shelf.

### Test 3, drainage-network filtration

The methodologically distinctive test, and an independent novelty
claim. Standard sublevel filtration on elevation captures basin
topology mixed with surface-relief topology. Compute flow accumulation
on the generated DEM and run sublevel filtration on the derived field.
The resulting persistence diagram captures drainage-network topology
specifically, the geomorphologically load-bearing structure. Persistent
H₀ classes correspond to persistent drainage basins; their merger
structure encodes the watershed hierarchy.

The closest published precedent is cosmology's sublevel-set PH on
density fields (Sousbie 2010 / DisPerSE; Pranav et al., *MNRAS* 2021;
Biagetti-Cole-Shiu 2020; Heydenreich et al., *A&A* 2021;
Yip-Rouhiainen-Shiu 2023). Flow accumulation plays the role on terrain
that density plays on cosmic webs. The standard hydrology workflow
(threshold flow accumulation $\to$ extract channels $\to$ compute
Strahler) is formally equivalent to a superlevel-set filtration
parameterized by threshold; no paper has published this equivalence
as a PH protocol.

This filtration is more discriminating than elevation-filtration for
terrain validity. Terrain can look right under elevation while having
a broken drainage network.

## Verification status

The two pre-implementation gates have cleared per literature review.

### Gate 1, generator availability: cleared

Of 16 surveyed generative terrain models, 7 have confirmed runnable
code and weights ($\approx 44\%$). Tiered by task and architectural
family:

| Tier | Generator | Task | Architecture |
|---|---|---|---|
| 1 (unconditional) | MESA (Borne-Pons et al., CVPR-W 2025) | text-conditioned | latent diffusion |
| 1 (unconditional) | TerraFusion (Higo et al., CGI 2025) | sketch + text, joint H+T | latent diffusion |
| 1 (unconditional) | Goslin Terrain Diffusion (2025) | seed-consistent | hierarchical DDPM |
| 1 (unconditional) | Guérin et al. (SIGGRAPH Asia 2017) | sketch-conditioned | cGAN |
| 1 (unconditional) | Beckham & Pal (2017) | unconditional | DCGAN |
| 1 (inverse) | GrounDiff (Dhaouadi et al. 2025) | DSM $\to$ DTM | diffusion |
| 1 (inverse) | Diff-DEM (Lo & Peters, *GRSL* 2024) | void-filling | DDPM |
| 2 (verify code) | TDN (Hu et al., AAAI 2024) | sketch-conditioned | multi-level diffusion |
| 2 (not yet released) | Geodiffussr (Inui et al. 2025) | texture-from-DEM | flow matching |

The five Tier-1 unconditional / sketch-conditioned generators span
GAN, DCGAN, latent diffusion, and hierarchical DDPM. This is the
empirical core. The two Tier-1 inverse-problem generators (GrounDiff,
Diff-DEM) require a separate evaluation protocol (topology preservation
conditional on input) and likely belong in an appendix.

### Gate 2, prior art: cleared

No paper applies persistence-based distributional tests as an
evaluation regime for generative DEM/terrain models. Separately, no
paper uses flow accumulation as the filtration function for
sublevel-set PH on a DEM. Both novelty claims survive the targeted
search.

The hard-constrained-architecture claim for the separate
constrained-diffusion paper also survives: no surveyed terrain
generator imposes architectural mass conservation, Helmholtz
decomposition, or PDE-derived priors. The closest soft analog is TFDM
(Yu et al., *RSE* 2024), which uses ridge/valley feature lines as
soft guidance only.

### Remaining reads (positioning, not novelty)

- **PTRM** (Rajasekaran et al., *ACM Trans. Appl. Percept.* 2022, DOI
  10.1145/3514244). Most sophisticated existing terrain-specific
  metric: geomorphons plus deep features. Position the topological
  protocol as complementary axis (topology vs. perceptual realism),
  not competitive.
- **TFDM** (Yu et al., *RSE* 2024, DOI 10.1016/j.rse.2024.114386).
  Confirm feature-line guidance is soft, preserving the hard-constraint
  claim for the diffusion paper.

Neither read blocks implementation.

## Anticipated reviewer objections

**"Why not just FID?"** Compute and report FID/CLIP-FID alongside the
topological metric, then show that two terrains with identical FID can
diverge topologically. Kim et al. (NeurIPS 2023, TopP&R) made the
broader-domain critique verbatim: "Existing metrics, such as Inception
Score (IS), Fréchet Inception Distance (FID), and various Precision
and Recall (P&R) variants, rely heavily on support estimates derived
from sample features. However, the reliability of these estimates has
been overlooked... current methods not only fail to accurately assess
sample quality when support estimation is unreliable, but also yield
inconsistent results." Cite verbatim.

**"Why flow accumulation, not elevation?"** Demonstrate empirically:
elevation-superlevel-set PH conflates ridge structures of equal
elevation, while flow-accumulation filtration tracks drainage
hierarchy under threshold sweep. The threshold-sweep equivalence
$\equiv$ Strahler-order accumulation connects the protocol back to
established geomorphology (Horton 1945; Strahler 1952, 1957;
Rodríguez-Iturbe & Rinaldo 1997).

**"Differentiable training-time extension?"** Cite Brüel-Gabrielsson
et al. (AISTATS 2020) and Carrière et al. (2021) to show the loss can
be made trainable. Defer empirical training-time use to future work;
this paper's contribution is evaluation, not loss design.

**"Position vs. PTRM?"** PTRM (Rajasekaran et al. 2022) measures
perceptual realism via geomorphons plus deep features. The topological
protocol measures structural correctness via persistence under a
hydrologically meaningful filtration. Different axes; report both.

## What this repository already contains

The karst-terrain-classification work in `docs/report/` and
`docs/presentation/` is GEOG 6591 Fall 2025 coursework. It contributes:

- `src/geo_tda/`: raster IO, QA/QC, plotting, DEM acquisition. Reusable
  as the TDA harness for the new direction.
- Persistence computation via gudhi and cripser, validated on synthetic
  and real DEMs.
- Patch extraction and per-tile feature pipelines, adaptable to
  generator-output evaluation.

The karst classification result is not the headline of this directory
going forward. It is pilot data and infrastructure validation. The
original framing (TDA versus pretrained DL on karst classification) was
deprecated by the first author as methodologically weak; training cost
was a sunk cost under frozen features, removing the intended asymmetry.

## Composition with the broader portfolio

| Project | Role | Active in this repo? |
|---|---|---|
| MS thesis: 3DGS topology-preserving pruning for CubeSat edge (Mishra/MOCI) | PhD methods signal, edge engineering | No, separate repo |
| Topological evaluation of generative terrain (this paper) | Methods + benchmark, standalone | Yes, primary |
| Constrained diffusion (Helmholtz, mass-conservation by construction) | Methods, "structural priors over spatial data" | No, separate repo |
| Spatial fairness | In progress | No, separate repo |

The four projects share one research identity: structural priors over
spatial data. This paper's role in the portfolio is to give the
diffusion paper a non-circular evaluation regime to plug into later.

## Project-level conventions

Reproducibility stack follows user-wide §5: `Containerfile` as canonical
install record, pixi for dependencies, `pixi.lock` committed alongside
`pyproject.toml`. README structure follows §6: one labeled section per
audience, no chained-command setup.

Per user-wide §3, prose in deliverables (.qmd, .md, paper draft) uses
no em dashes, no AI-tell hedge openers, no tricolons of three, no
trailing summaries.

Per §1 and §2, claims of work landed in tracked methodology files must
include the git diff hunk in the agent report, and pre-commits to
tracked methodology files must be committed before agent handoffs.
