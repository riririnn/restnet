# 把握している不具合の一覧（2026-09-06 作成）

見つかっている不具合を、**由来**と**影響範囲**で整理する。
「我々が加えた変更」の履歴は `upstream_modifications.md` にあり、こちらは不具合そのものを扱う。

| # | 不具合 | 由来 | 影響 | 状態 |
|---|---|---|---|---|
| 1 | value の視点が入力と食い違う | **将棋の実装** | 将棋のみ | **修正済み**（2026-09-08、再学習が必要） |
| 2 | 相対位置バイアスが正方形盤を前提 | **ResTNet 本家** | 非正方形盤で実行時エラー | **修正済み**（2026-09-08） |
| 3 | `console.cpp` が将棋専用メソッドを無条件に呼ぶ | **将棋の実装** | 将棋以外の全ゲームがビルド不可 | **修正済み**（2026-09-08） |
| 4 | Dirichlet ノイズが Gumbel ノイズを打ち消す | **我々の cfg** | 将棋の全学習（方策ターゲットが壊れる） | **修正済み**（2026-09-10、再学習が必要） |
| 5 | 書式チェッカが f文字列を壊す | **minizero 本家** | `;` を含む f文字列のある Python 全て | **未修正**（回避策あり） |

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

// minizero/minizero/environment/shogi/shogi.h — value は先手視点
inline std::vector<float> getValue(const int pos) const { return {getReturn()}; }
```

### 「先手視点」がどこでどう作られるか

勝敗は対局の終わりに**1つだけ**決まり、それが全局面の正解として使い回される。
経路は次のとおり。

```
ShogiEnv::getEvalScore()      先手勝ち +1 / 後手勝ち -1 / 引き分け 0   shogi.cpp:325
      ↓ 棋譜の RE タグに書き出す                                      base_env.h:218
BaseEnvLoader::getReturn()    RE タグを読み出す                        base_env.h:305
      ↓
ShogiEnvLoader::getValue(pos) ← pos を見ずにそのまま返していた         shogi.h
      ↓
DataLoader::getAlphaZeroData()  data.value_ に入れる          t_data_loader.cpp:95
      ↓
                              ネットワークの value の正解
```

```cpp
// shogi.cpp:325 — 勝敗の定義。先手（BLACK）を基準にしている
return (winner_ == GameResult::BLACK_WON) ? 1.0f : (winner_ == GameResult::WHITE_WON) ? -1.0f : 0.0f;

// base_env.h:305 — 棋譜に書かれた勝敗を読み直すだけ
inline float getReturn() const { return std::stof(getTag("RE")); }

