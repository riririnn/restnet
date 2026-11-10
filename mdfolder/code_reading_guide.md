# コードを読むための案内書（2026-11-11 作成）

[code_reading_plan.md](code_reading_plan.md) の順番で読む。各節は「どこを読むか → 何が起きているか → 問い」の順。
**答えは開く前に自分で考える。** わからなければ Claude に質問する（一緒に 1 行ずつ読んでもよい）。
行番号は 2026-11-11 のコード（本体 gpw ブランチ、minizero de253ec）。コードが変わるとずれるので、関数の名前で探す。
`minizero/...` は `/home/rin/restnet/minizero/minizero/...` のこと。

---

## 1 章　自己対局の 1 局から、value の正解まで（不具合のあった流れ）

### 1.1 全体の流れ

```
tools/quick-run.sh train ...            （学習を始めるコマンド。始めるたびにプログラムを作り直す：333-334 行）
 └ minizero/scripts/zero-server.sh      （サーバーを起動。続きから始めるときの処理：117-135 行）
    ├ ZeroServer（minizero/zero/zero_server.cpp）   … 自己対局を配り、棋譜を集め、学習を指示する
    ├ 自己対局のワーカー：build/shogi/restnet_shogi -mode sp（ActorGroup）… 対局して棋譜を送る
    └ 学習のワーカー：restnet/learner/train.py      … 棋譜から正解を作り、ネットワークを学習する
```

1 iteration ＝ 自己対局 2,000 局 → 学習 200 ステップ。これを 500 回くり返した（論文の 9×9）。

### 1.2 1 手を指す、投了する

- **読む所：** `minizero/actor/actor_group.cpp` の `SlaveThread::handleSearchDone`（116-134 行）
- 探索が終わると、投了でなければ選んだ手を指す（121 行）。投了か終局なら、その対局を出力する（122 行以降）。

> **問い 1：** 投了したとき、投了を決めた側は最後に手を指すか？ 棋譜の最後の手は、どちらの手か？

<details><summary>答え</summary>

指さない（121 行の `if (!actor->isResign())`）。だから棋譜の最後の手は、勝った側（投了しなかった側）の手になる。
</details>

### 1.3 投了の判定

- **読む所：** `minizero/actor/zero_actor.cpp` 26 行、`minizero/actor/zero_actor.h` 40 行、`minizero/actor/mcts.cpp` の `MCTS::isResign`（84-89 行）
- 対局の始めに、10% の確率で「この対局は投了しない」と決める（zero_actor.cpp 26 行、設定 `zero_disable_resign_ratio=0.1`）。
- 投了するのは、根の値と選んだ手の値が、どちらも手番側から見て −0.9 未満のとき（mcts.cpp 88 行、設定 `actor_resign_threshold=-0.9`）。

> **問い 2：** 動物将棋の設定は `actor_resign_threshold=-1` である。このとき投了は起きるか？

<details><summary>答え</summary>

