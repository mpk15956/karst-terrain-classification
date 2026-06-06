#!/usr/bin/env bash
# Submit the MESA-vs-real substrate comparability probe to GACRC teach (CPU).
#
# Usage (teach LOGIN node, from repo root):
#   scripts/submit_comparability_teach.sh [mesa_dir] [manifest] [run_name]
#
# The pre-registered gate that must clear before the 113-patch batch's MMD is
# trusted: (A) H0 scale-invariance under rescaling, (B) MESA patches in the real
# range on scale-free routing descriptors. Runs in the project pixi env; offline
# on staged GLO-30 + the generated MESA patches.
set -euo pipefail

MESA_DIR="${1:-results/validity/mesa_small}"
MANIFEST="${2:-results/validity/teach_run_20260530/tile_manifest.json}"
RUN_NAME="${3:-comparability}"

PARTITION="batch"; ACCOUNT="geog4592"; CORES=16; MEM="48G"; WALLTIME="02:00:00"

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
\$PY -u scripts/substrate_comparability_probe.py \
  --manifest ${MANIFEST} --glo30-dir data/glo30 --mesa-dir ${MESA_DIR} \
  --out results/validity/substrate_comparability.json --cpus ${CORES}
SB

echo "wrote $SBATCH_FILE"
echo "submit with: sbatch $SBATCH_FILE"