// shogi.h（修正前）— 引数 pos（手数）を使っていない。全局面に同じ値を返す
inline std::vector<float> getValue(const int pos) const { return {getReturn()}; }
```

**要点は `getValue` が引数 `pos` を無視していること。** 先手が勝った対局なら、
1手目も50手目も100手目も正解は +1 になる。

先手が勝った対局を例にすると、こうなる。

| 手数 | 手番 | 入力の見え方 | 修正前の正解 | その手番にとって |
|---|---|---|---|---|
| 0 | 先手 | 自分の駒が手前 | +1 | 勝ち。一致 |
| 1 | 後手 | 回転するので自分の駒が手前 | +1 | **負けなのに +1** |
| 2 | 先手 | 自分の駒が手前 | +1 | 勝ち。一致 |
| 3 | 後手 | 自分の駒が手前 | +1 | **負けなのに +1** |

特徴量は手番相対なので、どの行も「自分の駒が手前」という同じ形式の絵になる。
正解だけが先手固定なので、後手番の行で絵と符号が食い違う。

さらに**後手が勝った対局**では、後手番の局面に -1 が付く。つまり同じ「自分が優勢に
見える絵」に、対局によって +1 と -1 の両方が現れる。ネットワークが区別できるのは
手番平面1枚だけで、損失を最小にする答えは平均、すなわち 0 になる。

修正後は、その局面の手番から見た勝敗を返す。

```cpp
inline std::vector<float> getValue(const int pos) const
{
    return {getReturn() * (getTurnAt(pos) == Player::kPlayer1 ? 1.0f : -1.0f)};
}
```

**手番は手数の偶奇から推測せず、棋譜に記録された値を読む。** `loadFromString()` は
途中局面から始まる CSA 棋譜を受け付けるので、後手から始まる記録では偶奇の前提が崩れる。
指し手には必ず指した側が入っている（`shogi.cpp:636` の `ShogiAction(az_action_id, temp_env.getTurn())`）。

```cpp
inline Player getTurnAt(const int pos) const
{
    if (action_pairs_.empty()) { return Player::kPlayer1; }
    if (pos < static_cast<int>(action_pairs_.size())) { return action_pairs_[pos].first.getPlayer(); }
    return getNextPlayer(action_pairs_.back().first.getPlayer(), kShogiNumPlayer);
}
```

### 影響を受けるのは将棋だけ（実測）

全ゲームの `getFeatures` を調べた結果、**手番によって座標を反転させているのは将棋のみ**。

```
getValue        17ゲーム全て getReturn()（先手視点）  ← 規約は共通
座標の手番反転  将棋のみ（5箇所）                     ← 将棋だけが特殊
手番平面        囲碁・オセロ・ヘックス・五目並べ・breakthrough すべて有り
```

囲碁も自分/相手でチャンネルを割り当てる（`go.cpp:297`）。**違いは盤を回転させないこと。**
回転しないので、色を入れ替えた局面は鏡像の別テンソルになり、先手視点の正解と衝突しない。

```cpp
// go.cpp:297 — 自分/相手で割り当てる。ただし座標は動かさない
Player player = (channel % 2 == 0 ? turn_ : getNextPlayer(turn_, kGoNumPlayer));

