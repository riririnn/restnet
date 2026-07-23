#!/usr/bin/env python3
"""
Coordinate / move conversions for MiniZero shogi action ids.

Single source of truth for the AlphaZero action encoding used by the shogi
environment, so converters (CSA export, USI bridge) cannot drift apart.

File-axis convention (verified empirically against the engine: the encoded
move 7g7f was played on a fresh board and the 7七 pawn was confirmed to be
the piece that moved -- the opposite convention moves the 3七 pawn):

    col = 9 - file      (9筋 -> col 0, 1筋 -> col 8)
    row = rank - 1      (一段 -> row 0, 九段 -> row 8)
    square = row * 9 + col

Squares are stored from the moving side's point of view: white's squares are
rotated 180 degrees (sq -> 80 - sq), matching ShogiAction::convertAZ().

Action id layout (11259 total):
    0 .. 566        drops:  piece_id * 81 + to_square      (piece_id below)
    567 ..          board moves: 7*81 + from_sq * 132 + dir_id * 2 + promote
"""

BOARD_AREA = 81
NUM_DROP_ACTIONS = 7 * BOARD_AREA

# drop piece id (from shogi.h piece_map): P=0 L=1 N=2 S=3 B=4 R=5 G=6
DROP_PIECE_CHARS = ["P", "L", "N", "S", "B", "R", "G"]
DROP_PIECE_ID = {c: i for i, c in enumerate(DROP_PIECE_CHARS)}

# CSA piece names indexed by drop piece id
DROP_PIECE_CSA = ["FU", "KY", "KE", "GI", "KA", "HI", "KI"]

# CSA names for board pieces, indexed by "kind" as used by the Board tracker
# below: P=0 L=1 N=2 S=3 G=4 B=5 R=6 K=7
KIND_CSA = ["FU", "KY", "KE", "GI", "KI", "KA", "HI", "OU"]
PROMOTED_CSA = {"FU": "TO", "KY": "NY", "KE": "NK", "GI": "NG", "KA": "UM", "HI": "RY"}
# drop piece id -> Board kind
DROP_ID_TO_KIND = [0, 1, 2, 3, 5, 6, 4]


def square(file, rank):
    """(file 1-9, rank 1-9) -> absolute square index."""
    return (rank - 1) * 9 + (9 - file)


def square_to_file_rank(sq):
    """absolute square index -> (file, rank)."""
    return 9 - (sq % 9), sq // 9 + 1


def rotate(sq, is_black):
    """Absolute square <-> side-to-move square (involutive)."""
    return sq if is_black else 80 - sq


def dir_id(dx, dy):
    """(col delta, row delta) -> direction id (mirrors shogi.h)."""
    if dx == -1 and dy == -2: return 0
    if dx == 1 and dy == -2:  return 1
    if dx == 0 and dy < 0:    return 2 + (-dy - 1)
    if dx == 0 and dy > 0:    return 10 + (dy - 1)
    if dy == 0 and dx < 0:    return 18 + (-dx - 1)
    if dy == 0 and dx > 0:    return 26 + (dx - 1)
    if dx < 0 and dy < 0 and dx == dy:  return 34 + (-dx - 1)
    if dx > 0 and dy < 0 and dx == -dy: return 42 + (dx - 1)
    if dx < 0 and dy > 0 and dx == -dy: return 50 + (-dx - 1)
    if dx > 0 and dy > 0 and dx == dy:  return 58 + (dx - 1)
    return -1


def dir_delta(d):
    """direction id -> (col delta, row delta); inverse of dir_id."""
    if d == 0: return -1, -2
    if d == 1: return 1, -2
    if 2 <= d <= 9:   return 0, -(d - 2 + 1)
    if 10 <= d <= 17: return 0, (d - 10 + 1)
    if 18 <= d <= 25: return -(d - 18 + 1), 0
    if 26 <= d <= 33: return (d - 26 + 1), 0
    if 34 <= d <= 41: return -(d - 34 + 1), -(d - 34 + 1)
    if 42 <= d <= 49: return (d - 42 + 1), -(d - 42 + 1)
    if 50 <= d <= 57: return -(d - 50 + 1), (d - 50 + 1)
    if 58 <= d <= 65: return (d - 58 + 1), (d - 58 + 1)
    return None


