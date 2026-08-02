"""
XAI analysis for ResTNet Shogi model.

Three complementary methods:
  1. Integrated Gradients  — which board squares drove the value/policy output
  2. Attention Rollout     — how attention propagates through Transformer layers
  3. Perturbation/Occlusion — mask each square and measure the output change

Usage:
    python xai_analysis.py --model path/to/weight.pt --target value
    python xai_analysis.py --model path/to/weight.pt --target policy
    python xai_analysis.py --model path/to/weight.pt --target both
    python xai_analysis.py --model path/to/weight.pt --target perturbation
    python xai_analysis.py --model path/to/weight.pt --target all

Load a real board position from an SGF file:
    python xai_analysis.py --model path/to/weight.pt --target all \\
        --sgf path/to/game.sgf --conf path/to/config.cfg --game-type shogi_9x9
"""

import sys
import os
import argparse

import torch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ──────────────────────────────────────────────────────────────────────────────
# Model loading
# ──────────────────────────────────────────────────────────────────────────────

def load_torchscript_model(model_path: str, device: str = "cpu"):
    """Load .pt TorchScript model. Good for Integrated Gradients."""
    model = torch.jit.load(model_path, map_location=device)
    model.eval()
    return model


def load_python_model(model_path: str, device: str = "cpu"):
    """
    Reconstruct the Python AlphaZeroNetwork from a saved .pt TorchScript file.
    Needed for Attention Rollout (get_attn_table is not exported in TorchScript).
    """
    # Pull weights and hyperparams from the TorchScript model
    ts = torch.jit.load(model_path, map_location=device)
    ts.eval()

    state_dict = ts.state_dict()

    num_input_channels   = ts.get_num_input_channels()
    input_channel_height = ts.get_input_channel_height()
    input_channel_width  = ts.get_input_channel_width()
    num_hidden_channels  = ts.get_num_hidden_channels()
    action_size          = ts.get_action_size()
    num_value_hidden_channels = ts.get_num_value_hidden_channels()
    discrete_value_size  = ts.get_discrete_value_size()
    blocks_type          = ts.blocks_type
    game_name            = ts.get_game_name()

    # Resolve policy / value head types from the first block name in state_dict
    # (simpler: read from config, but we infer from the known blocks_type here)
    # Defaults match the RRTRRT shogi config
    embed_kernel_size = 3
    policy_type = "P"
    value_type  = "TV"

    # Add the project root to path so we can import from restnet/
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from restnet.learner.network.alphazero_network import AlphaZeroNetwork

    num_blocks = len(blocks_type.split("_"))
    model = AlphaZeroNetwork(
        game_name=game_name,
        num_input_channels=num_input_channels,
        input_channel_height=input_channel_height,
        input_channel_width=input_channel_width,
        num_hidden_channels=num_hidden_channels,
        hidden_channel_height=input_channel_height,
        hidden_channel_width=input_channel_width,
        num_blocks=num_blocks,
        action_size=action_size,
        num_value_hidden_channels=num_value_hidden_channels,
        discrete_value_size=discrete_value_size,
        embed_kernel_size=embed_kernel_size,
        blocks_type=blocks_type,
        policy_type=policy_type,
        value_type=value_type,
    )
    model.load_state_dict(state_dict)
    model.eval()
    model.to(device)
    return model


# ──────────────────────────────────────────────────────────────────────────────
# Method 0 — Perturbation / Occlusion
# ──────────────────────────────────────────────────────────────────────────────

def occlusion(
    model,
    board_state: torch.Tensor,
    target: str = "value",
    action_idx: int | None = None,
    device: str = "cpu",
) -> tuple[np.ndarray, int | None]:
    """
    Perturbation / Occlusion sensitivity map.

    For each of the 81 board squares, zero out all 362 channels at that
    position and measure how much the model output changes.
    All 81 masked inputs are batched into a single forward pass for speed.

    Args:
        model      : TorchScript or Python model
        board_state: (1, C, H, W) board tensor
        target     : 'value' or 'policy'
        action_idx : policy action to explain (None → top action)

    Returns:
        attribution: (H, W) numpy array — positive = square mattered
        action_idx : the action explained (None if target='value')
    """
    board_state = board_state.to(device).float()
    H, W = board_state.shape[2], board_state.shape[3]
    N = H * W  # 81

    # baseline score with the unmodified board
    with torch.no_grad():
        orig_out = model(board_state)
        if target == "value":
            orig_score = orig_out["value"].item()
        else:
            if action_idx is None:
                action_idx = int(orig_out["policy"].argmax(dim=1).item())
            orig_score = orig_out["policy"][0, action_idx].item()

    # build a batch of 81 boards, each with one square zeroed
    batch = board_state.expand(N, -1, -1, -1).clone()  # (81, C, H, W)
    for idx in range(N):
        r, c = divmod(idx, W)
        batch[idx, :, r, c] = 0.0

    with torch.no_grad():
        out = model(batch)

    if target == "value":
        scores = out["value"].squeeze(1).cpu().numpy()      # (81,)
    else:
        scores = out["policy"][:, action_idx].cpu().numpy() # (81,)

    # positive → occluding that square hurt the score → it was important
    attribution = (orig_score - scores).reshape(H, W).astype(np.float32)
    return attribution, action_idx


# Hand-piece channel order (matches getFeatures / sfen_to_tensor):
# own hand = channels 31-37, enemy hand = channels 38-44, in this piece order.
_HAND_ORDER = ['P', 'L', 'N', 'S', 'B', 'R', 'G']
_HAND_KANJI_LBL = {'P': '歩', 'L': '香', 'N': '桂', 'S': '銀', 'B': '角', 'R': '飛', 'G': '金'}


def hand_piece_contribution(model, board_state, target="value",
                            action_idx=None, device="cpu"):
    """Contribution of each hand piece to the output, by occluding its channel.

    Hand pieces are non-spatial: each type is a constant plane broadcast over the
    whole board (own = ch 31-37, enemy = ch 38-44), so they cannot be localised on
    an Attention Map. Instead we zero each hand-piece plane and measure how much the
    output changes, giving one scalar contribution per (side, piece type).

    Returns (own, enemy, action_idx): own/enemy are length-7 arrays over
    _HAND_ORDER; a positive value means removing that hand piece lowers the target
    output (the piece helped it). Pieces not held give exactly 0.
    """
    board_state = board_state.to(device).float()
    with torch.no_grad():
        base = model(board_state)
        if target == "value":
            base_score = base["value"].item()
        else:
            if action_idx is None:
                action_idx = int(base["policy"].argmax(dim=1).item())
            base_score = base["policy"][0, action_idx].item()

    own = np.zeros(7, dtype=np.float32)
    enemy = np.zeros(7, dtype=np.float32)
    for i in range(7):
        for arr, base_ch in ((own, 31), (enemy, 38)):
            ch = base_ch + i
            if ch >= board_state.shape[1] or float(board_state[0, ch, 0, 0]) <= 0:
                continue  # this piece is not in hand → no contribution
            masked = board_state.clone()
            masked[:, ch, :, :] = 0.0
            with torch.no_grad():
                out = model(masked)
                s = (out["value"].item() if target == "value"
                     else out["policy"][0, action_idx].item())
            arr[i] = base_score - s
    return own, enemy, action_idx


