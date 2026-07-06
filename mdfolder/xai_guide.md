# ResTNet Shogi — 学習の仕組みと XAI 可視化ガイド

このドキュメントは2部構成です。

1. **学習の階層構造** — MCTS シミュレーション / トレーニングステップ / イテレーション / 重みファイルの関係
2. **XAI 各手法の可視化方法** — GUI に表示される各図が「何を」「どう」表しているか

---

## 第1部 — 学習の階層構造

AlphaZero 系の学習には **3つの異なるレイヤー** があり、混同しやすい。
特に MCTS の4ステップ（selection → expansion → evaluation → backpropagation）と
学習側の「イテレーション / トレーニングステップ」は **別物** である。

### レイヤー1: MCTS シミュレーション
- selection → expansion → evaluation → backpropagation の1サイクル = **1シミュレーション**。
- **1手を決める**ための木探索。`n50` などのシミュレーション回数で深さが決まる。
- **対局時の思考**であり、ニューラルネット（NN）の重みは変化しない。
- MCTS の "backpropagation" は木のノードに価値を伝播するだけで、
  NN の誤差逆伝播（学習の backward）とは無関係。

### レイヤー2: トレーニングステップ (training step)
- **NN の重みを1回更新すること**（通常の深層学習の1ミニバッチ分の勾配降下）。
- 処理: リプレイバッファからミニバッチ取得 → forward → loss 計算
  （policy loss + value loss）→ `backward()` → `optimizer.step()` → 重み更新。
- 実装: [restnet/learner/train.py:305-418](../restnet/learner/train.py)
- 1ステップごとに `model.training_step += 1`。**重みが変わる。**

### レイヤー3: イテレーション
- **「自己対局 → 学習 → 保存」の大きな1周**。
- 構成:
  1. 自己対局を `zero_num_games_per_iteration`（例 2000）局実行 → 学習データ生成（レイヤー1を多数回）
  2. そのデータで `learner_training_step`（例 200）回 重みを更新（レイヤー2）
  3. モデルを `weight_iter_N.pt` として保存

### 包含関係まとめ

```
イテレーション (自己対局+学習の1周)
 ├─ ① 自己対局 2000局
 │     └─ 各手: MCTS を 50シミュレーション
 │           └─ 1シミュレーション = selection→expansion→evaluation→backprop
 └─ ② 200 トレーニングステップ
       └─ 1ステップ = 1ミニバッチで NN の重みを1回更新
```

| 用語 | 何の回数か | 重みは変わる？ |
|---|---|---|
| MCTSシミュレーション（4ステップ） | 1手を考える木探索 | 変わらない |
| トレーニングステップ | NN の重み更新 | **変わる** |
| イテレーション | 自己対局+学習の1周（=200トレステップ） | 変わる |

### 重みファイル `weight_iter_N`
学習中に保存される NN のスナップショット。保存は [train.py:218](../restnet/learner/train.py) `save_model`。

- **`.pt`** — `torch.jit.script` でシリアライズした **TorchScript** モデル。
  推論にそのまま使える。**XAI の IG / Perturbation はこれを使用。**
- **`.pkl`** — `training_step` / 重み / optimizer / scheduler を含む**学習再開用**スナップショット。

`N` = 累積 `training_step`。`learner_training_step=200`
（[configs/9x9_shogi/RRTRRT.cfg:49](../configs/9x9_shogi/RRTRRT.cfg)）なので、
1イテレーションごとに +200 → ファイル名が **200刻み**になる。

| イテレーション | training_step | ファイル名 |
|---|---|---|
| 1 | 200 | `weight_iter_200.pt` |
| 2 | 400 | `weight_iter_400.pt` |
| 3 | 600 | `weight_iter_600.pt` |

※ Go の大規模モデルでは設定が異なり `weight_iter_150000.pt` のように刻みが大きい。

### ディレクトリ名の意味（例 `shogi_9x9_gaz_2R1T2R1T_P_TV_n50`）
- `shogi_9x9` — ゲーム種別
- `gaz` — Gumbel AlphaZero
- `2R1T2R1T` — ブロック構成（R=Residual, T=Transformer ブロックの並び = `blocks_type`）
- `P` — Policy ヘッド種別
- `TV` — Value ヘッド種別（Transformer Value）
- `n50` — シミュレーション数

---

## 第2部 — XAI 各手法の可視化方法

実装は [xai_analysis.py](../xai_analysis.py)、Web GUI は [xai_app.py](../xai_app.py)（Gradio, http://localhost:7860）。

### GUI コントロール
| 入力 | 意味 |
|---|---|
| **Model path** | `weight_iter_N.pt`（TorchScript モデル） |
| **Target** | `value` / `policy` / `both` / `rollout` |
| **IG Steps** | IG の積分（リーマン和）刻み数。20=高速・粗い、300=論文品質 |
| **Source square** | rollout の起点マス `row,col`（0-8、例 `4,4`=中央） |

