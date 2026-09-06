# 把握している不具合の一覧（2026-09-06 作成）

見つかっている不具合を、**由来**と**影響範囲**で整理する。
「我々が加えた変更」の履歴は `upstream_modifications.md` にあり、こちらは不具合そのものを扱う。

| # | 不具合 | 由来 | 影響 | 状態 |
|---|---|---|---|---|
| 1 | value の視点が入力と食い違う | minizero の規約 | 将棋・全ゲーム | **未修正**（一度直したが差し戻した） |
| 2 | 相対位置バイアスが正方形盤を前提 | **ResTNet 本家** | 非正方形盤で実行時エラー | 未修正 |

---

## 1. value の視点が入力と食い違う

### 何が起きるか

特徴量は**手番相対**（後手番のとき盤を180度回転）なのに、value の教師信号は
**常に先手視点**だった。同じ見た目の入力に正反対の正解が与えられるため、
ネットワークは損失が最小になる「常に 0」を出力し続ける。

```
先手番、自分が優勢 → 入力「手前が優勢」 正解 +1
後手番、自分が優勢 → 入力「手前が優勢」 正解 -1   ← 同じ入力に逆の正解
```

### 該当箇所

```cpp
// minizero/minizero/environment/shogi/shogi.cpp — 特徴量は手番相対
bool is_white_turn = (turn_ == Player::kPlayer2);
if (is_white_turn) { r = 8 - r; f = 8 - f; }

// minizero/minizero/environment/shogi/shogi.h — value は先手視点だった
inline std::vector<float> getValue(const int pos) const { return {getReturn()}; }
```

### 実測した証拠

**教師あり学習では 130,000 ステップ回しても `loss_value` が動かなかった。**

```
step      先手固定(修正前)   手番視点(修正後)
   5,000      0.9975            0.9215
  10,000        —               0.8932
 130,000      0.9975              —
```

「何も学ばない場合の下限」は 0.996。修正前はこれを一度も下回っていない。

**自己対局のモデルも半分の局面を捨てていた。** `weight_iter_60000` に自己対局の
棋譜480局面を評価させ、実際の勝敗と照合した結果。

```
              ラベルの偏り   多数派を答えるだけ   モデルの正答率
先手番の局面    先手勝ち34%        65.5%            75.4%   ← 上回る
後手番の局面    先手勝ち29%        71.0%            51.2%   ← 基準線を19.8pt下回る
```

向きが一致する先手番だけを学習し、後手番は捨てていた。
自己対局には検証データが無いため、集計値だけでは気づけなかった。

### 現在の状態：未修正

一度は修正したが、**全ゲームに影響が及ぶことが分かったため差し戻した。**

```
da8dcd1  fix: give shogi a side-to-move value target          修正を入れた
763df40  Revert the value sign flip that reached every game   zero_actor.cpp を戻した
4d960a8  Revert shogi's value target to Black's perspective   shogi.h も戻した
```

差し戻した理由は、`zero_actor.cpp`（全ゲーム共通）で無条件に符号を反転させる形になっており、
`getValue()` が先手視点のままの囲碁・オセロ・ヘックス・五目並べで**後手番の符号が逆転する**ため。

現在のコードは論文と同じ状態に戻っている。

```cpp
// minizero/minizero/environment/shogi/shogi.h:327
inline std::vector<float> getValue(const int pos) const { return {getReturn()}; }
```

### 対処案（未実施）

将棋だけを上書きできる形にすれば、他ゲームに影響を与えずに直せる。

```cpp
// base_env.h — 既定は恒等
virtual float toFirstPlayerValue(float value) const { return value; }

// shogi.h — 将棋だけ手番視点に
float toFirstPlayerValue(float value) const override
    { return turn_ == Player::kPlayer2 ? -value : value; }
```

動物将棋も同じ経路を通るため、**論文再現の前に片付けておく必要がある。**

### 関連

- `value_perspective_check.md` — 切り分けの手順と初学者向け解説
- `value_overfitting.md` — 修正後に判明した別の問題（3.5周で過学習）

---

## 2. 相対位置バイアスが正方形盤を前提

### 何が起きるか

Transformer ブロックの相対位置バイアスで、**幅を使うべき箇所が高さになっている**。
高さと幅が等しい盤（9×9、19×19）では偶然正しく、**非正方形で初めて壊れる**。

### 該当箇所

`restnet/learner/network/block_unit.py:126-128`

```python
relative_coords[0] += input_channel_height - 1
relative_coords[1] += input_channel_height - 1      # ← input_channel_width であるべき
relative_coords[0] *= 2 * input_channel_height - 1  # ← 2 * input_channel_width - 1 であるべき
```

Swin Transformer の標準的な実装では、2行目は幅、3行目は幅の2倍から1を引いた値を使う。

**このファイルは論文時点（`39cbebf`）から一切変更されていない。本家由来の不具合。**
同じ計算は他のファイルに無く、`block_unit.py` のこの箇所だけ。

### 実測した証拠

インデックスがテーブルの範囲を超え、`gather` で実行時エラーになる。

```
 9x9  現行  : index範囲 0..288   table 289  OK
19x19 現行  : index範囲 0..1368  table 1369 OK
 4x3  現行  : index範囲 1..47    table 35   範囲外 → エラー
 4x3  修正版: index範囲 0..34    table 35   OK
```

**正方形では現行版と修正版でインデックスが完全に一致する。**
したがって修正しても論文の再現性（9×9・19×19）には影響しない。

### 影響範囲

```
影響あり : 非正方形の盤面を持つゲーム
影響なし : 9×9囲碁、19×19囲碁、19×19ヘックス、9×9将棋（すべて正方形）
```

現時点で実害は出ていない。**動物将棋（3×4）を実装すると顕在化する。**

### 対処

2行の修正で済む。

```python
relative_coords[1] += input_channel_width - 1
relative_coords[0] *= 2 * input_channel_width - 1
```

盤面を 4×4 に padding して回避する案もあるが、無駄なマスが25%生じ、
Attention の解釈に余計な要素が入る。

---

## 補足：なぜ本家で露見しなかったか

どちらも **「論文が扱った条件では問題が起きない」** 性質を持つ。

| | 露見しない条件 | 露見する条件 |
|---|---|---|
| 1. value の視点 | 特徴量を回転させないゲーム（囲碁等） | 手番相対に回転させる将棋 |
| 2. 相対位置バイアス | 正方形の盤 | 非正方形の盤 |

論文の3環境（9×9囲碁・19×19囲碁・19×19ヘックス）はいずれも正方形で、
特徴量の回転も行わない。**将棋と動物将棋という新しい条件を持ち込んだことで初めて表面化した。**
