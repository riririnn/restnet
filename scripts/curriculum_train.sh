#!/bin/bash
# Adaptive curriculum training for shogi.
#
# The curriculum axis is the move cap (env_shogi_max_moves), but unlike a
# fixed iteration schedule, the cap is raised only when the model has
# outgrown it: after each chunk of iterations, if the average game length of
# the latest iteration drops below RAISE_RATIO x cap (i.e. games end well
# before the cap, by mate/resign), the cap advances 200 -> 300 -> 500 -> 0.
# If the model keeps hugging the cap, the cap simply stays — no forced switch.
#
# actor_mcts_reward_discount=0.99 (set in the .cfg) rewards faster wins,
# pushing toward mating instead of waiting for adjudication.
#
# Usage (inside the container, from /workspace):
#   ./scripts/curriculum_train.sh NAME [GPU_LIST]
#   e.g. ./scripts/curriculum_train.sh shogi_9x9_curriculum_n64 0
#
# Tunables (environment variables):
#   MAX_ITER=300      total iterations to train
#   CHUNK=1           iterations per training run before re-checking the metric
#   RAISE_RATIO=0.75  raise the cap when avg game length < RAISE_RATIO * cap
#
# Interrupt / resume:
#   Ctrl+C loses only the unfinished iteration. Re-run the same command —
#   progress is read from NAME/model/ and the current cap from NAME/*.cfg,
#   so training continues where it left off.
#   After Ctrl+C, check for leftover workers before resuming:
#     ps aux | grep restnet_shogi   # kill leftovers if any
set -e

NAME=${1:?Usage: $0 NAME [GPU_LIST]}
GPU=${2:-0}
GAME=shogi
CFG=configs/9x9_shogi/RRTRRT.cfg

CAPS=(200 300 500 0)          # 0 = no cap (mate/repetition only)
MAX_ITER=${MAX_ITER:-300}
CHUNK=${CHUNK:-1}
RAISE_RATIO=${RAISE_RATIO:-0.75}

completed_iters() {
    # zero-server derives the start iteration from the model count; mirror it
    local n
    n=$(ls "${NAME}/model" 2>/dev/null | grep -c "\.pt$")
    echo $(( n > 0 ? n - 1 : 0 ))   # weight_iter_0.pt is the untrained model
}

current_cap() {
    # cap most recently applied to this training dir (fallback: first phase)
    local c
    c=$(grep -hoE "^env_shogi_max_moves=[0-9]+" "${NAME}"/*.cfg 2>/dev/null | head -1 | cut -d= -f2)
    echo "${c:-${CAPS[0]}}"
}

last_avg_length() {
    # line format: [timestamp] [SelfPlay Avg. Game Lengths] 191.167999
    # take the last field so the timestamp's digits are never matched
    grep "Avg. Game Lengths" "${NAME}/Training.log" 2>/dev/null \
        | tail -1 | awk '{print $NF}'
}

# resume at the cap the training dir was last using
idx=0
cur=$(current_cap)
for i in "${!CAPS[@]}"; do
    [[ "${CAPS[$i]}" == "${cur}" ]] && idx=$i
done

while :; do
    done_iters=$(completed_iters)
    if (( done_iters >= MAX_ITER )); then
        echo "reached MAX_ITER=${MAX_ITER}, done."
        break
    fi

    cap=${CAPS[$idx]}
    end=$(( done_iters + CHUNK ))
    (( end > MAX_ITER )) && end=${MAX_ITER}
    echo "===== iter $((done_iters + 1))..${end}  (env_shogi_max_moves=${cap}) ====="

    # "C" answers (R)estart/(C)ontinue, "y" confirms; harmless on a fresh dir
    printf "Cy" | ./tools/quick-run.sh train ${GAME} ${CFG} ${end} \
        -n "${NAME}" -g "${GPU}" -b 256 -c 8 \
        -conf_str "env_shogi_max_moves=${cap}"

    # abort if no progress was made (training failed / prompt mismatch)
    if (( $(completed_iters) <= done_iters )); then
        echo "error: no progress in the last run, aborting" >&2
        exit 1
    fi

    # raise the cap once games end well before it
    if (( cap > 0 )) && (( idx + 1 < ${#CAPS[@]} )); then
        avg=$(last_avg_length)
        if [[ ${avg} ]] && awk -v a="${avg}" -v c="${cap}" -v r="${RAISE_RATIO}" \
                'BEGIN { exit !(a < c * r) }'; then
            idx=$(( idx + 1 ))
            echo ">>> avg game length ${avg} < ${RAISE_RATIO} x ${cap}: raising cap to ${CAPS[$idx]}"
        fi
    fi
done

echo "check endgame stats with:  ./scripts/sgf_stats.sh ${NAME}"
