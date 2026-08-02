# MiniZero 将棋の入力特徴量（362チャンネル）とIGの出力の意味

正典は C++ の `ShogiEnv::getFeatures`
（`minizero/minizero/environment/shogi/shogi.cpp`）。
`getNumInputChannels()` は **362** を返す。

## 全体構成

**総数 = 8履歴ステップ × 45チャンネル/ステップ + グローバル2 = 362**
各チャンネルは 9×9 の面（board_area = 81）。

```
362 = T(8) × channels_per_step(45) + 2
```

## 1ステップ = 45チャンネルの内訳

| 範囲(ステップ内) | 数 | 内容 | 値 | 敷き方 |
| --- | --- | --- | --- | --- |
| 0–13   | 14 | 自分の盤上駒（駒種ごと1面） | 該当マス=1 | マス単位 |
| 14–27  | 14 | 相手の盤上駒               | 該当マス=1 | マス単位 |
| 28–30  | 3  | 千日手カウント (rep=1,2,3) | 全マス=1（該当時） | **盤面全体** |
| 31–37  | 7  | 自分の持ち駒               | 全マス=枚数 | **盤面全体** |
| 38–44  | 7  | 相手の持ち駒               | 全マス=枚数 | **盤面全体** |

小計: 28 + 3 + 7 + 7 = **45**

### 盤上駒 14種の順（`raw_kind` を詰めたもの）

```
P, L, N, S, G, B, R, K, +P, +L, +N, +S, +B, +R
歩 香 桂 銀 金 角 飛 玉 と  成香 成桂 成銀 馬  龍
```
- C++の `raw_kind`（`piece.index() & 0x0f`）を、成角(+B)/成飛(+R)のインデックスを1詰めて 0–13 にマップ。
- `side_offset`: 自分=0、相手=+14。`is_us = (piece.isBlack() == us_black)`。

### 持ち駒 7種の順（`py_hand_mapping`）

```
P, L, N, S, B, R, G   （歩 香 桂 銀 角 飛 金。※金が最後）
Sunfish ID: P=0,L=1,N=2,S=3,G=4,B=5,R=6 → 並べ替え {0,1,2,3,5,6,4}
```
- 自分の持ち駒: ch 31–37、相手: ch 38–44。値は**枚数**を全マスに敷く。

## 履歴とグローバル

- 45チャンネルを **T=8ステップ分**（現在 t=0 〜 7手前）並べる → 8×45 = **360**。
  - `history_index = board_history_.size() - 1 - t`。履歴不足の古いステップは全ゼロ。
- **ch 360**: 手番（先手番なら全マス=1.0、`turn_ == kPlayer1`）
- **ch 361**: 手数 `actions_.size() / 512`（全マス同値）

合計 360 + 2 = **362**。

## 座標の向き（重要）

- 後手番（`is_white_turn`）のとき `r = 8 - r; f = 8 - f` で**盤を180度回転**し、
  常に「自分から見た向き」に正規化する。
- `f = file - 1` として Python 側（1筋 = index0）と一致させている
  （`convertAZ` 整合のためのコメント修正あり）。

## 「盤面全体に敷き詰める」チャンネル（XAI上の注意）

以下は特定マスではなく**全81マスに同じ値**を書き込む（C++ は `std::fill`）:

- 千日手 (28–30)、持ち駒 (31–44) … 各ステップ内で 17面
- 手番 (360)、手数 (361)

**IGへの影響**: IG は `spatial_ig = ig[:360]` を空間方向に合計するため
（除外は 360・361 のみ）、**千日手・持ち駒チャンネルを含む**。
持ち駒は全マスに乗っているので、**駒の無い空マスにも IG 属性が出る**。
これは設計ミスではなく、持ち駒が盤面全体ブロードキャスト特徴であることの帰結。

- 盤上の駒の寄与だけを純粋に見たい場合 → **ch 0–27 だけを合計**し、28–44 を除外する。
- 持ち駒の寄与を知りたい場合 → 別途バー等で示す方が正確。

## Python版（`tsume_shogi.py` / `sfen_to_tensor`）との差

- **t=0（現在局面）のみ**を埋め、履歴ステップ 1〜7 と千日手(28–30)は 0 のままの簡易版
  （単一SFENには履歴が無いため）。
- チャンネル割り当て自体は C++ と一致させてある。