def visualize_hand_contribution(val_own, val_enemy, pol_own, pol_enemy,
                                pol_label="", save_path=None):
    """Grouped bar chart of hand-piece contributions (own vs enemy) to value and
    to the explained policy move. Non-spatial companion to the Attention Map."""
    labels = [_HAND_KANJI_LBL[p] if _CJK_FONT else p for p in _HAND_ORDER]
    x = np.arange(7)
    w = 0.38
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    fp = {"fontproperties": _CJK_FONT} if _CJK_FONT else {}
    for ax, own, enemy, ttl in (
            (axes[0], val_own, val_enemy, "Value への寄与"),
            (axes[1], pol_own, pol_enemy, f"Policy への寄与 {pol_label}".strip())):
        ax.bar(x - w / 2, own, w, label="先手持駒" if _CJK_FONT else "own",
               color="#D4A96A", edgecolor="#3a2000")
        ax.bar(x + w / 2, enemy, w, label="後手持駒" if _CJK_FONT else "enemy",
               color="#4a6fa5", edgecolor="#1a2a45")
        ax.axhline(0, color="#666", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, **fp)
        ax.set_title(ttl, fontsize=10, **fp)
        ax.tick_params(labelsize=8)
        ax.legend(fontsize=7, prop=_CJK_FONT if _CJK_FONT else None)
    axes[0].set_ylabel("寄与（除去で出力が下がる量）" if _CJK_FONT
                       else "contribution", fontsize=8, **fp)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Method 1 — Integrated Gradients
# ──────────────────────────────────────────────────────────────────────────────

def integrated_gradients(
    model,
    board_state: torch.Tensor,
    target: str = "value",
    action_idx: int | None = None,
    steps: int = 50,
    device: str = "cpu",
) -> tuple[np.ndarray, int | None]:
    """
    Compute Integrated Gradients attribution for one board position.

    The baseline is the all-zero tensor (empty board), which is the natural
    reference for a board game: "no pieces → no information."

    Args:
        model       : TorchScript or Python model
        board_state : (1, C, H, W) board tensor
        target      : 'value'  — explain the win-probability output
                      'policy' — explain the chosen move probability
        action_idx  : policy action to explain (None → top action)
        steps       : Riemann-sum steps; 50 is usually enough, 300 for papers

    Returns:
        attribution : (H, W) numpy array — positive = helps, negative = hurts
        action_idx  : the action that was explained (None if target='value')
    """
    board_state = board_state.to(device).float()
    baseline    = torch.zeros_like(board_state)          # empty board

    # Build (steps+1) equally spaced interpolations: baseline → input
    alphas = torch.linspace(0.0, 1.0, steps + 1, device=device)  # (S+1,)
    # Expand board_state and baseline to batch over alphas
    delta  = board_state - baseline                      # (1, C, H, W)
    interp = baseline + alphas.view(-1, 1, 1, 1) * delta # (S+1, C, H, W)
    interp = interp.requires_grad_(True)

    # Single forward pass over all interpolated inputs
    out = model(interp)

    if target == "value":
        scalar = out["value"].sum()
    else:  # "policy"
        if action_idx is None:
            with torch.no_grad():
                ref = model(board_state)
            action_idx = int(ref["policy"].argmax(dim=1).item())
        scalar = out["policy"][:, action_idx].sum()

    # Backprop to get ∂output/∂interp at each alpha step
    scalar.backward()
    grads = interp.grad.detach()  # (S+1, C, H, W)

    # Riemann-sum approximation of ∫₀¹ ∂F/∂x dα
    avg_grads = grads.mean(dim=0, keepdim=True)   # (1, C, H, W)

    # IG_i = (x_i - x'_i) × avg_grad_i
    ig = (delta * avg_grads).squeeze(0)           # (C, H, W)

    # Sum over spatial channels only (exclude global ch360=turn, ch361=move_count).
    # Global channels are broadcast uniformly to all squares; including them adds a
    # constant offset to every cell, washing out the piece-specific signal.
    spatial_ig = ig[:360]                          # (360, H, W)  — board + hand only
    attribution = spatial_ig.sum(dim=0).cpu().numpy()  # (H, W)

    return attribution, action_idx


# ──────────────────────────────────────────────────────────────────────────────
# Method 2 — Attention Rollout
# ──────────────────────────────────────────────────────────────────────────────

def attention_rollout(
    model,
    board_state: torch.Tensor,
    head_fusion: str = "mean",
    device: str = "cpu",
) -> dict:
    """
    Compute Attention Rollout across all Transformer blocks.

    Rolls up attention weights from layer to layer, accounting for residual
    connections (adds identity at each step before re-normalising).

    Args:
        model       : Python AlphaZeroNetwork (NOT TorchScript)
        board_state : (1, C, H, W) board tensor
        head_fusion : how to merge multi-head attention — 'mean' or 'max'

    Returns dict with:
        'rollout'   : (N, N) full propagated attention (N = H*W = 81)
        'per_layer' : list of (N, N) per-layer fused attention maps
        'raw_heads' : list of (num_heads, N, N) raw attention per T-block
    """
    model.eval()
    with torch.no_grad():
        out = model.get_attn_table(board_state.to(device).float())

    attn_list = out["att_table"]   # list of (1, num_heads, N, N)
    N = attn_list[0].shape[-1]     # 81 for 9×9
    eye = torch.eye(N, device=device)

    rollout    = None
    per_layer  = []
    raw_heads  = []

    for attn in attn_list:
        a = attn[0]  # (num_heads, N, N)
        raw_heads.append(a.cpu().numpy())

        # Fuse heads
        if head_fusion == "mean":
            a_fused = a.mean(dim=0)          # (N, N)
        elif head_fusion == "max":
            a_fused = a.max(dim=0).values
        else:
            raise ValueError(f"head_fusion must be 'mean' or 'max', got {head_fusion!r}")

        # Add identity for residual connection, then re-normalise rows
        a_fused = a_fused + eye
        a_fused = a_fused / a_fused.sum(dim=-1, keepdim=True)

        per_layer.append(a_fused.cpu().numpy())

        # Chain: rollout = rollout @ current_layer
        rollout = a_fused if rollout is None else rollout @ a_fused

    return {
        "rollout"   : rollout.cpu().numpy() if rollout is not None else None,
        "per_layer" : per_layer,
        "raw_heads" : raw_heads,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Visualisation helpers
# ──────────────────────────────────────────────────────────────────────────────

_SHOGI_COL_LABELS = [str(9 - i) for i in range(9)]   # 9 8 7 … 1
_SHOGI_ROW_LABELS = list("一二三四五六七八九")          # 一 二 三 … 九 (段)

# Channel 0-13: current player's pieces, 14-27: opponent's pieces (t=0 step)
# Order matches shogi.cpp final_kind mapping:
#   0=歩 1=香 2=桂 3=銀 4=金 5=角 6=飛 7=王 8=と 9=杏 10=圭 11=全 12=馬 13=龍
_PIECE_KANJI = ['歩', '香', '桂', '銀', '金', '角', '飛', '王',
                'と', '杏', '圭', '全', '馬', '龍']


def _draw_board_grid(ax, board_size: int = 9, line_color: str = "black"):
    for i in range(board_size + 1):
        ax.axhline(i - 0.5, color=line_color, linewidth=0.6)
        ax.axvline(i - 0.5, color=line_color, linewidth=0.6)
    ax.set_xticks(range(board_size))
    ax.set_yticks(range(board_size))
    # pass the CJK font explicitly so the kanji rank labels (一〜九) render
    _lbl_kw = {"fontproperties": _CJK_FONT} if _CJK_FONT else {}
    ax.set_xticklabels(_SHOGI_COL_LABELS, **_lbl_kw)
    ax.set_yticklabels(_SHOGI_ROW_LABELS, **_lbl_kw)


_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]

