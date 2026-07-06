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
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [_ipa_name] + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tsume_shogi import TSUME_POSITIONS, TSUME_NAMES, _TSUME_BY_NAME
from xai_analysis import (
    attention_rollout,
    dummy_board_state,
    get_pre_softmax_data,
    get_relative_bias_maps,
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
    visualize_pre_softmax_single_head,
    visualize_relative_bias,
    visualize_rollout,
    visualize_single_head,
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


    # ── 詰将棋 Attention Map 解析 ──────────────────────────────────────────────
    gr.Markdown("---")
    with gr.Accordion("② 詰将棋 Attention Map 解析（有名局面でアテンションを可視化）", open=True):
        gr.Markdown(
            "有名詰将棋局面を SFEN で入力し、**正解の一手**を USI 表記で与えると、\n"
            "IJCAI-25 論文スタイルで **Attention Map** と **Attention Rollout** を可視化します。\n\n"
            "- **Attention Map**: 指定ヘッドが正解手のマスから盤面のどこを参照しているか（生のAttention値、論文Figure5と同じ）\n"
            "- **Attention Rollout**: 全レイヤーを連鎖させた累積的な参照パターン\n\n"
            "USI 表記例: 盤上の駒移動 `7g7f`、成り `2b3c+`、打ち `G*4b`"
        )
        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                tsume_model_in = gr.Textbox(
                    label="Model path (.pt)",
                    placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt",
                )
                tsume_preset_in = gr.Dropdown(
                    choices=["（カスタム入力）"] + TSUME_NAMES,
                    value=TSUME_NAMES[0],
                    label="有名局面プリセット",
                )
                tsume_sfen_in = gr.Textbox(
                    label="SFEN（プリセット選択で自動入力）",
                    value=TSUME_POSITIONS[0]["sfen"],
                    lines=2,
                )
                tsume_move_in = gr.Textbox(
                    label="正解の一手（USI表記）",
                    value=TSUME_POSITIONS[0]["answer_usi"],
                    placeholder="例: G*5b  / 7g7f  / 2b3c+",
                )
                tsume_desc_out = gr.Textbox(
                    label="局面の説明",
                    value=TSUME_POSITIONS[0]["description"],
                    lines=4, interactive=False,
                )
                tsume_gpu_in = gr.Checkbox(label="Use GPU (if available)", value=True)
                tsume_run_btn = gr.Button("詰将棋 XAI 解析を実行", variant="primary", size="lg")
                tsume_log_out = gr.Textbox(label="Log", lines=5, interactive=False)

            with gr.Column(scale=2):
                gr.Markdown(
                    "**Attention Map（論文スタイル）**\n\n"
                    "緑 × = クエリ位置（正解手のマス）。赤いほどそのマスを参照している。\n"
                    "レイヤー・ヘッドを変えると異なる知識パターンが見える（モデル再実行なし）。"
                )
                with gr.Row():
                    tsume_layer_sl = gr.Slider(
                        minimum=1, maximum=2, step=1, value=1,
                        label="Layer（Tブロック番号）1〜2",
                    )
                    tsume_head_sl = gr.Slider(
                        minimum=1, maximum=4, step=1, value=1,
                        label="Head（アテンションヘッド番号）1〜4",
                    )
                tsume_attn_out = gr.Image(label="Attention Map（論文スタイル）", type="pil")
                gr.Markdown("**Attention Rollout** — 全レイヤー累積参照パターン")
                tsume_rollout_out = gr.Image(label="Attention Rollout", type="pil")

        # State: raw_heads / dots_table / board_state / source_square を保持
        _tsume_raw_heads_state  = gr.State(value=None)   # list of (H,N,N) arrays
        _tsume_dots_state       = gr.State(value=None)   # list of (1,H,N,N) tensors
        _tsume_board_state_st   = gr.State(value=None)   # torch tensor (CPU)
        _tsume_src_sq_state     = gr.State(value=None)   # (row, col) or None

        def _tsume_preset_change(name):
            if name == "（カスタム入力）":
                return gr.update(), gr.update(), gr.update()
            pos = _TSUME_BY_NAME.get(name)
            if pos is None:
                return gr.update(), gr.update(), gr.update()
            return pos["sfen"], pos["answer_usi"], pos["description"]

        tsume_preset_in.change(
            fn=_tsume_preset_change,
            inputs=[tsume_preset_in],
            outputs=[tsume_sfen_in, tsume_move_in, tsume_desc_out],
        )

        def _run_tsume(model_path, sfen, usi_move, use_gpu, layer_idx, head_idx):
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from tsume_shogi import sfen_to_tensor, _usi_sq_to_py

            model_path = model_path.strip()
            if not model_path or not os.path.isfile(model_path):
                raise gr.Error(f"Model not found: {model_path}")
            sfen     = sfen.strip()
            usi_move = usi_move.strip()
            if not sfen:
                raise gr.Error("SFENを入力してください。")
            if not usi_move:
                raise gr.Error("正解の一手（USI）を入力してください。")

            device   = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"
            log      = [f"Device: {device}", f"SFEN: {sfen}", f"Move: {usi_move}"]
            is_black = sfen.split()[1].lower() == "b" if len(sfen.split()) > 1 else True

            try:
                board_state = sfen_to_tensor(sfen, device=device)
            except Exception as e:
                raise gr.Error(f"SFEN parse error: {e}")

            # ── Attention（論文スタイル + Rollout + Pre-softmax） ─────────────────
            py_model     = _get_py_model(model_path, device)
            pre_data     = get_pre_softmax_data(py_model, board_state, device=device)
            raw_heads    = [a[0].cpu().numpy() for a in pre_data["att_table"]]
            dots_table   = pre_data["dots_table"]   # list of (1, H, N, N) tensors
            num_layers   = len(raw_heads)
            num_heads    = raw_heads[0].shape[0]
            log.append(f"Transformer: {num_layers} layers × {num_heads} heads")
            log.append(f"Pre-softmax logits captured: {len(dots_table)} layer(s)")

            # クエリ位置: 盤上移動 → 移動元、打ち駒 → 打つ先
            src_sq = None
            if "*" not in usi_move:
                core = usi_move.rstrip("+")
                if len(core) >= 4:
                    src_flat = _usi_sq_to_py(core[0], core[1], is_black)
                    src_sq   = (src_flat // 9, src_flat % 9)
            else:
                dest = usi_move[2:]
                if len(dest) >= 2:
                    src_flat = _usi_sq_to_py(dest[0], dest[1], is_black)
                    src_sq   = (src_flat // 9, src_flat % 9)

            li = max(0, min(int(layer_idx) - 1, num_layers - 1))
            hi = max(0, min(int(head_idx)  - 1, num_heads  - 1))

            # compute rollout from raw_heads
            import numpy as _np
            N_sq = board_size * board_size if (board_size := 9) else 81
            eye = _np.eye(N_sq)
            rollout_mat = None
            for rh in raw_heads:
                a_fused = rh.mean(axis=0) + eye
                a_fused /= a_fused.sum(axis=-1, keepdims=True)
                rollout_mat = a_fused if rollout_mat is None else rollout_mat @ a_fused

            attn_img = None
            rollout_img = None
            if src_sq is not None:
                attn_img = _fig_to_pil(
                    visualize_single_head(
                        raw_heads, src_sq,
                        layer_idx=li, head_idx=hi,
                        board_state=board_state,
                    )
                )
                if rollout_mat is not None:
                    rollout_img = _fig_to_pil(
                        visualize_rollout(
                            rollout_mat,
                            source_square=src_sq,
                            board_state=board_state,
                        )
                    )

            bs_cpu = board_state.cpu()
            return (attn_img, rollout_img,
                    raw_heads, dots_table, bs_cpu, src_sq,
                    "\n".join(log))

        tsume_run_btn.click(
            fn=_run_tsume,
            inputs=[tsume_model_in, tsume_sfen_in, tsume_move_in,
                    tsume_gpu_in, tsume_layer_sl, tsume_head_sl],
            outputs=[tsume_attn_out, tsume_rollout_out,
                     _tsume_raw_heads_state, _tsume_dots_state,
                     _tsume_board_state_st, _tsume_src_sq_state,
                     tsume_log_out],
        )

        # Pre-softmax出力先
        with gr.Row():
            tsume_presoftmax_out = gr.Image(
                label="Pre-softmax Logits（softmax前のQ·K内積、約60倍コントラスト）",
                type="pil",
            )

        # レイヤー / ヘッド変更で Attention Map + Pre-softmax を再描画
        def _update_attn_head(raw_heads, dots_table, board_state, src_sq, layer_idx, head_idx):
            if raw_heads is None or src_sq is None:
                return gr.update(), gr.update()
            num_layers = len(raw_heads)
            num_heads  = raw_heads[0].shape[0]
            li = max(0, min(int(layer_idx) - 1, num_layers - 1))
            hi = max(0, min(int(head_idx)  - 1, num_heads  - 1))
            bs = board_state if board_state is not None else None

            attn_img = _fig_to_pil(
                visualize_single_head(raw_heads, src_sq, layer_idx=li, head_idx=hi, board_state=bs)
            )

            pre_img = None
            if dots_table:
                pre_img = _fig_to_pil(
                    visualize_pre_softmax_single_head(
                        dots_table, src_sq, layer_idx=li, head_idx=hi, board_state=bs
                    )
                )

            return attn_img, pre_img

        for _sl in [tsume_layer_sl, tsume_head_sl]:
            _sl.change(
                fn=_update_attn_head,
                inputs=[_tsume_raw_heads_state, _tsume_dots_state,
                        _tsume_board_state_st, _tsume_src_sq_state,
                        tsume_layer_sl, tsume_head_sl],
                outputs=[tsume_attn_out, tsume_presoftmax_out],
            )

    # ── Relative Position Bias 可視化 ───────────────────────────────────────────
    gr.Markdown("---")
    with gr.Accordion("③ Relative Position Bias 可視化（モデルが学習した位置依存性）", open=False):
        gr.Markdown(
            "各Tブロック・各ヘッドが「どの相対位置を優先するか」を可視化します。\n\n"
            "- **赤** = 正バイアス（その位置への注意を強める）\n"
            "- **青** = 負バイアス（その位置への注意を抑える）\n"
            "- 学習が進んでいないと全て白（ゼロ付近）になります\n\n"
            "クエリ位置（緑×）からの相対バイアスを9×9盤面上に表示します。"
        )
        with gr.Row():
            bias_model_in = gr.Textbox(
                label="Model path (.pt)",
                placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt",
                scale=3,
            )
            bias_gpu_in = gr.Checkbox(label="Use GPU", value=False, scale=1)
        with gr.Row():
            bias_row_in = gr.Number(value=4, precision=0, label="クエリ行 (0〜8)", scale=1)
            bias_col_in = gr.Number(value=4, precision=0, label="クエリ列 (0〜8)", scale=1)
            bias_btn    = gr.Button("Relative Bias を表示", variant="primary", scale=2)
        bias_log_out = gr.Textbox(label="Log", lines=3, interactive=False)
        bias_img_out = gr.Image(label="Relative Position Bias（全レイヤー×全ヘッド）", type="pil")

        def _run_bias(model_path, use_gpu, qrow, qcol):
            model_path = model_path.strip()
            if not model_path or not os.path.isfile(model_path):
                raise gr.Error(f"Model not found: {model_path}")
            device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"
            py_model = _get_py_model(model_path, device)
            bias_maps = get_relative_bias_maps(py_model)
            if not bias_maps:
                return "relative_bias_table が見つかりませんでした。", None
            num_layers = len(bias_maps)
            num_heads  = len(bias_maps[0])
            src_sq = (int(qrow), int(qcol))
            fig = visualize_relative_bias(bias_maps, source_square=src_sq)
            log = f"relative_bias: {num_layers} T-layer(s) × {num_heads} head(s)  query={src_sq}"
            return log, _fig_to_pil(fig)

        bias_btn.click(
            fn=_run_bias,
            inputs=[bias_model_in, bias_gpu_in, bias_row_in, bias_col_in],
            outputs=[bias_log_out, bias_img_out],
        )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=None,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
    )
