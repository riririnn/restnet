#!/bin/bash
# Phase-based curriculum training for shogi.
#
# The curriculum axis is the move cap (env_shogi_max_moves):
#   Phase A (iter   1- 50): cap 200 — force decisive games, learn material value fast
#   Phase B (iter  51-150): cap 300 — allow longer battles
#   Phase C (iter 151-300): cap 500 — near-normal shogi
# Raise/remove the cap further (env_shogi_max_moves=0) manually once the model
# ends most games by mate (check with ./scripts/sgf_stats.sh).
#
# actor_mcts_reward_discount=0.99 (set in the .cfg) makes faster wins more
# valuable, pushing the model toward mating instead of waiting for adjudication.
#
# Usage (inside the container, from /workspace):
#   ./scripts/curriculum_train.sh NAME [GPU_LIST]
#   e.g. ./scripts/curriculum_train.sh shogi_9x9_curriculum_n64 0
#
# Notes:
# - Phases B/C continue from the same training directory (answers the
#   (C)ontinue prompt automatically).
# - actor_select_action_softmax_temperature_decay uses zero_end_iteration of
#   the *current run*, so the temperature schedule restarts each phase; this is
#   acceptable (each phase re-explores briefly after its rule change).
set -e

NAME=${1:?Usage: $0 NAME [GPU_LIST]}
GPU=${2:-0}
GAME=shogi
CFG=configs/9x9_shogi/RRTRRT.cfg

phase() {
    local end_iter=$1 conf_str=$2
    echo "===== phase up to iter ${end_iter}: ${conf_str} ====="
    # "C" answers (R)estart/(C)ontinue, "y" confirms; harmless on a fresh dir
    printf "Cy" | ./tools/quick-run.sh train ${GAME} ${CFG} ${end_iter} \
        -n "${NAME}" -g "${GPU}" -b 256 -c 8 -conf_str "${conf_str}"
}

# Phase A: short games, decisive results, fast material learning
phase 50  "env_shogi_max_moves=200"

# Phase B: longer battles
phase 150 "env_shogi_max_moves=300"

# Phase C: near-normal shogi
phase 300 "env_shogi_max_moves=500"

echo "curriculum finished. Check endgame stats with:"
echo "  ./scripts/sgf_stats.sh ${NAME}"
