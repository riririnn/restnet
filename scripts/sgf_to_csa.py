#!/usr/bin/env python3
"""
Convert minizero shogi self-play game records (as found in TRAIN_DIR/sgf/*.sgf,
one file = many games back-to-back) into CSA v2 files that ShogiHome (and
other CSA-compatible viewers) can open.

This is a standalone converter: it does NOT touch the C++ shogi environment.
It re-derives the action-ID decoding (AlphaZero action id -> from/to/piece/
promote) by porting the same math already implemented in
minizero/minizero/environment/shogi/shogi.h (ShogiAction::convertSunfish /
get_to_sq_from_direction), and tracks its own lightweight board (piece
positions + hands) to resolve which piece is being moved/captured, since a
game record's action ids alone don't carry that -- it must be replayed.

Usage:
    ./scripts/sgf_to_csa.py TRAIN_DIR/sgf/5.sgf -o out_dir/
    ./scripts/sgf_to_csa.py TRAIN_DIR/sgf/5.sgf          # prints all games to stdout, separated by blank lines
"""

import argparse
import os
import re
import sys

BOARD_AREA = 81

# sunfish kind enumeration (Piece.h): Pawn=0 Lance=1 Knight=2 Silver=3 Gold=4 Bishop=5 Rook=6 King=7
KIND_CSA = ["FU", "KY", "KE", "GI", "KI", "KA", "HI", "OU"]
PROMOTED_CSA = {"FU": "TO", "KY": "NY", "KE": "NK", "GI": "NG", "KA": "UM", "HI": "RY"}
# az_action_id drop encoding uses a 7-entry python piece-type index (P,L,N,S,B,R,G per
# the comment in shogi.h's convertAZ); rev_piece_map converts that back to sunfish kind.
REV_PIECE_MAP = [0, 1, 2, 3, 5, 6, 4]

PAWN, LANCE, KNIGHT, SILVER, GOLD, BISHOP, ROOK, KING = range(8)


def get_to_sq_from_direction(from_sq, direction_id):
    """Mirrors ShogiAction::get_to_sq_from_direction in shogi.h (rank-major squares)."""
    from_rank, from_file = divmod(from_sq, 9)
    if direction_id == 0:
        dx, dy = -1, -2
    elif direction_id == 1:
        dx, dy = 1, -2
    elif 2 <= direction_id <= 9:
        d = direction_id - 2 + 1
        dx, dy = 0, -d
    elif 10 <= direction_id <= 17:
        d = direction_id - 10 + 1
        dx, dy = 0, d
    elif 18 <= direction_id <= 25:
        d = direction_id - 18 + 1
        dx, dy = -d, 0
    elif 26 <= direction_id <= 33:
        d = direction_id - 26 + 1
        dx, dy = d, 0
    elif 34 <= direction_id <= 41:
        d = direction_id - 34 + 1
        dx, dy = -d, -d
    elif 42 <= direction_id <= 49:
        d = direction_id - 42 + 1
        dx, dy = d, -d
    elif 50 <= direction_id <= 57:
        d = direction_id - 50 + 1
        dx, dy = -d, d
    elif 58 <= direction_id <= 65:
        d = direction_id - 58 + 1
        dx, dy = d, d
    else:
        return -1

    to_file = from_file + dx
    to_rank = from_rank + dy
    if not (0 <= to_file <= 8 and 0 <= to_rank <= 8):
        return -1
    return to_rank * 9 + to_file


def decode_action(az_action_id, is_white_move):
    """Returns either ('drop', kind, file_to, rank_to) or
    ('move', file_from, rank_from, file_to, rank_to, promote_flag)."""
    if az_action_id < 7 * BOARD_AREA:
        py_piece_type = az_action_id // BOARD_AREA
        rotated_to = az_action_id % BOARD_AREA
        az_to = (BOARD_AREA - 1 - rotated_to) if is_white_move else rotated_to
        kind = REV_PIECE_MAP[py_piece_type]
        file_to, rank_to = az_to % 9 + 1, az_to // 9 + 1
        return ("drop", kind, file_to, rank_to)

    move_id_raw = az_action_id - 7 * BOARD_AREA
    rotated_from, move_type_id = divmod(move_id_raw, 132)
    direction_id, promote = divmod(move_type_id, 2)
    rotated_to = get_to_sq_from_direction(rotated_from, direction_id)
    if rotated_to == -1:
        return None

    az_from = (BOARD_AREA - 1 - rotated_from) if is_white_move else rotated_from
    az_to = (BOARD_AREA - 1 - rotated_to) if is_white_move else rotated_to
    file_from, rank_from = az_from % 9 + 1, az_from // 9 + 1
    file_to, rank_to = az_to % 9 + 1, az_to // 9 + 1
    return ("move", file_from, rank_from, file_to, rank_to, bool(promote))


