#!/usr/bin/env bash
#SBATCH --job-name=m2stab_sweep
#SBATCH --partition=batch
#SBATCH --account=geog4592
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=/home/mpk15956/karst-terrain-classification/logs/m2stab_sweep_%j.out

# Stage 0.5: pre-registered amplitude sweep for the saddle-stable statistic, on the
# saddle-probe corpus (whole 30 m tiles with known ground truth). CPU-only; the per
# realization whitebox D8 is the cost and stays SERIAL (whitebox races on its shared
# install dir under a process pool), so walltime is over-provisioned rather than the
# loop parallelized. Each realization is single-receiver D8 (a forest, beta1 = 0).
set -euo pipefail
cd "/home/mpk15956/karst-terrain-classification"
PY="/home/mpk15956/karst-terrain-classification/.pixi/envs/cpu/bin/python"

$PY -u scripts/m2_stabilized.py sweep \
  --manifest results/validity/teach_run_20260530/tile_manifest.json \
  --n-tiles 8 \
  --J 16 \
  --out results/validity/m2_stabilized_sweep.json
