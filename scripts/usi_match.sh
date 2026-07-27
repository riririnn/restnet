#!/bin/bash
# Measure the Elo between a restnet model and an external USI engine
# (YaneuraOu + Suisho5 / Elmo).
#
# Usage (inside the container, from /workspace):
#   ./scripts/usi_match.sh MODEL GAMES TIME [EVAL_DIR]
#
#   MODEL     : restnet model .pt (required)
#   GAMES     : number of games, colors alternate (required)
#   TIME      : seconds/move (required)
#   EVAL_DIR  : YaneuraOu eval folder (default: eval)
#                 eval       = Suisho5   (engines/YaneuraOu/source/eval)
#                 eval_elmo  = Elmo NNUE (engines/YaneuraOu/source/eval_elmo)
#
# Example: iter 60000 vs Suisho5, 20 games, 1 second/move
#   ./scripts/usi_match.sh shogi_9x9_restnet64_v2/model/weight_iter_60000.pt 20 1.0
#   # vs Elmo
#   ./scripts/usi_match.sh shogi_9x9_restnet64_v2/model/weight_iter_60000.pt 20 1.0 eval_elmo
#
# Prints the per-game log and a summary (W-D-L, score%, Elo diff).
set -e

MODEL=${1:?Usage: $0 MODEL GAMES TIME [EVAL_DIR]}
GAMES=${2:?Usage: $0 MODEL GAMES TIME [EVAL_DIR]}
TIME=${3:?Usage: $0 MODEL GAMES TIME [EVAL_DIR]}
EVAL_DIR=${4:-eval}

CONF=configs/9x9_shogi/RRTRRT-bigserver.cfg
YANE=/workspace/engines/YaneuraOu/source/YaneuraOu-by-gcc

REC="usi_rec_$(basename "$MODEL" .pt)_${EVAL_DIR}"

python3 scripts/usi_bridge.py \
    --conf "$CONF" --model "$MODEL" \
    --usi-engine "$YANE" \
    --usi-option Threads=1 --usi-option USI_Hash=1024 \
    --usi-option NetworkDelay=0 --usi-option NetworkDelay2=0 \
    --usi-option EvalDir="$EVAL_DIR" \
    --games "$GAMES" --time-per-move "$TIME" \
    --record-dir "$REC"

echo "game records (USI, openable in ShogiHome) saved to $REC/"