// hex.cpp:130 — ヘックスも同じ。rotation_pos = pos で座標変換なし
features.push_back((board_[rotation_pos].player == turn_ ? 1.0f : 0.0f));
```

ヘックスは黒が上下、白が左右をつなぐ**非対称なゲーム**だが盤を転置していない。
minizero では非対称性を正規化ではなく手番平面で扱う。

### ただし将棋の回転は AlphaZero 論文の仕様である

**回転は場当たりの実装ミスではない。** AlphaZero 論文の将棋の定義をそのまま移植したもの。

> The board is oriented to the perspective of the current player.
> — AlphaZero (arXiv:1712.01815)

入力平面数も一致する（論文の将棋は362平面、`shogi.cpp:353` も `num_channels = 362`）。
論文では value も手番側から見た期待値。実際の将棋エンジンも同様で、dlshogi は後手の盤面を
180度回転させ、対称性を保つため手番平面すら持たない。

**最初のコミット `0c35936` の時点で、回転・相対行動ID・手番平面が一式そろっている。**
後から誤って足されたものではない。

### つまり規約が2系統ある

| 出自 | 規約 |
|---|---|
| minizero（囲碁・ヘックス・オセロ） | 回転しない、行動IDは絶対、value は先手視点 |
| AlphaZero 論文（チェス・将棋） | **回転する、行動IDは手番相対、value は手番視点** |

将棋は AlphaZero 側の規約で書かれており、**移植されなかったのが value の視点だけ**だった。
新しく環境を追加するときは、盤を回転させるかどうかがそのまま value の扱いを決める。

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

### なぜ将棋だけを直せないのか：MCTS が先手視点を前提にしている

value の視点は学習だけの話ではない。**MCTS は value が先手視点で来ることを前提に、
節点ごとに符号を反転している。**

```cpp
// minizero/minizero/actor/mcts.cpp — MCTSNode::getNormalizedMean
value = (action_.getPlayer() == charToPlayer(config::actor_mcts_value_flipping_player) ? -value : value);
```

```cpp
// minizero/minizero/config/configuration.cpp
char actor_mcts_value_flipping_player = 'W';   // 既定
```

つまり **「value は先手視点」はフレームワーク全体の規約**であり、
`getValue()` を変えるだけでは MCTS 側と食い違う。差し戻した修正が
`zero_actor.cpp`（全ゲーム共通）に手を入れる形になったのはこのため。

```
特徴量を回転させる  → ネットワークが学ぶ value は手番視点 → MCTS の規約と食い違う
特徴量を回転させない → 先手視点の value が素直に学べる    → 規約と一致
```

**将棋の不具合は「盤を回転させたのに規約は守った」ことに起因する。**
新しい環境を作るときは、盤を回転させるかどうかがそのまま value の扱いを決める。
どうぶつしょうぎは回転させない設計にしたので、この問題を持ち込まない
（`minizero/minizero/environment/dobutsu/README.md`）。

### 一度目の修正が差し戻された経緯（2026-08-26）

```
da8dcd1  fix: give shogi a side-to-move value target          修正を入れた
763df40  Revert the value sign flip that reached every game   zero_actor.cpp を戻した
4d960a8  Revert shogi's value target to Black's perspective   shogi.h も戻した
```

差し戻した理由は、`zero_actor.cpp`（全ゲーム共通）で無条件に符号を反転させる形になっており、
`getValue()` が先手視点のままの囲碁・オセロ・ヘックス・五目並べで**後手番の符号が逆転する**ため。

```cpp
// da8dcd1 の zero_actor.cpp — 将棋の都合を共通ファイルに直接書いてしまった
if (env_transition.getTurn() == env::Player::kPlayer2) { value = -value; }
```

**教訓：将棋の都合を共通ファイルに無条件で書いてはいけない。**

### 二度目の修正（2026-09-08）：環境ごとに差し替える形にした

反転するかどうかを環境が決める仮想関数を入れ、共通ファイルには**恒等の既定だけ**を置いた。
これで他16ゲームの計算結果は変わらない。

```cpp
// base_env.h — 既定は恒等。他ゲームはこれを使うので無影響
virtual float toFirstPlayerValue(float value) const { return value; }

// shogi.h ShogiEnv — 将棋だけ上書き
float toFirstPlayerValue(float value) const override
    { return turn_ == Player::kPlayer2 ? -value : value; }

// shogi.h ShogiEnvLoader — 教師信号を手番視点に（手番は棋譜から読む）
inline std::vector<float> getValue(const int pos) const
    { return {getReturn() * (getTurnAt(pos) == Player::kPlayer1 ? 1.0f : -1.0f)}; }

