#!/bin/bash
# Train two dobutsu architectures and play them against each other.
#
# The point is not which one wins. It is to find out whether dobutsu separates
# architectures at all: if 6R and RRTRRT finish within noise of each other, the
# game has saturated and the eleven-way comparison the paper runs on 9x9 Go will
# not carry over. Better to learn that from two runs than from eleven.
#
# The configs match configs/9x9_go/RRTRRT.cfg -- the paper's own 9x9 Go setup --
# in everything but env_board_size and nn_blocks_type, so everything else stays
# at the defaults the paper used (batch 1024, 500 training steps per iteration,
# a 20-iteration replay buffer, 64 simulations).
#
# Usage (inside the container, from /workspace):
#   ./scripts/dobutsu_arch_compare.sh [ITERATIONS] [GAMES]
#
#   ITERATIONS  training iterations per architecture (default 100; the paper uses 500)
#   GAMES       games per model pair in the evaluation (default 200)
set -e

ITER=${1:-100}
GAMES=${2:-200}
OUT=models/dobutsu_arch_compare
mkdir -p "$OUT"

for arch in 6R RRTRRT; do
    if [[ -d models/dobutsu_${arch} ]]; then
        echo "===== ${arch}: models/dobutsu_${arch} exists, skipping ====="
        continue
    fi
    echo "===== training ${arch} for ${ITER} iterations ====="
    tools/quick-run.sh train dobutsu "configs/dobutsu/${arch}.cfg" "$ITER" \
        -n "dobutsu_${arch}" 2>&1 | tee "${OUT}/train_${arch}.log"
done

# fight-eval walks both folders in step; the interval decides how many
# checkpoints are played, and the last pair is the one that answers the question
echo "===== 6R against RRTRRT, ${GAMES} games per checkpoint pair ====="
tools/fight-eval.sh dobutsu \
    models/dobutsu_6R models/dobutsu_RRTRRT \
    configs/dobutsu/6R.cfg configs/dobutsu/RRTRRT.cfg \
    "$ITER" "$GAMES" -d "${OUT}/6R_vs_RRTRRT" 2>&1 | tee "${OUT}/fight.log"

cat <<EOF

===== where to look =====
training   ${OUT}/train_*.log
evaluation ${OUT}/fight.log  and  ${OUT}/6R_vs_RRTRRT/

Read RRTRRT's win rate against 6R. With ${GAMES} games the standard error is
about $(python3 -c "print(f'{50/(${GAMES}**0.5):.1f}')") points, so treat anything inside 50 +/- $(python3 -c "print(f'{100/(${GAMES}**0.5):.0f}')") as no difference.

  clearly above 50%    the architecture matters here; the 11-way comparison is worth running
  within noise of 50%  dobutsu has saturated at this size. Before changing game,
                       try fewer simulations or fewer channels to widen the gap,
                       or score against the solved game's ground truth instead of
                       win rate -- accuracy separates models that win rate cannot.
EOF
