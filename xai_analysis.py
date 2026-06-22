"""
XAI analysis for ResTNet Shogi model.

Two complementary methods:
  1. Integrated Gradients  — which board squares drove the value/policy output
  2. Attention Rollout     — how attention propagates through Transformer layers

Usage:
    python xai_analysis.py --model path/to/weight.pt --target value
    python xai_analysis.py --model path/to/weight.pt --target policy
    python xai_analysis.py --model path/to/weight.pt --target both

For a real board state, replace `dummy_board_state()` with your own loader.
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

    # Sum over channels → spatial attribution map (H, W)
    attribution = ig.sum(dim=0).cpu().numpy()

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
_SHOGI_ROW_LABELS = list("abcdefghi")                 # a b c … i


def _draw_board_grid(ax, board_size: int = 9, line_color: str = "black"):
    for i in range(board_size + 1):
        ax.axhline(i - 0.5, color=line_color, linewidth=0.6)
        ax.axvline(i - 0.5, color=line_color, linewidth=0.6)
    ax.set_xticks(range(board_size))
    ax.set_yticks(range(board_size))
    ax.set_xticklabels(_SHOGI_COL_LABELS)
    ax.set_yticklabels(_SHOGI_ROW_LABELS)


def visualize_ig(
    attribution: np.ndarray,
    title: str = "Integrated Gradients",
    save_path: str | None = None,
) -> plt.Figure:
    """
    Heatmap of a (9, 9) IG attribution map.
    Red = positive attribution (helps the target), Blue = negative.
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    vmax = max(abs(attribution.max()), abs(attribution.min())) + 1e-9
    im = ax.imshow(attribution, cmap="RdBu_r", vmin=-vmax, vmax=vmax, origin="upper")
    _draw_board_grid(ax)
    ax.set_title(title, fontsize=12)
    plt.colorbar(im, ax=ax, label="Attribution score", fraction=0.046, pad=0.04)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


