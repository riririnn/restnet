# AttentionMap 改善計画

## 現状の問題

GUIの実装は**正しい**（`get_attn_table()` → T-block の `attn()` → softmax後の本物の attention weight）。
問題はモデル側にある。

```
relative_bias_table 初期値 = zeros（ほぼ学習されていない）
Q・K 内積 std ≈ 0.07 × scaling 0.125 = 0.009
→ softmax 後 ≈ 1/81 = 0.012（均等分散）
```

---

## 優先タスク一覧

### ★★★ 即効・高効果

#### 1. Pre-softmax logit 可視化（実装1〜2時間）
- softmax **前** の Q·K 内積値をそのまま可視化
- softmax 後より **60倍のコントラスト**
- 論文と「同じAttentionの概念」を説明しながら現モデルでも明確なパターンを示せる
- **実装箇所**: `block_unit.py` の `attn()` で `dots` を返す + GUI に切り替えオプション追加

```python
# 現在: softmax後（0.009〜0.017）
attn = self.attend(dots)   # softmax
return x, attn

# 追加: softmax前（-0.23〜+0.29）も返す
return x, attn, dots       # dots = pre-softmax logits
```

#### 2. relative_bias 初期値変更（再学習必要）
- 現在: `torch.zeros(...)` → 学習されにくい
- 変更: `torch.randn(...) * 0.02` → 初期から位置依存性を持つ
- **最もAttentionMap品質に直結する変更**
- **実装箇所**: `block_unit.py` の `__init__()` 内 `relative_bias_table`

```python
# 現在
self.relative_bias_table = nn.Parameter(
    torch.zeros((2 * input_channel_height - 1) * (2 * input_channel_width - 1), num_heads)
)

# 変更後
self.relative_bias_table = nn.Parameter(
    torch.randn((2 * input_channel_height - 1) * (2 * input_channel_width - 1), num_heads) * 0.02
)
```

---

### ★★☆ 中期・中効果

#### 3. Attention Entropy 正則化（再学習必要）
- 学習時の損失に「Attentionのエントロピーを下げる」正則化項を追加
- 集中したAttentionを促す

```python
attn_entropy = -torch.sum(attn * torch.log(attn + 1e-12), dim=-1).mean()
loss = loss_policy + loss_value + λ * attn_entropy   # λ = 0.01
```

#### 4. 学習継続（iter 100〜200）
- Q・K 重みと relative_bias は iter が進むほど洗練される
- iter 100 以降で Attention の集中度が向上する可能性
- 現在 iter 38、ゲーム長が増加トレンド（問題あり）

---

### ★☆☆ 長期・要設計変更

#### 5. T-block 数の増加
- 現在: `R→R→T→R→R→T`（T-block 2個）
- 提案: T-block を 3〜4 個に増やす
- 各ヘッドが異なる役割（局所・大局・攻め・守り）を分担しやすくなる
- アーキテクチャ変更 + 完全再学習が必要

---

## ゲーム長増加問題（並行して調査）

- iter 38 で Avg. Game Lengths = **428**（iter 1 の 278 から増加し続けている）
- Std が 175 → 120 に減少（500手打ち切りが常態化している可能性）
- **考えられる原因**:
  1. `actor_resign_threshold=-0.9` が厳しすぎる
  2. 千日手処理の問題
  3. 入玉将棋化

---

## 推奨アクション順序

1. **今すぐ**: Pre-softmax logit 可視化を実装
2. **再学習時**: `relative_bias_table` 初期値を `randn * 0.02` に変更して再スタート
3. **学習中**: ゲーム長増加の原因調査（SGFファイルを確認）
4. **iter 100 到達後**: AttentionMap の集中度を再確認
5. **必要なら**: Entropy 正則化を追加して再学習

---

## アーキテクチャのハイパーパラメータ詳細

### CFGから操作できるもの（既に対応済み）