class Board:
    """(file, rank) -> ('B'|'W', kind, promoted) or None. file/rank in 1..9."""

    def __init__(self):
        self.cells = {}
        self.hands = {"B": {k: 0 for k in range(7)}, "W": {k: 0 for k in range(7)}}
        back = [LANCE, KNIGHT, SILVER, GOLD, KING, GOLD, SILVER, KNIGHT, LANCE]
        for file in range(1, 10):
            self.cells[(file, 9)] = ("B", back[file - 1], False)
            self.cells[(file, 1)] = ("W", back[file - 1], False)
            self.cells[(file, 7)] = ("B", PAWN, False)
            self.cells[(file, 3)] = ("W", PAWN, False)
        self.cells[(2, 8)] = ("B", ROOK, False)
        self.cells[(8, 8)] = ("B", BISHOP, False)
        self.cells[(8, 2)] = ("W", ROOK, False)
        self.cells[(2, 2)] = ("W", BISHOP, False)

    def apply(self, mover, decoded):
        """Mutates board state; returns the CSA move-line piece code + coords."""
        if decoded[0] == "drop":
            _, kind, file_to, rank_to = decoded
            self.hands[mover][kind] -= 1
            self.cells[(file_to, rank_to)] = (mover, kind, False)
            return "00", f"{file_to}{rank_to}", KIND_CSA[kind]

        _, file_from, rank_from, file_to, rank_to, promote = decoded
        piece = self.cells.pop((file_from, rank_from))
        _, kind, was_promoted = piece
        captured = self.cells.get((file_to, rank_to))
        if captured is not None:
            cap_kind = captured[1]
            self.hands[mover][cap_kind] += 1
        now_promoted = was_promoted or promote
        self.cells[(file_to, rank_to)] = (mover, kind, now_promoted)
        code = PROMOTED_CSA[KIND_CSA[kind]] if now_promoted and KIND_CSA[kind] in PROMOTED_CSA else KIND_CSA[kind]
        return f"{file_from}{rank_from}", f"{file_to}{rank_to}", code


def game_to_csa(action_pairs, result=None, cap=0):
    """action_pairs: list of (player_char 'B'/'W', action_id:int).

    result: the game's RE tag as a float (Black's perspective: >0 Black won,
    <0 White won, 0 draw), or None if unknown.
    cap: env_shogi_max_moves used for this game, or 0/unknown. Needed to tell
    a sennichite draw (ended before the cap) from a move-cap adjudication tie
    (ended at/after the cap) -- both have result==0 but CSA marks them
    differently (%SENNICHITE vs %HIKIWAKE).
    """
    board = Board()
    lines = ["V2", "PI", "+"]
    last_mover = None
    for player_char, action_id in action_pairs:
        is_white = player_char == "W"
        decoded = decode_action(action_id, is_white)
        if decoded is None:
            lines.append(f"# undecodable action_id={action_id}")
            continue
        mover = "B" if player_char == "B" else "W"
        last_mover = mover
        from_str, to_str, piece_code = board.apply(mover, decoded)
        sign = "+" if mover == "B" else "-"
        lines.append(f"{sign}{from_str}{to_str}{piece_code}")

    # CSA end-of-game marker -- without this, viewers like ShogiHome treat
    # the record as still in progress even though minizero already recorded
    # a definite result (RE tag) for it.
    if result is not None:
        n_moves = sum(1 for p in lines if p[0] in "+-" and len(p) > 1 and p[1].isdigit())
        if result == 0.0:
            lines.append("%HIKIWAKE" if (cap and n_moves >= cap) else "%SENNICHITE")
        else:
            # minizero's actor resigns (or is adjudicated) rather than playing
            # to an on-board checkmate in almost all games; CSA's convention
            # is to record any decisive non-continuing end as %TORYO
            # (resignation), the mover who didn't make the last move "resigns".
            lines.append("%TORYO")
    return "\n".join(lines) + "\n"


def parse_sgf_records(content, default_cap=0):
    """Splits a minizero game-record file into per-game (;...) records and
    extracts the ordered list of (player, action_id) pairs plus the RE
    (result) tag from each."""
    starts = [m.start() for m in re.finditer(r"\(;", content)]
    games = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(content)
        chunk = content[s:e]
        pairs = re.findall(r";([BW])\[(\d+)\]", chunk)
        re_match = re.search(r"RE\[([^\]]*)\]", chunk)
        result = float(re_match.group(1)) if re_match else None
        games.append(([(p, int(a)) for p, a in pairs], result))
    return games


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("sgf_file", help="minizero game-record file (e.g. TRAIN_DIR/sgf/5.sgf)")
    ap.add_argument("-o", "--out_dir", default="",
                     help="write one .csa file per game here instead of stdout")
    ap.add_argument("--cap", type=int, default=0,
                     help="env_shogi_max_moves used to generate this file (from the "
                          "training dir's .cfg) -- only affects whether a draw is "
                          "labeled %%SENNICHITE vs %%HIKIWAKE; omit if unknown")
    args = ap.parse_args()

    with open(args.sgf_file) as f:
        content = f.read()
    games = parse_sgf_records(content)

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(args.sgf_file))[0]
        for i, (pairs, result) in enumerate(games):
            out_path = os.path.join(args.out_dir, f"{base}_{i}.csa")
            with open(out_path, "w") as f:
                f.write(game_to_csa(pairs, result, args.cap))
        print(f"wrote {len(games)} CSA file(s) to {args.out_dir}", file=sys.stderr)
    else:
        for pairs, result in games:
            print(game_to_csa(pairs, result, args.cap))


if __name__ == "__main__":
    main()