### 共通の表現ルール
- 盤面はすべて **9×9 ヒートマップ**。軸ラベルは将棋座標（列 9→1、段 a→i）。
- **2系統のカラースキーム**:
  - **発散 (`RdBu_r`, 赤青)** … 値に符号がある手法（IG / Perturbation）。
    赤=正の寄与、青=負の寄与。0中心の対称スケール（`vmin=-vmax, vmax=vmax`）。
  - **連続 (`hot`)** … 非負の重みの手法（Attention Rollout）。明=大、暗=小。

---

### 手法1: Integrated Gradients (IG)
**実装:** [xai_analysis.py:104](../xai_analysis.py) / 可視化 `visualize_ig` [:252](../xai_analysis.py)

- **何を表すか:** 各マスがモデル出力（value=勝率 / policy=指し手確率）に
  どれだけ寄与したか。
- **計算:** 空の盤面（ベースライン）→ 実局面まで `steps` 個に補間 →
  各中間盤面で勾配を測りリーマン和で平均 → `(入力 − ベースライン)` を掛ける →
  362チャンネルを合計して (9×9) マップに。
- **可視化:** `RdBu_r` ヒートマップ。
  - **赤** = そのマスが出力を押し上げた（正の寄与）
  - **青** = 押し下げた（負の寄与）
  - 色の濃さ = 影響の大きさ
- **出力:** `ig_value.png` / `ig_policy.png`（policy はタイトルに説明対象 `action N`）

### 手法2: Attention Rollout
**実装:** [xai_analysis.py:172](../xai_analysis.py) / 可視化 `visualize_rollout` [:274](../xai_analysis.py), `visualize_per_head` [:319](../xai_analysis.py)

- **何を表すか:** Transformer 全層を通したアテンションの伝播。
  「モデルが盤面のどこを見ているか」。
- **計算:** 各層のアテンションを `get_attn_table` で取得
  （[alphazero_network.py:175](../restnet/learner/network/alphazero_network.py)）→
  ヘッドを融合（mean/max）→ 残差接続のため単位行列を加えて行正規化 →
  層ごとの行列を連鎖的に掛け合わせ (81×81) のロールアウトを得る。
- **可視化（3種、すべて `hot`）:**
  1. **平均受信アテンション** (`rollout_avg.png`): 列方向に平均し各マスが
     平均どれだけ注目を集めたか。Source square 空欄でこれだけ表示。
  2. **ソース別** (`rollout_rXcY.png`): 指定マスの行を取り出し、そのマスが
     どこに注目しているか。起点を**シアン枠**で強調。
  3. **ヘッド別** (`per_head_rXcY.png`): 融合前の生アテンションを
     層（行）× ヘッド（列）のグリッドで表示。各ヘッドの着目点の違いがわかる。

### 手法3: Perturbation / Occlusion
**実装:** [xai_analysis.py:367](../xai_analysis.py) / 可視化 `visualize_perturbation` [:423](../xai_analysis.py)
※ **CLI のみ**（GUI の Target ドロップダウンには未追加）

- **何を表すか:** 各マスを直接消したときの出力変化による重要度（勾配を使わない介入法）。
- **計算:** 81マスそれぞれについて、その位置の全チャンネルを 0 にして
  モデルを再実行 → `元 − マスク後` でスコア化。
- **可視化:** `RdBu_r` ヒートマップ。
  - **赤** = そのマスを消すと出力が下がる（= 重要なマス）
  - **青** = 消すと出力が上がる（出力に逆らっていたマス）
- **出力:** `perturb_value.png` / `perturb_policy.png`

---

## 注意点
- 現状 GUI は **ランダムなダミー盤面** (`dummy_board_state`,
  [xai_app.py:97](../xai_app.py)) を使用。実局面の解釈にするには
  `.sgf` ローダー（`load_board_from_sgf`, [xai_analysis.py:456](../xai_analysis.py)）の接続が必要。
- **Perturbation/Occlusion は GUI 未対応**。CLI（`--target perturbation`）でのみ利用可。
- IG / Perturbation は TorchScript (`.pt`)、Attention Rollout は
  再構築した Python 版ネットワーク（`get_attn_table` が TorchScript 未エクスポートのため）を使用。

---

## 第3部 — 各手法の説明の仕方（計算方法と考え方）

発表・論文・報告書で説明するときは、毎回
**「何の問いに答えるか → 直感（考え方）→ 計算式 → 図の読み方 → 一言まとめ」**
の流れにすると伝わりやすい。

### 手法1: Integrated Gradients (IG)

**問い:** モデルが「勝てる」「この手を指す」と判断したとき、盤面のどのマスが効いたのか？

**考え方:**
単純な勾配 ∂出力/∂入力（Saliency）は勾配が飽和して 0 になる欠点がある。
IG はそれを避けるため、「空の盤面（ベースライン）から実際の盤面まで、
駒を少しずつ濃くしていったときの勾配を全部足し合わせる」という発想。
ベースラインに空盤（全ゼロ＝情報なし）を使うのは、盤ゲームで
「駒が無い＝情報が無い」という自然な基準だから。

**計算式:**