def visualize_rollout(
    rollout: np.ndarray,
    source_square: tuple[int, int] | None = None,
    board_size: int = 9,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Visualise attention rollout on the Shogi board.

    source_square = None        → show average attention received per square
    source_square = (row, col)  → show where that square's attention flows
    """
    if source_square is None:
        attn_map = rollout.mean(axis=0).reshape(board_size, board_size)
        title = "Attention Rollout — avg received per square"
    else:
        r, c = source_square
        token_idx = r * board_size + c
        attn_map = rollout[token_idx].reshape(board_size, board_size)
        col_label = _SHOGI_COL_LABELS[c]
        row_label = _SHOGI_ROW_LABELS[r]
        title = f"Attention Rollout — source {col_label}{row_label}"

    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(attn_map, cmap="hot", origin="upper")
    _draw_board_grid(ax, line_color="white")
    ax.set_title(title, fontsize=12)
    plt.colorbar(im, ax=ax, label="Attention weight", fraction=0.046, pad=0.04)

    # Highlight the source square
    if source_square is not None:
        r, c = source_square
        rect = mpatches.Rectangle(
            (c - 0.5, r - 0.5), 1, 1,
            linewidth=2, edgecolor="cyan", facecolor="none"
        )
        ax.add_patch(rect)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


def visualize_per_head(
    raw_heads: list[np.ndarray],
    source_square: tuple[int, int],
    board_size: int = 9,
    save_path: str | None = None,
) -> plt.Figure:
    """
    Show each attention head in each Transformer block for one source square.
    raw_heads: list of (num_heads, N, N)  — one entry per T-block
    """
    num_layers = len(raw_heads)
    num_heads  = raw_heads[0].shape[0]
    r, c = source_square
    token_idx = r * board_size + c

    fig, axes = plt.subplots(
        num_layers, num_heads,
        figsize=(num_heads * 3, num_layers * 3),
        squeeze=False,
    )

    for li, heads in enumerate(raw_heads):
        for hi in range(num_heads):
            attn_map = heads[hi, token_idx].reshape(board_size, board_size)
            ax = axes[li][hi]
            ax.imshow(attn_map, cmap="hot", origin="upper")
            _draw_board_grid(ax, line_color="white")
            ax.set_title(f"L{li+1} H{hi+1}", fontsize=9)
            ax.tick_params(labelsize=6)

    col_label = _SHOGI_COL_LABELS[c]
    row_label = _SHOGI_ROW_LABELS[r]
    fig.suptitle(
        f"Per-head attention from {col_label}{row_label} "
        f"(layers = T-blocks, columns = heads)",
        fontsize=11,
    )
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Demo helpers
# ──────────────────────────────────────────────────────────────────────────────

def dummy_board_state(num_input_channels: int = 362, device: str = "cpu") -> torch.Tensor:
    """
    Returns a random board state tensor for quick testing.
    Replace this with real board feature loading from your pipeline.
    """
    state = torch.rand(1, num_input_channels, 9, 9, device=device)
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="XAI analysis for ResTNet Shogi")
    parser.add_argument("--model",  required=True, help="Path to weight_iter_N.pt")
    parser.add_argument("--target", default="both",
                        choices=["value", "policy", "both", "rollout"],
                        help="What to explain")
    parser.add_argument("--steps",  type=int, default=50,
                        help="IG Riemann-sum steps (50 = fast, 300 = paper quality)")
    parser.add_argument("--source-square", default=None,
                        help="Row,col for rollout source, e.g. '4,4' for centre")
    parser.add_argument("--no-show", action="store_true",
                        help="Save figures without calling plt.show()")
    parser.add_argument("--out-dir", default=".",
                        help="Directory for saved figures")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    os.makedirs(args.out_dir, exist_ok=True)

    # ── board state ──────────────────────────────────────────────────────────
    # TODO: replace dummy_board_state() with your real board feature loader
    board_state = dummy_board_state(num_input_channels=362, device=device)

    # ── Integrated Gradients ─────────────────────────────────────────────────
    if args.target in ("value", "policy", "both"):
        ts_model = load_torchscript_model(args.model, device=device)

        if args.target in ("value", "both"):
            attr, _ = integrated_gradients(
                ts_model, board_state, target="value",
                steps=args.steps, device=device,
            )
            print(f"[IG-value]  range [{attr.min():.4f}, {attr.max():.4f}]")
            visualize_ig(
                attr, title="IG — Value attribution",
                save_path=os.path.join(args.out_dir, "ig_value.png"),
            )

        if args.target in ("policy", "both"):
            attr, action = integrated_gradients(
                ts_model, board_state, target="policy",
                steps=args.steps, device=device,
            )
            print(f"[IG-policy] top action={action}, range [{attr.min():.4f}, {attr.max():.4f}]")
            visualize_ig(
                attr, title=f"IG — Policy attribution (action {action})",
                save_path=os.path.join(args.out_dir, "ig_policy.png"),
            )

    # ── Attention Rollout ────────────────────────────────────────────────────
    if args.target in ("rollout", "both"):
        py_model = load_python_model(args.model, device=device)
        rollout_data = attention_rollout(py_model, board_state, device=device)

        # Average attention per square
        visualize_rollout(
            rollout_data["rollout"],
            save_path=os.path.join(args.out_dir, "rollout_avg.png"),
        )

        # Per-source-square rollout
        if args.source_square:
            r, c = map(int, args.source_square.split(","))
            visualize_rollout(
                rollout_data["rollout"],
                source_square=(r, c),
                save_path=os.path.join(args.out_dir, f"rollout_r{r}c{c}.png"),
            )
            visualize_per_head(
                rollout_data["raw_heads"],
                source_square=(r, c),
                save_path=os.path.join(args.out_dir, f"per_head_r{r}c{c}.png"),
            )

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
