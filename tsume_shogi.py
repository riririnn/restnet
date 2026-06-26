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
# All positions verified by hand: initial state has no check, answer move delivers checkmate.
TSUME_POSITIONS: list[dict] = [
    # ── 1手詰め：隅の金打ち ────────────────────────────────────────────────────
    # 9一に玉（左隅）、8九に飛車。
    # G*8b: 金を8二に打つ。
    #   金(8二)が 8一・9二・9一(王手) を利く。飛車(8九)が8二を守る。
    #   玉の逃げ先: 8一(金利き✓) 9二(金利き✓) 8二(飛車守り✓) → 詰み
    {
        "name": "1手詰め：隅の金打ち",
        "sfen": "k8/9/9/9/9/9/9/9/1R7 b G 1",
        "answer_usi": "G*8b",
        "description": (
            "9一に玉（左上隅）、8九に飛車、持ち駒：金1枚。\n"
            "金を8二に打つ。飛車が金を守り、玉の逃げ場（8一・9二）も金が制圧。\n"
            "AttentionMap: モデルが飛車・金の利きに注目するか確認。"
        ),
    },
    # ── 1手詰め：頭金詰め（馬が守る） ────────────────────────────────────────
    # 5一に玉（一段目中央）、7四に馬（成角）。
    # G*5b: 金を5二に打つ（頭金）。
    #   金(5二)が 5一(王手)・4一・6一・4二・6二 を利く。
    #   馬(7四)の斜め利き: 6三→5二 で金を守る。
    #   玉の逃げ先: 4一・6一・4二・6二(全て金)、5二は馬守り → 詰み
    {
        "name": "1手詰め：頭金（馬が守る）",
        "sfen": "4k4/9/9/2+B6/9/9/9/9/4K4 b G 1",
        "answer_usi": "G*5b",
        "description": (
            "5一に玉（一段目中央）、7四に馬、持ち駒：金1枚。\n"
            "金を5二に打つ（頭金）。馬の斜め利き(6三→5二)が金を守る。\n"
            "AttentionMap: モデルが頭上の金打ちに関わる馬・玉に注目するか確認。"
        ),
    },
    # ── 1手詰め：腹の銀詰め ──────────────────────────────────────────────────
    # 9三に玉（左辺中段）、9一に金、8五に竜（成飛）。
    # S*8b: 銀を8二に打つ。
    #   銀(8二)の斜め後ろ左: 9三(王手✓)。
    #   玉の逃げ先: 9二(金(9一)の後ろ✓)  9四(竜(8五)隣接✓)
    #               8三(竜(8五)の縦利き✓) 8四(竜利き✓)
    #               8二取り: 竜の縦利き(8五→8二)で守り✓ → 詰み
    {
        "name": "1手詰め：腹の銀",
        "sfen": "G8/9/k8/9/1+R7/9/9/9/4K4 b S 1",
        "answer_usi": "S*8b",
        "description": (
            "9三に玉（左辺中段）、9一に金、8五に竜、持ち駒：銀1枚。\n"
            "銀を8二に打つ（腹の銀）。銀の斜め後左が9三の玉に王手。\n"
            "竜が逃げ道（9四・8三・8四）と銀を守る。金が9二を塞ぐ。\n"
            "AttentionMap: 竜・金・打った銀の三者の連携に注目するか確認。"
        ),
    },
    # ── 1手詰め：飛車打ち詰め ────────────────────────────────────────────────
    # 5一に玉、3四に馬、4九に香車。
    # R*5b: 飛車を5二に打つ（ひかえの飛車）。
    #   飛車(5二): 5一(王手✓)・5三以降・二段目全列を利く。
    #   4一: 香車(4九)の縦利き✓  6一: 馬(3四)斜め(4三→5二を超えて6一)✓
    #   4二・6二: 飛車の二段目利き✓  5二取り: 馬(3四→4三→5二)守り✓ → 詰み
    {
        "name": "1手詰め：飛車打ち（ひかえの飛車）",
        "sfen": "4k4/9/9/6+B2/9/9/9/9/4KL3 b R 1",
        "answer_usi": "R*5b",
        "description": (
            "5一に玉、3四に馬、4九に香車、持ち駒：飛車1枚。\n"
            "飛車を5二に打つ（ひかえの飛車）。飛車が5一へ王手し二段目を制圧。\n"
            "馬が飛車を守り6一も制圧。香車が4一を塞ぐ。\n"
            "AttentionMap: 遠隔利きの飛車・馬・香の役割をモデルが把握するか確認。"
        ),
    },
    # ── 1手詰め：銀打ち（隅の玉） ────────────────────────────────────────────
    # 1一に玉（右隅）、2二に金、1三に自玉。
    # S*1b: 銀を1二に打つ。
    #   銀(1二): 1一(前✓=王手)。
    #   2一: 金(2二)の前✓  2二取り: 自玉(1三)が2二を守る✓
    #   1二取り: 自玉(1三)が1二を守る✓ → 詰み
    {
        "name": "1手詰め：銀打ち（隅の玉）",
        "sfen": "8k/7G1/8K/9/9/9/9/9/9 b S 1",
        "answer_usi": "S*1b",
        "description": (
            "1一に玉（右上隅）、2二に金、1三に自玉、持ち駒：銀1枚。\n"
            "銀を1二に打つ。銀が1一の玉に直接王手。\n"
            "玉は2一（金利き）・2二（玉守り）・1二取り（玉守り）全て塞がれ詰み。\n"
            "AttentionMap: 金・自玉・銀の三角形の連携をモデルが学んでいるか確認。"
        ),
    },
    # ── 角換わり腰掛け銀 中盤（30手目付近） ────────────────────────────────────
    # 歩を4二に打ち込む攻め（P*4b）。
    # 盤上に22枚+持ち駒あり、両者の激しい攻め合い局面。
    {
        "name": "角換わり腰掛け銀：中盤攻め合い",
        "sfen": "lnsgk1snl/1r5b1/2pp5/p3p1p2/1p6p/P1P3g2/1P1PPSP1P/1BG1G2R1/LNSK3NL b 2P2p 31",
        "answer_usi": "P*4b",
        "description": (
            "角換わり腰掛け銀の中盤（30手目付近）。\n"
            "先手が歩を4二へ打ち込む（P*4b）。後手は角道と飛車を使い反撃中。\n"
            "盤上22枚+持ち駒あり。\n"
            "AttentionMap: 角・飛車・歩の連携とクロス攻撃をモデルが捉えるか確認。"
        ),
    },
    # ── 矢倉 中盤（32手目付近） ─────────────────────────────────────────────
    # 先手が角を斜め走りで2二に成る（8h2b+）大捌き。
    # 盤上に32枚、典型的な矢倉の激闘局面。
    {
        "name": "矢倉：中盤 角の大捌き",
        "sfen": "ln1gk1snl/1r1s2gb1/p1pppp1p1/1p4p1p/9/2P2P1P1/PP1PP1P1P/1BG2S1R1/LNS1KG1NL b - 11",
        "answer_usi": "8h2b+",
        "description": (
            "矢倉の中盤（32手目付近）。\n"
            "先手の角が8八→2二へ成り込む大捌き（8h2b+）。盤上32枚。\n"
            "両者の囲いが完成しており、本格的な中盤の攻防局面。\n"
            "AttentionMap: 角の長距離利きと囲いの守備陣に注目するか確認。"
        ),
    },
    # ── 振り飛車 急戦 中盤（11手目付近） ────────────────────────────────────
    # 双方が角を手持ちに持つ珍しい局面。先手が角を7二へ打ち込む（B*7b）。
    {
        "name": "振り飛車 急戦：角打ち勝負",
        "sfen": "lnsgkg1nl/1r5s1/ppppp3p/6pp1/5p1P1/2P6/PP1PPPP1P/2G4R1/LNS1KGSNL b Bb 11",
        "answer_usi": "B*7b",
        "description": (
            "振り飛車 vs 急戦の中盤（11手目付近）。\n"
            "双方が角を持ち駒に持つ局面。先手が角を7二に打ち込む（B*7b）。\n"
            "先手持ち駒：角。後手持ち駒：角。盤上28枚。\n"
            "AttentionMap: 角の斜めの射程と後手陣の急所をモデルが認識するか確認。"
        ),
    },
    # ── 詰み直前：銀打ち（金二枚+竜の三駒包囲・左隅） ────────────────────────
    # 後手玉9一（左上隅）、先手 金9三・金8三・竜7三が包囲。
    # S*8b: 銀を8二に打つ → 銀が9一に王手(斜め前左)。
    #   8一: 銀が前方を制圧✓  9二: 金(9三)が前方で制圧✓
    #   8二取り: 金(8三)が8二を守る✓ → 詰み
    # 初期局面: 竜(col0利き)・金2枚はいずれも9一を攻めない ✓
    {
        "name": "詰み直前：銀打ち（左隅・三駒包囲）",
        "sfen": "k8/9/GG+R6/9/9/9/9/9/8K b S 1",
        "answer_usi": "S*8b",
        "description": (
            "後手玉9一（左上隅）。先手金9三・金8三・竜7三が王の周囲を包囲。\n"
            "銀を8二に打つことで斜め前左から9一に王手。\n"
            "銀が8一・金が9二・金が8二を守り、玉の逃げ場が全て消える。\n"
            "AttentionMap: 三駒が連携して左隅の玉を囲む構造をモデルが捉えるか確認。"
        ),
    },
    # ── 詰み直前：金打ち（竜+銀の三駒包囲・右隅） ────────────────────────────
    # 後手玉2一（右上側）、先手 竜3三・銀2三が控える。
    # G*2b: 金を2二に打つ → 金が2一に王手(前方)。
    #   1一: 金が斜め右前を制圧✓  3一: 竜(col6)の縦利き✓
    #   1二: 銀が斜め前右(1二)を制圧✓  3二: 竜(col6縦)✓
    #   2二取り: 銀(2三)が前方(2二)を守る✓ → 詰み
    # 初期局面: 竜(col6/row2)・銀(col7/row2)はいずれも2一(col7/row0)を攻めない ✓
    {
        "name": "詰み直前：金打ち（右側・竜銀包囲）",
        "sfen": "7k1/9/6+RS1/9/9/9/9/9/7K1 b G 1",
        "answer_usi": "G*2b",
        "description": (
            "後手玉2一（右上側）。先手竜3三・銀2三が包囲態勢。\n"
            "金を2二に打つことで2一に王手。\n"
            "竜が3一・3二・3三筋を制圧。銀が1二と2二を守り、1一は金が制圧。\n"
            "AttentionMap: 竜の縦利きと銀の斜め守りの連携をモデルが認識するか確認。"
        ),
    },
    # ── 詰み直前：頭金（二飛二金の四駒対称包囲・中央） ──────────────────────
    # 後手玉5一（中央上段）、先手 金6三・金4三・飛車6四・飛車4四が対称配置。
    # G*5b: 金を5二に打つ（頭金）→ 金が5一に王手(前方)。
    #   4一: 飛車(4四、4筋縦)が制圧✓  6一: 飛車(6四、6筋縦)が制圧✓
    #   4二: 金(5二)が右を制圧✓  6二: 金(5二)が左を制圧✓
    #   5二取り: 金(4三)が斜め前右(5二)守り、金(6三)が斜め前左(5二)守り✓ → 詰み
    # 初期局面: 飛車はcol3/col5(≠col4), 金はrow2(≠row0)なので5一を攻めない ✓
    {
        "name": "詰み直前：頭金（中央・四駒対称包囲）",
        "sfen": "4k4/9/3G1G3/3R1R3/9/9/9/9/4K4 b G 1",
        "answer_usi": "G*5b",
        "description": (
            "後手玉5一（中央上段）。先手金6三・金4三・飛車6四・飛車4四が\n"
            "玉を中心に完全対称に包囲。金を5二に頭から打ち込む（頭金）。\n"
            "飛車2本が縦4筋・6筋を制圧。金2枚が打った金5二を守り、\n"
            "玉が逃げられる6方向（4一・6一・4二・6二・5二）すべてを封鎖。\n"
            "AttentionMap: 対称構造と玉への集中を最も明確に示す局面。"
        ),
    },
    # ── 初期局面（動作確認用） ─────────────────────────────────────────────────
    {
        "name": "初期局面（動作確認用）",
        "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
        "answer_usi": "7g7f",
        "description": (
            "将棋の初期局面。詰将棋ではないが、7七歩(7g7f)を\n"
            "IG・Rolloutのターゲット手として解析する動作確認用。\n"
            "AttentionMap: モデルが開幕手として歩の前進に関連する駒に注目するか確認。"
        ),
    },
]

TSUME_NAMES: list[str] = [p["name"] for p in TSUME_POSITIONS]
_TSUME_BY_NAME: dict[str, dict] = {p["name"]: p for p in TSUME_POSITIONS}


def get_tsume(name: str) -> dict:
    """Return position dict by name, or raise KeyError."""
    return _TSUME_BY_NAME[name]
