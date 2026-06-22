"""
Gradio web UI for ResTNet Shogi XAI analysis.

Run inside the Docker container:
    python xai_app.py
Then open http://localhost:7860 in your browser.

Methods:
  - Integrated Gradients  (Sundararajan et al., ICML 2017)
  - Attention Rollout     (Abnar & Zuidema, ACL 2020)
"""

import io
import os
import sys

import gradio as gr
import matplotlib.pyplot as plt
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xai_analysis import (
    attention_rollout,
    dummy_board_state,
    integrated_gradients,
    load_python_model,
    load_torchscript_model,
    visualize_ig,
    visualize_per_head,
    visualize_rollout,
)

# ── model cache: avoid reloading the same .pt file on every button click ──────
_ts_cache: dict = {}
_py_cache: dict = {}


def _get_ts_model(model_path: str, device: str):
    key = (model_path, device)
    if key not in _ts_cache:
        _ts_cache[key] = load_torchscript_model(model_path, device=device)
    return _ts_cache[key]


def _get_py_model(model_path: str, device: str):
    key = (model_path, device)
    if key not in _py_cache:
        _py_cache[key] = load_python_model(model_path, device=device)
    return _py_cache[key]


def _fig_to_pil(fig: plt.Figure) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img = Image.open(buf).copy()
    buf.close()
    plt.close(fig)
    return img


# ── main analysis function ────────────────────────────────────────────────────

def run_analysis(
    model_path: str,
    target: str,
    steps: int,
    source_square_str: str,
    use_gpu: bool,
):
    """Called when the user clicks Run Analysis."""

    # ── validate inputs ───────────────────────────────────────────────────────
    model_path = model_path.strip()
    if not model_path:
        raise gr.Error("Please enter a model path.")
    if not os.path.isfile(model_path):
        raise gr.Error(f"File not found: {model_path}")

    device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"

    # ── parse source square ───────────────────────────────────────────────────
    source_square = None
    if source_square_str and source_square_str.strip():
        try:
            r_str, c_str = source_square_str.strip().split(",")
            source_square = (int(r_str), int(c_str))
            if not (0 <= source_square[0] <= 8 and 0 <= source_square[1] <= 8):
                raise ValueError
        except ValueError:
            raise gr.Error(
                "Source square must be 'row,col' with values 0–8, e.g. '4,4' for centre."
            )

    # ── board state (replace with real loader if needed) ─────────────────────
    board_state = dummy_board_state(num_input_channels=362, device=device)

    ig_value_img  = None
    ig_policy_img = None
    rollout_avg_img = None
    rollout_src_img = None
    per_head_img  = None
    log_lines: list[str] = [f"Device: {device}"]

    # ── Integrated Gradients ──────────────────────────────────────────────────
    if target in ("value", "policy", "both"):
        ts_model = _get_ts_model(model_path, device)

        if target in ("value", "both"):
            attr, _ = integrated_gradients(
                ts_model, board_state, target="value",
                steps=steps, device=device,
            )
            log_lines.append(
                f"IG-value : range [{attr.min():.4f}, {attr.max():.4f}]"
            )
            fig = visualize_ig(attr, title="IG — Value attribution")
            ig_value_img = _fig_to_pil(fig)

        if target in ("policy", "both"):
            attr, action = integrated_gradients(
                ts_model, board_state, target="policy",
                steps=steps, device=device,
            )
            log_lines.append(
                f"IG-policy: top action={action}, "
                f"range [{attr.min():.4f}, {attr.max():.4f}]"
            )
            fig = visualize_ig(attr, title=f"IG — Policy attribution (action {action})")
            ig_policy_img = _fig_to_pil(fig)

    # ── Attention Rollout ─────────────────────────────────────────────────────
    if target in ("rollout", "both"):
        py_model = _get_py_model(model_path, device)
        rollout_data = attention_rollout(py_model, board_state, device=device)
        num_t_layers = len(rollout_data["raw_heads"])
        num_heads    = rollout_data["raw_heads"][0].shape[0] if num_t_layers else 0
        log_lines.append(
            f"Rollout  : {num_t_layers} T-layer(s) × {num_heads} head(s)"
        )

        fig = visualize_rollout(rollout_data["rollout"])
        rollout_avg_img = _fig_to_pil(fig)

        if source_square is not None:
            fig = visualize_rollout(rollout_data["rollout"], source_square=source_square)
            rollout_src_img = _fig_to_pil(fig)

            fig = visualize_per_head(rollout_data["raw_heads"], source_square=source_square)
            per_head_img = _fig_to_pil(fig)
        else:
            log_lines.append(
                "Tip: enter a source square (e.g. 4,4) to see per-source and per-head maps."
            )

    log_text = "\n".join(log_lines)
    return ig_value_img, ig_policy_img, rollout_avg_img, rollout_src_img, per_head_img, log_text


# ── Gradio UI ─────────────────────────────────────────────────────────────────

_DESC = """
## ResTNet Shogi — XAI Analysis

**Integrated Gradients** (Sundararajan et al., ICML 2017) — which board squares drove the output?
**Attention Rollout** (Abnar & Zuidema, ACL 2020) — where does the Transformer look?
"""

with gr.Blocks(title="ResTNet XAI", theme=gr.themes.Soft()) as demo:
    gr.Markdown(_DESC)

    with gr.Row():
        # ── left column: controls ─────────────────────────────────────────────
        with gr.Column(scale=1, min_width=320):
            model_path_in = gr.Textbox(
                label="Model path (.pt)",
                placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt",
            )
            target_in = gr.Dropdown(
                choices=["value", "policy", "both", "rollout"],
                value="both",
                label="Target",
            )
            steps_in = gr.Slider(
                minimum=20, maximum=300, step=10, value=50,
                label="IG Steps  (20=fast, 300=paper quality)",
            )
            source_sq_in = gr.Textbox(
                label="Source square for rollout  (row,col)",
                placeholder="4,4  →  centre square",
                value="4,4",
            )
            use_gpu_in = gr.Checkbox(
                label="Use GPU (if available)",
                value=True,
            )
            run_btn = gr.Button("Run Analysis", variant="primary", size="lg")
            log_out = gr.Textbox(
                label="Log", lines=6, interactive=False,
            )

        # ── right column: outputs ─────────────────────────────────────────────
        with gr.Column(scale=2):
            with gr.Row():
                ig_value_out  = gr.Image(label="IG — Value attribution",  type="pil")
                ig_policy_out = gr.Image(label="IG — Policy attribution", type="pil")
            with gr.Row():
                rollout_avg_out = gr.Image(label="Rollout — Average received", type="pil")
                rollout_src_out = gr.Image(label="Rollout — Source square",    type="pil")
            per_head_out = gr.Image(label="Per-head attention (layers × heads)", type="pil")

    run_btn.click(
        fn=run_analysis,
        inputs=[model_path_in, target_in, steps_in, source_sq_in, use_gpu_in],
        outputs=[
            ig_value_out, ig_policy_out,
            rollout_avg_out, rollout_src_out,
            per_head_out,
            log_out,
        ],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",   # accessible from host when using Docker port-forward
        server_port=7860,
        share=False,
        show_error=True,
    )
