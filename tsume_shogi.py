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
_HAND_IDX: dict[str, int] = {p: i for i, p in enumerate(_HAND_ORDER)}

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
    if dx == -1 and dy == -2:
        return 0   # 桂馬 左
    if dx == 1 and dy == -2:
        return 1   # 桂馬 右
    if dx == 0 and dy < 0:
        return 2 + (-dy - 1)   # 上
    if dx == 0 and dy > 0:
        return 10 + (dy - 1)   # 下
    if dy == 0 and dx < 0:
        return 18 + (-dx - 1)   # 左
    if dy == 0 and dx > 0:
        return 26 + (dx - 1)   # 右
    if dx < 0 and dy < 0 and dx == dy:
        return 34 + (-dx - 1)  # 左上
    if dx > 0 and dy < 0 and dx == -dy:
        return 42 + (dx - 1)  # 右上
    if dx < 0 and dy > 0 and dx == -dy:
        return 50 + (-dx - 1)  # 左下
    if dx > 0 and dy > 0 and dx == dy:
        return 58 + (dx - 1)  # 右下
    return -1


# ── coordinate helpers ─────────────────────────────────────────────────────────

def _usi_sq_to_py(file_ch: str, rank_ch: str, is_black: bool) -> int:
    """
    USI square (e.g. '5', 'e') → Python flat index (row*9 + col).
    col 0 = 1筋, col 8 = 9筋 (canonical C++ convertAZ / getFeatures frame).
    """
    shogi_file = int(file_ch)        # 1..9  (1筋..9筋)
    shogi_rank = ord(rank_ch) - ord("a") + 1  # 1..9 (a=一段..i=九段)
    row = shogi_rank - 1
    col = shogi_file - 1             # canonical (C++ convertAZ): 1筋→col0, 9筋→col8
    sq = row * 9 + col
    return (80 - sq) if not is_black else sq


# ── public API ─────────────────────────────────────────────────────────────────

def sfen_to_tensor(sfen: str, device: str = "cpu") -> torch.Tensor:
    """
    Convert a SFEN string to the MiniZero (1, 362, 9, 9) float32 tensor.

    A position of a game in _GAME_MOVES is replayed from the initial position
    by the C++ environment, so the 7 previous positions are filled as in
    training. Any other SFEN encodes only the current position (t=0 history
    step); history steps t=1..7 are left as zeros, which the network never
    sees in the middle of a game.

    Args:
        sfen   : full SFEN string, e.g. "4k4/9/4R4/... b G 1"
        device : 'cpu' or 'cuda'

    Returns:
        Tensor of shape (1, 362, 9, 9)
    """
    if sfen.strip() in _GAME_MOVES:
        return _replay(_GAME_MOVES[sfen.strip()]).to(device)
    parts = sfen.strip().split()
    if len(parts) < 3:
        raise ValueError(f"Invalid SFEN (need at least 3 fields): {sfen!r}")

    board_str = parts[0]
    turn = parts[1]          # 'b' or 'w'
    hand_str = parts[2]          # '-' or e.g. '2P3LG'

    is_black = (turn == "b")
    features = np.zeros((362, 9, 9), dtype=np.float32)

    # ── board pieces (t=0, channels 0-27) ────────────────────────────────────
    rank = 0
    for row_str in board_str.split("/"):
        col = 0
        promoted = False
        i = 0
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
                # SFEN lists files left→right as 9筋..1筋 (col 0 = 9筋);
                # canonical tensor frame is col = file-1 (1筋→0), so mirror: f = 8 - col.
                r = rank
                f = 8 - col
                if not is_black:      # flip board 180° for white's turn (matches getFeatures)
                    r = 8 - r
                    f = 8 - f

                is_ours = (piece_is_black == is_black)
                side_off = 0 if is_ours else 14
                ch_idx = side_off + kind
                features[ch_idx, r, f] = 1.0

            col += 1
            i += 1
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
                    base = 31 if is_ours else 38
                    ch_idx = base + _HAND_IDX[pt]
                    features[ch_idx, :, :] = float(count)
                count = 1

    # the position has appeared once: getFeatures() fills the first repetition plane
    features[28, :, :] = 1.0

    # ── global channels (360=turn, 361=move_count) ────────────────────────────
    if is_black:
        features[360, :, :] = 1.0
    if len(parts) >= 4:
        try:
            # SFEN counts the initial position as move 1; getFeatures() uses the
            # number of moves played, which is 0 there. Subtract one or every
            # position carries a move count one larger than the network was
            # trained on.
            features[361, :, :] = max(int(parts[3]) - 1, 0) / 512.0
        except ValueError:
            pass

    tensor = torch.from_numpy(features).unsqueeze(0)   # (1, 362, 9, 9)
    return tensor.to(device)