// zero_actor.cpp — 無条件反転ではなく環境の変換を通す
getMCTS()->backup(node_path, env_transition.toFirstPlayerValue(alphazero_output->value_), env_transition.getReward());
```

**回転をやめて minizero 側に揃える案は採らなかった。** 回転が AlphaZero 論文の仕様である
ことに加え、行動空間の方向IDが前向きを前提にしているため（`shogi.h:66` の桂馬は `dy == -2`
の2通りだけ）、回転を外すと後手の桂馬が表現できず、`kShogiPolicySize` を 11,259 → 11,583 に
変える必要が生じる。壊れているのは value 1か所なので、そこだけを直した。

動物将棋も同じ経路を通るため、**論文再現の前に片付けておく必要がある。**

### 確かめ方

`loss_value` の数字だけでは分からない。**学習済みモデルの出力を手番で分けて測る**のが
最も手軽で、再学習も要らない。手順と判定基準は `value_perspective_check.md` の
「6. 確かめ方」にある。

```
先手番の局面 → 入力の向きと正解が一致するので、まともに当たる
後手番の局面 → 食い違うので、当てずっぽうと同じ水準に落ちる
```

比較の基準線は「局面を見ずにその群の多数派を答えたときの正答率」。

### 関連

- `value_perspective_check.md` — 切り分けの手順、確かめ方、初学者向け解説
- `value_overfitting.md` — 修正後に判明した別の問題（3.5周で過学習）

---

## 2. 相対位置バイアスが正方形盤を前提

### 何が起きるか

Transformer ブロックの相対位置バイアスで、**幅を使うべき箇所が高さになっている**。
高さと幅が等しい盤（9×9、19×19）では偶然正しく、**非正方形で初めて壊れる**。

### 該当箇所

`restnet/learner/network/block_unit.py`

```python
coords = torch.meshgrid(..., indexing="xy")          # ← 列優先に並ぶ
relative_coords[0] += input_channel_height - 1
relative_coords[1] += input_channel_height - 1       # ← input_channel_width であるべき
relative_coords[0] *= 2 * input_channel_height - 1   # ← 2 * input_channel_width - 1 であるべき
```

問題は2つある。

**幅を使うべき箇所が高さになっている。** Swin Transformer の標準的な実装では、
2行目は幅、3行目は幅の2倍から1を引いた値を使う。

**`indexing="xy"` がトークンの並び順と食い違う。** ブロックは
`Rearrange("b (h w) c")`、つまり**行優先**（トークン k は行 `k // w`、列 `k % w`）で
並べているのに、`"xy"` は座標を**列優先**で展開する。

```
meshgrid 順序  (0,0) (1,0) (2,0) (3,0) (0,1) ...   列優先
トークン順序   (0,0) (0,1) (0,2) (1,0) (1,1) ...   行優先
```

正方形なら「行と列を入れ替えただけ」の一貫した対応になり、学習可能なテーブルなので
表現力は変わらない。**非正方形では対応そのものが崩れ、隣接しないトークン対に
隣接用のバイアスが付く。**

**このファイルは論文時点（`39cbebf`）から一切変更されていない。本家由来の不具合。**
同じ計算は他のファイルに無く、`block_unit.py` のこの箇所だけ。

### 実測した証拠

インデックスがテーブルの範囲を超え、`gather` で実行時エラーになる。

定義（トークン `k = (k // w, k % w)` の相対位置）と突き合わせた結果。

```
          範囲    定義と一致
 9x9  現行  OK      False     ← 転置された相対位置を学習していた
 9x9  修正  OK      True
19x19 現行  OK      False
19x19 修正  OK      True
 4x3  現行  NG      False     ← テーブル範囲外。gather でエラー
 4x3  修正  OK      True
```

**正方形でも定義とは一致していなかった。** ただし転置は一貫した読み替えであり、
バイアステーブルは学習パラメータなので**表現できる関数の集合は変わらない**。
論文の数値（9×9・19×19）が転置版で出ていること自体は問題ない。

既存の学習済みモデルは `relative_index` を buffer として保存しているため、
読み込み時は保存された値が使われる。**過去のモデルの挙動は変わらない。**

### 影響範囲

```
影響あり : 非正方形の盤面を持つゲーム
影響なし : 9×9囲碁、19×19囲碁、19×19ヘックス、9×9将棋（すべて正方形）
```

現時点で実害は出ていない。**動物将棋（3×4）を実装すると顕在化する。**

### 対処（2026-09-08 修正済み）

`indexing` と幅の3箇所を直した。

```python
coords = torch.meshgrid(..., indexing="ij")          # トークン順序に合わせる
relative_coords[1] += input_channel_width - 1
relative_coords[0] *= 2 * input_channel_width - 1
```

実際に TransformerBlock を構築して確認した。

```
動物将棋 3x4   入力(2,64,4,3)   → 出力(2,12,64)   OK   ← 修正前はエラー
将棋   9x9    入力(2,64,9,9)   → 出力(2,81,64)   OK
囲碁 19x19    入力(2,64,19,19) → 出力(2,361,64)  OK
```

