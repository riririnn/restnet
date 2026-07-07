#!/bin/bash
# Summarise self-play SGF results per iteration: draws, mate-endings,
# adjudication-endings, and game lengths.
#
# Usage:
#   ./scripts/sgf_stats.sh TRAIN_DIR [ITER...]
#
#   TRAIN_DIR : training folder containing sgf/ (e.g. shogi_9x9_gaz_2R1T2R1T_P_TV_n50)
#   ITER...   : iteration numbers to report (default: every *.sgf in TRAIN_DIR/sgf)
#
# The move cap (env_shogi_max_moves) is read from the .cfg inside TRAIN_DIR
# so that games are classified as:
#   詰み・投了  : decisive result before the cap
#   千日手     : draw before the cap (repetition/stalemate)
#   判定       : game reached the cap (27-point adjudication)
set -e

TRAIN_DIR=${1:?Usage: $0 TRAIN_DIR [ITER...]}
shift || true

if [ ! -d "$TRAIN_DIR/sgf" ]; then
    echo "error: $TRAIN_DIR/sgf not found" >&2
    exit 1
fi

# move cap from the training dir's cfg (fallback 500)
CAP=$(grep -hoE "^env_shogi_max_moves=[0-9]+" "$TRAIN_DIR"/*.cfg 2>/dev/null | head -1 | cut -d= -f2)
CAP=${CAP:-500}

TRAIN_DIR="$TRAIN_DIR" CAP="$CAP" ITERS="$*" python3 - <<'EOF'
import glob
import os
import re
import statistics as st

train_dir = os.environ["TRAIN_DIR"]
cap       = int(os.environ["CAP"])
iters_arg = os.environ["ITERS"].split()

if iters_arg:
    iters = [int(i) for i in iters_arg]
else:
    iters = sorted(int(os.path.splitext(os.path.basename(p))[0])
                   for p in glob.glob(os.path.join(train_dir, "sgf", "*.sgf"))
                   if os.path.splitext(os.path.basename(p))[0].isdigit())

print(f"move cap (env_shogi_max_moves): {cap if cap > 0 else 'none'}")
print(f"{'iter':>4} {'games':>5} {'詰み・投了':>8} {'千日手':>6} {'判定':>6} "
      f"{'引分計':>6} {'平均手数':>8} {'中央値':>6}")

for it in iters:
    path = os.path.join(train_dir, "sgf", f"{it}.sgf")
    if not os.path.isfile(path):
        print(f"{it:>4} (not found)")
        continue
    content = open(path).read()
    starts = [m.start() for m in re.finditer(r"\(;GM\[", content)]

    mate = repdraw = adjud = draws = 0
    lens = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(content)
        g = content[s:e]
        moves = len(re.findall(r";[BW]\[\d+\]", g))
        m = re.search(r"RE\[([^\]]+)\]", g)
        r = m.group(1) if m else "?"
        is_draw = r in ("0", "0.000000")
        lens.append(moves)

        if cap > 0 and moves >= cap:
            adjud += 1          # reached the cap → 27-point adjudication
        elif is_draw:
            repdraw += 1        # ended early with a draw → repetition/stalemate
        else:
            mate += 1           # ended early decisively → mate/resign/foul
        if is_draw:
            draws += 1

    n = len(starts)
    if n == 0:
        print(f"{it:>4} (empty)")
        continue
    pct = lambda x: f"{100 * x / n:5.1f}%"
    print(f"{it:>4} {n:>5} {mate:>5} {pct(mate)} {repdraw:>4} {pct(repdraw)} "
          f"{adjud:>4} {pct(adjud)} {draws:>4} {pct(draws)} "
          f"{st.mean(lens):>7.1f} {st.median(lens):>6.0f}")
EOF