def _replay_env(moves: list[str]):
    """The C++ environment the network was trained with, after the USI moves from the
    initial position."""
    import os
    from xai_analysis import _load_build_so
    root = os.path.dirname(os.path.abspath(__file__))
    env_py = _load_build_so(os.path.join(root, "build", "shogi"), "env_py")
    env_py.init(os.path.join(root, "configs", "9x9_shogi", "RRTRRT-bigserver.cfg"))
    env = env_py.Env()
    env.reset()
    for m in moves:
        env.act({a.to_console_string(): a for a in env.get_legal_actions()}[m])
    return env


def _replay(moves: list[str]) -> torch.Tensor:
    """Features after playing the USI moves from the initial position."""
    env = _replay_env(moves)
    return torch.tensor(np.asarray(env.get_features(), dtype=np.float32).reshape(1, 362, 9, 9))


def legal_moves(sfen: str) -> list[str] | None:
    """The legal moves (USI) of a preset that comes from a game record; None for any
    other SFEN, whose legal moves this module cannot work out."""
    if sfen.strip() not in _GAME_MOVES:
        return None
    return [a.to_console_string() for a in _replay_env(_GAME_MOVES[sfen.strip()]).get_legal_actions()]


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
        dest = move[2:]
        to_sq = _usi_sq_to_py(dest[0], dest[1], is_black)
        py_pid = _DROP_PIECE_MAP.get(piece_char)
        if py_pid is None:
            raise ValueError(f"Unknown drop piece: {piece_char!r}")
        return py_pid * 81 + to_sq

    # ── board move ────────────────────────────────────────────────────────────
    promote = move.endswith("+")
    core = move.rstrip("+")
    if len(core) != 4:
        raise ValueError(f"Cannot parse move: {move!r}")

    from_sq = _usi_sq_to_py(core[0], core[1], is_black)
    to_sq = _usi_sq_to_py(core[2], core[3], is_black)

    fr, fc = from_sq // 9, from_sq % 9
    tr, tc = to_sq // 9, to_sq % 9
    dx = tc - fc
    dy = tr - fr

    dir_id = _dir_id(dx, dy)
    if dir_id < 0:
        raise ValueError(f"Cannot compute direction for move {move!r} (dx={dx}, dy={dy})")

    promo_off = 1 if promote else 0
    return 7 * 81 + from_sq * 132 + dir_id * 2 + promo_off


# ── famous tsume positions ────────────────────────────────────────────────────

# Each entry: {name, sfen, answer_usi, description}
# All positions verified by hand: initial state has no check, answer move delivers checkmate.
TSUME_POSITIONS: list[dict] = [
    {
        "name": "第13問 1手詰め（歩成）",
        "sfen": "6k2/9/5SP2/4b4/9/9/9/9/9 b -2rb4g3s4n4l17p 1",
        "answer_usi": "3c3b+",
        "description": (
            "後手玉3一、後手角5四。▲3二歩成（と金）。\n"
            "と金は4三の銀が支えるため△同玉と取れず、逃げ場を塞いで詰み。\n"
            "▲3二銀成は△同角で不詰め（銀を動かす手は不正解）。"
        ),
    },
    {
        "name": "第14問 1手詰め（香打）",
        "sfen": "6B2/7n1/7pk/9/7PP/9/9/9/9 b L2rb4g4s3n3l15p 1",
        "answer_usi": "L*1d",
        "description": (
            "後手玉1三、守りの桂2二、歩2三。▲1四香。\n"
            "1四は1五歩が支え△同玉不可。1二は香の利きで封鎖。\n"
            "2二桂は3一角と1三玉の間でピンされ△同桂と取れない。"
        ),
    },
    {
        "name": "第15問 1手詰め（飛成・二段ロケット）",
        "sfen": "7k1/6g2/5s1p1/5pp2/8R/9/9/9/8L b r2b3g3s4n3l15p 1",
        "answer_usi": "1e1a+",
        "description": (
            "後手玉2一。飛(1五)と香(1九)が縦に並ぶ「二段ロケット」。▲1一飛成。\n"
            "龍は1九香が支え△同玉不可。横利きで3一、斜め利きで2二を封鎖、\n"
            "3二は後手金が自ら塞ぐ。▲1二飛成は△3一玉で失敗。"
        ),
    },
    {
        "name": "第16問 1手詰め（銀不成）",
        "sfen": "6+B1l/6S1k/6pp1/5p2p/9/9/9/9/9 b 2rb4g3s4n3l14p 1",
        "answer_usi": "3b2a",
        "description": (
            "後手玉1二。▲2一銀不成で王手。1一は後手香、2三は後手歩で塞がり、\n"
            "1三・2二は3一馬の斜め利きが通る。▲2一馬は2二の利きが消え\n"
            "△1三玉で失敗（不成が正解）。"
        ),
    },
    {
        "name": "藤井-羽生2018 60手目（先手番）",
        "sfen": "l7l/1r2gkg1p/2n1p1np1/p1ppsspR1/1p3p2L/P1P1S1P2/1PSPP1N2/2G2G3/LNK6 b B2Pbp 61",
        "answer_usi": "2d2i",
        "description": (
            "第11回朝日杯将棋オープン戦 準決勝 藤井聡太 対 羽生善治、60手目（先手番）。\n"
            "分布内の中盤局面でモデルの確信度が高い（entropy 0.44）。実戦次手は▲2九飛。"
        ),
    },
    {
        "name": "藤井-羽生2018 80手目（先手番）",
        "sfen": "lr6l/4gk2p/2n1pgnp1/3p2p2/P1p1sps1L/2P1S4/LP1PP1N2/1G3G3/1NK4R1 b B4Pbs2p 81",
        "answer_usi": "5f5e",
        "description": (
            "同一対局の80手目（先手番）。モデルの確信度が高い（entropy 0.48）。\n"
            "実戦次手は▲5五銀（モデルの最有力手とも一致）。"
        ),
    },
    {
        "name": "藤井-羽生2018 103手目（後手番）",
        "sfen": "lr5p+R/4g1b1p/2n1p1nP1/3p1kp2/P4ps1L/3B2n2/LP+pPP1N2/G3K1G2/s+p7 w GSL3Ps2p 104",
        "answer_usi": "S*5e",
        "description": (
            "同一対局の103手目（▲6六角）の後、後手番。実戦次手は▽5五銀打（駒打ち）。"
        ),
    },
    {
        "name": "藤井-羽生2018 118手目（寄せ・先手番）",
        "sfen": "lr5p+R/4g2+Pp/2+P1pbn2/3p2p2/P3kp2L/6n2/LP+pPP1N2/G3K1G2/s+pb6 b GSNL2P2s2p 119",
        "answer_usi": "N*4g",
        "description": (
            "同一対局の118手目（先手番）。実戦次手は▲4七桂打で、次に羽生が投了。\n"
            "終盤の寄せ局面でモデルはやや散漫（entropy 3.13）。"
        ),
    },
    {
        "name": "藤井-羽生2018 投了図（後手番）",
        "sfen": "lr5p+R/4g2+Pp/2+P1pbn2/3p2p2/P3kp2L/6n2/LP+pPPNN2/G3K1G2/s+pb6 w GSL2P2s2p 120",
        "answer_usi": "",
        "description": (
            "同一対局の最終局面（▲4七桂打まで、後手番）。ここで羽生が投了。\n"
            "120手目は指されないため query 手は空（必要なら任意の手を手入力）。"
        ),
    },
]

