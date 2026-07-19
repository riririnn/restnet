#!/bin/bash
# AlphaZero-paper-aligned training driver for shogi.
#
# The move cap is fixed at 512 (AZ paper; capped games score as draws, z=0)
# and the per-chunk loop applies the paper's stepped learning-rate schedule.
# The adaptive cap-raising curriculum (200->300->500->0) this script once
# implemented is retired but its machinery is kept (set CAPS to multiple
# values to re-enable it).
#
# Usage (inside the container, from /workspace):
#   ./scripts/curriculum_train.sh NAME [GPU_LIST] [CFG]
#   e.g. small box (16GB VRAM):
#     ./scripts/curriculum_train.sh shogi_9x9_curriculum_n64 0
#   e.g. big box (98GB VRAM / 128GB RAM, e.g. RTX PRO 6000):
#     ./scripts/curriculum_train.sh shogi_9x9_curriculum_big 0 \
#         configs/9x9_shogi/RRTRRT-bigserver.cfg
#
# Tunables (environment variables):
#   MAX_ITER=300      total iterations to train
#   CHUNK=1           iterations per training run before re-checking the metric
#   RAISE_RATIO=0.75  raise the cap when avg game length < RAISE_RATIO * cap
#   SP_BATCH=256      self-play batch size (-b); raise on bigger GPUs (e.g. 1024)
#   CPU_PER_GPU=8     CPU threads per GPU (-c); match to `nproc`
#   LR_BASE=0.02      initial learning rate; dropped 10x at ~1/7, ~3/7 and ~5/7
#                     of MAX_ITER (AZ-paper schedule, batch-scaled)
#
# Interrupt / resume:
#   Ctrl+C loses only the unfinished iteration. Re-run the same command —
#   progress is read from NAME/model/ and the current cap from NAME/*.cfg,
#   so training continues where it left off.
#   After Ctrl+C, check for leftover workers before resuming:
#     ps aux | grep restnet_shogi   # kill leftovers if any
set -e

NAME=${1:?Usage: $0 NAME [GPU_LIST] [CFG]}
GPU=${2:-0}
GAME=shogi
CFG=${3:-configs/9x9_shogi/RRTRRT.cfg}

CAPS=(512)                    # AZ paper: fixed cap (multiple entries re-enable the adaptive curriculum)
MAX_ITER=${MAX_ITER:-300}
CHUNK=${CHUNK:-1}
RAISE_RATIO=${RAISE_RATIO:-0.75}
SP_BATCH=${SP_BATCH:-256}
CPU_PER_GPU=${CPU_PER_GPU:-8}
LR_BASE=${LR_BASE:-0.02}      # initial LR; AZ paper's 0.2 scaled to our batch (0.2 * 512/4096)

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

    # AZ-paper LR schedule: 10x drops at ~1/7, ~3/7, ~5/7 of total training.
    # train.py re-reads the LR from the config on every chunk restart.
    if   (( done_iters * 7 < MAX_ITER * 1 )); then lr=${LR_BASE}
    elif (( done_iters * 7 < MAX_ITER * 3 )); then lr=$(awk -v b="${LR_BASE}" 'BEGIN{print b/10}')
    elif (( done_iters * 7 < MAX_ITER * 5 )); then lr=$(awk -v b="${LR_BASE}" 'BEGIN{print b/100}')
    else                                           lr=$(awk -v b="${LR_BASE}" 'BEGIN{print b/1000}')
    fi
    echo "===== iter $((done_iters + 1))..${end}  (env_shogi_max_moves=${cap}, lr=${lr}) ====="

    # "C" answers (R)estart/(C)ontinue, "y" confirms; harmless on a fresh dir
    printf "Cy" | ./tools/quick-run.sh train ${GAME} ${CFG} ${end} \
        -n "${NAME}" -g "${GPU}" -b "${SP_BATCH}" -c "${CPU_PER_GPU}" \
        -conf_str "env_shogi_max_moves=${cap}:learner_learning_rate=${lr}"

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