起きない。値は −1 より小さくならないので、「−1 未満」は成り立たない（configs/dobutsu/*.cfg の注釈にも書いてある）。
</details>

### 1.4 記録（棋譜）を作る

- **読む所：** `minizero/actor/base_actor.cpp` の `BaseActor::getRecord`（42-56 行）
- 対局が規則で終わっていなければ（＝投了で終わったなら）、結果 RE に `getEvalScore(true)` の値を書く（50 行）。
- 各手には、探索の結果 P（手の分布）と V（根の値）も書く（62-63 行）。

### 1.5 結果を返す（不具合のあった所）

- **読む所：** `minizero/environment/shogi/shogi.cpp` の `ShogiEnv::getEvalScore`（330-335 行）と、`ShogiEnv::act`（156 行から。終局の判定は 191-280 行）
- 今のコード：投了（`is_resign` が true）で勝負がついていなければ、手番側の負けを返す（333 行）。そうでなければ、先手勝ち +1、後手勝ち −1、それ以外 0。
- 修正前（2026-11-02 より前）は 333 行がなく、`is_resign` を見ていなかった。
- 終局の種類（棋譜の `RR[...]`）：mate（詰み）、stalemate、perpetual_check（連続王手の千日手）、sennichite（千日手）、declaration（入玉宣言）、cap（512 手）。規則で終わらなかった対局は resign（shogi.h 413 行）。

> **問い 3：** 投了の時点で、`winner_` はどんな値か？ 修正前の `getEvalScore(true)` は何を返したか？

<details><summary>答え</summary>

投了の時点ではまだ詰んでいないので、`winner_` は UNDECIDED（勝負がついていない）。修正前の式では、先手勝ちでも後手勝ちでもないので 0（引き分け）を返した。
</details>

> **問い 4：** 囲碁や動物将棋の `getEvalScore` は、投了をどう扱っているか？（`minizero/environment/dobutsu/dobutsu.cpp` 284 行を見る）

<details><summary>答え</summary>

`is_resign` が true なら、投了した側（手番側）の負けを返す。将棋だけがこれをしていなかった。
</details>

### 1.6 サーバーが受け取って記録する

- **読む所：** `minizero/actor/actor_group.cpp` の `ThreadSharedData::outputGame`（24-50 行。「SelfPlay ...」の行を出す。35 行が対局の結果）、`minizero/zero/zero_server.cpp` の `ZeroServer::selfPlay`（188-244 行）
- サーバーは iteration ごとに、結果の平均と標準偏差を Training.log に書く（238-241 行）。

**点検の式：** 結果が +1、−1、0 だけなら、結果 0 の割合 ＝ 1 − 標準偏差² − 平均²。

> **問い 5：** 論文の R3(RRT) の Training.log で、iteration 500 の平均は 0.0025、標準偏差は 0.660842 だった。結果 0 の割合は？

<details><summary>答え</summary>

1 − 0.660842² − 0.0025² ≈ 0.563（56%）。棋譜で数えた値（1,127 / 2,000）と合う。
</details>

### 1.7 棋譜から正解を作る

- **読む所：** `minizero/learner/data_loader.cpp` の `ReplayBuffer::addData`（27-55 行）、`sampleEnvAndPos`（56-60 行）、`setAlphaZeroTrainingData`（160-180 行。171 行が policy、172 行が value）。`minizero/environment/shogi/shogi.h` の `getValue`（397 行）、`minizero/environment/base/base_env.h` の `getReturn`（309 行）
- 直近 15 iteration（3 万局）の棋譜をためておき、全局面から同じ確率で 1 局面を選ぶ（優先度なし）。
- value の正解 ＝ 棋譜の RE ×（その局面の手番が先手なら +1、後手なら −1）。手番側から見た勝ち負けになる。
- policy の正解 ＝ 棋譜の P（その局面での探索の結果の手の分布）。RE は使わない。

> **問い 6：** 投了で終わった対局の局面の value の正解は、修正前はいくつだったか？ policy の正解は影響を受けたか？

<details><summary>答え</summary>

RE が 0 なので、どの局面も 0。policy の正解は RE を使わないので、直接は影響しない。ただし探索は value を使うので、間接的には影響しうる（確かめていない）。
</details>

### 1.8 損失と学習

- **読む所：** `restnet/learner/train.py` の `calculate_loss`（257 行から）、`train`（320 行から）、損失の合計（346 行）
- value の損失は二乗誤差（`mse_loss`）。policy の損失は、探索の手の分布との交差エントロピー。合計は policy ＋ 係数 × value。

> **問い 7：** value の正解の半分が 0、残りが +1 だったら、二乗誤差を最小にする予測はいくつか？ 論文のモデルの value が終局の近くで約 +0.4 だったことと、どう関係するか？

<details><summary>答え</summary>

二乗誤差を最小にするのは正解の平均なので、約 +0.5。論文の R3(RRT) の iteration 500 では、勝った側から見た正解の平均が +0.44（詰み・入玉宣言の局面の割合）で、モデルの value は +0.37〜+0.41 だった。モデルが誤った正解に合わせて学習したことと合う（mdfolder/after_gpw_submission.md 5.2 節）。
</details>

---

## 2 章　ゲームの規則と入力

- **将棋：** `minizero/environment/shogi/shogi.cpp` の `reset`（11 行）、`act`（156 行。千日手・入玉宣言・手数の上限の判定もここ）、`isTerminal`（325 行）、`getFeatures`（359 行。362 枚の入力）。入力の説明は [input_features.md](input_features.md)。
- **動物将棋（作り直した v2）：** `minizero/environment/dobutsu/dobutsu.cpp` の `encodeMove`（73 行。手番側から見た行動の番号）、`isTerminal`（273 行）、`getEvalScore`（284 行）、`getFeatures`（299 行。19 枚）。
- 規則の確かめ：`scripts/shogi_env_check.py`、`scripts/dobutsu_env_check.py`（別の実装や実際の対局と突き合わせる）。

> **問い：** 9×9 の将棋の入力は、後手番のときに盤をどうするか？ value の正解の符号とどう対応するか？（1.7 節の `getValue` と合わせて考える）

---

## 3 章　ネットワークと Attention

- **全体：** `restnet/learner/network/alphazero_network.py`。`blocks_type`（例 `R_R_R_T_R_R_T_R_R_T`）を `_` で区切ってブロックを並べる（52 行）。`forward`（189 行）、Attention を取り出す `get_attn_table`（167 行）。
- **ブロック：** `restnet/learner/network/block_unit.py` の `ResidualBlock`（8 行）、`TransformerBlock`（31 行）、`MSA_rel`（82 行）。Attention の重みは、内積に相対位置のバイアス（`relative_bias_table`、111 行）を足して softmax したもの（142-153 行）。
- **出力：** `value_unit.py` の `TValueNetwork`（最後に tanh で −1〜+1、28 行）、`policy_unit.py`。

> **問い：** 「位置のバイアスだけの対照」（after_gpw_submission.md 6.2 節）は、Attention の式のどの項だけを残したものか？

---

## 4 章　分析の数え方

- **先生の集計（Attention と手の良し悪し）：** `scripts/attention_move_rank.py` の `features_paper`（48 行）、`quality`（83 行。完全解析の値から手の良し悪しを決める）、`run`（186 行）、9×9 の `run_shogi`（611 行）、重みの偏りの `peaked`（167 行）。方法と表は [attention_map.md](attention_map.md) の 6b・6c。
- **IG と比べた方法：** `xai_analysis.py` の `integrated_gradients_inputs`（332 行）、`occlusion`（104 行）、`scripts/ig_statistics.py` の `shapley`（97 行）、`analyse`（120 行）。基準の問題は gpw_paper/IG_基準.md。
- **完全解析との一致率：** `scripts/dobutsu_all_agreement.py` の `features`（41 行）、`choose`（67 行。探索なしで policy が最大の合法手）、`full`（111 行）。**注意：** 今のスクリプトは v2 用。論文の記録（data/dobutsu_all/full）に使うと、誤った数字がエラーなしで出る。

> **問い：** 一致率の分母から除いている局面は何か？ なぜ除くのか？（paper.tex の 4.1 節と `kind`（35 行）を見る）

---

## 5 章　動かす道具

- `tools/quick-run.sh`：学習を始める前にプログラムを作り直す（333-334 行）、学習のフォルダの名前（450-462 行）、SL の重みから始める `--pretrained`（475-489 行）、SL の学習（`pretrain`、`DATA=` を付けないと古い lishogi のデータを読む：167 行）。
- `minizero/scripts/zero-server.sh`：続きから始めるとき、フォルダの中の *.cfg を読み、終えた iteration の数から再開する（117-135 行）。
- `scripts/train_archs.sh`：動物将棋の 11 構成を順に学習する（使い方は 23-37 行。`RESUME=1` で途中から）。

> **問い：** サーバーで学習を始めたとき、どの版のプログラムで動いたかは、どこを見ればわかるか？

<details><summary>答え</summary>

Training.log の最初の `[Version]` の行（minizero の版の 6 文字）。quick-run.sh が始めるたびにプログラムを作り直すので、そのときのコードの版が書かれる。
</details>