# 藤井聡太 対 羽生善治, the semifinal of the 11th Asahi Cup (2018-02-17), 119 moves, won by black.
# From the record on https://sakidori-ch.com/fujiisouta-20180217 (credited to 連盟モバイル), read
# with move 86 as 8九歩成 (the page says 8九飛成, which cannot be played) and move 115 as 5五銀打
# (the page leaves out 打); so read, the positions after moves 60, 80 and 118 equal the SFENs above.
FUJII_HABU_2018 = """
    2g2f 8c8d 7g7f 4a3b 6i7h 8d8e 8h7g 3c3d 7i6h 4c4d 3i4h 7a6b 4g4f 6c6d 4h4g 6b6c 4g5f 6c5d
    5i6i 3a4b 6i7i 6a5b 2f2e 2b3c 3g3f 4b4c 2i3g 5a4b 9g9f 9c9d 1g1f 1c1d 4i4h 7c7d 4f4e 4d4e
    7g3c+ 2a3c 2e2d 2c2d 2h2d P*2c 2d2i B*4d B*7g 4d7g+ 6h7g 8a7c B*1g B*4d 1g4d 4c4d 1f1e 1d1e
    P*2d 2c2d 1i1e P*1b 2i2d P*2c 2d2i 7d7e 7g6f 9d9e 9f9e P*9g 9i9g 8e8f 8g8f 8b8f P*8g 8f8a
    3f3e 4d3e 6f5e P*8h 7h8h 5d5e P*4c 3b4c 5f5e S*9i 8h9h P*8h 2i2c+ 8h8i+ 7i6h B*3b 2c2b P*2a
    2b1a N*3f 4h3h 7e7f P*2c 7f7g+ 6h5h 4c4d P*4c 4b4c 5e4d 4c4d B*6f S*5e 6f5e 4d5e S*5f 5e5d
    2c2b+ 3b4c P*7d 3e4f 7d7c+ B*7i S*5e 4f5e 5f5e 5d5e N*4g
""".split()

# SFEN of a preset -> the moves that lead to it, to fill the history planes
_GAME_MOVES: dict[str, list[str]] = {
    p["sfen"]: FUJII_HABU_2018[:int(p["sfen"].split()[3]) - 1]
    for p in TSUME_POSITIONS if p["name"].startswith("藤井-羽生2018")
}

TSUME_NAMES: list[str] = [p["name"] for p in TSUME_POSITIONS]
_TSUME_BY_NAME: dict[str, dict] = {p["name"]: p for p in TSUME_POSITIONS}


def get_tsume(name: str) -> dict:
    """Return position dict by name, or raise KeyError."""
    return _TSUME_BY_NAME[name]