def _resolve_cjk_font():
    """Register CJK font with matplotlib and return FontProperties, or None."""
    from matplotlib.font_manager import FontProperties, fontManager, findfont
    import matplotlib as mpl
    for path in _CJK_FONT_CANDIDATES:
        if os.path.isfile(path):
            fontManager.addfont(path)
            fp = FontProperties(fname=path)
            name = fp.get_name()
            # Verify the font is actually findable by name after registration
            found = findfont(FontProperties(family=name), fallback_to_default=False)
            if found and path in found:
                # Font is correctly registered — set as default
                mpl.rcParams["font.family"] = "sans-serif"
                mpl.rcParams["font.sans-serif"] = [name] + mpl.rcParams["font.sans-serif"]
                mpl.rcParams["axes.unicode_minus"] = False
            else:
                # Font registered but name lookup failed — fall back to fname-only mode
                # rcParams won't work; callers must pass fontproperties=fp explicitly
                pass
            return fp
    return None

_CJK_FONT = _resolve_cjk_font()   # resolved once at import time


def _piece_pentagon(cx: float, cy: float, size: float = 0.38, flipped: bool = False):
    """Return (N,2) vertices for a shogi-piece pentagon centred at (cx, cy).

    The board is drawn with imshow(origin="upper"), so the data y-axis points
    DOWN on screen.  We therefore build the tip at -y in data coordinates so
    that, on screen, the current player's pieces POINT UP like real shogi.

    flipped=False → points UP on screen   → current player (先手 相当)
    flipped=True  → points DOWN on screen → opponent (後手, 180° rotated)
    """
    import numpy as np
    # sharper tip so the up/down orientation (own vs opponent) is obvious
    w, h, tip = size, size * 0.95, size * 0.55
    # tip at -h → renders UPWARD on the origin="upper" axis
    pts = np.array([
        [-w,  h],          # bottom-left (screen)
        [ w,  h],          # bottom-right (screen)
        [ w, -(h - tip)],  # right shoulder
        [ 0, -h],          # top point (screen up)
        [-w, -(h - tip)],  # left shoulder
    ], dtype=float)
    if flipped:
        pts = -pts         # rotate 180° for opponent → points DOWN on screen
    pts += np.array([cx, cy])
    return pts


def _draw_hand_pieces(ax, data, num_ch: int, fp_kwargs: dict):
    """Render captured pieces (持ち駒) above/below the board.

    Hand counts live in channels 31-37 (side to move) and 38-44 (opponent),
    each filled uniformly with the piece count (see tsume_shogi.sfen_to_tensor).
    """
    if num_ch < 45:                       # no hand channels available
        return
    _HAND_ORDER = ['P', 'L', 'N', 'S', 'B', 'R', 'G']
    _HAND_KANJI = {'P': '歩', 'L': '香', 'N': '桂', 'S': '銀',
                   'B': '角', 'R': '飛', 'G': '金'}
    _HAND_ASCII = {p: p for p in _HAND_ORDER}
    kmap = _HAND_KANJI if _CJK_FONT else _HAND_ASCII

    def _hand_str(base: int) -> str:
        parts = []
        for i, p in enumerate(_HAND_ORDER):
            cnt = int(round(float(data[base + i, 0, 0])))
            if cnt > 0:
                parts.append(kmap[p] + (str(cnt) if cnt > 1 else ""))
        return "　".join(parts) if parts else "なし"

    own_hand   = _hand_str(31)            # side to move
    enemy_hand = _hand_str(38)            # opponent
    # turn channel 360: 1.0 = black (先手) to move
    black_to_move = num_ch > 360 and float(data[360, 0, 0]) > 0.5
    sente_hand = own_hand if black_to_move else enemy_hand
    gote_hand  = enemy_hand if black_to_move else own_hand
    sente_lbl, gote_lbl = "先手", "後手"
    if not _CJK_FONT:
        sente_lbl, gote_lbl = "Sente", "Gote"

    # 両方の持ち駒を盤の下に積んで表示（上部のタイトルと重ならないように）
    ax.text(0.5, -0.11, f"{gote_lbl}持駒: {gote_hand}",
            transform=ax.transAxes, ha='center', va='top',
            fontsize=8, color="#1a0a00", clip_on=False, zorder=5, **fp_kwargs)
    ax.text(0.5, -0.18, f"{sente_lbl}持駒: {sente_hand}",
            transform=ax.transAxes, ha='center', va='top',
            fontsize=8, color="#1a0a00", clip_on=False, zorder=5, **fp_kwargs)


def _is_white_to_move(board_state) -> bool:
    """True if it is White's (後手) turn, read from the global turn channel 360.

    getFeatures encodes the board in a side-to-move-relative frame (rotated 180°
    when White is to move). Detecting this lets the visualisers un-rotate to a
    fixed absolute orientation (Black/先手 at the bottom, matching shogihome) so
    the board does not appear to flip every ply.
    """
    if board_state is None:
        return False
    bs = board_state[0] if hasattr(board_state, "dim") and board_state.dim() == 4 else board_state
    data = bs.detach().cpu().numpy() if hasattr(bs, "detach") else np.asarray(bs)
    return data.shape[0] > 360 and float(data[360, 0, 0]) <= 0.5


def _disp_map(m: np.ndarray, white: bool) -> np.ndarray:
    """Transform a (9,9) tensor-frame heat map to the standard display orientation.

    Tensor frame: col = file-1 (1筋 at col 0), rotated 180° when White is to move.
    Standard display: 先手 at bottom, 1筋 on the RIGHT (shogihome).
      Black to move → mirror columns (fliplr).
      White to move → undo the 180°, which reduces to a row flip (flipud).
    """
    return m[::-1, :] if white else m[:, ::-1]


def _disp_sq(r: int, c: int, white: bool, n: int = 9) -> tuple[int, int]:
    """Map a tensor-frame square (row, col) to its standard-display (row, col)."""
    return (n - 1 - r, c) if white else (r, n - 1 - c)