```
IG_i = (x_i - x'_i) × ∫₀¹ ∂F(x' + α(x - x')) / ∂x_i dα
```

- x = 実局面、x' = ベースライン（空盤）
- 積分は `steps` 個の中間盤面での勾配の平均（リーマン和）で近似
  （[xai_analysis.py:134-160](../xai_analysis.py)）
- 362チャンネル分を合計して (9×9) のマップにする

**図の読み方（赤青 `RdBu_r`）:** 赤=出力を押し上げた、青=押し下げた、濃さ=影響の大きさ。

**一言で:** 「空の盤から駒を足していく過程で、各マスが結論にどれだけ貢献したかを積分で測る」

### 手法2: Attention Rollout

**問い:** Transformer は盤面のどこを「見て」判断しているのか？

**考え方:**
各層のアテンション1つだけ見ても、情報は複数層・残差接続を通って伝わるので不十分。
Rollout は「全層のアテンションを順に掛け合わせて、入力から最終層まで
情報がどう流れたかを追跡する」手法。

**計算式:**

各層 ℓ の融合アテンション（ヘッド平均）に残差項として単位行列を足し、行正規化:

```
A_ℓ = normalize( mean_head(A_ℓ) + I )
Rollout = A_L · A_{L-1} · … · A_1
```

（実装 [xai_analysis.py:206-225](../xai_analysis.py)。I を足すのは残差接続で自分の情報も保持されるため）

**図の読み方（`hot`、3種類）:**
- 平均受信: 各マスが平均どれだけ注目を集めたか
- ソース別: 指定マスがどこを見ているか（起点をシアン枠で強調）
- ヘッド別: 各層×各ヘッドの着目点の違い

**一言で:** 「アテンション行列を層ごとに掛け算して、情報の流れの全体像を1枚に集約する」

> 限界: 残差項 I の影響で対角（自分自身）が支配的になり、図が真っ黒になりやすい。
> 説明時はこの限界も併せて触れると誠実。

### 手法3: Perturbation / Occlusion（現在 CLI のみ）

**問い:** あるマスを消したら、モデルの判断はどれだけ変わるか？

**考え方:**
勾配を一切使わず「実際にマスを隠して出力の変化を測る」という最も直感的な方法（介入実験）。
モデルを箱として扱える（model-agnostic）のが強み。

**計算式:**

```
Attr(r,c) = F(x) - F(x_mask(r,c))
```

81マスそれぞれを 0 にして再実行し、元の出力との差をとる
（[xai_analysis.py:406-418](../xai_analysis.py)）。

**図の読み方（赤青 `RdBu_r`）:** 赤=消すと出力が下がる＝重要なマス、青=消すと上がる＝逆効果だったマス。

**一言で:** 「駒を1つずつ隠して、結論がどれだけ揺らぐかで重要度を測る」

### 3手法の対比（説明の締めに使える表）

| 手法 | 種類 | 勾配 | 出力の符号 | カラー | 一言 |
|---|---|---|---|---|---|
| IG | 勾配ベース | 使う | あり(±) | 赤青 | 寄与を積分で測る |
| Attention Rollout | 構造ベース | 使わない | なし(+) | hot | 注目の流れを追う |
| Perturbation | 介入ベース | 使わない | あり(±) | 赤青 | 隠して影響を測る |

→ 「勾配 / 構造 / 介入 の3つの異なる視点から同じ判断を説明する」とまとめると、
複数手法を併用する根拠になる。

---

## 第4部 — 現在の実装状況

| 項目 | 状態 | 備考 |
|---|---|---|
| Integrated Gradients (value/policy) | ✅ 実装・GUI対応 | [xai_analysis.py:104](../xai_analysis.py) |
| Attention Rollout（平均/ソース別/ヘッド別） | ✅ 実装・GUI対応 | [xai_analysis.py:172](../xai_analysis.py) |
| Perturbation / Occlusion | ⚠️ 実装済みだが **GUI未対応** | CLI `--target perturbation` のみ |
| SHAP / LRP | ❌ 未実装 | コミットメッセージにはあるが実コードなし |
| Web GUI (Gradio) | ✅ 動作可 | http://localhost:7860, [xai_app.py](../xai_app.py) |
| 入力局面 | ⚠️ **ランダムダミー盤面** | `dummy_board_state` [xai_app.py:97](../xai_app.py) |
| `.sgf` 実局面ローダー | ⚠️ コードはあるが **GUI未接続 & 実行不可** | C++ 環境 (`build/`) が未ビルド |
| 駒のオーバーレイ表示 | ❌ 未実装 | どのマスに何の駒があるか分からない |
| rollout の真っ黒問題 | ⚠️ 未対応の表示バグ | 対角優位＋自動スケール |

### 要約
- **動くもの:** IG と Attention Rollout は GUI で可視化できる。Perturbation は CLI で動く。
- **意味のある分析にはまだ不足:**
  ① 入力がランダムダミー（実局面でない）、
  ② 駒情報の重ね描きなし、
  ③ rollout の表示スケール問題、
  ④ `.sgf` 接続には C++ ビルドが必要。