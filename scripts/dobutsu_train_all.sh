#!/bin/bash
# Train every architecture the ResTNet paper compares on 9x9 Go, one after
# another, on the 3x4 dobutsu board.
#
# The learning rate stays at 0.02 throughout. The paper decays it only in its
# 9x9 Go run; 19x19 Hex is a flat 0.02 and 19x19 Go a flat 0.1, and no reason is
# given for any of the three. So its 70,000 and 90,000 step boundaries carry no
# authority on a board this small. All eleven runs get identical treatment,
# which is what the comparison needs, and their loss curves are what will decide
# whether a decay is worth adding later.
#
# Runs are sequential, not parallel: eleven runs sharing one GPU would each be
# slower and the wall-clock total no better.
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
#   ARCH        which ones to run, e.g. RRTRRT RRRRRR (default: all eleven)
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
ALL_ARCHS=(RRRRRR TTTTTT RRRRRT RRRRTT RRRTTT RRTTTT RTTTTT TRRRRT RTRRRT RRTRRT RRRTRT)
ARCHS=("${ALL_ARCHS[@]}")
[[ $# -gt 0 ]] && ARCHS=("$@")

LOGDIR=models/dobutsu_train_logs
mkdir -p "$LOGDIR"

for arch in "${ARCHS[@]}"; do
    cfg=configs/dobutsu/${arch}.cfg
    dir=models/dobutsu_${arch}

    if [[ ! -f $cfg ]]; then
        echo "!!!!! ${arch}: no ${cfg}; run scripts/gen_dobutsu_configs.sh" >&2
        exit 1
    fi

    # checkpoints are named by training step, not by iteration
    steps_per_iter=$(sed -nE 's/^learner_training_step=([0-9]+).*/\1/p' "$cfg")
    final_step=$((ITER * steps_per_iter))

    # a run is finished when the last iteration's weights are on disk
    if [[ -f ${dir}/model/weight_iter_${final_step}.pt ]]; then
        echo "===== ${arch}: already trained to ${ITER} iterations, skipping ====="
        continue
    fi
    if [[ -d $dir ]]; then
        echo "!!!!! ${arch}: ${dir} exists but is incomplete." >&2
        echo "      Resume it by hand and answer (C)ontinue:" >&2
        echo "      tools/quick-run.sh train dobutsu ${cfg} ${ITER} -n ${dir}" >&2
        exit 1
    fi

    echo "===== ${arch}: ${ITER} iterations, lr 0.02 throughout ====="
    tools/quick-run.sh train dobutsu "$cfg" "$ITER" -n "$dir" 2>&1 |
        tee "${LOGDIR}/${arch}.log"

    if [[ -f ${dir}/model/weight_iter_${final_step}.pt ]]; then
        prune_run "$dir" "$steps_per_iter" "$final_step"
    else
        echo "!!!!! ${arch}: no weight_iter_${final_step}.pt; not pruning" >&2
        exit 1
    fi
done

cat <<EOF

===== done =====
models     models/dobutsu_<ARCH>/model/
logs       ${LOGDIR}/

Before comparing architectures, look at one loss curve. If it is still falling
at the last iteration, these runs are too short and the ranking is premature.
If it flattened early, that is where a learning rate drop belongs.
EOF
