"""
Gradio web UI for ResTNet Shogi XAI analysis.

Run inside the Docker container:
    python xai_app.py
Then open the URL printed in the terminal (default http://localhost:7860).

Methods:
  - Perturbation/Occlusion  (Zeiler & Fergus, ECCV 2014)
  - Integrated Gradients    (Sundararajan et al., ICML 2017)
  - Attention Rollout       (Abnar & Zuidema, ACL 2020)
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
    load_board_from_sgf,
    load_python_model,
    load_torchscript_model,
    occlusion,
    visualize_ig,
    visualize_per_head,
    visualize_perturbation,
    visualize_rollout,
)

# ── model cache ────────────────────────────────────────────────────────────────
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


# ── analysis function ──────────────────────────────────────────────────────────

def run_analysis(
    model_path: str,
    methods: list[str],
    target: str,
    steps: int,
    source_square_str: str,
    use_gpu: bool,
    sgf_path: str,
    conf_path: str,
    game_type: str,
):
    model_path = model_path.strip()
    if not model_path:
        raise gr.Error("Please enter a model path.")
    if not os.path.isfile(model_path):
        raise gr.Error(f"File not found: {model_path}")
    if not methods:
        raise gr.Error("Select at least one method.")

    device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"

    # parse source square for rollout
    source_square = None
    if source_square_str and source_square_str.strip():
        try:
            r_str, c_str = source_square_str.strip().split(",")
            source_square = (int(r_str), int(c_str))
            if not (0 <= source_square[0] <= 8 and 0 <= source_square[1] <= 8):
                raise ValueError
        except ValueError:
            raise gr.Error("Source square must be 'row,col' with values 0–8, e.g. '4,4'.")

    # ── board state ──────────────────────────────────────────────────────────
    sgf_path = sgf_path.strip() if sgf_path else ""
    conf_path = conf_path.strip() if conf_path else ""
    board_overlay = None   # tensor passed to visualize functions for piece overlay

    log_lines = [f"Device : {device}"]

    if sgf_path:
        if not os.path.isfile(sgf_path):
            raise gr.Error(f"SGF file not found: {sgf_path}")
        if not conf_path:
            raise gr.Error("Config file path is required when using an SGF file.")
        if not os.path.isfile(conf_path):
            raise gr.Error(f"Config file not found: {conf_path}")
        try:
            board_state = load_board_from_sgf(
                sgf_path, conf_path, game_type.strip() or "shogi_9x9", device=device
            )
            board_overlay = board_state
            log_lines.append(f"Board    : loaded from SGF {os.path.basename(sgf_path)}, "
                             f"shape {tuple(board_state.shape)}")
        except ImportError as e:
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"Failed to load SGF: {e}")
    else:
        board_state = dummy_board_state(num_input_channels=362, device=device)
        log_lines.append("Board    : random dummy (no SGF provided)")

    results = dict(
        occ_value=None, occ_policy=None,
        ig_value=None,  ig_policy=None,
        rollout_avg=None, rollout_src=None, per_head=None,
    )

    # ── Perturbation / Occlusion ───────────────────────────────────────────────
    if "Perturbation/Occlusion" in methods:
        ts_model = _get_ts_model(model_path, device)

        if target in ("value", "both"):
            attr, _ = occlusion(ts_model, board_state, target="value", device=device)
            log_lines.append(f"Occ-value : range [{attr.min():.4f}, {attr.max():.4f}]")
            fig = visualize_perturbation(
                attr, title="Occlusion — Value sensitivity", board_state=board_overlay
            )
            results["occ_value"] = _fig_to_pil(fig)

        if target in ("policy", "both"):
            attr, action = occlusion(ts_model, board_state, target="policy", device=device)
            log_lines.append(
                f"Occ-policy: top action={action}, "
                f"range [{attr.min():.4f}, {attr.max():.4f}]"
            )
            fig = visualize_perturbation(
                attr,
                title=f"Occlusion — Policy sensitivity (action {action})",
                board_state=board_overlay,
            )
            results["occ_policy"] = _fig_to_pil(fig)

    # ── Integrated Gradients ───────────────────────────────────────────────────
    if "Integrated Gradients" in methods:
        ts_model = _get_ts_model(model_path, device)

        if target in ("value", "both"):
            attr, _ = integrated_gradients(
                ts_model, board_state, target="value",
                steps=steps, device=device,
            )
            log_lines.append(f"IG-value  : range [{attr.min():.4f}, {attr.max():.4f}]")
            fig = visualize_ig(
                attr, title="IG — Value attribution", board_state=board_overlay
            )
            results["ig_value"] = _fig_to_pil(fig)

        if target in ("policy", "both"):
            attr, action = integrated_gradients(
                ts_model, board_state, target="policy",
                steps=steps, device=device,
            )
            log_lines.append(
                f"IG-policy : top action={action}, "
                f"range [{attr.min():.4f}, {attr.max():.4f}]"
            )
            fig = visualize_ig(
                attr,
                title=f"IG — Policy attribution (action {action})",
                board_state=board_overlay,
            )
            results["ig_policy"] = _fig_to_pil(fig)

    # ── Attention Rollout ──────────────────────────────────────────────────────
    if "Attention Rollout" in methods:
        py_model = _get_py_model(model_path, device)
        rollout_data = attention_rollout(py_model, board_state, device=device)
        num_t  = len(rollout_data["raw_heads"])
        n_head = rollout_data["raw_heads"][0].shape[0] if num_t else 0
        log_lines.append(f"Rollout   : {num_t} T-layer(s) × {n_head} head(s)")

        fig = visualize_rollout(rollout_data["rollout"], board_state=board_overlay)
        results["rollout_avg"] = _fig_to_pil(fig)

        if source_square is not None:
            fig = visualize_rollout(
                rollout_data["rollout"],
                source_square=source_square,
                board_state=board_overlay,
            )
            results["rollout_src"] = _fig_to_pil(fig)

            fig = visualize_per_head(
                rollout_data["raw_heads"],
                source_square=source_square,
                board_state=board_overlay,
            )
            results["per_head"] = _fig_to_pil(fig)
        else:
            log_lines.append("Tip: enter a source square (e.g. 4,4) for per-source and per-head maps.")

    return (
        results["occ_value"],  results["occ_policy"],
        results["ig_value"],   results["ig_policy"],
        results["rollout_avg"], results["rollout_src"], results["per_head"],
        "\n".join(log_lines),
    )


# ── Gradio UI ──────────────────────────────────────────────────────────────────

_DESC = """
## ResTNet Shogi — XAI Analysis

