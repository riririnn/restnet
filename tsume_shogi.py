"""
Tsume-Shogi (詰将棋) position encoder for ResTNet XAI analysis.

Converts SFEN strings and USI move notation to the MiniZero 362-channel
tensor format expected by AlphaZeroNetwork.

Feature layout (from minizero/environment/shogi/shogi.cpp):
  8 history steps × 45 channels/step + 2 global = 362 total
  Per step:
    ch  0-27 : board pieces (14 ours + 14 opponent), kind index below
    ch 28-30 : repetition count (千日手 1/2/3)
    ch 31-37 : our hand pieces   [P,L,N,S,B,R,G]
    ch 38-44 : enemy hand pieces [P,L,N,S,B,R,G]
  Global:
    ch 360   : turn (1.0 = black/先手)
    ch 361   : move count / 512

Piece kind indices (0-13):
  P=0 L=1 N=2 S=3 G=4 B=5 R=6 K=7  +P=8 +L=9 +N=10 +S=11 +B=12 +R=13

Board coordinate convention (when black's turn):
  row 0 = rank 1 (一段, black's opponent back rank)
  col 0 = 9筋 (leftmost in standard diagram)
  col 8 = 1筋 (rightmost)
  This matches SFEN left-to-right order exactly for black's turn.
"""

from __future__ import annotations
import numpy as np
import torch

# ── piece tables ───────────────────────────────────────────────────────────────

# SFEN char (upper) → piece kind index
_PIECE_KIND: dict[str, int] = {
    "P": 0, "L": 1, "N": 2, "S": 3, "G": 4, "B": 5, "R": 6, "K": 7
}
# With '+' prefix → promoted kind index
_PROMO_KIND: dict[str, int] = {
    "P": 8, "L": 9, "N": 10, "S": 11, "B": 12, "R": 13
}

# Hand piece order in feature channels (matches C++ py_hand_mapping)
_HAND_ORDER: list[str] = ["P", "L", "N", "S", "B", "R", "G"]
_HAND_IDX:  dict[str, int] = {p: i for i, p in enumerate(_HAND_ORDER)}

# Drop action piece map: hand piece char → Python action piece id
# From shogi.h: piece_map[] = {P:0, L:1, N:2, S:3, G:6, B:4, R:5}
_DROP_PIECE_MAP: dict[str, int] = {
    "P": 0, "L": 1, "N": 2, "S": 3, "B": 4, "R": 5, "G": 6
}

# ── direction id table (mirrors shogi.h map_dx_dy_to_direction_id) ─────────────

def _dir_id(dx: int, dy: int) -> int:
    """
    dx = file-delta (positive = rightward = toward 1筋)
    dy = rank-delta (positive = downward = toward 9段)
    Matches the direction_id table in shogi.h exactly.
    """
    if dx == -1 and dy == -2: return 0   # 桂馬 左
    if dx ==  1 and dy == -2: return 1   # 桂馬 右
    if dx == 0  and dy <  0:  return  2 + (-dy - 1)   # 上
    if dx == 0  and dy >  0:  return 10 + ( dy - 1)   # 下
    if dy == 0  and dx <  0:  return 18 + (-dx - 1)   # 左
    if dy == 0  and dx >  0:  return 26 + ( dx - 1)   # 右
    if dx < 0 and dy < 0 and dx == dy:   return 34 + (-dx - 1)  # 左上
    if dx > 0 and dy < 0 and dx == -dy:  return 42 + ( dx - 1)  # 右上
    if dx < 0 and dy > 0 and dx == -dy:  return 50 + (-dx - 1)  # 左下
    if dx > 0 and dy > 0 and dx ==  dy:  return 58 + ( dx - 1)  # 右下
    return -1


# ── coordinate helpers ─────────────────────────────────────────────────────────

def _usi_sq_to_py(file_ch: str, rank_ch: str, is_black: bool) -> int:
    """
    USI square (e.g. '5', 'e') → Python flat index (row*9 + col).
    col 0 = 9筋, col 8 = 1筋 (matches SFEN order).
    """
    shogi_file = int(file_ch)        # 1..9  (1筋..9筋)
    shogi_rank = ord(rank_ch) - ord("a") + 1  # 1..9 (a=一段..i=九段)
    row = shogi_rank - 1
    col = 9 - shogi_file             # 1筋→col8, 9筋→col0
    sq = row * 9 + col
    return (80 - sq) if not is_black else sq


# ── public API ─────────────────────────────────────────────────────────────────

