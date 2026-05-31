#!/usr/bin/env bash
# Submit the Phase C construct-validity run to GACRC teach.
#
# Usage (run on the teach LOGIN node, from the repo root):
#   scripts/submit_teach.sh <tile_manifest.json> [window] [run_name]
#
# Defaults: window=4096 (a 1-degree 3DEP tile is ~3600 px, so 4096 = full
# tile, no crop), run_name = the manifest's parent dir name.
#
# ---------------------------------------------------------------------------
# PREREQUISITES (do these on the login node first; it has internet, compute
# nodes do not):
#   1) Repo is on teach and the cpu env is installed:
#        pixi install -e cpu          # euchar/cripser are unused by Phase C;
#                                     # if they fail to build, drop them from
#                                     # pyproject pypi-deps for the install
#                                     # (they are not imported by topo_eval).
#   2) Inputs are staged for offline use:
#        pixi run -e cpu python scripts/prefetch_tiles.py <tile_manifest.json>
#
# VERIFY ON TEACH BEFORE FIRST SUBMIT (do not guess these):
#   - PARTITION: run `sinfo -s`; set PARTITION below (e.g. batch / highmem).
#   - ACCOUNT:   run `sacctmgr show assoc user=$USER format=account`; if an
#                account/allocation is required, set ACCOUNT and uncomment its
#                #SBATCH line in the heredoc.
#   - pixi reachable on compute nodes: a shared-filesystem install (this repo
#                under /home or /scratch) is visible to compute nodes; confirm
#                `pixi --version` works in an `salloc` shell, else load a module.
#   - This run uses the pixi env directly (NOT apptainer), because it runs the
#     edited source as-is and avoids the euchar container-build issue. To use
#     the container instead, build the .sif from a rebuilt OCI image and swap
#     the RUN line for `apptainer exec --bind "$PWD" karst.sif python ...`.
# ---------------------------------------------------------------------------
set -euo pipefail

MANIFEST="${1:?usage: submit_teach.sh <tile_manifest.json> [window] [run_name]}"
WINDOW="${2:-4096}"
RUN_NAME="${3:-$(basename "$(dirname "$MANIFEST")")}"

# ---- cluster knobs (verified on teach 2026-05-30/31) -----------------------
# With the cycle-safe _strahler fix, per-tile is ~1 min and ~1 GB (the earlier
# 900 GB / multi-hour blowups were an unbounded-stack hang on cyclic coastal
# flowline graphs, now fixed). So this runs on batch with 10 shards: ~2 waves,
# peak well under 80 GB, done in minutes.
PARTITION="batch"          # 6 idle CPU nodes, 128 GB each
ACCOUNT="geog4592"         # sacctmgr: the user's only assoc on teach
CORES=20                   # cpus-per-task; batch nodes have 32 cores
SHARDS=10                  # concurrent tiles -> 20 tiles = 2 waves
MEM="80G"                  # ample: peak ~10-30 GB across 10 tiles
WALLTIME="02:00:00"        # padded; real runtime is minutes
# ---------------------------------------------------------------------------

REPO="$(pwd)"
OUTDIR="results/validity/${RUN_NAME}"
mkdir -p "$OUTDIR/per_tile" logs
SBATCH_FILE="$OUTDIR/run.sbatch"

cat > "$SBATCH_FILE" <<SB
#!/usr/bin/env bash
#SBATCH --job-name=phaseC_${RUN_NAME}
#SBATCH --partition=${PARTITION}
#SBATCH --account=${ACCOUNT}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${CORES}
#SBATCH --mem=${MEM}
#SBATCH --time=${WALLTIME}
#SBATCH --output=${REPO}/logs/phaseC_${RUN_NAME}_%j.out

set -euo pipefail
cd "${REPO}"

# Use the env python directly, NOT 'pixi run': pixi run re-validates the
# manifest and would try to (re)build euchar/cripser, which are unused here
# and fail to build without a system compiler. The installed env is complete
# for Phase C.
PY="${REPO}/.pixi/envs/cpu/bin/python"

RUN="\$PY scripts/validity_real_construct.py \
  --manifest ${MANIFEST} --window ${WINDOW} --out ${OUTDIR}/construct.json"

# Fan tiles across cores; each shard writes per_tile/{key}.json as it goes,
# so a wallclock timeout or single-tile crash never loses completed tiles.
for k in \$(seq 0 \$(( ${SHARDS} - 1 ))); do
  \$RUN --shard \$k/${SHARDS} &
done
wait

# Roll the per-tile rows up into the summary (gap headline + secondary verdict).
\$PY scripts/validity_real_construct.py \
  --rollup-only --out ${OUTDIR}/construct.json
SB

echo "wrote $SBATCH_FILE"
echo "submitting..."
sbatch "$SBATCH_FILE"
echo
echo "monitor:  squeue -u \$USER"
echo "results:  $OUTDIR/construct.json  (+ per_tile/*.json)"
