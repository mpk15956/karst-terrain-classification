# Topological evaluation of generative terrain models

Persistence-based distributional evaluation for generative terrain
models (diffusion, flow matching, GAN). The goal is to surface
drainage-network topological pathology that current scalar metrics
(FID, Horton-Strahler ratio, slope-area scaling, hypsometric integral)
miss.

**Status (2026-05-11):** Proposal stage. See [docs/proposal.md](docs/proposal.md)
for the framework and the two open literature-verification gates.

The TDA infrastructure under `src/geo_tda/` was built for last
semester's karst classification project (GEOG 6591, Fall 2025) and is
being repurposed as the evaluation harness. Karst-specific analyses
live in [docs/report/](docs/report/) and [docs/presentation/](docs/presentation/)
as pilot work; the directory's project name lags the current focus and
will be reconciled at submission time.

## What's in here

```
src/geo_tda/             # raster IO, QA/QC, plotting, DEM acquisition
src/drp_2025fall/        # coursework: persistence on synthetic height matrices
src/earthscape-main/     # vendored upstream; has its own envs and tooling
notebooks/               # exploration + minimal feature-comparison notebooks
docs/proposal.md         # current framework (this project)
docs/report/             # karst pilot work, prior semester
docs/presentation/       # karst pilot work, prior semester (two audience cuts)
docs/literature/         # literature scans, dated MMDDYY/
scripts/smoke.py         # smoke test (the entry point for `pixi run smoke`)
data/processed/          # processed inputs (rasters, vectors)
```

The vendored `src/earthscape-main` keeps its own packaging story and is
not governed by this repo's pixi env.

## Quickstart

There are three audiences. Each has one command. Don't chain them.

### 1. Developer (editing code, on a machine with NVIDIA GPU)

```bash
pixi install
pixi run smoke    # ~seconds, sanity-checks the env
pixi run lab      # JupyterLab on http://localhost:8888
```

`pixi install` resolves the locked `default` environment, which uses
conda-forge `pytorch-gpu` and assumes a CUDA 12.x driver. On a CPU-only
machine, replace `pixi install` with `pixi install -e cpu` and use
`pixi run -e cpu <task>` for everything else.

Pre-condition: pixi on the `PATH`. Install via
`curl -fsSL https://pixi.sh/install.sh | bash`.

### 2. Release engineer (producing the OCI image)

```bash
pixi run image
```

Runs `podman build` against the `Containerfile` and produces
`karst-terrain-classification:latest`. The image bakes the locked CPU
environment. Pixi auto-installs the `default` env on first `pixi run`,
so this is one command from a fresh clone.

Pre-condition: podman on the host. Podman is host-level and not
pixi-installable.

### 3. Reproducer (running the published pipeline)

```bash
podman run --rm karst-terrain-classification:latest
```

The default container entrypoint runs `python /app/scripts/smoke.py`
and exits with code 0 on success. To run something else:

```bash
podman run --rm -v "$PWD:/workspace:Z" karst-terrain-classification:latest \
    python -c "import gudhi; print(gudhi.__version__)"
```

The `:Z` flag is required on Fedora/RHEL/Bazzite hosts (silent no-op
elsewhere).

## Reproduction tiers

The repo's compute is CPU-bound (TDA on small rasters). There is no HPC
floor: every cell of the experiment matrix runs on a single laptop
core.

| Tier    | Command                                       | Runtime     |
|---------|-----------------------------------------------|-------------|
| Smoke   | `podman run --rm karst-terrain-classification:latest` | seconds |
| Partial | not yet wired; use the notebooks under `notebooks/minimal_exploration/` | minutes |
| Full    | not yet wired; the planned driver lives in `scripts/` | TBD |

Smoke validates that the environment resolves and the TDA + raster IO
stack is functional. Partial and full reproduction paths land as the
generator-benchmarking driver is built.

## When dependencies change

Edit `pyproject.toml` under `[tool.pixi.dependencies]` or
`[tool.pixi.pypi-dependencies]`, then:

```bash
pixi install            # re-resolves and updates pixi.lock
pixi run image          # rebuild the OCI image to pick up the new lock
```

Commit both `pyproject.toml` and `pixi.lock` together.

## Containerfile as install record

The Containerfile is the canonical install record. A reader who doesn't
want to use a container can read it to learn what host libraries,
Python version, and packages are required to run the code from scratch.
