#!/usr/bin/env bash
# Submit one stage of the optical-metric contrast to GACRC teach.
#
# Usage (teach LOGIN node, repo root):  scripts/submit_optical_teach.sh <stage>
#   render   -> project pixi env, batch CPU (rasterio+numpy; parallel-safe)
#   embed    -> MESA conda env, franklin_gpu (torch/torchvision/CLIP, offline)
#   contrast -> project pixi env, batch CPU (distributional + FID/KID)
#
# Run in order: render, then embed, then contrast (each reads the previous
# stage's output under results/validity/m2_optical_cache/).
set -euo pipefail
STAGE="${1:?usage: submit_optical_teach.sh <render|embed|contrast>}"
ACCOUNT="geog4592"; REPO="$(pwd)"; mkdir -p logs
MANIFEST="results/validity/teach_run_20260530/tile_manifest.json"
PROJ_PY="${REPO}/.pixi/envs/cpu/bin/python"
MESA_PY="/home/mpk15956/mesa/.condaenv/bin/python"
SB="results/validity/optical_${STAGE}.sbatch"

case "$STAGE" in
  render)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=opt_render
#SBATCH --partition=batch
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --output=${REPO}/logs/opt_render_%j.out
set -euo pipefail
cd "${REPO}"
${PROJ_PY} -u scripts/m2_optical_render.py --manifest ${MANIFEST} --cpus 16
SBF
    ;;
  embed)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=opt_embed
#SBATCH --partition=franklin_gpu
#SBATCH --account=${ACCOUNT}
#SBATCH --gres=gpu:A30:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=${REPO}/logs/opt_embed_%j.out
set -euo pipefail
cd "${REPO}"
${MESA_PY} -u scripts/m2_optical_embed.py
SBF
    ;;
  contrast)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=opt_contrast
#SBATCH --partition=batch
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=${REPO}/logs/opt_contrast_%j.out
set -euo pipefail
cd "${REPO}"
${PROJ_PY} -u scripts/m2_optical_contrast.py
SBF
    ;;
  *) echo "unknown stage $STAGE"; exit 1 ;;
esac
echo "wrote $SB"; sbatch "$SB"