| CFGキー | 説明 | 現在値 |
|---------|------|--------|
| `nn_num_hidden_channels` | 埋め込み次元（emb_size） | 256 |
| `nn_num_blocks` | ブロック数 | 1 |
| `nn_embed_kernel_size` | 埋め込みConvカーネルサイズ | 3 |
| `nn_blocks_type` | ブロック構成 | R_R_T_R_R_T |
| `nn_policy_type` | 方策ヘッドの種類 | P |
| `nn_value_type` | 価値ヘッドの種類 | TV |

### CFGから操作**できない**（コードにハードコード）

| パラメータ | 場所 | 現在値 | 推奨値 |
|-----------|------|--------|--------|
| `num_head` | `alphazero_network.py` L43 | 4 | 4〜8 |
| `mlp_ratio` | `alphazero_network.py` L44 | 2 | 2〜4 |
| `drop`（Attention Dropout） | `alphazero_network.py` L69-75 | 0.0 | 0.1（iter100以降） |
| `MLP_drop`（MLP Dropout） | `alphazero_network.py` L69-75 | 0.0 | 0.1（iter100以降） |
| `relative_bias_table` 初期化方式 | `block_unit.py` L111-116 | zeros | randn×0.02 |

→ **これらをCFGから制御できるよう4ファイルを修正予定**
（`RRTRRT.cfg`, `train.py`, `create_network.py`, `alphazero_network.py`）

---

### MLP隠れ層の倍率（mlp_ratio）とは

TransformerブロックのAttention後に入る全結合層（MLP）の拡大倍率。

```
入力 256次元
  ↓ Linear（拡大）
隠れ層 256 × mlp_ratio = 512次元（mlp_ratio=2の場合）
  ↓ GELU活性化
  ↓ Linear（縮小）
出力 256次元
```

- `mlp_ratio=2`（現在）: 計算コスト低め
- `mlp_ratio=4`（GPT等の標準）: 表現力高め、計算コスト増

---

### Dropoutとは

学習中にランダムにニューロンを一時的に無効化する正則化手法。過学習を防ぎ汎化性能を上げる。

```
Dropout=0.2の場合（学習時のみ）:
  入力 [0.5, 0.3, 0.8, 0.1, 0.9]
       ↓ 20%をランダムにゼロに
  出力 [0.5,  0  , 0.8,  0 , 0.9]  → 以降の計算へ
  （推論時は全ニューロンを使用）
```

- `Dropout=0.0`（現在）: 正則化なし
- `Dropout=0.1`: 軽い正則化（iter100以降で推奨）
- `Dropout=0.5`: 強すぎると学習が不安定になる

**将棋への影響**: iterが進んで同じゲームデータを繰り返し学習する段階になると過学習リスクが増すため、その段階で0.1程度に設定すると効果的。ただし**再学習が必要**。

---

### 囲碁・Hexと将棋のゲーム特性の違い

Originalの論文（IJCAI-25）は囲碁とHexでResTNetを評価している。将棋は性質が異なるため最適なハイパーパラメータも変わる。

| 特性 | 囲碁・Hex | 将棋 |
|------|-----------|------|
| 駒の流れ | 置くだけ（増える） | 動く・取る・**打つ**（持ち駒） |
| 方向性 | 囲碁は8方向対称 | **前後非対称**（歩・香・銀・金は方向に意味） |
| 入力チャンネル数 | 少ない | **362チャンネル**（28駒種×8履歴+持ち駒+手番） |
| 行動空間 | 361手+パス | **〜5000手以上**（移動+成り+打ち） |
| ゲーム長 | 9x9囲碁: 40〜80手 | 現在平均428手（問題あり） |

**Relative Position Biasが将棋で特に重要な理由**:
囲碁は方向対称だが将棋は方向が意味を持つ（歩は前のみ、飛車は縦横など）。
そのためRelative Position Biasが「方向の非対称性」を学ぶ手段として囲碁より重要。
ゼロ初期化で学習されにくい現状は将棋において特に大きな損失。

---

## 参考

- 詳細な均等分散の原因分析: [attention_map_analysis.md](attention_map_analysis.md)
- カリキュラムトレーニング設計: [curriculum_training.md](curriculum_training.md)
- モデルアーキテクチャ: `restnet/learner/network/block_unit.py`
- Attention抽出: `restnet/learner/network/alphazero_network.py` `get_attn_table()`
