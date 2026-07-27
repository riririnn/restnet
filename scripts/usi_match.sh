#!/bin/bash
# Measure the Elo between a restnet model and an external USI engine
# (YaneuraOu + Suisho5 / Elmo).
#
# Usage (inside the container, from /workspace):
#   ./scripts/usi_match.sh MODEL GAMES TIME [EVAL_DIR] [NODES]
#
#   MODEL     : restnet model .pt (required)
#   GAMES     : number of games, colors alternate (required)
#   TIME      : seconds/move for restnet (required)
#   EVAL_DIR  : YaneuraOu eval folder (default: eval)
#                 eval       = Suisho5   (engines/YaneuraOu/source/eval)
#                 eval_elmo  = Elmo NNUE (engines/YaneuraOu/source/eval_elmo)
#   NODES     : YaneuraOu NodesLimit handicap; 0 = full strength (default: 0)
#                 lower = weaker opponent. Sweep this to find the level where
#                 restnet is ~50% (its strength anchored to a fixed opponent).
#
# Examples:
#   # vs full-strength Suisho5, 20 games, 1s/move
#   ./scripts/usi_match.sh shogi_9x9_restnet64_v2/model/weight_iter_60000.pt 20 1.0
#   # vs Elmo weakened to 100 nodes/move
#   ./scripts/usi_match.sh shogi_9x9_restnet64_v2/model/weight_iter_60000.pt 20 1.0 eval_elmo 100
#
# Prints the per-game log and a summary (W-D-L, score%, Elo diff).
set -e

MODEL=${1:?Usage: $0 MODEL GAMES TIME [EVAL_DIR] [NODES]}
GAMES=${2:?Usage: $0 MODEL GAMES TIME [EVAL_DIR] [NODES]}
TIME=${3:?Usage: $0 MODEL GAMES TIME [EVAL_DIR] [NODES]}
EVAL_DIR=${4:-eval}
NODES=${5:-0}

CONF=configs/9x9_shogi/RRTRRT-bigserver.cfg
YANE=/workspace/engines/YaneuraOu/source/YaneuraOu-by-gcc

REC="usi_rec_$(basename "$MODEL" .pt)_${EVAL_DIR}_n${NODES}"

python3 scripts/usi_bridge.py \
    --conf "$CONF" --model "$MODEL" \
    --usi-engine "$YANE" \
    --usi-option Threads=1 --usi-option USI_Hash=1024 \
    --usi-option NetworkDelay=0 --usi-option NetworkDelay2=0 \
    --usi-option EvalDir="$EVAL_DIR" --usi-option NodesLimit="$NODES" \
    --games "$GAMES" --time-per-move "$TIME" \
    --record-dir "$REC"

echo "game records (USI, openable in ShogiHome) saved to $REC/"