def _draw_piece_overlay(ax, board_state, board_size: int = 9, flip: bool | None = None):
    """Overlay shogi pieces as pentagon shapes with kanji labels.

    board_state: (1, C, H, W) or (C, H, W) float tensor, or None (no-op).
    Black (先手) pieces point upward (tan fill); White (後手) point downward (dark).
    When the position is White-to-move the feature tensor is 180°-rotated and its
    piece-ownership planes are swapped; `flip` un-rotates and re-swaps so the board
    is always drawn in the absolute (先手 at bottom) orientation. flip=None → auto.
    """
    if board_state is None:
        return

    from matplotlib.patches import Polygon as MplPolygon

    _PIECE_ASCII = ['P', 'L', 'N', 'S', 'G', 'B', 'R', 'K',
                    '+P', '+L', '+N', '+S', '+B', '+R']
    symbols = _PIECE_KANJI if _CJK_FONT else _PIECE_ASCII

    bs   = board_state[0] if board_state.dim() == 4 else board_state
    data = bs.detach().cpu().numpy()
    num_ch = data.shape[0]
    fp_kwargs = {"fontproperties": _CJK_FONT} if _CJK_FONT else {}

    if flip is None:
        flip = _is_white_to_move(board_state)

    # Tensor is in the canonical frame (col = file-1, i.e. 1筋 at col 0), rotated
    # 180° when White is to move. The standard board (先手 bottom, 1筋 on the RIGHT,
    # matching shogihome) is obtained by mirroring columns; when White is to move we
    # additionally undo the 180° (which nets to a row flip) and swap piece ownership.
    #   Black to move: display (row,col) ← tensor (row, 8-col)
    #   White to move: display (row,col) ← tensor (8-row, col)
    for row in range(board_size):
        for col in range(board_size):
            src_r = board_size - 1 - row if flip else row
            src_c = col if flip else board_size - 1 - col
            sym   = None
            flipped = False

            # channels 0-13 = side-to-move pieces; 14-27 = opponent.
            # When flip (White to move), swap ownership so Black renders as 先手 (up).
            for ch, s in enumerate(symbols):
                if ch >= num_ch:
                    break
                if data[ch, src_r, src_c] >= 0.5:
                    sym = s
                    flipped = flip
                    break

            if sym is None:
                for off, s in enumerate(symbols):
                    ch = 14 + off
                    if ch >= num_ch:
                        break
                    if data[ch, src_r, src_c] >= 0.5:
                        sym = s
                        flipped = not flip
                        break

            if sym is None:
                continue

            # Draw pentagon body
            verts = _piece_pentagon(col, row, size=0.38, flipped=flipped)
            face  = "#D4A96A" if not flipped else "#2c2c2c"
            edge  = "#3a2000" if not flipped else "#888888"
            patch = MplPolygon(verts, closed=True,
                               facecolor=face, edgecolor=edge,
                               linewidth=0.8, zorder=3)
            ax.add_patch(patch)

            # Kanji label on top
            txt_color = "#1a0a00" if not flipped else "#f0f0f0"
            ax.text(col, row, sym,
                    ha='center', va='center',
                    fontsize=10, fontweight='bold',
                    color=txt_color, zorder=4,
                    **fp_kwargs)

    # captured pieces (持ち駒) above/below the board
    _draw_hand_pieces(ax, data, num_ch, fp_kwargs)


def visualize_ig(
    attribution: np.ndarray,
    title: str = "Integrated Gradients",
    board_state=None,
    board_info: dict | None = None,
    save_path: str | None = None,
    mark_from: tuple[int, int] | None = None,
    mark_to: tuple[int, int] | None = None,
    board_size: int = 9,
) -> plt.Figure:
    """
    Heatmap of a (9, 9) IG attribution map.
    Red = positive attribution (helps the target), Blue = negative.
    Pass board_state (1,C,H,W) tensor to overlay piece kanji.
    Pass board_info dict (from load_board_from_sgf) to add SGF/move subtitle.
    mark_from / mark_to : tensor-frame (row, col) of the explained move's origin
      and destination. The destination is drawn as a green X in a blue box, the
      origin (board moves only) as a blue circle with an arrow to the destination,
      so it is clear WHICH move the policy attribution explains.
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_facecolor("#F0D9B5")  # shogi board wood color

    # Clip negative values: for policy explanation, negative attribution (hurts the
    # target move) is less informative than positive (helps). Show only positive signal
    # in red so that occupied squares "pop" clearly against the tan background.
    pos = np.clip(attribution, 0, None)
    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)
    pos = _disp_map(pos, flip)
    vmax = pos.max() + 1e-9
    im = ax.imshow(pos, cmap="Reds", vmin=0, vmax=vmax,
                   origin="upper", alpha=0.80)
    _draw_board_grid(ax)
    _draw_piece_overlay(ax, board_state, flip=flip)

    # Mark the explained move so the figure is self-explanatory.
    if mark_to is not None:
        dr, dc = _disp_sq(mark_to[0], mark_to[1], flip, board_size)
        if mark_from is not None:
            fr, fc = _disp_sq(mark_from[0], mark_from[1], flip, board_size)
            ax.annotate("", xy=(dc, dr), xytext=(fc, fr),
                        arrowprops=dict(arrowstyle="->", color="#1a6fcc",
                                        lw=2.2, shrinkA=6, shrinkB=6), zorder=6)
            ax.plot(fc, fr, marker="o", markersize=11, markerfacecolor="none",
                    markeredgecolor="#1a6fcc", markeredgewidth=2.2, zorder=6)
        ax.add_patch(mpatches.Rectangle((dc - 0.5, dr - 0.5), 1, 1, linewidth=2.5,
                                        edgecolor="#1a6fcc", facecolor="none", zorder=6))
        ax.plot(dc, dr, marker="x", color="#00cc44", markersize=13,
                markeredgewidth=3, zorder=7)

    ax.set_title(title, fontsize=12)
    _set_subtitle(ax, _board_subtitle(board_info))
    plt.colorbar(im, ax=ax, label="Attribution (positive only)", fraction=0.046, pad=0.04)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


def visualize_rollout(
    rollout: np.ndarray,
    source_square: tuple[int, int] | None = None,
    board_size: int = 9,
    board_state=None,
    board_info: dict | None = None,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Visualise attention rollout on the Shogi board.

    Self-attention (diagonal) is removed and rows are renormalised so that
    cross-square attention is visible instead of being washed out by residual
    self-weight.  Values are then clipped at the 99th percentile for contrast.

    source_square = None        → show average attention received per square
    source_square = (row, col)  → show where that square's attention flows to
    board_state                 → (1,C,H,W) tensor; if given, overlays piece kanji
    """
    N = rollout.shape[0]

    # Remove diagonal dominance: zero self-attention, renormalise rows
    r_clean = rollout.copy()
    np.fill_diagonal(r_clean, 0.0)
    row_sums = r_clean.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums < 1e-12, 1.0, row_sums)
    r_clean = r_clean / row_sums

    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)

    if source_square is None:
        attn_map = r_clean.mean(axis=0).reshape(board_size, board_size)
        title = "Attention Rollout — avg received (self excl.)"
        disp_sq = None
    else:
        r, c = source_square
        token_idx = r * board_size + c
        attn_map = r_clean[token_idx].reshape(board_size, board_size)
        disp_r, disp_c = _disp_sq(r, c, flip, board_size)
        col_label = _SHOGI_COL_LABELS[disp_c]
        row_label = _SHOGI_ROW_LABELS[disp_r]
        title = f"Attention Rollout — {col_label}{row_label} → others (self excl.)"
        disp_sq = (disp_r, disp_c)

    attn_map = _disp_map(attn_map, flip)

    # Clip at 99th percentile so a few hot squares do not drown the rest
    vmax = float(np.percentile(attn_map, 99))
    vmax = max(vmax, 1e-12)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_facecolor("#F0D9B5")
    im = ax.imshow(attn_map, cmap="YlOrRd", origin="upper", vmin=0.0, vmax=vmax,
                   alpha=0.80)
    _draw_board_grid(ax, line_color="#5a3a1a")
    _draw_piece_overlay(ax, board_state, flip=flip)
    ax.set_title(title, fontsize=10)
    _set_subtitle(ax, _board_subtitle(board_info))
    plt.colorbar(im, ax=ax, label="Attention weight (clipped p99)", fraction=0.046, pad=0.04)

    if disp_sq is not None:
        disp_r, disp_c = disp_sq
        # Blue rectangle: source square (matches paper style)
        rect = mpatches.Rectangle(
            (disp_c - 0.5, disp_r - 0.5), 1, 1,
            linewidth=2.5, edgecolor="#1a6fcc", facecolor="none",
        )
        ax.add_patch(rect)
        # Green cross at centre of source square
        ax.plot(disp_c, disp_r, marker="x", color="#00cc44", markersize=10, markeredgewidth=2)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig

