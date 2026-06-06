#!/usr/bin/env bash
# Submit the M2 generated-vs-real MMD headline test to GACRC teach (CPU).
#
# Usage (teach LOGIN node, from repo root):
#   scripts/submit_m2test_teach.sh [mesa_dir] [manifest] [run_name]
#
# Extracts generated H0 diagrams (retry on transient), builds the real-gen +
# gen-gen SW blocks (the real-real block is cached), and tests generated-vs-real
# MMD^2 against the spatial null floor at the operating point. Project pixi env;
# offline on cached real diagrams + generated patches.
set -euo pipefail

MESA_DIR="${1:-results/validity/mesa_batch113}"
MANIFEST="${2:-results/validity/teach_run_20260530/tile_manifest.json}"
RUN_NAME="${3:-m2test}"

PARTITION="batch"; ACCOUNT="geog4592"; CORES=24; MEM="64G"; WALLTIME="04:00:00"

REPO="$(pwd)"; mkdir -p logs results/validity
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
\$PY -u scripts/m2_generated_vs_real.py \
  --manifest ${MANIFEST} --mesa-dir ${MESA_DIR} \
  --cache results/validity/m2_diag_cache \
  --power results/validity/m2_power.json \
  --out results/validity/m2_generated_vs_real.json --cpus ${CORES}
SB

echo "wrote $SBATCH_FILE"
echo "submit with: sbatch $SBATCH_FILE"