def decode_action(action_id, is_black):
    """action id -> move description, in absolute (file, rank) coordinates.

    Returns ('drop', drop_piece_id, to_file, to_rank)
         or ('move', from_file, from_rank, to_file, to_rank, promote)
         or None if the id does not encode an on-board move.
    """
    if action_id < NUM_DROP_ACTIONS:
        piece_id, to_rot = divmod(action_id, BOARD_AREA)
        f, r = square_to_file_rank(rotate(to_rot, is_black))
        return ("drop", piece_id, f, r)

    rest = action_id - NUM_DROP_ACTIONS
    from_rot, move_type = divmod(rest, 132)
    d, promote = divmod(move_type, 2)
    delta = dir_delta(d)
    if delta is None:
        return None
    dx, dy = delta
    to_col = (from_rot % 9) + dx
    to_row = (from_rot // 9) + dy
    if not (0 <= to_col <= 8 and 0 <= to_row <= 8):
        return None
    to_rot = to_row * 9 + to_col
    ff, fr = square_to_file_rank(rotate(from_rot, is_black))
    tf, tr = square_to_file_rank(rotate(to_rot, is_black))
    return ("move", ff, fr, tf, tr, bool(promote))


# ── USI ────────────────────────────────────────────────────────────────────────

def _usi_sq(file, rank):
    return f"{file}{chr(ord('a') + rank - 1)}"


def _parse_usi_sq(s):
    return int(s[0]), ord(s[1]) - ord("a") + 1


def action_id_to_usi(action_id, is_black):
    """action id -> USI move string (e.g. '7g7f', '2b3c+', 'P*5e')."""
    dec = decode_action(action_id, is_black)
    if dec is None:
        raise ValueError(f"action id {action_id} does not encode a move")
    if dec[0] == "drop":
        _, piece_id, f, r = dec
        return f"{DROP_PIECE_CHARS[piece_id]}*{_usi_sq(f, r)}"
    _, ff, fr, tf, tr, promote = dec
    return _usi_sq(ff, fr) + _usi_sq(tf, tr) + ("+" if promote else "")


def usi_to_action_id(move, is_black):
    """USI move string -> action id; inverse of action_id_to_usi."""
    move = move.strip()
    if "*" in move:
        piece_char, dest = move[0].upper(), move[2:]
        if piece_char not in DROP_PIECE_ID:
            raise ValueError(f"unknown drop piece: {move!r}")
        f, r = _parse_usi_sq(dest)
        return DROP_PIECE_ID[piece_char] * BOARD_AREA + rotate(square(f, r), is_black)

    promote = move.endswith("+")
    core = move.rstrip("+")
    if len(core) != 4:
        raise ValueError(f"cannot parse move: {move!r}")
    from_rot = rotate(square(*_parse_usi_sq(core[0:2])), is_black)
    to_rot = rotate(square(*_parse_usi_sq(core[2:4])), is_black)
    d = dir_id((to_rot % 9) - (from_rot % 9), (to_rot // 9) - (from_rot // 9))
    if d < 0:
        raise ValueError(f"cannot encode move {move!r} as a direction")
    return NUM_DROP_ACTIONS + from_rot * 132 + d * 2 + (1 if promote else 0)


if __name__ == "__main__":
    # round-trip self-test: every encodable board move and drop, both colours
    checked = 0
    for aid in range(11259):
        for is_black in (True, False):
            dec = decode_action(aid, is_black)
            if dec is None:
                continue
            usi = action_id_to_usi(aid, is_black)
            back = usi_to_action_id(usi, is_black)
            assert back == aid, f"round trip failed: {aid} -> {usi} -> {back}"
            checked += 1
    print(f"round-trip OK for {checked} (action id, colour) pairs")
    # spot check against the empirically verified convention
    assert action_id_to_usi(7963, True) == "7g7f", action_id_to_usi(7963, True)
    print("7963 (black) == 7g7f  OK")