# ──────────────────────────────────────────────────────────────────────────────
# Method  — AttentionMap
# ──────────────────────────────────────────────────────────────────────────────

def visualize_single_head(
    raw_heads: list[np.ndarray],
    source_square: tuple[int, int],
    layer_idx: int = 0,
    head_idx: int = 0,
    board_size: int = 9,
    board_state=None,
    board_info: dict | None = None,
    save_path: str | None = None,
    subtract_uniform: bool = False,
) -> plt.Figure:
    """
    Visualise raw attention from ONE specific (layer, head) pair — paper style.

    Matches Figure 5/6 of the IJCAI-25 paper:
      - Single head, single layer (no rollout across layers)
      - Query position = source_square (green X = next move)
      - Values normalised to [0, 1], redder = higher attention

    Args:
        raw_heads     : list of (num_heads, N, N) per T-block raw attention
        source_square : (row, col) of the query position (next move square)
        layer_idx     : T-block index (0-based)
        head_idx      : attention head index (0-based)
        subtract_uniform : if True, exclude self-attention and subtract the uniform
                        baseline (1/N) before peak-normalising, so only above-uniform
                        attention is coloured. Default False = paper-faithful [0,1].
    """
    num_layers = len(raw_heads)
    num_heads  = raw_heads[0].shape[0]

    layer_idx = max(0, min(layer_idx, num_layers - 1))
    head_idx  = max(0, min(head_idx,  num_heads  - 1))

    r, c = source_square
    token_idx = r * board_size + c

    attn = raw_heads[layer_idx][head_idx, token_idx].copy()  # (N,) query row, self included

    if subtract_uniform:
        # Optional (non-paper): drop self-attention and subtract the uniform
        # baseline 1/N, so "attending equally to all squares" → 0 (white) and only
        # above-uniform attention is coloured. Useful for diffuse early-layer heads.
        attn[token_idx] = 0.0
        uniform = 1.0 / (board_size * board_size)
        above = np.maximum(0.0, attn - uniform)
        peak = above.max()
        attn = above / peak if peak > 1e-9 else np.zeros_like(above)
    else:
        # Faithful to the paper (IJCAI-25, Fig 5/6): the values are the query token's
        # raw attention weights over all tokens ("relative importance of other tokens"),
        # normalised to [0, 1] for visualisation, redder = higher. Self-attention is
        # NOT excluded — the paper applies a plain min–max normalisation only.
        lo = attn.min()
        hi = attn.max()
        if hi - lo > 1e-12:
            attn = (attn - lo) / (hi - lo)
        else:
            attn = np.zeros_like(attn)   # constant row → fully white

    # Entropy of the raw row for the auxiliary focus readout (not part of the paper).
    raw_row = raw_heads[layer_idx][head_idx, token_idx].copy()
    raw_row = raw_row / (raw_row.sum() + 1e-12)
    entropy = float(-np.sum(raw_row * np.log(raw_row + 1e-12)))
    max_entropy = float(np.log(board_size * board_size))

    attn_map = attn.reshape(board_size, board_size)
    vmax = 1.0

    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)
    attn_map = _disp_map(attn_map, flip)
    disp_r, disp_c = _disp_sq(r, c, flip, board_size)

    col_label = _SHOGI_COL_LABELS[disp_c]
    row_label = _SHOGI_ROW_LABELS[disp_r]
    focus_pct = 100.0 * (1.0 - entropy / max_entropy)   # 0%=uniform, 100%=one square
    title = (f"Attention  L{layer_idx+1} H{head_idx+1} — query: {col_label}{row_label}"
             f"\n集中度 {focus_pct:.1f}%  (低いほど均等分散)")

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_facecolor("#F0D9B5")
    im = ax.imshow(attn_map, cmap="Reds", origin="upper", vmin=0.0, vmax=vmax,
                   alpha=0.80)
    _draw_board_grid(ax, line_color="#5a3a1a")
    _draw_piece_overlay(ax, board_state, flip=flip)

    # Green X at source square (paper style)
    ax.plot(disp_c, disp_r, marker="x", color="#00cc44", markersize=12,
            markeredgewidth=2.5, zorder=5)
    # Blue rectangle outline
    rect = mpatches.Rectangle(
        (disp_c - 0.5, disp_r - 0.5), 1, 1,
        linewidth=2.5, edgecolor="#1a6fcc", facecolor="none", zorder=5,
    )
    ax.add_patch(rect)

    ax.set_title(title, fontsize=11)
    _set_subtitle(ax, _board_subtitle(board_info))
    plt.colorbar(im, ax=ax, label="Attention weight [0,1]",
                 fraction=0.046, pad=0.04)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def visualize_per_head(
    raw_heads: list[np.ndarray],
    source_square: tuple[int, int],
    board_size: int = 9,
    board_state=None,
    board_info: dict | None = None,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Show each attention head in each Transformer block for one source square.
    raw_heads: list of (num_heads, N, N) — one entry per T-block.
    Faithful to the paper (IJCAI-25): each cell is the query token's raw attention
    row for that (layer, head), min-max normalised to [0, 1]; self-attention kept.
    """
    num_layers = len(raw_heads)
    num_heads  = raw_heads[0].shape[0]
    r, c = source_square
    token_idx = r * board_size + c

    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)
    disp_r, disp_c = _disp_sq(r, c, flip, board_size)

    fig, axes = plt.subplots(
        num_layers, num_heads,
        figsize=(num_heads * 3, num_layers * 3),
        squeeze=False,
    )

    for li, heads in enumerate(raw_heads):
        for hi in range(num_heads):
            attn = heads[hi, token_idx].copy()   # (N,) query row, self included
            lo, hi_v = attn.min(), attn.max()
            attn = (attn - lo) / (hi_v - lo) if hi_v - lo > 1e-12 else np.zeros_like(attn)
            attn_map = _disp_map(attn.reshape(board_size, board_size), flip)
            ax = axes[li][hi]
            ax.set_facecolor("#F0D9B5")
            ax.imshow(attn_map, cmap="YlOrRd", origin="upper", vmin=0.0, vmax=1.0,
                      alpha=0.80)
            _draw_board_grid(ax, line_color="#5a3a1a")
            _draw_piece_overlay(ax, board_state, board_size, flip=flip)
            ax.set_title(f"L{li+1} H{hi+1}", fontsize=9)
            ax.tick_params(labelsize=6)

    col_label = _SHOGI_COL_LABELS[disp_c]
    row_label = _SHOGI_ROW_LABELS[disp_r]
    fig.suptitle(
        f"Per-head attention from {col_label}{row_label}",
        fontsize=11,
    )
    subtitle = _board_subtitle(board_info)
    if subtitle:
        fp_kwargs = {"fontproperties": _CJK_FONT} if _CJK_FONT else {}
        fig.text(0.5, 0.01, subtitle, ha="center", fontsize=7, color="gray", **fp_kwargs)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Pre-softmax logits & Relative Position Bias
# ──────────────────────────────────────────────────────────────────────────────

def get_pre_softmax_data(model, board_state: torch.Tensor, device: str = "cpu") -> dict:
    """
    Extract pre-softmax Q·K logits (dots) from each T-block via forward hooks
    on the attend (Softmax) sub-module, without modifying the model source.

    Returns dict with:
        'att_table'  : list of (1, num_heads, N, N) post-softmax attention
        'dots_table' : list of (1, num_heads, N, N) pre-softmax logits
    """
    model.eval()
    dots_captured: list[torch.Tensor] = []

    def _hook(module, inp, out):
        dots_captured.append(inp[0].detach().cpu())

    hooks = []
    # The attend (nn.Softmax) module lives inside each MSA_rel block.
    # get_attn_table() calls block.attn() → MSA_rel.attn() → self.attend(dots),
    # so hooking attend captures dots as input[0].
    # Match any module whose dotted name ends with ".attend" (covers MSA.attend etc.)
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.Softmax) and name.endswith(".attend"):
            hooks.append(mod.register_forward_hook(_hook))

    with torch.no_grad():
        out = model.get_attn_table(board_state.to(device).float())

    for h in hooks:
        h.remove()

    return {
        "att_table" : out["att_table"],
        "dots_table": dots_captured,
    }


def get_relative_bias_maps(model, board_size: int = 9) -> list[list[np.ndarray]]:
    """
    Extract the learned relative_bias_table from every T-block and convert it
    to per-head (N, N) matrices where entry [q, k] is the bias added to the
    attention logit from token q attending to token k.

    Returns list (one per T-block) of list (one per head) of (N, N) numpy arrays.
    """
    N = board_size * board_size
    results = []
    for name, mod in model.named_modules():
        if hasattr(mod, "relative_bias_table") and hasattr(mod, "relative_index"):
            table  = mod.relative_bias_table.detach().cpu()  # (K, num_heads)
            rel_idx = mod.relative_index.cpu().squeeze(1)    # (N*N,)
            num_heads = table.shape[1]
            head_maps = []
            for h in range(num_heads):
                bias = table[rel_idx, h].reshape(N, N).numpy()  # (N, N)
                head_maps.append(bias)
            results.append(head_maps)
    return results


def visualize_pre_softmax_single_head(
    dots_table: list[torch.Tensor],
    source_square: tuple[int, int],
    layer_idx: int = 0,
    head_idx: int = 0,
    board_size: int = 9,
    board_state=None,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Visualise pre-softmax Q·K logits for one (layer, head, query) combination.

    Unlike the post-softmax map (values ≈ 1/81, low contrast), the raw logits
    have much higher dynamic range (~60×) and reveal attention patterns even in
    early training.  Blue = low logit, Red = high logit (softmax favours red).
    """
    num_layers = len(dots_table)
    li = max(0, min(layer_idx, num_layers - 1))

    dots = dots_table[li]  # (1, num_heads, N, N) or (num_heads, N, N)
    if dots.dim() == 4:
        dots = dots[0]     # (num_heads, N, N)

    num_heads = dots.shape[0]
    hi = max(0, min(head_idx, num_heads - 1))

    r, c = source_square
    token_idx = r * board_size + c

    logits = dots[hi, token_idx].numpy().copy()  # (N,)
    logit_map = logits.reshape(board_size, board_size)

    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)
    logit_map = _disp_map(logit_map, flip)
    disp_r, disp_c = _disp_sq(r, c, flip, board_size)

    col_label = _SHOGI_COL_LABELS[disp_c]
    row_label = _SHOGI_ROW_LABELS[disp_r]
    vabs = max(abs(logits.min()), abs(logits.max()), 1e-6)
    title = (f"Pre-softmax logits  L{li+1} H{hi+1} — query: {col_label}{row_label}\n"
             f"range [{logits.min():.3f}, {logits.max():.3f}]  (赤ほど高スコア)")

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_facecolor("#F0D9B5")
    im = ax.imshow(logit_map, cmap="RdBu_r", origin="upper",
                   vmin=-vabs, vmax=vabs, alpha=0.85)
    _draw_board_grid(ax, line_color="#5a3a1a")
    _draw_piece_overlay(ax, board_state, flip=flip)
    ax.plot(disp_c, disp_r, marker="x", color="#00cc44", markersize=12,
            markeredgewidth=2.5, zorder=5)
    import matplotlib.patches as _mp
    rect = _mp.Rectangle((disp_c - 0.5, disp_r - 0.5), 1, 1,
                          linewidth=2.5, edgecolor="#1a6fcc", facecolor="none", zorder=5)
    ax.add_patch(rect)
    ax.set_title(title, fontsize=10)
    plt.colorbar(im, ax=ax, label="Q·K dot product (+ rel_bias)",
                 fraction=0.046, pad=0.04)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def visualize_relative_bias(
    bias_maps: list[list[np.ndarray]],
    source_square: tuple[int, int] | None = None,
    board_size: int = 9,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Visualise the learned relative position bias for every (layer, head) pair.

    source_square = None      → use centre square (4, 4) as reference query
    source_square = (row, col) → bias received by each key when THIS square is the query

    Blue = negative bias (model suppresses attending here),
    Red  = positive bias (model boosts attending here).
    """
    if source_square is None:
        source_square = (board_size // 2, board_size // 2)

    r, c = source_square
    token_idx = r * board_size + c
    col_label = _SHOGI_COL_LABELS[c]
    row_label = _SHOGI_ROW_LABELS[r]

    num_layers = len(bias_maps)
    num_heads  = len(bias_maps[0]) if num_layers else 0

    fig, axes = plt.subplots(
        num_layers, num_heads,
        figsize=(num_heads * 3, num_layers * 3),
        squeeze=False,
    )

    global_abs = max(
        abs(bias_maps[li][hi][token_idx].max())
        for li in range(num_layers) for hi in range(num_heads)
    )
    global_abs = max(global_abs, 1e-6)

    for li in range(num_layers):
        for hi in range(num_heads):
            bias_row = bias_maps[li][hi][token_idx]        # (N,)
            bias_2d  = bias_row.reshape(board_size, board_size)
            ax = axes[li][hi]
            ax.set_facecolor("#F0D9B5")
            ax.imshow(bias_2d, cmap="RdBu_r", origin="upper",
                      vmin=-global_abs, vmax=global_abs, alpha=0.85)
            _draw_board_grid(ax, line_color="#5a3a1a")
            ax.plot(c, r, marker="x", color="#00cc44", markersize=10,
                    markeredgewidth=2, zorder=5)
            ax.set_title(f"L{li+1} H{hi+1}", fontsize=9)
            ax.tick_params(labelsize=6)

    fig.suptitle(
        f"Relative Position Bias — query: {col_label}{row_label}\n"
        f"（赤=正バイアス / 青=負バイアス）",
        fontsize=11,
    )
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Method 3 — Perturbation / Occlusion
# ──────────────────────────────────────────────────────────────────────────────

def visualize_perturbation(
    attribution: np.ndarray,
    title: str = "Perturbation / Occlusion",
    board_state=None,
    board_info: dict | None = None,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Heatmap of a (9, 9) perturbation attribution map.
    Red = removing this square hurts the output (important piece).
    Blue = removing this square helps the output.
    Pass board_state (1,C,H,W) tensor to overlay piece kanji.
    Pass board_info dict (from load_board_from_sgf) to add SGF/move subtitle.
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    # Convert tensor frame → standard display (先手 bottom, 1筋 right).
    flip = _is_white_to_move(board_state)
    attribution = _disp_map(attribution, flip)
    vmax = max(abs(attribution.max()), abs(attribution.min())) + 1e-9
    im = ax.imshow(attribution, cmap="RdBu_r", vmin=-vmax, vmax=vmax, origin="upper")
    _draw_board_grid(ax)
    _draw_piece_overlay(ax, board_state, flip=flip)
    ax.set_title(title, fontsize=12)
    _set_subtitle(ax, _board_subtitle(board_info))
    plt.colorbar(im, ax=ax, label="Δ output (original − masked)", fraction=0.046, pad=0.04)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Board state loading
# ──────────────────────────────────────────────────────────────────────────────

def sgf_file_stats(sgf_file: str) -> dict:
    """Return statistics about all games in an SGF file.

    Returns dict with:
        num_games    : total number of games
        move_counts  : list of move counts per game (index = game_idx)
        results      : list of RE[] values per game ("1.0" = player1 win, "-1.0" = player2 win)
    """
    import re as _re
    with open(sgf_file) as f:
        content = f.read()
    starts = [m.start() for m in _re.finditer(r"\(;GM\[", content)]
    move_counts, results = [], []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(content)
        g = content[s:e]
        move_counts.append(len(_re.findall(r";[BW]\[(\d+)\]", g)))
        r = _re.search(r"RE\[([^\]]+)\]", g)
        results.append(r.group(1) if r else "?")
    return {"num_games": len(starts), "move_counts": move_counts, "results": results}


def sgf_game_values(sgf_file: str, game_idx: int = 0) -> tuple[list[float], int]:
    """Return (value_trajectory, total_moves) for game_idx-th game.

    value_trajectory[i] = model's value estimate V after move i+1.
    Only moves with a valid numeric V[] field are included.
    """
    import re as _re
    with open(sgf_file) as f:
        content = f.read()
    starts = [m.start() for m in _re.finditer(r"\(;GM\[", content)]
    if game_idx >= len(starts):
        raise ValueError(f"game_idx {game_idx} >= num_games {len(starts)}")
    s = starts[game_idx]
    e = starts[game_idx + 1] if game_idx + 1 < len(starts) else len(content)
    game = content[s:e]
    total_moves = len(_re.findall(r";[BW]\[(\d+)\]", game))
    values: list[float] = []
    for raw in _re.findall(r";[BW]\[[^\]]+\](?:[^;]*)V\[([^\]]+)\]", game):
        try:
            values.append(float(raw))
        except ValueError:
            pass
    return values, total_moves


def _parse_sgf_game(sgf_file: str, game_idx: int = 0) -> tuple[list, int]:
    """Return (moves, total) for game_idx-th game in an SGF file.

    moves  : list of (player_char, action_id) e.g. [('B', 10683), ('W', 9067), ...]
    total  : total moves in that game
    """
    import re as _re

    with open(sgf_file) as f:
        content = f.read()

    pos = 0
    for idx in range(game_idx + 1):
        start = content.find("(;GM[", pos)
        if start == -1:
            raise ValueError(f"Game index {game_idx} not found in {sgf_file!r} "
                             f"(only {idx} game(s) found).")
        next_start = content.find("(;GM[", start + 1)
        game_text  = content[start:next_start] if next_start != -1 else content[start:]
        pos = next_start if next_start != -1 else len(content)

    raw = _re.findall(r";([BW])\[(\d+)\]", game_text)
    moves = [(p, int(a)) for p, a in raw]
    return moves, len(moves)


def _board_subtitle(info: dict | None) -> str:
    """Format a one-line subtitle from board_info dict returned by load_board_from_sgf."""
    if not info:
        return ""
    turn_label = {"player_1": "先手番", "player_2": "後手番"}.get(info.get("turn", ""), info.get("turn", ""))
    return (f"{info['sgf_file']}  game {info['game_idx']} / "
            f"{info['move']}/{info['total_moves']}手目  {turn_label}")


def _set_subtitle(ax, subtitle: str) -> None:
    """Add subtitle text below the x-axis using the CJK font when available."""
    if not subtitle:
        return
    fp_kwargs = {"fontproperties": _CJK_FONT} if _CJK_FONT else {}
    ax.set_xlabel(subtitle, fontsize=7, color="gray", **fp_kwargs)


def _load_build_so(build_dir: str, mod_name: str):
    """Load a C++ pybind11 extension from build_dir by file path (no __init__.py needed).

    Raises ImportError with actionable instructions if the Python version does not
    match the one used to compile the .so file.
    """
    import importlib.util
    import glob
    import re

    matches = glob.glob(os.path.join(build_dir, f"{mod_name}*.so"))
    if not matches:
        raise ImportError(f"Module '{mod_name}' not found in {build_dir!r}. "
                          "Check that the C++ project was built successfully.")

    so_path = matches[0]

    # Detect version mismatch before attempting to load
    m = re.search(r"cpython-(\d+)", os.path.basename(so_path))
    if m:
        built = m.group(1)                             # e.g. "310"
        cur   = f"{sys.version_info.major}{sys.version_info.minor}"  # e.g. "312"
        if built != cur:
            built_str = f"{built[0]}.{built[1:]}"     # "3.10"
            raise ImportError(
                f"Python version mismatch: '{os.path.basename(so_path)}' was compiled "
                f"for Python {built_str}, but you are running Python "
                f"{sys.version_info.major}.{sys.version_info.minor}.\n\n"
                f"Fix: create a matching conda environment and re-run the app:\n"
                f"  conda create -n restnet{built} python={built_str} -y\n"
                f"  conda activate restnet{built}\n"
                f"  pip install torch gradio timm einops matplotlib pillow pyyaml\n"
                f"  python xai_app.py"
            )

    spec   = importlib.util.spec_from_file_location(mod_name, so_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def load_board_from_sgf(
    sgf_file: str,
    conf_file: str,
    game_type: str,
    game_idx: int = 0,
    move_idx: int = -1,
    device: str = "cpu",
) -> tuple[torch.Tensor, dict]:
    """
    Load a board feature tensor from an SGF file using the ResTNet C++ env.

    Args:
        sgf_file  : path to the .sgf file
        conf_file : path to the config .cfg file
        game_type : build subdirectory name (e.g. 'shogi')
        game_idx  : which game in the file (0-based; default 0 = first game)
        move_idx  : position to analyse (-1 = final position, 0 = initial,
                    N = after N moves)

    Returns:
        board_state : (1, C, H, W) float32 tensor on `device`
        info        : dict with keys sgf_file, game_idx, move, total_moves, turn
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    build_dir    = os.path.join(project_root, "build", game_type)

    if not os.path.isdir(build_dir):
        build_root = os.path.join(project_root, "build")
        if os.path.isdir(build_root):
            available = [d for d in os.listdir(build_root)
                         if os.path.isdir(os.path.join(build_root, d))]
        else:
            available = []
        hint = f"  Available build targets: {available}" if available else \
               "  No build/ directory found — build the project first."
        raise ImportError(
            f"Build directory not found: {build_dir!r}\n{hint}"
        )

    env_py = _load_build_so(build_dir, "env_py")
    env_py.init(conf_file)

    moves, total_moves = _parse_sgf_game(sgf_file, game_idx)
    stop = total_moves if move_idx < 0 else min(move_idx, total_moves)

    env = env_py.Env()
    env.reset()
    for player_char, action_id in moves[:stop]:
        player = env_py.player_1 if player_char == "B" else env_py.player_2
        env.act(env_py.Action(action_id, player))

    features = torch.FloatTensor(env.get_features())

    turn_raw = str(env.get_turn())                # "Player.player_1" or "Player.player_2"
    turn_key = turn_raw.split(".")[-1]            # "player_1" or "player_2"

    restnet_py = _load_build_so(build_dir, "restnet_py")
    restnet_py.load_config_file(conf_file)
    C = restnet_py.get_nn_num_input_channels()
    H = restnet_py.get_nn_input_channel_height()
    W = restnet_py.get_nn_input_channel_width()

    info = {
        "sgf_file"   : os.path.basename(sgf_file),
        "game_idx"   : game_idx,
        "move"       : stop,
        "total_moves": total_moves,
        "turn"       : turn_key,
    }
    return features.view(1, C, H, W).to(device), info


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="XAI analysis for ResTNet Shogi")
    parser.add_argument("--model",  required=True, help="Path to weight_iter_N.pt")
    parser.add_argument("--target", default="both",
                        choices=["value", "policy", "both", "rollout", "perturbation", "all"],
                        help="What to explain")
    parser.add_argument("--steps",  type=int, default=50,
                        help="IG Riemann-sum steps (50 = fast, 300 = paper quality)")
    parser.add_argument("--source-square", default=None,
                        help="Row,col for rollout source, e.g. '4,4' for centre")
    parser.add_argument("--sgf",  default=None,
                        help="Path to .sgf file to load a real board position")
    parser.add_argument("--conf", default=None,
                        help="Path to .cfg config file (required with --sgf)")
    parser.add_argument("--game-type", default="shogi",
                        help="Build target name, e.g. 'shogi' (used with --sgf)")
    parser.add_argument("--game-idx", type=int, default=0,
                        help="Which game in the SGF file (0-based, default 0)")
    parser.add_argument("--move-idx", type=int, default=-1,
                        help="Which position to analyse (-1=final, 0=initial, N=after N moves)")
    parser.add_argument("--no-show", action="store_true",
                        help="Save figures without calling plt.show()")
    parser.add_argument("--out-dir", default=".",
                        help="Directory for saved figures")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    os.makedirs(args.out_dir, exist_ok=True)

    # ── board state ──────────────────────────────────────────────────────────
    # A real position is required: XAI on a random board is meaningless.
    board_info = None
    if args.sgf is None:
        parser.error("--sgf is required (analysis needs a real board position)")
    if args.conf is None:
        parser.error("--conf is required when --sgf is specified")
    print(f"Loading board from SGF: {args.sgf}")
    board_state, board_info = load_board_from_sgf(
        args.sgf, args.conf, args.game_type,
        game_idx=args.game_idx, move_idx=args.move_idx, device=device
    )
    print(f"Board state shape: {tuple(board_state.shape)}")
    print(f"Position: {_board_subtitle(board_info)}")

    # ── Integrated Gradients ─────────────────────────────────────────────────
    run_ig = args.target in ("value", "policy", "both", "all")
    if run_ig:
        ts_model = load_torchscript_model(args.model, device=device)

        ig_targets = []
        if args.target in ("value", "both", "all"):
            ig_targets.append("value")
        if args.target in ("policy", "both", "all"):
            ig_targets.append("policy")

        for tgt in ig_targets:
            attr, action = integrated_gradients(
                ts_model, board_state, target=tgt,
                steps=args.steps, device=device,
            )
            _bs = board_state if args.sgf else None
            if tgt == "value":
                print(f"[IG-value]  range [{attr.min():.4f}, {attr.max():.4f}]")
                visualize_ig(
                    attr, title="IG — Value attribution",
                    board_state=_bs, board_info=board_info,
                    save_path=os.path.join(args.out_dir, "ig_value.png"),
                )
            else:
                print(f"[IG-policy] top action={action}, range [{attr.min():.4f}, {attr.max():.4f}]")
                visualize_ig(
                    attr, title=f"IG — Policy attribution (action {action})",
                    board_state=_bs, board_info=board_info,
                    save_path=os.path.join(args.out_dir, "ig_policy.png"),
                )

    # ── Perturbation / Occlusion ─────────────────────────────────────────────
    if args.target in ("perturbation", "all"):
        if not run_ig:
            ts_model = load_torchscript_model(args.model, device=device)

        _bs = board_state if args.sgf else None
        for tgt in ("value", "policy"):
            attr, action = occlusion(
                ts_model, board_state, target=tgt, device=device,
            )
            if tgt == "value":
                print(f"[Perturbation-value]  range [{attr.min():.4f}, {attr.max():.4f}]")
                visualize_perturbation(
                    attr, title="Perturbation — Value attribution",
                    board_state=_bs, board_info=board_info,
                    save_path=os.path.join(args.out_dir, "perturb_value.png"),
                )
            else:
                print(f"[Perturbation-policy] top action={action}, range [{attr.min():.4f}, {attr.max():.4f}]")
                visualize_perturbation(
                    attr, title=f"Perturbation — Policy attribution (action {action})",
                    board_state=_bs, board_info=board_info,
                    save_path=os.path.join(args.out_dir, "perturb_policy.png"),
                )

    # ── Attention Rollout ────────────────────────────────────────────────────
    if args.target in ("rollout", "both", "all"):
        py_model = load_python_model(args.model, device=device)
        rollout_data = attention_rollout(py_model, board_state, device=device)

        _bs_overlay = board_state if args.sgf else None
        visualize_rollout(
            rollout_data["rollout"],
            board_state=_bs_overlay, board_info=board_info,
            save_path=os.path.join(args.out_dir, "rollout_avg.png"),
        )

        if args.source_square:
            r, c = map(int, args.source_square.split(","))
            visualize_rollout(
                rollout_data["rollout"],
                source_square=(r, c),
                board_state=_bs_overlay, board_info=board_info,
                save_path=os.path.join(args.out_dir, f"rollout_r{r}c{c}.png"),
            )
            visualize_per_head(
                rollout_data["raw_heads"],
                source_square=(r, c),
                board_state=_bs_overlay, board_info=board_info,
                save_path=os.path.join(args.out_dir, f"per_head_r{r}c{c}.png"),
            )

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
