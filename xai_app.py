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
import matplotlib.font_manager as _fm
import torch
from PIL import Image

# Register IPA Mincho so Japanese text renders in charts
_IPA_PATH = "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf"
if os.path.isfile(_IPA_PATH):
    _fm.fontManager.addfont(_IPA_PATH)
    _ipa_name = _fm.FontProperties(fname=_IPA_PATH).get_name()
    plt.rcParams["font.family"] = _ipa_name

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xai_analysis import (
    attention_rollout,
    dummy_board_state,
    integrated_gradients,
    load_board_from_sgf,
    load_python_model,
    load_torchscript_model,
    occlusion,
    sgf_file_stats,
    sgf_game_values,
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


def _sgf_overview(sgf_path: str) -> tuple[str, Image.Image | None]:
    """Return (summary_text, move_distribution_image) for an SGF file."""
    sgf_path = sgf_path.strip() if sgf_path else ""
    if not sgf_path or not os.path.isfile(sgf_path):
        return "SGF ファイルのパスを入力してください。", None

    try:
        stats = sgf_file_stats(sgf_path)
    except Exception as e:
        return f"読み込みエラー: {e}", None

    n = stats["num_games"]
    mc = stats["move_counts"]
    import statistics as _st
    summary = (
        f"📄 {os.path.basename(sgf_path)}\n"
        f"局数       : {n} 局\n"
        f"手数 最小  : {min(mc)} 手\n"
        f"手数 最大  : {max(mc)} 手\n"
        f"手数 平均  : {_st.mean(mc):.1f} 手\n"
        f"手数 中央値: {_st.median(mc):.0f} 手\n"
    )

    # histogram of move counts
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.hist(mc, bins=40, color="#4a90d9", edgecolor="white", linewidth=0.4)
    ax.set_xlabel("手数（何手で終了したか）", fontsize=10)
    ax.set_ylabel("局数", fontsize=10)
    ax.set_title(f"{os.path.basename(sgf_path)} — 各局の手数分布（全 {n} 局）", fontsize=11)
    ax.axvline(_st.mean(mc), color="red",    linestyle="--", linewidth=1.2, label=f"平均 {_st.mean(mc):.0f}手")
    ax.axvline(_st.median(mc), color="orange", linestyle=":",  linewidth=1.2, label=f"中央値 {_st.median(mc):.0f}手")
    ax.legend(fontsize=9)
    plt.tight_layout()
    img = _fig_to_pil(fig)
    return summary, img


def _sgf_value_chart(sgf_path: str, game_idx: int) -> tuple[str, Image.Image | None]:
    """Return (info_text, value_trajectory_image) for one game."""
    sgf_path = sgf_path.strip() if sgf_path else ""
    if not sgf_path or not os.path.isfile(sgf_path):
        return "SGF ファイルのパスを入力してください。", None

    try:
        values, total = sgf_game_values(sgf_path, int(game_idx))
    except Exception as e:
        return f"エラー: {e}", None

    if not values:
        return "V[] フィールドが見つかりません。", None

    import numpy as _np
    moves = list(range(1, len(values) + 1))
    dv    = _np.diff(values)
    crit  = int(_np.argmax(_np.abs(dv))) + 1   # move index (1-based) of max |ΔV|

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(moves, values, color="#2c7bb6", linewidth=1.4, label="V（価値推定）")
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.fill_between(moves, values, 0,
                    where=[v > 0 for v in values], alpha=0.15, color="#d73027", label="先手優勢")
    ax.fill_between(moves, values, 0,
                    where=[v < 0 for v in values], alpha=0.15, color="#4575b4", label="後手優勢")
    ax.axvline(crit, color="crimson", linewidth=1.5, linestyle="-.",
               label=f"形勢最大変動: {crit}手目 (ΔV={dv[crit-1]:+.3f})")
    ax.set_xlabel("手数", fontsize=10)
    ax.set_ylabel("価値 V（先手視点）", fontsize=10)
    ax.set_title(
        f"{os.path.basename(sgf_path)} — game {int(game_idx)}  "
        f"（全 {total} 手）",
        fontsize=11,
    )
    ax.set_xlim(1, total)
    ax.set_ylim(-1.05, 1.05)
    ax.legend(fontsize=8, loc="best")
    plt.tight_layout()
    img = _fig_to_pil(fig)

    info = (
        f"game {int(game_idx)}: 全 {total} 手\n"
        f"形勢最大変動: {crit} 手目  ΔV={dv[crit-1]:+.3f}\n"
        f"  → 手数欄に「{crit}」を入力して XAI 解析を実行してください"
    )
    return info, img


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
    game_idx: int,
    move_idx: int,
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
    board_overlay = None
    board_info    = None

    log_lines = [f"Device : {device}"]

    if sgf_path:
        if not os.path.isfile(sgf_path):
            raise gr.Error(f"SGF file not found: {sgf_path}")
        if not conf_path:
            raise gr.Error("Config file path is required when using an SGF file.")
        if not os.path.isfile(conf_path):
            raise gr.Error(f"Config file not found: {conf_path}")
        try:
            board_state, board_info = load_board_from_sgf(
                sgf_path, conf_path, game_type.strip() or "shogi",
                game_idx=int(game_idx), move_idx=int(move_idx), device=device,
            )
            board_overlay = board_state
            from xai_analysis import _board_subtitle
            log_lines.append(f"Board    : {_board_subtitle(board_info)}, "
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
                attr, title="Occlusion — Value sensitivity",
                board_state=board_overlay, board_info=board_info,
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
                board_state=board_overlay, board_info=board_info,
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
                attr, title="IG — Value attribution",
                board_state=board_overlay, board_info=board_info,
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
                board_state=board_overlay, board_info=board_info,
            )
            results["ig_policy"] = _fig_to_pil(fig)

    # ── Attention Rollout ──────────────────────────────────────────────────────
    if "Attention Rollout" in methods:
        py_model = _get_py_model(model_path, device)
        rollout_data = attention_rollout(py_model, board_state, device=device)
        num_t  = len(rollout_data["raw_heads"])
        n_head = rollout_data["raw_heads"][0].shape[0] if num_t else 0
        log_lines.append(f"Rollout   : {num_t} T-layer(s) × {n_head} head(s)")

        fig = visualize_rollout(rollout_data["rollout"],
                               board_state=board_overlay, board_info=board_info)
        results["rollout_avg"] = _fig_to_pil(fig)

        if source_square is not None:
            fig = visualize_rollout(
                rollout_data["rollout"],
                source_square=source_square,
                board_state=board_overlay, board_info=board_info,
            )
            results["rollout_src"] = _fig_to_pil(fig)

            fig = visualize_per_head(
                rollout_data["raw_heads"],
                source_square=source_square,
                board_state=board_overlay, board_info=board_info,
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

    # ── SGF 情報パネル ──────────────────────────────────────────────────────────
    with gr.Accordion("① SGF ファイル情報を確認する（手数選択の参考に）", open=False):
        gr.Markdown(
            "**使い方**:\n"
            "1. SGF ファイルのパスを入力し「ファイル情報を表示」で局数・手数分布を確認\n"
            "2. ゲーム番号を入力し「価値推移を表示」でそのゲームの形勢グラフを確認\n"
            "3. グラフの赤い点線（形勢最大変動）付近の手数を、下の XAI 解析の「手数」欄に入力"
        )
        with gr.Row():
            info_sgf_path = gr.Textbox(
                label="SGF file path",
                placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/sgf/5.sgf",
                scale=3,
            )
            info_btn = gr.Button("ファイル情報を表示", scale=1)
        info_summary_out = gr.Textbox(label="ファイル統計", lines=7, interactive=False)
        info_hist_out    = gr.Image(label="各局の手数分布", type="pil")

        with gr.Row():
            info_game_idx = gr.Number(value=0, precision=0, label="ゲーム番号", scale=1)
            value_btn     = gr.Button("価値推移を表示", scale=1)
        value_info_out  = gr.Textbox(label="形勢情報（推奨手数が表示されます）",
                                     lines=4, interactive=False)
        value_chart_out = gr.Image(label="価値推移グラフ（赤点線=形勢最大変動）", type="pil")

        info_btn.click(
            fn=_sgf_overview,
            inputs=[info_sgf_path],
            outputs=[info_summary_out, info_hist_out],
        )
        value_btn.click(
            fn=_sgf_value_chart,
            inputs=[info_sgf_path, info_game_idx],
            outputs=[value_info_out, value_chart_out],
        )

    gr.Markdown("---")

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
                    placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/sgf/5.sgf",
                )
                conf_path_in = gr.Textbox(
                    label="Config file path (.cfg)",
                    placeholder="configs/9x9_shogi/RRTRRT.cfg",
                )
                game_type_in = gr.Textbox(
                    label="Game type (build/<name>/ directory)",
                    value="shogi",
                    placeholder="shogi",
                )
                with gr.Row():
                    game_idx_in = gr.Number(
                        value=0, precision=0,
                        label="ゲーム番号 (0-基準)",
                    )
                    move_idx_in = gr.Number(
                        value=-1, precision=0,
                        label="手数 (-1=最終局面, 0=初期配置, N=N手目)",
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
            sgf_path_in, conf_path_in, game_type_in, game_idx_in, move_idx_in,
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
