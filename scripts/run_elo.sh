#!/bin/bash
# Round-robin self-play Elo measurement for a shogi training run.
#
# Picks the weight_iter_<N>.pt checkpoints at a given training-step interval,
# plays a round robin between them, and writes the results + a paper-ready
# report (CSV, Elo curve png/pdf with bootstrap CI) into the training dir.
#
# Round robin cost grows with (models)^2, and every model is held as a live
# engine process for the whole run, so prefer a coarse interval (fewer, well
# spaced checkpoints) -- STEP=5000 gives 13 models / 78 pairs, a clean curve.
#
# Usage (inside the container, from /workspace):
#   ./scripts/run_elo.sh TRAIN_DIR [STEP] [GAMES] [CONF] [GPU]
#   e.g.  ./scripts/run_elo.sh shogi_9x9_restnet64_v2 5000 50
set -e

NAME=${1:?Usage: $0 TRAIN_DIR [STEP] [GAMES] [CONF] [GPU]}
STEP=${2:-5000}
GAMES=${3:-50}
CONF=${4:-configs/9x9_shogi/RRTRRT-bigserver.cfg}
GPU=${5:-0}

MODEL_DIR="${NAME}/model"
[ -d "${MODEL_DIR}" ] || { echo "no model dir: ${MODEL_DIR}" >&2; exit 1; }

# highest available training step
MAX=$(ls "${MODEL_DIR}"/weight_iter_*.pt 2>/dev/null \
      | sed -E 's/.*weight_iter_([0-9]+)\.pt/\1/' | sort -n | tail -1)
[ -n "${MAX}" ] || { echo "no weight_iter_*.pt in ${MODEL_DIR}" >&2; exit 1; }

# checkpoints on the STEP grid, plus the final one, deduplicated
steps=$( { seq 0 "${STEP}" "${MAX}"; echo "${MAX}"; } | sort -n -u )
models=()
for n in ${steps}; do
    f="${MODEL_DIR}/weight_iter_${n}.pt"
    [ -f "${f}" ] && models+=(--model "${f}")
done

count=$(( ${#models[@]} / 2 ))
pairs=$(( count * (count - 1) / 2 ))
echo "evaluating ${count} models from ${NAME} (step ${STEP}, up to ${MAX})"
echo "  ${pairs} pairs x ${GAMES} games = $(( pairs * GAMES )) games"

CUDA_VISIBLE_DEVICES=${GPU} python3 scripts/shogi_elo.py run \
    --conf "${CONF}" --games "${GAMES}" \
    --results "${NAME}/elo_final.json" \
    --log     "${NAME}/elo_final.log" \
    --report  "${NAME}/elo_final" \
    "${models[@]}"

echo "done. outputs in ${NAME}/:  elo_final.{json,log,csv,png,pdf}"
