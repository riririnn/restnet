# Attention Map — 均等分散問題の分析と改善計画

（旧 `docs/attention_map_analysis.md` + `docs/attention_map_improvement_plan.md` を統合。2026-07-07）

## 1. 観察された問題と結論（要約）

全レイヤー・ヘッド（2層×4ヘッド）でAttention重みがほぼ均等（≈1/81=0.012、最大でも1.4倍未満）。

**結論**:
- GUIの実装は正しい（`get_attn_table()` → 本物のsoftmax後Attention重み）
- 原因はモデル側：Q・K内積が小さすぎる + relative_bias未学習
- ただし「完全な均等」はmin-max正規化の誇張で、均等値基準の正規化に修正後は
  **ヘッドごとに異なる空間パターンが確認できた**（L2H1は玉の位置に注目）

```
Q·K内積:        std ≈ 0.071 × scaling 0.125 = 0.009
→ softmax後:    ≈ 1/81 = 0.012（ほぼ均等）
relative_bias:  L1 std=0.0001, L2 std=0.00003（ゼロ初期化のままほぼ未学習）
projq/projk:    重み平均絶対値 0.0153（小さい）
```

---

## 2. Attention Map とは何か

```
Q = W_q · x        # Query: 「何を探しているか」
K = W_k · x        # Key:   「何を持っているか」
V = W_v · x        # Value: 「実際に渡す情報」

attention_logit[i,j]  = (Q[i] · K[j]) * scaling + relative_bias[i,j]
attention_weight[i,j] = softmax_j(attention_logit[i,:])
output[i] = Σ_j attention_weight[i,j] * V[j]
```

`attention_weight[i,j]` を可視化している。
**「どの手を指すか」とは直接関係しない**。「マスiの表現を作るためにマスjをどれだけ参照したか」。

---

## 3. なぜ均等分散になるか（原因4つ）

### 原因A：訓練ステップ不足
AlphaZero学習の初期は方策・価値の学習が優先され、Q・K射影とrelative_biasの勾配は小さい。
→ iterが進めば改善する可能性。

### 原因B：Residual接続によるバイパス（"Lazy Attention"）
`output = x + MSA(LN(x))` の残差xが支配的なため、Attentionが均等（≈mean(V)）でも
損失は下がり、Attentionに学習圧力がかからない。

### 原因C：将棋タスクに空間集中Attentionが不要な可能性
Conv（R-block）が局所パターンを既に捉えており、T-blockは「大局の均等集約」で十分かもしれない。
この場合、均等分散はバグではなく設計通りの動作。均等分散のAttentionは
Global Average Poolingとして機能する（`output[i] ≈ mean(V)`）。

### 原因D：Softmaxの温度が高い
`scaling = 1/sqrt(d_head) = 0.125`（emb 256 / 4ヘッド → d_head=64）。
標準値だが、訓練済みモデルでは事後変更不可。

---

## 4. 対策一覧と実装状況

| 優先度 | 対策 | 状態 | コスト |
|--------|------|------|--------|
| ★★★ | Pre-softmax logit可視化（60倍のコントラスト） | ✅ **実装済み**（フォワードフック方式、モデル変更なし） | — |
| ★★★ | Relative Position Bias可視化 | ✅ **実装済み**（GUIセクション③） | — |
| ★★★ | 均等値基準の正規化への修正 | ✅ **実装済み** | — |
| ★★☆ | より進んだ訓練モデルで確認 | 学習再開待ち | 低 |
| ★☆☆ | relative_bias初期値を `randn*0.02` に変更 | 未実施 | **再学習必要** |
| ★☆☆ | Attention Entropy正則化（λ≈0.01） | 未実施 | 再学習必要 |
| ★☆☆ | T-block数の増加（2個→3〜4個） | 未実施 | 設計変更+再学習 |

### relative_bias初期値変更（再学習時に適用）

```python
# block_unit.py — 現在
self.relative_bias_table = nn.Parameter(torch.zeros(...))
# 変更後
self.relative_bias_table = nn.Parameter(torch.randn(...) * 0.02)
```