盤面を 4×4 に padding して回避する案もあったが、無駄なマスが25%生じ、
Attention の解釈に余計な要素が入るため採らなかった。

---

## 3. `console.cpp` が将棋専用メソッドを無条件に呼ぶ

### 何が起きるか

`load_sfen` コンソールコマンドが `setFromSFEN()` を呼ぶが、これは将棋にしか無い。
共通ファイルから無条件に呼んでいるため、**将棋以外の全ゲームがコンパイルできなかった。**

```
error: 'Environment' {aka 'class minizero::env::dobutsu::DobutsuEnv'}
       has no member named 'setFromSFEN'
```

### 該当箇所

```cpp
// minizero/minizero/console/console.cpp:149 — 全ゲームが通る
if (!actor_->getEnvironment().setFromSFEN(sfen)) {
```

```cpp
// setFromSFEN は将棋にしか無い
minizero/minizero/environment/shogi/shogi.h:281
minizero/minizero/environment/shogi/shogi.cpp:44
```

コミット `c4687c6`（`feat: add load_sfen console command to inspect NN output from SFEN`）で入った。
将棋しかビルドしていなかったので気づかなかった。

### 対処（#1 と同じ形）

共通側に**恒等ではなく「対応していない」を返す既定**を置き、将棋だけ上書きする。

```cpp
// base_env.h — 既定は常に失敗
virtual bool setFromSFEN(const std::string& sfen) { return false; }

// shogi.h — 将棋だけ上書き
bool setFromSFEN(const std::string& sfen) override;
```

他ゲームで `load_sfen` を叩くと `Invalid SFEN` が返るだけになる。

### #1 と同じ教訓

```
#1  将棋の value の都合を zero_actor.cpp に書いた  → 他ゲームの挙動が壊れた
#3  将棋の setFromSFEN を console.cpp から呼んだ   → 他ゲームがビルドできなくなった
```

**将棋の都合を共通ファイルに無条件で書いてはいけない。** #1 は挙動が変わる形で、
#3 はコンパイルが通らない形で現れただけで、原因は同じ。

#3 は動物将棋をビルドするまで**2週間以上気づかれなかった**。将棋以外を一度も
ビルドしていなかったため。共通ファイルに手を入れたら、他ゲームでビルドを通すべき。

```bash
scripts/build.sh go release   # 将棋以外が通るかの最小確認
```

## 4. Dirichlet ノイズが Gumbel ノイズを打ち消す

### 何が起きるか

cfg で `actor_use_dirichlet_noise=true` と `actor_use_gumbel=true` を同時に立てると、
**Gumbel ノイズが一度も加算されない。** その結果、

1. 根の候補手が決定的になり、探索の多様性が失われる
2. **学習に使う方策ターゲットが壊れる**（こちらが深刻）

### 該当箇所

ノイズの追加は排他的な分岐になっている。

```cpp
// minizero/actor/zero_actor.cpp:206
if (config::actor_use_dirichlet_noise) {
    child->setPolicyNoise(dirichlet_noise[i]);
    child->setPolicy((1 - epsilon) * child->getPolicy() + epsilon * dirichlet_noise[i]);
} else if (config::actor_use_gumbel_noise) {
    child->setPolicyNoise(gumbel_noise[i]);
    child->setPolicyLogit(child->getPolicyLogit() + gumbel_noise[i]);   // ← 呼ばれない
}
```

**Dirichlet は確率に混ぜ、Gumbel はロジットに足す。**層が違う。

### 害1：候補手が固定される

```cpp
// minizero/actor/gumbel_zero.cpp:96
sort(candidates_.begin(), candidates_.end(),
     [](const MCTSNode* lhs, const MCTSNode* rhs) { return lhs->getPolicyLogit() > rhs->getPolicyLogit(); });
candidates_.resize(config::actor_gumbel_sample_size);
```

