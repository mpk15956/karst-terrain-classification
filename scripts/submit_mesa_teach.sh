#!/usr/bin/env bash
# Submit a MESA generation batch to GACRC teach franklin_gpu (A30).
#
# Usage (teach LOGIN node, from the repo root):
#   scripts/submit_mesa_teach.sh <out_dir> <counts> [run_name]
#   e.g. scripts/submit_mesa_teach.sh results/validity/mesa_small \
#          cumberland_plateau=5,appalachian_highlands=5,coastal_plain=5 mesa_small
#
# Runs scripts/mesa_generate.py in the MESA conda env (venv_geoai) on a GPU node
# (offline; node has no internet). Emits one 768px DEM .npy per inference call +
# manifest.json with the pre-registered province prompts. A MESA call = one patch
# (the MMD unit), so <counts> is in PATCHES per province.
set -euo pipefail

OUTDIR="${1:?usage: submit_mesa_teach.sh <out_dir> <counts> [run_name]}"
COUNTS="${2:?missing counts, e.g. cumberland_plateau=5,appalachian_highlands=5,coastal_plain=5}"
RUN_NAME="${3:-mesa_gen}"

# ---- teach GPU knobs (franklin_gpu: A30 24GB) ------------------------------
PARTITION="franklin_gpu"
ACCOUNT="geog4592"
GRES="gpu:A30:1"
CORES=4
MEM="32G"
WALLTIME="01:00:00"   # padded; ~15 patches is ~10-15 min incl. model load
# The MESA env is a PREFIX conda env inside the repo (torch 2.6.0+cu124,
# transformers 4.51.1, diffusers 0.32.2). Call its python directly -- no
# conda activate needed, and avoids conda-init issues on the compute node.
MESA_PY="/home/mpk15956/mesa/.condaenv/bin/python"
# ---------------------------------------------------------------------------

REPO="$(pwd)"
mkdir -p "$OUTDIR" logs
SBATCH_FILE="$(dirname "$OUTDIR")/${RUN_NAME}.sbatch"

cat > "$SBATCH_FILE" <<SB
#!/usr/bin/env bash
#SBATCH --job-name=${RUN_NAME}
#SBATCH --partition=${PARTITION}
#SBATCH --account=${ACCOUNT}
#SBATCH --gres=${GRES}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${CORES}
#SBATCH --mem=${MEM}
#SBATCH --time=${WALLTIME}
#SBATCH --output=${REPO}/logs/${RUN_NAME}_%j.out

set -euo pipefail
cd "${REPO}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

${MESA_PY} -u scripts/mesa_generate.py --out "${OUTDIR}" --counts "${COUNTS}"
SB

echo "wrote $SBATCH_FILE"
echo "submit with: sbatch $SBATCH_FILE"