def sfen_to_tensor(sfen: str, device: str = "cpu") -> torch.Tensor:
    """
    Convert a SFEN string to the MiniZero (1, 362, 9, 9) float32 tensor.

    Only the current position is encoded (t=0 history step).
    History steps t=1..7 are left as zeros, which is acceptable for
    attention / IG visualisation of a single position.

    Args:
        sfen   : full SFEN string, e.g. "4k4/9/4R4/... b G 1"
        device : 'cpu' or 'cuda'

    Returns:
        Tensor of shape (1, 362, 9, 9)
    """
    parts = sfen.strip().split()
    if len(parts) < 3:
        raise ValueError(f"Invalid SFEN (need at least 3 fields): {sfen!r}")

    board_str = parts[0]
    turn      = parts[1]          # 'b' or 'w'
    hand_str  = parts[2]          # '-' or e.g. '2P3LG'

    is_black  = (turn == "b")
    features  = np.zeros((362, 9, 9), dtype=np.float32)

    # ── board pieces (t=0, channels 0-27) ────────────────────────────────────
    rank = 0
    for row_str in board_str.split("/"):
        col     = 0
        promoted = False
        i       = 0
        while i < len(row_str):
            ch = row_str[i]
            if ch == "+":
                promoted = True
                i += 1
                continue
            if ch.isdigit():
                col += int(ch)
                i += 1
                continue

            piece_upper = ch.upper()
            piece_is_black = ch.isupper()

            kind = (_PROMO_KIND if promoted else _PIECE_KIND).get(piece_upper, -1)
            promoted = False

            if kind >= 0:
                r = rank
                f = col
                if not is_black:      # flip board for white's turn
                    r = 8 - r
                    f = 8 - f

                is_ours   = (piece_is_black == is_black)
                side_off  = 0 if is_ours else 14
                ch_idx    = side_off + kind
                features[ch_idx, r, f] = 1.0

            col += 1
            i   += 1
        rank += 1

    # ── hand pieces (t=0, channels 31-44) ────────────────────────────────────
    if hand_str != "-":
        count = 1
        digits = ""
        for ch in hand_str:
            if ch.isdigit():
                digits += ch
            else:
                count = int(digits) if digits else 1
                digits = ""
                pt = ch.upper()
                if pt in _HAND_IDX:
                    piece_is_black = ch.isupper()
                    is_ours = (piece_is_black == is_black)
                    base  = 31 if is_ours else 38
                    ch_idx = base + _HAND_IDX[pt]
                    features[ch_idx, :, :] = float(count)
                count = 1

    # ── global channels (360=turn, 361=move_count) ────────────────────────────
    if is_black:
        features[360, :, :] = 1.0
    if len(parts) >= 4:
        try:
            features[361, :, :] = int(parts[3]) / 512.0
        except ValueError:
            pass

    tensor = torch.from_numpy(features).unsqueeze(0)   # (1, 362, 9, 9)
    return tensor.to(device)


def usi_to_action_id(move: str, is_black: bool = True) -> int:
    """
    Convert a USI move string to the AlphaZero action_id used by MiniZero.

    Supports:
        Board moves : '7g7f', '2b3c+' (with optional promotion suffix '+')
        Drop moves  : 'P*5e', 'G*4b'

    Args:
        move     : USI move string
        is_black : True if it is black's (先手) turn

    Returns:
        Integer action_id matching ShogiAction::convertAZ()
    """
    move = move.strip()
    if not move:
        raise ValueError("Empty move string")

    # ── drop move ─────────────────────────────────────────────────────────────
    if "*" in move:
        piece_char = move[0].upper()
        dest       = move[2:]
        to_sq  = _usi_sq_to_py(dest[0], dest[1], is_black)
        py_pid = _DROP_PIECE_MAP.get(piece_char)
        if py_pid is None:
            raise ValueError(f"Unknown drop piece: {piece_char!r}")
        return py_pid * 81 + to_sq

    # ── board move ────────────────────────────────────────────────────────────
    promote = move.endswith("+")
    core    = move.rstrip("+")
    if len(core) != 4:
        raise ValueError(f"Cannot parse move: {move!r}")

    from_sq = _usi_sq_to_py(core[0], core[1], is_black)
    to_sq   = _usi_sq_to_py(core[2], core[3], is_black)

    fr, fc = from_sq // 9, from_sq % 9
    tr, tc = to_sq   // 9, to_sq   % 9
    dx = tc - fc
    dy = tr - fr

    dir_id = _dir_id(dx, dy)
    if dir_id < 0:
        raise ValueError(f"Cannot compute direction for move {move!r} (dx={dx}, dy={dy})")

    promo_off = 1 if promote else 0
    return 7 * 81 + from_sq * 132 + dir_id * 2 + promo_off


# ── famous tsume positions ────────────────────────────────────────────────────

# Each entry: {name, sfen, answer_usi, description}
TSUME_POSITIONS: list[dict] = [
    {
        "name": "1手詰め：金打ち",
        "sfen": "4k4/9/4R4/9/9/9/9/9/4K4 b G 1",
        "answer_usi": "G*5b",
        "description": (
            "5一に玉、5三に飛車、持ち駒：金1枚。\n"
            "5二に金を打つと、玉の逃げ場がなく即詰み。\n"
            "飛車が5二の金を守っているため取れない。"
        ),
    },
    {
        "name": "1手詰め：銀打ち",
        "sfen": "8k/7G1/8K/9/9/9/9/9/9 b S 1",
        "answer_usi": "S*1b",
        "description": (
            "1一に玉（隅）、1二に金、持ち駒：銀1枚。\n"
            "1二に銀を打ち、玉の逃げ場をふさいで詰み。"
        ),
    },
    {
        "name": "3手詰め：飛車成り→金打ち",
        "sfen": "4k4/9/9/4R4/9/9/9/9/4K4 b G 1",
        "answer_usi": "5d5b+",
        "description": (
            "5一に玉、5四に飛車、持ち駒：金1枚。\n"
            "手順: ①飛車を5四→5二に成る（5一玉が4一or6一へ逃げる）\n"
            "②金を打って詰み（3手詰めの例示）。"
        ),
    },
    {
        "name": "初期局面（動作確認用）",
        "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
        "answer_usi": "7g7f",
        "description": (
            "将棋の初期局面。詰将棋ではないが、7七歩(7g7f)を\n"
            "IG・Occlusionのターゲット手として解析する動作確認用。"
        ),
    },
]

TSUME_NAMES: list[str] = [p["name"] for p in TSUME_POSITIONS]
_TSUME_BY_NAME: dict[str, dict] = {p["name"]: p for p in TSUME_POSITIONS}


def get_tsume(name: str) -> dict:
    """Return position dict by name, or raise KeyError."""
    return _TSUME_BY_NAME[name]