ロジット上位 k 手を取る。Gumbel ノイズが乗っていれば、これは
**Gumbel top-k サンプリング**、すなわち「方策から非復元で k 回サンプリングする」ことと
厳密に同じ分布になる（Danihelka et al., ICLR 2022）。ノイズが無ければ、
同じ局面では毎回まったく同じ k 手が候補になる。

### 害2：方策ターゲットが壊れる

```cpp
// minizero/actor/gumbel_zero.cpp:42
float logit_without_noise = child->getPolicyLogit() - child->getPolicyNoise();
```

「足したノイズを引いて戻す」意図のコード。Dirichlet の場合、
`setPolicyNoise()` には**確率値**（0〜1）が入り、`setPolicyLogit()` は変更されていない。
つまり**生のロジットから確率値を引く**ことになり、単位の違うものを引き算している。

この値が棋譜に書き込まれ、学習の方策ターゲットになる。
探索が乱れるだけでなく、**学習が誤ったターゲットを追いかける。**

### 原論文と本家の記述

Gumbel AlphaZero の原論文は
[Policy improvement by planning with Gumbel](https://iclr.cc/virtual/2022/spotlight/6419)
（Danihelka et al., ICLR 2022）。根の PUCT と **Dirichlet ノイズを置き換えるもの**として
sequential halving と Gumbel サンプリングを提案しており、併用する設計ではない。

本家 MiniZero も `README.md:240` でこの論文を出典に挙げ、
Gumbel AlphaZero の実行はアルゴリズム名 `gaz` の指定で行うよう書いている。

```bash
tools/quick-run.sh train go gaz 300 -n go_9x9_gaz_n16 -conf_str actor_num_simulation=16
```

`gaz` を指定すると `tools/quick-run.sh:382` が
`actor_use_dirichlet_noise=false` を自動で付ける。**上流の想定した使い方では
両方 true になることはない。** cfg に直接 `actor_use_gumbel=true` と書きながら
Dirichlet を切り忘れたときだけ起きる。

### 影響範囲

`configs/9x9_shogi/` の6本すべてが該当していた。**これまでの将棋の学習は
Gumbel AlphaZero になっておらず、壊れた方策ターゲットで学習していた。**
#1（value の視点）とは独立した別の不具合で、value を直した後もモデルが
期待ほど強くならなかった理由の候補になる。

### 対処（2026-09-10 修正済み）

将棋6本と動物将棋のテンプレートで1行を変えた。動物将棋は
`scripts/gen_dobutsu_configs.sh` で11本を再生成している。

```
actor_use_dirichlet_noise=false
```

`actor_dirichlet_noise_alpha` と `actor_dirichlet_noise_epsilon` はそのまま残してある。
`actor_use_gumbel=false` に戻して素の AlphaZero を回すときに必要になるため。

### 教訓

#1・#3 は「将棋の都合を共通ファイルに書いた」ことが原因だったが、
#4 は**共通の仕組みを cfg で正しく組み立てられていなかった**という別種の失敗。
上流がプリセット（`gaz`）で提供しているものを cfg に手で写すと、
その中の1行を落としても何のエラーも出ない。**プリセットがある機能は
プリセットの中身と突き合わせる。**

---

## 5. 書式チェッカが f文字列を壊す

### 何が起きるか

`.githooks/autopep8.py` は内部で `lib2to3` を使う。これは Python 3.6 で入った
f文字列を解釈できない。そのため **f文字列の中の `;` を文の区切りと誤認**し、
そこで改行する差分を提案する。適用すると文字列が閉じず、**構文エラーになる。**

```python
# 元のコード
eprint(f"WARNING: failed to load {conf_file_name}; using default settings")

# チェッカが提案する「修正」
eprint(f"WARNING: failed to load {conf_file_name}
using default settings")        # ← 文字列が閉じていない
```

実行時の警告がそのまま原因を示している。

```
DeprecationWarning: lib2to3 package is deprecated and may not be able to parse Python 3.10+
```

### 実際に起きた被害（2026-09-11）

`303f3a7` でこの提案を `-i` で自動適用し、`restnet/learner/train.py` が
構文エラーのままコミットされた。**学習が一切起動しなくなった。**

```
zero-server.sh:115 が train.py を呼んで weight_iter_0 を作る
  → SyntaxError で失敗 → モデルが無い
  → "Failed to start zero training server"
```

どうぶつしょうぎの11種類連続学習が `6R` の開始直後に停止した。`ff8cd52` で修正。

**フック自体はファイルを書き換えない。** 差分を表示して止めるだけである。壊したのは
その差分を `-i` で適用した操作の側。チェッカの提案は検証してから適用すること。

### なぜ今まで起きなかったか

**Python の書式検査が一度も動いていなかった。** `pycodestyle` が入っておらず、
フックはツールが無いと違反0件として通す（#3 と同じ「静かに成功する」型）。
2026-09-10 に導入した結果、初めて検査が動き、初めてこの提案が出た。

### 対処

f文字列の中で `;` を使わない。`,` に置き換えれば意味は変わらない。

```python
eprint(f"WARNING: failed to load {conf_file_name}, using default settings")
```

### 残っている箇所

同じ形が4か所ある。**触らなければ壊れないが、チェッカの提案を適用すると壊れる。**
これらを含むコミットはフックに止められるので、そのとき同じ置き換えを行う。

```
scripts/check_value_perspective.py:46
xai_app.py:504
scripts/bootstrap/build_dataset.py:170   # SGF の書式そのものなので置換不可、要注意
minizero/minizero/learner/train.py:249   # サブモジュール側
```

`build_dataset.py` の2箇所は SGF の区切り文字として `;` が必須なので置き換えられない。
このファイルを変更するときはフックを迂回する（`git commit --no-verify`）か、
チェッカの提案を無視して手で確認する。

### 根本的な対処（未実施）

同梱の `autopep8.py` を f文字列を解釈できる版に差し替える。上流由来のファイルであり、
`.githooks` は `minizero/.githooks` へのシンボリックリンクなのでサブモジュール側の変更になる。
あわせて `pycodestyle` の版にも制約がある。2.11 で
`missing_whitespace_around_operator` が統合されて消えたため、同梱版は **2.10.x が必要**。
Ubuntu のパッケージは 2.11.1 で、入れると例外で落ちる。

---

## 補足：なぜ本家で露見しなかったか

どちらも **「論文が扱った条件では問題が起きない」** 性質を持つ。

| | 露見しない条件 | 露見する条件 |
|---|---|---|
| 1. value の視点 | 特徴量を回転させないゲーム（囲碁等・17ゲーム中16） | 手番相対に回転させる将棋のみ |
| 3. `setFromSFEN` | 将棋だけをビルドしている限り | 将棋以外をビルドしたとき |
| 2. 相対位置バイアス | 正方形の盤 | 非正方形の盤 |

#4 だけは本家由来ではなく**我々の cfg の書き方**が原因なので、この表には載らない。
本家は `gaz` プリセットで正しく設定している。

#5 は本家由来だが性質が違う。**道具が古いだけ**で、論文の条件とは関係がない。
本家で露見しなかったのは、`pycodestyle` を入れた環境で f文字列に `;` を書いた人が
いなかったためと考えられる。

論文の3環境（9×9囲碁・19×19囲碁・19×19ヘックス）はいずれも正方形で、
特徴量の回転も行わない。**将棋と動物将棋という新しい条件を持ち込んだことで初めて表面化した。**

なお #1 は将棋の実装に起因するので、**動物将棋で盤を回転させなければ持ち込まずに済む。**
#2 は 3×4 の盤を使う限り避けられない。