将棋は方向非対称（歩は前のみ等）なので、位置バイアスの重要性は囲碁より高い。
ゼロ初期化で学習されない現状は将棋で特に損失が大きい。

---

## 5. 実装済み可視化の仕組み

### Pre-softmax logit（xai_analysis.py `get_pre_softmax_data`）
モデルコードを変更せず、各Tブロックの `attend`（nn.Softmax）にフォワードフックを仕掛け、
softmax前の `dots`（Q・K内積+relative_bias）を横取りする。
値域 ±0.3 程度で、softmax後（幅0.008）の約60倍の情報量。

### Relative Position Bias（xai_analysis.py `get_relative_bias_maps`）
`relative_bias_table` パラメータを直接読み、`relative_index` で (N,N) に展開。
クエリ位置を指定して9×9盤面に表示（赤=正バイアス、青=負バイアス）。
学習前はほぼ全面白（ゼロ付近）。

---

## 6. 終盤局面での実測結果

SFEN `k8/1p7/KP7/9/9/9/9/9/9 b RBGSLNrb2g2s2l2n3p 1`、手 `R*9b`、クエリ9b。

均等値基準の正規化で全ヘッドを比較した結果、各ヘッドが異なる空間パターンを示した：

| ヘッド | 注目領域 | 解釈 |
|--------|---------|------|
| L1H1 | 9筋・中央左 | 玉の縦ライン |
| L1H2〜H4 | 右上・右隅・左下 | 各方面の状況 |
| **L2H1** | **9筋（玉のいる列）** | **玉の位置を強く意識** |
| L2H2〜H4 | 左中段・中央右・右端 | 各方面 |

絶対値は小さい（均等値の約1.4倍）ため論文ほど鮮明ではないが、
これは訓練量の限界と考えられ、学習進行+カリキュラム導入で改善を見込む。

---

## 7. アーキテクチャのハイパーパラメータ

### CFGから操作できるもの

| CFGキー | 説明 | 現在値 |
|---------|------|--------|
| `nn_num_hidden_channels` | 埋め込み次元（emb_size） | 256 |
| `nn_num_blocks` | ブロック数 | 1 |
| `nn_embed_kernel_size` | 埋め込みConvカーネル | 3 |
| `nn_blocks_type` | ブロック構成 | R_R_T_R_R_T |
| `nn_policy_type` / `nn_value_type` | ヘッド種類 | P / TV |

### CFGから操作できない（ハードコード）

| パラメータ | 場所 | 現在値 | 推奨値 |
|-----------|------|--------|--------|
| `num_head` | `alphazero_network.py` L43 | 4 | 4〜8 |
| `mlp_ratio` | `alphazero_network.py` L44 | 2 | 2〜4 |
| `drop` / `MLP_drop`（Dropout） | `alphazero_network.py` L69-75 | 0.0 | 0.1（iter100以降） |
| `relative_bias_table` 初期化 | `block_unit.py` L111-116 | zeros | randn×0.02 |

→ CFG制御可能にするには `RRTRRT.cfg` / `train.py` / `create_network.py` /
`alphazero_network.py` の4ファイル修正が必要（未実施）。

### 用語メモ

- **mlp_ratio**: TransformerブロックのMLP拡大倍率（256→512→256、GPT標準は4）
- **Dropout**: 学習中にランダムにニューロンを無効化する正則化。現在0.0（無効）。
  同じデータを繰り返し学習する段階（iter100以降）で0.1程度が有効。要再学習。

### 囲碁・Hexと将棋の違い（元論文との差異）

| 特性 | 囲碁・Hex | 将棋 |
|------|-----------|------|
| 駒の流れ | 置くだけ（増える） | 動く・取る・**打つ** |
| 方向性 | 対称 | **前後非対称** |
| 入力チャンネル | 少ない | **362** |
| 行動空間 | 361+パス | **〜5000以上** |
| ゲーム長 | 40〜80手 | 平均428手（引き分け悪循環、[curriculum_training.md](curriculum_training.md)参照） |

---

## 関連ドキュメント

- カリキュラム設計・引き分け悪循環: [curriculum_training.md](curriculum_training.md)
- XAI手法と学習構造の解説: [xai_guide.md](xai_guide.md)
