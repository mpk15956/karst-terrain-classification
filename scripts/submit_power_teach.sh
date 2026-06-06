#!/usr/bin/env bash
# Submit the M2 spatial-split power analysis to GACRC teach.
#
# Usage (on the teach LOGIN node, from the repo root):
#   scripts/submit_power_teach.sh [manifest] [run_name]
#
# This is the FREE half of the headline experiment: the real-vs-real
# spatial-split null on staged GLO-30, whose band-vs-N curve is the greenlight
# criterion for the MESA generation batch. Compute only (offline); GLO-30 must
# already be staged under data/glo30/ (scripts/pull_glo30.py, on the login
# node, which has internet -- compute nodes do not).
#
# The refactored driver parallelizes H0 extraction across cores, caches the
# per-patch diagrams and the pairwise sliced-Wasserstein matrix once, then
# reads the power curve out by index lookup -- so the redundant SW recompute
# that timed out job 28556 (non-indexed power_curve) is gone. Re-runnable: a
# second submit reuses the cache and only re-tunes the curve.
set -euo pipefail

MANIFEST="${1:-results/validity/teach_run_20260530/tile_manifest.json}"
RUN_NAME="${2:-m2power}"

# ---- cluster knobs (teach batch: 32-core / 128 GB nodes) -------------------
PARTITION="batch"
ACCOUNT="geog4592"
CORES=24            # parallel patch extraction; <= 32 per node
MEM="64G"          # 768^2 patches are small; ample headroom
WALLTIME="04:00:00" # >=2x a few-min smoke; extraction+SW matrix is ~15 min
# ---------------------------------------------------------------------------

REPO="$(pwd)"
mkdir -p logs results/validity
SBATCH_FILE="results/validity/${RUN_NAME}.sbatch"

cat > "$SBATCH_FILE" <<SB
#!/usr/bin/env bash
#SBATCH --job-name=${RUN_NAME}
#SBATCH --partition=${PARTITION}
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${CORES}
#SBATCH --mem=${MEM}
#SBATCH --time=${WALLTIME}
#SBATCH --output=${REPO}/logs/${RUN_NAME}_%j.out

set -euo pipefail
cd "${REPO}"
PY="${REPO}/.pixi/envs/cpu/bin/python"

\$PY -u scripts/m2_power_analysis.py \
  --manifest ${MANIFEST} \
  --glo30-dir data/glo30 \
  --out results/validity/m2_power.json \
  --cache results/validity/m2_diag_cache \
  --cpus ${CORES}
SB

echo "wrote $SBATCH_FILE"
echo "submit with: sbatch $SBATCH_FILE"
