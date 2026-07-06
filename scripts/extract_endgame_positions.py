#!/usr/bin/env python3
"""
Extract endgame positions from self-play SGF files as an SFEN opening pool
for curriculum training.

Replays decisive games (win/loss, not draws) with the C++ env_py module and
exports positions N moves before the end as SFEN strings. Each generated SFEN
is validated by round-tripping through tsume_shogi.sfen_to_tensor and
comparing with the original feature planes.

Usage (inside the container, from the repo root):
    python3 scripts/extract_endgame_positions.py \
        --sgf-dir shogi_9x9_gaz_2R1T2R1T_P_TV_n50/sgf \
        --conf configs/9x9_shogi/RRTRRT.cfg \
        --iters 30 35 38 \
        --offsets 2 4 6 \
        --max-positions 3000 \
        --out endgame_pool.sfen
"""

import argparse
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tsume_shogi import _PIECE_KIND, _PROMO_KIND, _HAND_IDX, sfen_to_tensor  # noqa: E402

# kind index (0-13) → SFEN letter, promoted flag
_KIND_TO_SFEN = {}
for letter, kind in _PIECE_KIND.items():
    _KIND_TO_SFEN[kind] = (letter, False)
for letter, kind in _PROMO_KIND.items():
    _KIND_TO_SFEN[kind] = (letter, True)

# hand channel offset (0-6) → SFEN letter, order matches _HAND_IDX
_HAND_LETTERS = sorted(_HAND_IDX, key=_HAND_IDX.get)


def load_env_py(build_dir: str, conf_file: str):
    import importlib.util
    import glob
    matches = glob.glob(os.path.join(build_dir, "env_py*.so"))
    if not matches:
        raise ImportError(f"env_py not found in {build_dir}")
    spec = importlib.util.spec_from_file_location("env_py", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.init(conf_file)
    return module


def parse_sgf_games(sgf_file: str):
    """Yield (moves, result) per game; moves = [(player_char, action_id), ...]."""
    with open(sgf_file) as f:
        content = f.read()
    starts = [m.start() for m in re.finditer(r"\(;GM\[", content)]
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(content)
        g = content[s:e]
        moves = [(p, int(a)) for p, a in re.findall(r";([BW])\[(\d+)\]", g)]
        m = re.search(r"RE\[([^\]]+)\]", g)
        yield moves, (m.group(1) if m else "?")


def features_to_sfen(features: np.ndarray, move_count: int) -> str:
    """Convert a (362, 9, 9) feature array (t=0 planes) to an SFEN string."""
    is_black = features[360, 0, 0] >= 0.5

    # board: channels 0-13 ours, 14-27 opponent; flipped when white to move
    board = [["" for _ in range(9)] for _ in range(9)]
    for ch in range(28):
        kind = ch % 14
        is_ours = ch < 14
        letter, promoted = _KIND_TO_SFEN[kind]
        # ours = side to move; SFEN uppercase = black
        piece_is_black = (is_ours == is_black)
        sym = letter if piece_is_black else letter.lower()
        if promoted:
            sym = "+" + sym
        for r, f in zip(*np.nonzero(features[ch] >= 0.5)):
            rr, ff = (r, f) if is_black else (8 - r, 8 - f)
            board[rr][ff] = sym

    rows = []
    for r in range(9):
        row = ""
        empty = 0
        for f in range(9):
            if board[r][f]:
                if empty:
                    row += str(empty)
                    empty = 0
                row += board[r][f]
            else:
                empty += 1
        if empty:
            row += str(empty)
        rows.append(row)
    board_str = "/".join(rows)

    # hands: ours 31-37, enemy 38-44 (value = piece count on the whole plane)
    hand = ""
    for base, ours in ((31, True), (38, False)):
        for off, letter in enumerate(_HAND_LETTERS):
            count = int(round(float(features[base + off, 0, 0])))
            if count <= 0:
                continue
            piece_is_black = (ours == is_black)
            sym = letter if piece_is_black else letter.lower()
            hand += (str(count) if count > 1 else "") + sym
    if not hand:
        hand = "-"

    turn = "b" if is_black else "w"
    return f"{board_str} {turn} {hand} {max(move_count, 1)}"


def validate_sfen(sfen: str, features: np.ndarray) -> bool:
    """Round-trip check: SFEN → tensor must reproduce the t=0 planes."""
    try:
        t = sfen_to_tensor(sfen).numpy()[0]
    except Exception:
        return False
    # board channels 0-27 and hand channels 31-44 must match exactly
    return (np.array_equal(t[0:28] >= 0.5, features[0:28] >= 0.5)
            and np.allclose(t[31:45, 0, 0], features[31:45, 0, 0]))


def main():
    ap = argparse.ArgumentParser(description="Extract endgame SFEN pool from SGFs")
    ap.add_argument("--sgf-dir", required=True)
    ap.add_argument("--conf", required=True)
    ap.add_argument("--iters", type=int, nargs="+", required=True,
                    help="iteration numbers (SGF file names) to process")
    ap.add_argument("--offsets", type=int, nargs="+", default=[2, 4, 6],
                    help="how many moves before the end to snapshot")
    ap.add_argument("--max-positions", type=int, default=3000)
    ap.add_argument("--build-dir", default="build/shogi")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    env_py = load_env_py(args.build_dir, args.conf)

    pool: dict[str, None] = {}   # ordered dedupe
    n_games = n_decisive = n_invalid = 0

    for it in args.iters:
        sgf_file = os.path.join(args.sgf_dir, f"{it}.sgf")
        if not os.path.isfile(sgf_file):
            print(f"skip (not found): {sgf_file}")
            continue
        for moves, result in parse_sgf_games(sgf_file):
            n_games += 1
            if result in ("0", "0.000000", "?") or not moves:
                continue   # draws give no useful endgame signal
            n_decisive += 1

            env = env_py.Env()
            env.reset()
            snapshots = {len(moves) - off for off in args.offsets if len(moves) - off > 0}
            for idx, (player_char, action_id) in enumerate(moves):
                if idx in snapshots:
                    feats = np.asarray(env.get_features(),
                                       dtype=np.float32).reshape(362, 9, 9)
                    sfen = features_to_sfen(feats, idx + 1)
                    if validate_sfen(sfen, feats):
                        pool[sfen] = None
                    else:
                        n_invalid += 1
                player = env_py.player_1 if player_char == "B" else env_py.player_2
                env.act(env_py.Action(action_id, player))

            if len(pool) >= args.max_positions:
                break
        if len(pool) >= args.max_positions:
            break

    sfens = list(pool)[: args.max_positions]
    with open(args.out, "w") as f:
        f.write("\n".join(sfens) + "\n")

    print(f"games scanned   : {n_games}")
    print(f"decisive games  : {n_decisive}")
    print(f"positions saved : {len(sfens)}  (validation failures: {n_invalid})")
    print(f"output          : {args.out}")


if __name__ == "__main__":
    main()
