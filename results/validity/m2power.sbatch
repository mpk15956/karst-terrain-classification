#!/usr/bin/env bash
#SBATCH --job-name=m2power
#SBATCH --partition=batch
#SBATCH --account=geog4592
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/home/mpk15956/karst-terrain-classification/logs/m2power_%j.out

set -euo pipefail
cd "/home/mpk15956/karst-terrain-classification"
PY="/home/mpk15956/karst-terrain-classification/.pixi/envs/cpu/bin/python"

$PY -u scripts/m2_power_analysis.py   --manifest results/validity/teach_run_20260530/tile_manifest.json   --glo30-dir data/glo30   --out results/validity/m2_power.json   --cache results/validity/m2_diag_cache   --cpus 24
