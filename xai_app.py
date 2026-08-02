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
from tsume_shogi import TSUME_NAMES, _TSUME_BY_NAME
from xai_analysis import (
    attention_rollout,
    get_pre_softmax_data,
    hand_piece_contribution,
    visualize_hand_contribution,
    get_relative_bias_maps,
    integrated_gradients,
    load_board_from_sgf,
    load_python_model,
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
_py_cache: dict = {}


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
                    value="shogi_9x9_restnet64_v2/model/weight_iter_60000.pt",
                    placeholder="shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_200.pt",
                )
                tsume_preset_in = gr.Dropdown(
                    choices=["（カスタム入力）"] + TSUME_NAMES,
                    value="（カスタム入力）",
                    label="詰将棋プリセット（選択でSFEN・正解手を自動入力）",
                )
                tsume_sfen_in = gr.Textbox(
                    label="SFEN（局面を入力）",
                    value="",
                    placeholder="例: lnsgkgsnl/1r5b1/ppppppppp/... b - 1",
                    lines=2,
                )
                tsume_move_in = gr.Textbox(
                    label="正解の一手（USI表記）",
                    value="",
                    placeholder="例: G*5b  / 7g7f  / 2b3c+",
                )
                tsume_desc_out = gr.Textbox(
                    label="局面の説明",
                    value="",
                    lines=4, interactive=False,
                )
                tsume_board_source_in = gr.Radio(
                    choices=["SFEN入力", "自己対局SGF"],
                    value="SFEN入力",
                    label="盤面ソース（自己対局SGFを選ぶと下のSGF設定を使用）",
                )
                with gr.Accordion("自己対局SGF 設定（C++ build + conf が必要）", open=False):
                    tsume_sgf_path_in = gr.Textbox(
                        label="SGF path",
                        value="shogi_9x9_restnet64_v2/sgf/300.sgf",
                    )
                    tsume_conf_path_in = gr.Textbox(
                        label="Config path (.cfg)",
                        value="shogi_9x9_restnet64_v2/shogi_9x9_restnet64_v2.cfg",
                    )
                    with gr.Row():
                        tsume_game_idx_in = gr.Number(
                            label="Game index", value=0, precision=0)
                        tsume_move_idx_in = gr.Number(
                            label="Move index（その手を指す前の局面）", value=40, precision=0)
                    gr.Markdown(
                        "※ 300.sgf は多数の自己対局を含む集合ファイル。"
                        "Game index は 0〜(局数-1)、範囲外は自動で丸められます。"
                    )
                    gr.Markdown(
                        "自己対局SGFでは、その手数で**実際に指された手**を「正解手」として"
                        "Attention/IG に使います（SFEN欄は無視）。"
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
                tsume_subunif_in = gr.Checkbox(
                    value=False,
                    label="一様分布を引く（自己注意を除外し 1/N を基準に強調・非論文）",
                )
                tsume_attn_out = gr.Image(label="Attention Map（論文スタイル）", type="pil")
                gr.Markdown("**Attention Rollout** — 全レイヤー累積参照パターン")
                tsume_rollout_out = gr.Image(label="Attention Rollout", type="pil")
                gr.Markdown("**Integrated Gradients** — この局面に対する属性（赤=出力を上げる寄与）")
                tsume_ig_target_in = gr.Radio(
                    choices=["指定した正解手", "モデルの最善手"],
                    value="指定した正解手",
                    label="IG — Policy の説明対象",
                )
                with gr.Row():
                    tsume_ig_value_out  = gr.Image(label="IG — Value（勝率）", type="pil")
                    tsume_ig_policy_out = gr.Image(label="IG — Policy（正解手）", type="pil")
                gr.Markdown("**Occlusion / Perturbation** — 各マスを隠して出力変化を測定（赤=重要マス）")
                with gr.Row():
                    tsume_occ_value_out  = gr.Image(label="Occlusion — Value", type="pil")
                    tsume_occ_policy_out = gr.Image(label="Occlusion — Policy", type="pil")
                gr.Markdown(
                    "**持ち駒寄与（試作）** — 持ち駒は盤面全体に一様展開されAttentionでは局在化"
                    "できないため、持ち駒チャネルを除去して出力変化をスカラーで測定（駒種別・"
                    "先後別）。※持ち駒の寄与の扱いは本体論文で検討予定の暫定手法。")
                tsume_hand_out = gr.Image(label="持ち駒寄与（Value / Policy）", type="pil")

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

        def _run_tsume(model_path, sfen, usi_move, use_gpu, layer_idx, head_idx,
                       subtract_uniform, ig_policy_target,
                       board_source, sgf_path, conf_path, game_idx, move_idx):
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
            from tsume_shogi import sfen_to_tensor, _usi_sq_to_py, usi_to_action_id

            model_path = model_path.strip()
            if not model_path or not os.path.isfile(model_path):
                raise gr.Error(f"Model not found: {model_path}")

            device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"

            if board_source == "自己対局SGF":
                # ── self-play position loaded from an SGF via the C++ env ──────────
                from xai_analysis import _parse_sgf_game, sgf_file_stats
                from shogi_coords import action_id_to_usi
                sgf_path  = (sgf_path or "").strip()
                conf_path = (conf_path or "").strip()
                if not sgf_path or not os.path.isfile(sgf_path):
                    raise gr.Error(f"SGF not found: {sgf_path}")
                if not conf_path or not os.path.isfile(conf_path):
                    raise gr.Error("自己対局SGFの読み込みには conf(.cfg) が必要です。")
                # clamp indices into valid ranges (file may hold many games)
                stats  = sgf_file_stats(sgf_path)
                ng     = stats["num_games"]
                gi_req = int(game_idx)
                gi     = max(0, min(gi_req, ng - 1))
                tot_g  = stats["move_counts"][gi] if gi < len(stats["move_counts"]) else 0
                mi_req = int(move_idx)
                mi     = max(0, min(mi_req, max(0, tot_g - 1)))
                clamp_note = []
                if gi != gi_req:
                    clamp_note.append(f"game {gi_req}→{gi} (0–{ng-1})")
                if mi != mi_req:
                    clamp_note.append(f"move {mi_req}→{mi} (0–{tot_g-1})")
                try:
                    board_state, board_info = load_board_from_sgf(
                        sgf_path, conf_path, "shogi",
                        game_idx=gi, move_idx=mi, device=device,
                    )
                except Exception as e:
                    raise gr.Error(f"Failed to load SGF board: {e}")
                # actual self-play move played at this ply (the "answer" move)
                moves, total = _parse_sgf_game(sgf_path, gi)
                if 0 <= mi < total:
                    player_char, action_id = moves[mi]
                    is_black = (player_char == "B")
                    try:
                        usi_move = action_id_to_usi(action_id, is_black)
                    except Exception as e:
                        usi_move = ""
                        log_note = f"(move decode failed: {e})"
                    else:
                        log_note = ""
                else:
                    is_black, usi_move, log_note = True, "", "(no move at this ply)"
                sfen = f"[SGF {os.path.basename(sgf_path)} game {gi} move {mi}/{total}]"
                log = [f"Device: {device}", f"Board: {sfen} (of {ng} games)",
                       f"Self-play move: {usi_move} {log_note}"]
                if clamp_note:
                    log.append("clamped: " + ", ".join(clamp_note))
            else:
                # ── SFEN input path (tsume / manual) ──────────────────────────────
                sfen     = sfen.strip()
                usi_move = usi_move.strip()
                if not sfen:
                    raise gr.Error("SFENを入力してください。")
                if not usi_move:
                    raise gr.Error("正解の一手（USI）を入力してください。")
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
                        subtract_uniform=subtract_uniform,
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

            # ── Integrated Gradients on the SFEN board ───────────────────────────
            # Explain the network output for THIS position. Value = win-prob;
            # policy = the specified correct move (converted to its action_id).
            ig_value_img = None
            ig_policy_img = None
            try:
                attr_v, _ = integrated_gradients(
                    py_model, board_state, target="value",
                    steps=50, device=device,
                )
                log.append(f"IG-value : range [{attr_v.min():.4f}, {attr_v.max():.4f}]")
                ig_value_img = _fig_to_pil(visualize_ig(
                    attr_v, title="IG — Value attribution",
                    board_state=board_state,
                ))

                # policy target: the specified correct move, or the model's own top move
                if ig_policy_target == "モデルの最善手":
                    action_idx = None   # integrated_gradients() uses policy.argmax
                    log.append("IG-policy: explaining the model's top move (argmax)")
                else:
                    try:
                        action_idx = usi_to_action_id(usi_move, is_black)
                    except Exception as e:
                        action_idx = None
                        log.append(f"IG-policy: could not convert '{usi_move}' → action_id ({e}); "
                                   "explaining the model's top move instead")
                attr_p, action = integrated_gradients(
                    py_model, board_state, target="policy",
                    action_idx=action_idx, steps=50, device=device,
                )
                # Decode the explained action into its move (from/to squares + USI)
                # so the IG figure shows WHICH move it explains.
                from shogi_coords import action_id_to_usi as _aid2usi
                mv_from = mv_to = None
                mv_usi = "?"
                try:
                    mv_usi = _aid2usi(int(action), is_black)
                    if "*" in mv_usi:                       # drop: destination only
                        d = _usi_sq_to_py(mv_usi[2], mv_usi[3], is_black)
                        mv_to = (d // 9, d % 9)
                    else:                                   # board move: from → to
                        s = _usi_sq_to_py(mv_usi[0], mv_usi[1], is_black)
                        d = _usi_sq_to_py(mv_usi[2], mv_usi[3], is_black)
                        mv_from, mv_to = (s // 9, s % 9), (d // 9, d % 9)
                except Exception as e:
                    log.append(f"IG-policy: could not decode action {action} ({e})")
                kind = "最善手" if ig_policy_target == "モデルの最善手" else "指定手"
                log.append(f"IG-policy: {kind}={mv_usi} (action={action}), "
                           f"range [{attr_p.min():.4f}, {attr_p.max():.4f}]")
                ig_policy_img = _fig_to_pil(visualize_ig(
                    attr_p, title=f"IG — Policy: {kind} {mv_usi}  (action {action})",
                    board_state=board_state,
                    mark_from=mv_from, mark_to=mv_to,
                ))
                ig_action_idx = action_idx   # reuse for occlusion policy target
            except Exception as e:
                log.append(f"IG failed: {e}")
                ig_action_idx = None

            # ── Occlusion / Perturbation on the same board ───────────────────────
            # Mask each square and measure the output change (Zeiler & Fergus 2014).
            occ_value_img = None
            occ_policy_img = None
            try:
                attr_ov, _ = occlusion(py_model, board_state, target="value", device=device)
                log.append(f"Occ-value: range [{attr_ov.min():.4f}, {attr_ov.max():.4f}]")
                occ_value_img = _fig_to_pil(visualize_perturbation(
                    attr_ov, title="Occlusion — Value sensitivity",
                    board_state=board_state,
                ))
                attr_op, occ_action = occlusion(
                    py_model, board_state, target="policy",
                    action_idx=ig_action_idx, device=device,
                )
                log.append(f"Occ-policy: action={occ_action}, "
                           f"range [{attr_op.min():.4f}, {attr_op.max():.4f}]")
                occ_policy_img = _fig_to_pil(visualize_perturbation(
                    attr_op, title=f"Occlusion — Policy sensitivity (action {occ_action})",
                    board_state=board_state,
                ))
            except Exception as e:
                log.append(f"Occlusion failed: {e}")

            # ── Hand-piece contribution (non-spatial; see paper limitation) ──────
            hand_img = None
            try:
                vo, ve, _ = hand_piece_contribution(py_model, board_state,
                                                    target="value", device=device)
                po, pe, hact = hand_piece_contribution(
                    py_model, board_state, target="policy",
                    action_idx=ig_action_idx, device=device)
                pol_lbl = f"(action {hact})"
                hand_img = _fig_to_pil(visualize_hand_contribution(
                    vo, ve, po, pe, pol_label=pol_lbl))
                log.append(f"Hand-contrib: value own max={float(vo.max()):+.4f}, "
                           f"enemy max={float(ve.max()):+.4f}")
            except Exception as e:
                log.append(f"Hand contribution failed: {e}")

            bs_cpu = board_state.cpu()
            return (attn_img, rollout_img, ig_value_img, ig_policy_img,
                    occ_value_img, occ_policy_img, hand_img,
                    raw_heads, dots_table, bs_cpu, src_sq,
                    "\n".join(log))

        tsume_run_btn.click(
            fn=_run_tsume,
            inputs=[tsume_model_in, tsume_sfen_in, tsume_move_in,
                    tsume_gpu_in, tsume_layer_sl, tsume_head_sl, tsume_subunif_in,
                    tsume_ig_target_in,
                    tsume_board_source_in, tsume_sgf_path_in, tsume_conf_path_in,
                    tsume_game_idx_in, tsume_move_idx_in],
            outputs=[tsume_attn_out, tsume_rollout_out,
                     tsume_ig_value_out, tsume_ig_policy_out,
                     tsume_occ_value_out, tsume_occ_policy_out, tsume_hand_out,
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
        def _update_attn_head(raw_heads, dots_table, board_state, src_sq, layer_idx, head_idx,
                              subtract_uniform):
            if raw_heads is None or src_sq is None:
                return gr.update(), gr.update()
            num_layers = len(raw_heads)
            num_heads  = raw_heads[0].shape[0]
            li = max(0, min(int(layer_idx) - 1, num_layers - 1))
            hi = max(0, min(int(head_idx)  - 1, num_heads  - 1))
            bs = board_state if board_state is not None else None

            attn_img = _fig_to_pil(
                visualize_single_head(raw_heads, src_sq, layer_idx=li, head_idx=hi,
                                      board_state=bs, subtract_uniform=subtract_uniform)
            )

            pre_img = None
            if dots_table:
                pre_img = _fig_to_pil(
                    visualize_pre_softmax_single_head(
                        dots_table, src_sq, layer_idx=li, head_idx=hi, board_state=bs
                    )
                )

            return attn_img, pre_img

        for _sl in [tsume_layer_sl, tsume_head_sl, tsume_subunif_in]:
            _sl.change(
                fn=_update_attn_head,
                inputs=[_tsume_raw_heads_state, _tsume_dots_state,
                        _tsume_board_state_st, _tsume_src_sq_state,
                        tsume_layer_sl, tsume_head_sl, tsume_subunif_in],
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
                value="shogi_9x9_restnet64_v2/model/weight_iter_60000.pt",
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
