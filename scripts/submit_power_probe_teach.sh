#!/usr/bin/env bash
# Submit one stage of the optical power probe to GACRC teach.
#   perturb -> project env, batch CPU (whitebox SERIAL; randomized trenches + H0 + render)
#   embed   -> MESA env, franklin_gpu (CLIP + Inception on base/pert renders)
#   curve   -> project env, batch CPU (MMD^2/floor curves vs f; reads the branch)
# Run in order: perturb, embed, curve.
set -euo pipefail
STAGE="${1:?usage: submit_power_probe_teach.sh <perturb|embed|curve>}"
ACCOUNT="geog4592"; REPO="$(pwd)"; mkdir -p logs
MANIFEST="results/validity/teach_run_20260530/tile_manifest.json"
PROJ_PY="${REPO}/.pixi/envs/cpu/bin/python"
MESA_PY="/home/mpk15956/mesa/.condaenv/bin/python"
SB="results/validity/power_${STAGE}.sbatch"

case "$STAGE" in
  perturb)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=pp_perturb
#SBATCH --partition=batch
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=${REPO}/logs/pp_perturb_%j.out
set -euo pipefail
cd "${REPO}"
${PROJ_PY} -u scripts/m2_power_perturb.py --manifest ${MANIFEST} --tiles-per-province 2
SBF
    ;;
  embed)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=pp_embed
#SBATCH --partition=franklin_gpu
#SBATCH --account=${ACCOUNT}
#SBATCH --gres=gpu:A30:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=${REPO}/logs/pp_embed_%j.out
set -euo pipefail
cd "${REPO}"
${MESA_PY} -u scripts/m2_power_embed.py
SBF
    ;;
  curve)
    cat > "$SB" <<SBF
#!/usr/bin/env bash
#SBATCH --job-name=pp_curve
#SBATCH --partition=batch
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=${REPO}/logs/pp_curve_%j.out
set -euo pipefail
cd "${REPO}"
${PROJ_PY} -u scripts/m2_power_curve.py --cpus 24
SBF
    ;;
  *) echo "unknown stage $STAGE"; exit 1 ;;
esac
echo "wrote $SB"; sbatch "$SB"
