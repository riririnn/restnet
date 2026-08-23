#!/bin/bash
# Supervised pretraining on human game records, before any self-play.
# Reachable as `tools/quick-run.sh pretrain shogi ACTION ...` too.
#
# Usage (inside the container, from /workspace):
#   ./scripts/bootstrap/pretrain.sh data     [BUILD_ARGS]...     build the dataset
#   ./scripts/bootstrap/pretrain.sh train    NAME [STEPS] [CFG]  pretrain from scratch
#   ./scripts/bootstrap/pretrain.sh resume   NAME [STEPS]        continue pretraining
#
# Hand the result to self-play with tools/quick-run.sh --pretrained (see below).
#
#   e.g.
#     ./scripts/bootstrap/pretrain.sh data --min-rating 2000 --target-games 10000
#     ./scripts/bootstrap/pretrain.sh train shogi_9x9_bootstrap 3000
#     ./scripts/bootstrap/pretrain.sh resume shogi_9x9_bootstrap 3000
#     tools/quick-run.sh train shogi configs/9x9_shogi/RRTRRT.cfg 500 \
#         -n shogi_9x9_from_human --pretrained shogi_9x9_bootstrap/model/weight_iter_3600.pt
#
# Tunables (environment variables):
#   GPU=0                   GPU(s) to use for pretraining
#   DATA=data/bootstrap/sgf/1.sgf   records to train on
#
# See mdfolder/bootstrap_pretraining.md for the background and measured results.
set -e

MODE=${1:?Usage: $0 data|train|resume ...}
shift

GAME=shogi
GPU=${GPU:-0}
DATA=${DATA:-data/bootstrap/sgf/1.sgf}
# ResTNet has its own config keys, so its learner must be used -- not minizero's
OP=restnet/learner/train.py

# feed one command to the learner and quit; it saves model/weight_iter_<step>.{pkl,pt}
run_learner() {   # run_learner TRAIN_DIR CFG MODEL_FILE
    printf 'train "%s" 1 1\nquit\n' "$3" \
        | CUDA_VISIBLE_DEVICES=${GPU} PYTHONPATH=. python3 -u ${OP} ${GAME} "$1" "$2"
}

latest_model() {  # latest_model TRAIN_DIR -> weight_iter_N.pkl
    ls "$1"/model/*.pkl 2>/dev/null | sort -V | tail -1 | xargs -r basename
}

gcd() { local a=$1 b=$2 t; while (( b )); do t=$b; b=$((a % b)); a=$t; done; echo "$a"; }

# train.py divides the accumulated metrics by learner_training_display_step no
# matter how many steps actually accumulated. Displays fire on the *global* step
# counter, so when resuming from a checkpoint that is not a multiple of the
# interval the first line covers fewer steps and every metric is scaled down.
# Shrinking the interval to a divisor of the starting step keeps them honest.
set_display_step() {   # set_display_step CFG START_STEP
    local want=${DISPLAY_STEP:-250} use
    use=$(gcd "$2" "${want}")
    (( use == 0 )) && use=${want}
    sed -i "s/^learner_training_display_step=.*/learner_training_display_step=${use}/" "$1"
    (( use != want )) && echo "note: display interval ${want} -> ${use} to align with step $2"
    return 0
}

# the loader keeps at most zero_replay_buffer * zero_num_games_per_iteration games
warn_if_truncated() {   # warn_if_truncated CFG NUM_GAMES
    local buf per cap
    buf=$(grep -oP '^zero_replay_buffer=\K[0-9]+' "$1")
    per=$(grep -oP '^zero_num_games_per_iteration=\K[0-9]+' "$1")
    cap=$((buf * per))
    if (( $2 > cap )); then
        echo "WARNING: $2 games exceed the replay buffer cap (${buf} x ${per} = ${cap});" >&2
        echo "         the oldest records will be dropped. Raise zero_replay_buffer." >&2
    fi
}

case ${MODE} in
data)
    python3 scripts/bootstrap/build_dataset.py "$@"
    ;;

train)
    NAME=${1:?Usage: $0 train NAME [STEPS] [CFG]}
    STEPS=${2:-3000}
    CFG_SRC=${3:-configs/9x9_shogi/RRTRRT.cfg}
    [[ -f ${DATA} ]] || { echo "no dataset at ${DATA}; run '$0 data' first" >&2; exit 1; }

    mkdir -p "${NAME}"/{model,sgf,analysis}
    touch "${NAME}/op.log" "${NAME}/Training.log"   # the post-run analysis reads both
    cp "${DATA}" "${NAME}/sgf/1.sgf"
    CFG="${NAME}/$(basename ${NAME}).cfg"
    cp "${CFG_SRC}" "${CFG}"
    sed -i "s/^learner_training_step=.*/learner_training_step=${STEPS}/" "${CFG}"
    set_display_step "${CFG}" 0

    warn_if_truncated "${CFG}" "$(wc -l < ${DATA})"
    echo "===== pretrain ${NAME}: $(wc -l < ${DATA}) games, ${STEPS} steps ====="
    run_learner "${NAME}" "${CFG}" ""
    ;;

resume)
    NAME=${1:?Usage: $0 resume NAME [STEPS]}
    STEPS=${2:-3000}
    CFG="${NAME}/$(basename ${NAME}).cfg"
    [[ -f ${CFG} ]] || { echo "no config at ${CFG}; run '$0 train' first" >&2; exit 1; }
    MODEL=$(latest_model "${NAME}")
    [[ ${MODEL} ]] || { echo "no checkpoint in ${NAME}/model; run '$0 train' first" >&2; exit 1; }

    sed -i "s/^learner_training_step=.*/learner_training_step=${STEPS}/" "${CFG}"
    set_display_step "${CFG}" "$(echo "${MODEL}" | grep -oP '\d+')"
    touch "${NAME}/Training.log"
    echo "===== resume ${NAME} from ${MODEL}: +${STEPS} steps ====="
    run_learner "${NAME}" "${CFG}" "${MODEL}"
    ;;

*)
    echo "Usage: $0 data|train|resume ..." >&2
    exit 1
    ;;
esac
