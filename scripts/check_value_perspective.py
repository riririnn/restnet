#!/usr/bin/env python
"""Check that the shogi value target follows the side to move.

Samples positions through the same DataLoader path training uses, reads the side
to move out of the feature tensor (channel 360 is 1.0 for Black), and groups the
value target by it.

Before the fix every position of a game carried the same sign, so one group came
out entirely wrong. After it, the sign follows the side to move: with a single
game the two groups hold opposite signs.

Usage (from the repo root, inside the container):
    PYTHONPATH=. python scripts/check_value_perspective.py \
        models/<run>/sgf/1.sgf configs/9x9_shogi/10R-bigserver.cfg [samples]
"""

import os
import sys
from collections import Counter

TURN_CHANNEL = 360  # 1.0 = Black to move
BOARD_AREA = 81


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    sgf_file, conf_file = sys.argv[1], sys.argv[2]
    num_samples = int(sys.argv[3]) if len(sys.argv) > 3 else 2000

    # an empty loader divides by its data size when sampling, so stop here rather
    # than segfault
    for path in (sgf_file, conf_file):
        if not os.path.isfile(path):
            print(f"ERROR: no such file: {path}")
            return 1
    if os.path.getsize(sgf_file) == 0:
        print(f"ERROR: empty record file: {sgf_file}")
        return 1

    temps = __import__("build.shogi", globals(), locals(), ["restnet_py"], 0)
    restnet_py = temps.restnet_py

    if not restnet_py.load_config_file(conf_file):
        print(f"WARNING: failed to load {conf_file}; using default settings")

    data_loader = restnet_py.DataLoader(conf_file)
    data_loader.initialize()
    # get_alphazero_sl_training_data() reads the records this call fills, not the
    # ones load_data_from_file() populates for the training loop
    data_loader.load_data_from_env_file(sgf_file)

    counts = Counter()
    for _ in range(num_samples):
        data = data_loader.get_alphazero_sl_training_data()
        black_to_move = data["features"][TURN_CHANNEL * BOARD_AREA] == 1.0
        value = data["value"]
        sign = "+1" if value > 0 else "-1" if value < 0 else " 0"
        counts[("black" if black_to_move else "white", sign)] += 1

    print(f"file    : {sgf_file}")
    print(f"samples : {num_samples}\n")
    print("side to move |    +1     -1      0")
    print("-------------+-----------------------")
    for side in ("black", "white"):
        row = [counts[(side, s)] for s in ("+1", "-1", " 0")]
        print(f"{side:12} | {row[0]:5}  {row[1]:5}  {row[2]:5}")

    black_signs = {s for (side, s), n in counts.items() if side == "black" and n}
    white_signs = {s for (side, s), n in counts.items() if side == "white" and n}
    print()
    if not black_signs or not white_signs:
        print("INCONCLUSIVE: only one side was sampled; use a file with more games")
        return 1
    if black_signs | white_signs == {" 0"}:
        print("INCONCLUSIVE: every game was a draw, so both sides label 0")
        print("              use a file whose records have RE other than 0")
        return 1
    if black_signs == white_signs and len(black_signs) == 1:
        print("FAIL: both sides carry the same sign -- the target ignores the turn")
        return 1
    print("OK: the value target depends on the side to move")
    return 0


if __name__ == "__main__":
    sys.exit(main())