## IG（Integrated Gradients）が説明する「出力」とは

IG は「入力のどの要素が、ある**スカラー出力**に寄与したか」を測る
（baseline = 空盤、`IG = 入力 × 平均勾配`）。出力は2種類:

### IG — Value（勝率）
- 出力 = **value ヘッドのスカラー**（手番側から見た勝率/期待勝敗、概ね [-1, 1]）。

### IG — Policy
- 出力 = **policy ヘッドが、指定した action_id に割り当てるスコア/確率**。
- コード: `scalar = out["policy"][:, action_idx].sum()`。

**重要な注意（誤解しやすい点）**:
xai_app の詰将棋タブでは、`action_idx` に
「ユーザーが入力した**正解手**（USI → `usi_to_action_id`）」を渡している。
これは **モデルが実際に選ぶ手ではない**。

- 例: 「藤井-羽生2018 118手目」局面で、こちらが提示した正解手は
  **4七桂打（N*4g, action 221）**だが、**モデルが実際に最善と評価する手は別**
  （例: 2二と → 1二歩 のような手）。
- したがって `IG — Policy (action 221)` は
  「**もしこの指定手を選ぶとしたら**、どの入力が寄与するか」を説明しているのであって、
  「モデルが実際に選んだ手の理由」ではない。
- モデル自身の選択手を説明したい場合は、`action_idx = None`
  （`integrated_gradients` 内で `policy.argmax` を採用）にすればよい。

## 計算式の所在（コード上の位置）

### IG（Integrated Gradients）の計算式

関数: `xai_analysis.py:integrated_gradients`（165–229行）

正式な定義:

```
IG_i = (x_i - x'_i) × ∫₀¹ ∂F(x' + α(x - x')) / ∂x_i dα
```

を α を steps+1 点で離散化して近似する。x' = 空盤（baseline）。

| 数式 | コード | 行 |
| --- | --- | --- |
| baseline = 空盤（全ゼロ） | `baseline = torch.zeros_like(board_state)` | 192 |
| 補間 x' + α(x-x') | `interp = baseline + alphas.view(-1,1,1,1) * delta` | 198 |
| 出力スカラー F | `out["value"].sum()` / `out["policy"][:, action_idx].sum()` | 205, 211 |
| 勾配 ∂F/∂x | `scalar.backward()` → `grads = interp.grad` | 214–215 |
| リーマン和 (1/S)Σ∇ | `avg_grads = grads.mean(dim=0, keepdim=True)` | 218 |
| IG = (x-x') × 平均∇ | `ig = (delta * avg_grads).squeeze(0)` | 221 |
| 盤面方向に合計 (ch0–359) | `attribution = ig[:360].sum(dim=0)` | 226–227 |

（`ig[:360]` は千日手・持ち駒チャンネルを含む。手番360・手数361のみ除外。
 → 前述の「空マスにも属性が出る」理由。）

### Attention Map の計算式

- **Attention 本体** `A = softmax(QK^T/√d + bias)` はモデル内部
  （Transformerブロックの forward）で計算される。
- その中間出力を取り出すのが `xai_analysis.py:get_pre_softmax_data`（750行〜）:
  - `att_table` … softmax 後の Attention 行列
  - `dots_table` … softmax 前の QK^T ロジット
- **可視化用の正規化式** は `xai_analysis.py:visualize_single_head`（598行〜）:

| 内容 | コード | 行 |
| --- | --- | --- |
| クエリ行の抽出 A[q,:] | `attn = raw_heads[layer_idx][head_idx, token_idx]` | 631 |
| クエリマス index | `token_idx = r*9 + c` | 629 |
| 論文準拠 min-max: (A-min)/(max-min) | `attn = (attn - lo) / (hi - lo)` | 647–653 |
| 一様分布オプション: max(0, A-1/N)/peak（自己注意除外） | `above = max(0, attn - 1/N); attn = above/peak` | 638–645 |

- softmax 前ロジット QK^T/√d の可視化: `visualize_pre_softmax_single_head`（812行〜）。

---

参照: `xai_analysis.py:integrated_gradients` / `visualize_single_head` /
`get_pre_softmax_data` / `visualize_pre_softmax_single_head`、
`tsume_shogi.py:sfen_to_tensor` / `usi_to_action_id`、
`minizero/minizero/environment/shogi/shogi.cpp:getFeatures`。
