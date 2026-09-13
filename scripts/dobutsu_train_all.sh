#!/bin/bash
# Train every architecture the ResTNet paper compares on 9x9 Go, one after
# another, on the 3x4 dobutsu board.
#
# The learning rate schedule lives in the configs, not here. All eleven get the
# same one, which is what the comparison needs.
#
# Runs are sequential, not parallel: eleven runs sharing one GPU would each be
# slower and the wall-clock total no better.
#
# One run failing does not stop the rest. A GPU fault killed 6T at iteration 11
# on 2026-09-12 and took the nine untouched architectures down with it, because
# this script used to exit on the first failure. Days of queued work should not
# hinge on one transient fault. Failures are collected and reported at the end,
# and the exit status is nonzero if there were any.
#
# Keeping every checkpoint of all eleven runs would need about 360GB, more than
# this disk has free, so each finished run is thinned: one .pt every KEEP_EVERY
# iterations, and only the last .pkl. The .pkl is twice the size of the .pt
# because it carries the SGD momentum, which only a resume needs. Fifty points
# is plenty to draw a curve. Set KEEP_EVERY=1 to keep everything.
#
# Usage:
#   ./scripts/dobutsu_train_all.sh [ITERATIONS] [ARCH]...
#
#   ITERATIONS  iterations per architecture (default 500, the paper's count)
#   ARCH        which ones to run, e.g. RRTRRT 6R (default: all eleven)
#
# Environment:
#   KEEP_EVERY  keep one checkpoint every this many iterations (default 10)
#
# A finished run is skipped, so re-running the script fills in what is missing.
# An interrupted run is NOT resumed here: zero-server asks
# "(R)estart / (C)ontinue / (Q)uit?" and that answer should be a person's.
set -e

ITER=${1:-500}
shift || true
KEEP_EVERY=${KEEP_EVERY:-10}

# Thin a finished run: one .pt every KEEP_EVERY iterations, only the last .pkl.
# Runs after training, never during, so a resume always has its checkpoint.
prune_run() {
    local dir=$1 step=$2 final=$3
    [[ $KEEP_EVERY -le 1 ]] && return 0
    local before after
    before=$(du -sm "$dir/model" | cut -f1)
    for f in "$dir"/model/weight_iter_*.pt; do
        local n=${f##*weight_iter_}
        n=${n%.pt}
        # keep the last one whatever happens, and every KEEP_EVERY-th iteration
        [[ $n -eq $final ]] && continue
        (((n / step) % KEEP_EVERY == 0)) && continue
        rm -f "$f"
    done
    find "$dir/model" -name 'weight_iter_*.pkl' ! -name "weight_iter_${final}.pkl" -delete
    after=$(du -sm "$dir/model" | cut -f1)
    echo "      pruned ${dir}/model: ${before}MB -> ${after}MB"
}

# paper order: the two ends of the sweep, then CoAtNet-like, then interleaved
ALL_ARCHS=(6R 6T 5R1T 4R2T 3R3T 2R4T 1R5T TRRRRT RTRRRT RRTRRT RRRTRT)
ARCHS=("${ALL_ARCHS[@]}")
[[ $# -gt 0 ]] && ARCHS=("$@")

LOGDIR=models/dobutsu_train_logs
mkdir -p "$LOGDIR"

declare -a DONE=() FAILED=() MANUAL=()

for arch in "${ARCHS[@]}"; do
    cfg=configs/dobutsu/${arch}.cfg
    dir=models/dobutsu_${arch}

    if [[ ! -f $cfg ]]; then
        echo "!!!!! ${arch}: no ${cfg}; run scripts/gen_dobutsu_configs.sh" >&2
        FAILED+=("${arch} (no config)")
        continue
    fi

    # checkpoints are named by training step, not by iteration
    steps_per_iter=$(sed -nE 's/^learner_training_step=([0-9]+).*/\1/p' "$cfg")
    final_step=$((ITER * steps_per_iter))

    # a run is finished when the last iteration's weights are on disk
    if [[ -f ${dir}/model/weight_iter_${final_step}.pt ]]; then
        echo "===== ${arch}: already trained to ${ITER} iterations, skipping ====="
        continue
    fi
    # a half-finished folder is left alone: zero-server would ask
    # "(R)estart / (C)ontinue / (Q)uit?" and that answer should be a person's
    if [[ -d $dir ]]; then
        echo "!!!!! ${arch}: ${dir} exists but is incomplete; leaving it alone" >&2
        MANUAL+=("$arch")
        continue
    fi

    echo "===== ${arch}: ${ITER} iterations ====="
    # append, so a rerun keeps the record of what failed last time
    tools/quick-run.sh train dobutsu "$cfg" "$ITER" -n "$dir" 2>&1 |
        tee -a "${LOGDIR}/${arch}.log" || true

    if [[ -f ${dir}/model/weight_iter_${final_step}.pt ]]; then
        prune_run "$dir" "$steps_per_iter" "$final_step"
        DONE+=("$arch")
    else
        echo "!!!!! ${arch}: stopped early, no weight_iter_${final_step}.pt." >&2
        echo "      Not pruning: a resume needs the .pkl files kept." >&2
        FAILED+=("$arch")
    fi
done

cat <<EOF

===== done =====
trained this run  ${DONE[*]:-none}
stopped early     ${FAILED[*]:-none}
left for a person ${MANUAL[*]:-none}

models     models/dobutsu_<ARCH>/model/
logs       ${LOGDIR}/

Before comparing architectures, look at one loss curve. If it is still falling
at the last iteration, these runs are too short and the ranking is premature.
EOF

if [[ ${#FAILED[@]} -gt 0 || ${#MANUAL[@]} -gt 0 ]]; then
    cat >&2 <<EOF

Read the tail of the log for each name above. A CUDA error there is the GPU,
not the training: check the kernel log for the same minute.

  journalctl -k -S "<the minute it stopped>" | grep -i "PCIe Bus Error\|Xid"

To carry a stopped run on, answer (C)ontinue and then y:

  tools/quick-run.sh train dobutsu configs/dobutsu/<ARCH>.cfg ${ITER} -n models/dobutsu_<ARCH>
EOF
    exit 1
fi
