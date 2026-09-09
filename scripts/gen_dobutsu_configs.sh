#!/bin/bash
# Write one config per architecture compared in the ResTNet paper's 9x9 Go
# experiment (Table 1), ported to dobutsu shogi. Eleven 6-block arrangements of
# residual (R) and Transformer (T) blocks, not all 64 possible ones.
#
# configs/dobutsu/RRTRRT.cfg is the template. Every generated file is identical
# to it apart from the two header lines and nn_blocks_type, so a change to the
# paper settings is made once in the template and re-generated from here.
#
# The file name is the arrangement read left to right, in the order the blocks
# run: RRTRRT.cfg is R_R_T_R_R_T. The paper's own shorthand, 6R and 5R1T, is
# kept in the header comment instead, since it cannot express TRRRRT.
#
# Usage:
#   ./scripts/gen_dobutsu_configs.sh [OUTPUT_DIR]
set -e

TEMPLATE=configs/dobutsu/RRTRRT.cfg
OUT=${1:-configs/dobutsu}

# arrangement:paper name:win rate against the paper's 9x9 Go baseline
ARCHS=(
    "RRRRRR:6R:54.60%, the convolution-only baseline"
    "TTTTTT:6T:39.85%, transformer-only"
    "RRRRRT:5R1T:56.00%, CoAtNet-like"
    "RRRRTT:4R2T:51.75%, CoAtNet-like"
    "RRRTTT:3R3T:47.85%, CoAtNet-like"
    "RRTTTT:2R4T:37.40%, CoAtNet-like"
    "RTTTTT:1R5T:31.15%, CoAtNet-like"
    "TRRRRT:TRRRRT:43.90%, interleaved"
    "RTRRRT:RTRRRT:54.35%, interleaved"
    "RRTRRT:RRTRRT:60.80%, interleaved, the paper's best"
    "RRRTRT:RRRTRT:49.10%, interleaved"
)

if [[ ! -f $TEMPLATE ]]; then
    echo "template not found: $TEMPLATE" >&2
    exit 1
fi
mkdir -p "$OUT"

# the template is one of the eleven, so read it before anything is overwritten
template_body=$(cat "$TEMPLATE")

for entry in "${ARCHS[@]}"; do
    IFS=: read -r seq_name paper_name note <<<"$entry"

    # RRTRRT -> R_R_T_R_R_T
    blocks_type=$(echo "$seq_name" | sed 's/./&_/g; s/_$//')

    printf '%s\n' "$template_body" \
        | sed -e "1s|.*|# MiniZero / ResTNet Configuration File for Dobutsu Shogi (${paper_name})|" \
              -e "2s|.*|# ResTNet paper Table 1: ${note}. Ported to the 3x4 board|" \
              -e "s|^nn_blocks_type=[^ ]*|nn_blocks_type=${blocks_type}|" \
        > "${OUT}/${seq_name}.cfg"
done

echo "wrote ${#ARCHS[@]} configs to ${OUT}/"
grep -h '^nn_blocks_type=' "${OUT}"/*.cfg | sort -u | wc -l | xargs echo "distinct block layouts:"
