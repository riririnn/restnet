#!/bin/bash
# Carry the eleven trained dobutsu models on so they learn the repetition planes.
#
# The planes were appended as channels 18 and 19, so every channel the old models
# were trained on keeps its meaning. transfer.py widens embed.conv.weight and its
# momentum buffer from 18 to 20 with zeros, which leaves the model's output
# unchanged, and the training that follows teaches it to use the two new planes.
#
# Usage (from /workspace, inside the container):
#   ./scripts/dobutsu_learn_repetition.sh [ITERATIONS]
set -e

ITER=${1:-50}
SRC_STEP=100000   # the step the eleven runs finished at
ARCHS=(6R 6T 5R1T 4R2T 3R3T 2R4T 1R5T TRRRRT RTRRRT RRTRRT RRRTRT)
LOGDIR=models/dobutsu_repetition_logs
mkdir -p "$LOGDIR"

declare -a DONE=() FAILED=()

for arch in "${ARCHS[@]}"; do
    src=models/dobutsu_${arch}/model/weight_iter_${SRC_STEP}.pkl
    widened=models/dobutsu_${arch}_widened
    out=models/dobutsu_${arch}_rep

    if [[ ! -f $src ]]; then
        echo "!!!!! ${arch}: no ${src}" >&2
        FAILED+=("${arch} (no source model)")
        continue
    fi
    if [[ -d $out ]]; then
        echo "===== ${arch}: ${out} exists, skipping ====="
        continue
    fi

    echo "===== ${arch}: widening 18 -> 20 channels ====="
    rm -rf "$widened"
    (cd restnet/learner && PYTHONPATH=/workspace python3 transfer.py dobutsu \
        "/workspace/${src}" "/workspace/${widened}" "/workspace/configs/dobutsu/${arch}.cfg") 2>&1 |
        grep -E "widening|Error" || true

    echo "===== ${arch}: ${ITER} more iterations ====="
    tools/quick-run.sh train dobutsu "configs/dobutsu/${arch}.cfg" "$ITER" -n "$out" \
        --pretrained "${widened}/model/weight_iter_${SRC_STEP}.pt" 2>&1 |
        tee -a "${LOGDIR}/${arch}.log" || true

    steps=$(sed -nE 's/^learner_training_step=([0-9]+).*/\1/p' "configs/dobutsu/${arch}.cfg")
    if [[ -f ${out}/model/weight_iter_$((ITER * steps)).pt ]]; then
        DONE+=("$arch")
        rm -rf "$widened"
    else
        echo "!!!!! ${arch}: stopped early" >&2
        FAILED+=("$arch")
    fi
done

cat <<EOS

===== done =====
trained   ${DONE[*]:-none}
failed    ${FAILED[*]:-none}
models    models/dobutsu_<ARCH>_rep/
logs      ${LOGDIR}/

The originals in models/dobutsu_<ARCH>/ are untouched.
EOS
[[ ${#FAILED[@]} -eq 0 ]]