| Method | Paper |
|---|---|
| **Perturbation/Occlusion** | Zeiler & Fergus, ECCV 2014 |
| **Integrated Gradients** | Sundararajan et al., ICML 2017 |
| **Attention Rollout** | Abnar & Zuidema, ACL 2020 |
"""

with gr.Blocks(title="ResTNet XAI") as demo:
    gr.Markdown(_DESC)

    with gr.Row():
        # ── controls ───────────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=320):
            model_path_in = gr.Textbox(
                label="Model path (.pt)",
                placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt",
            )
            methods_in = gr.CheckboxGroup(
                choices=["Perturbation/Occlusion", "Integrated Gradients", "Attention Rollout"],
                value=["Integrated Gradients"],
                label="Methods",
            )
            target_in = gr.Dropdown(
                choices=["value", "policy", "both"],
                value="value",
                label="Target  (for Occlusion and IG)",
            )
            steps_in = gr.Slider(
                minimum=20, maximum=300, step=10, value=50,
                label="IG Steps  (20=fast · 300=paper quality)",
            )
            source_sq_in = gr.Textbox(
                label="Source square for Rollout  (row,col)",
                placeholder="4,4  →  centre",
                value="4,4",
            )
            use_gpu_in = gr.Checkbox(label="Use GPU (if available)", value=True)

            with gr.Accordion("SGF board input (requires C++ build)", open=False):
                gr.Markdown(
                    "Load a real board position from an SGF file.\n"
                    "Piece kanji will be overlaid on all heatmaps.\n"
                    "**Requires the C++ environment to be built** (`build/<game_type>/`)."
                )
                sgf_path_in = gr.Textbox(
                    label="SGF file path",
                    placeholder="games/example.sgf",
                )
                conf_path_in = gr.Textbox(
                    label="Config file path (.cfg)",
                    placeholder="configs/9x9_shogi/2R1T2R1T.cfg",
                )
                game_type_in = gr.Textbox(
                    label="Game type (build/<name>/ directory)",
                    value="shogi",
                    placeholder="shogi",
                )

            run_btn = gr.Button("Run Analysis", variant="primary", size="lg")
            log_out = gr.Textbox(label="Log", lines=8, interactive=False)

        # ── outputs ────────────────────────────────────────────────────────────
        with gr.Column(scale=2):
            gr.Markdown("### Perturbation / Occlusion")
            with gr.Row():
                occ_value_out  = gr.Image(label="Occlusion — Value",  type="pil")
                occ_policy_out = gr.Image(label="Occlusion — Policy", type="pil")

            gr.Markdown("### Integrated Gradients")
            with gr.Row():
                ig_value_out  = gr.Image(label="IG — Value",  type="pil")
                ig_policy_out = gr.Image(label="IG — Policy", type="pil")

            gr.Markdown("### Attention Rollout")
            with gr.Row():
                rollout_avg_out = gr.Image(label="Rollout — Average",       type="pil")
                rollout_src_out = gr.Image(label="Rollout — Source square", type="pil")
            per_head_out = gr.Image(label="Per-head attention (layers × heads)", type="pil")

    run_btn.click(
        fn=run_analysis,
        inputs=[
            model_path_in, methods_in, target_in, steps_in, source_sq_in, use_gpu_in,
            sgf_path_in, conf_path_in, game_type_in,
        ],
        outputs=[
            occ_value_out, occ_policy_out,
            ig_value_out,  ig_policy_out,
            rollout_avg_out, rollout_src_out, per_head_out,
            log_out,
        ],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=None,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
    )
