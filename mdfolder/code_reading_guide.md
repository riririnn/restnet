# コードを読むための案内書（2026-11-11 作成）

[code_reading_plan.md](code_reading_plan.md) の順番で読む。各節は「どこを読むか → 何が起きているか → 問い」の順。
**答えは開く前に自分で考える。** わからなければ Claude に質問する（一緒に 1 行ずつ読んでもよい）。
行番号は 2026-11-11 のコード（本体 gpw ブランチ b6b342c、minizero de253ec）。ただし `scripts/dobutsu_all_agreement.py` だけは、まだコミットしていない今の作業ツリーの行番号である。コードが変わるとずれるので、関数の名前で探す。
行番号にファイルの名前がないときは、その節の「読む所」の最初のファイルの行番号である。
`minizero/actor/...` のように書いたものは `/home/rin/restnet/minizero/minizero/...` のこと。`minizero/scripts/...` だけは `/home/rin/restnet/minizero/scripts/...` のこと。

---

## 1 章　自己対局の 1 局から、value の正解まで（不具合のあった流れ）

### 1.1 全体の流れ

```
tools/quick-run.sh train ...            （学習を始めるコマンド。始めるたびにプログラムを作り直す：333-334 行）
 ├ scripts/zero-server.sh（499 行）→ minizero/scripts/zero-server.sh
 │   └ ZeroServer（minizero/zero/zero_server.cpp）   … 自己対局を配り、棋譜を集め、学習を指示する
 ├ scripts/zero-worker.sh ... sp（528 行）
 │   └ 自己対局のワーカー：build/shogi/restnet_shogi -mode sp（ActorGroup）… 対局して棋譜を送る
 └ scripts/zero-worker.sh ... op（538 行）
     └ 学習のワーカー：restnet/learner/train.py      … 棋譜から正解を作り、ネットワークを学習する
```

1 iteration ＝ 自己対局 2,000 局 → 学習 200 ステップ。これを 500 回くり返した（論文の 9×9）。

### 1.2 1 手を指す、投了する

- **読む所：** `minizero/actor/actor_group.cpp` の `SlaveThread::handleSearchDone`（116-134 行）
- 探索が終わると、投了でなければ選んだ手を指す（121 行）。投了か終局なら、その対局を出力する（122 行以降）。

> **問い 1：** 投了したとき、投了を決めた側は最後に手を指すか？ 棋譜の最後の手は、どちらの手か？

<details><summary>答え</summary>

指さない（121 行の `if (!actor->isResign())`）。だから棋譜の最後の手は、勝った側（投了しなかった側）の手になる（1 手でも指されていれば）。
</details>

### 1.3 投了の判定

- **読む所：** `minizero/actor/zero_actor.cpp` 26 行、`minizero/actor/zero_actor.h` 40 行、`minizero/actor/mcts.cpp` の `MCTS::isResign`（84-89 行）
- 対局の始めに、10% の確率で「この対局は投了しない」と決める（zero_actor.cpp 26 行、設定 `zero_disable_resign_ratio=0.1`）。
- 投了するのは、根の値と選んだ手の値が、どちらも手番側から見て −0.9 未満のとき（mcts.cpp 88 行、設定 `actor_resign_threshold=-0.9`）。
- 根の値は 1 つ前に指した側から見た値なので、88 行で符号を変えて手番側の値にする（mcts.cpp 50 行、zero_actor.cpp 33 行）。

> **問い 2：** 動物将棋の設定は `actor_resign_threshold=-1` である。このとき投了は起きるか？

<details><summary>答え</summary>

起きない。値は −1 より小さくならないので、「−1 未満」は成り立たない（configs/dobutsu/*.cfg の注釈にも書いてある）。
</details>

### 1.4 記録（棋譜）を作る

- **読む所：** `minizero/actor/base_actor.cpp` の `BaseActor::getRecord`（42-56 行）、`getActionInfo`（59-66 行）、`minizero/environment/base/base_env.h` 222 行
- 規則で終わった対局の結果 RE は、base_env.h 222 行で `getEvalScore()` の値を書く。
- 対局が規則で終わっていなければ（＝投了で終わったなら）、RE を `getEvalScore(true)` の値で書き直す（base_actor.cpp 50 行）。
- 各手には、探索の結果 P（手の分布）と V（根の値）も書く（base_actor.cpp 62-63 行）。

### 1.5 結果を返す（不具合のあった所）

- **読む所：** `minizero/environment/shogi/shogi.cpp` の `ShogiEnv::getEvalScore`（330-335 行）と、`ShogiEnv::act`（156 行から。終局の判定は 186-281 行）
- 今のコード：投了（`is_resign` が true）で勝負がついていなければ、手番側の負けを返す（333 行）。そうでなければ、先手勝ち +1、後手勝ち −1、それ以外 0。
- 修正前（2026-11-02 より前）は 333 行がなく、`is_resign` を見ていなかった。
- 終局の種類（棋譜の `RR[...]`）：mate（詰み）、stalemate、perpetual_check（連続王手の千日手）、sennichite（千日手）、declaration（入玉宣言）、cap（512 手）。規則で終わらなかった対局は resign（shogi.h 413 行）。

> **問い 3：** 投了の時点で、`winner_` はどんな値か？ 修正前の `getEvalScore(true)` は何を返したか？

<details><summary>答え</summary>

投了の時点ではまだ詰んでいないので、`winner_` は UNDECIDED（勝負がついていない）。修正前の式では、先手勝ちでも後手勝ちでもないので 0（引き分け）を返した。
</details>

> **問い 4：** 囲碁や動物将棋の `getEvalScore` は、投了をどう扱っているか？（`minizero/environment/go/go.cpp` 259 行、`minizero/environment/dobutsu/dobutsu.cpp` 284 行を見る）

<details><summary>答え</summary>

`is_resign` が true なら、投了した側（手番側）の負けを返す。5五将棋（minishogi.cpp 474 行）も同じ。この 4 つのうち、9×9 の将棋だけがこれをしていなかった。
</details>

### 1.6 サーバーが受け取って記録する

- **読む所：** `minizero/actor/actor_group.cpp` の `ThreadSharedData::outputGame`（24-50 行。「SelfPlay ...」の行を出す。35 行が対局の結果）、`minizero/zero/zero_server.cpp` の `ZeroServer::selfPlay`（188-244 行）
- サーバーは iteration ごとに、結果の平均と標準偏差を Training.log に書く（zero_server.cpp 240-241 行）。

**点検の式：** 結果が +1、−1、0 だけなら、結果 0 の割合 ≈ 1 − 標準偏差² − 平均²。標準偏差は n − 1 で割っている（`minizero/utils/utils.h` 117 行）ので、少しだけずれる。

> **問い 5：** 論文の R3(RRT) の Training.log で、iteration 500 の平均は 0.0025、標準偏差は 0.660842 だった。結果 0 の割合は？

<details><summary>答え</summary>

1 − 0.660842² − 0.0025² ≈ 0.563（56%）。棋譜で数えた値（1,127 / 2,000 ＝ 0.5635）と合う。標準偏差² に 1999/2000 を掛けると 0.5635 になる。
</details>

### 1.7 棋譜から正解を作る

- **読む所：** `minizero/learner/data_loader.cpp` の `ReplayBuffer::addData`（27-54 行）、`sampleEnvAndPos`（56-61 行）、`setAlphaZeroTrainingData`（160-181 行。171 行が policy、172 行が value）。`minizero/environment/shogi/shogi.h` の `getValue`（397 行）、`minizero/environment/base/base_env.h` の `getReturn`（309 行）
- 直近 15 iteration（3 万局）の棋譜をためておき、全局面から同じ確率で 1 局面を選ぶ（優先度なし）。
- value の正解 ＝ 棋譜の RE ×（その局面の手番が先手なら +1、後手なら −1）。手番側から見た勝ち負けになる。
- policy の正解 ＝ 棋譜の P（その局面での探索の結果の手の分布）。RE は使わない。

> **問い 6：** 投了で終わった対局の局面の value の正解は、修正前はいくつだったか？ policy の正解は影響を受けたか？

<details><summary>答え</summary>

RE が 0 なので、どの局面も 0。policy の正解は RE を使わないので、直接は影響しない。ただし探索は value を使うので、間接的には影響しうる（確かめていない）。
</details>

### 1.8 損失と学習

- **読む所：** `restnet/learner/train.py` の `calculate_loss`（257 行から）、`train`（320 行から）、損失の合計（346 行）
- value の損失は二乗誤差（`mse_loss`、279-284 行）。
- policy の損失は、Gumbel を使う設定（`actor_use_gumbel=true`。9×9 も動物将棋もこれ）では KL ダイバージェンス（259-267 行）。使わない設定では交差エントロピー（269-275 行）。2 つの差は正解の分布だけで決まる定数なので、勾配は同じ。
- 合計は policy ＋ 係数 × value。

> **問い 7：** value の正解の半分が 0、残りが +1 だったら、二乗誤差を最小にする予測はいくつか？ 論文のモデルの value が終局の近くで約 +0.4 だったことと、どう関係するか？

<details><summary>答え</summary>

二乗誤差を最小にするのは正解の平均なので、約 +0.5。論文の R3(RRT) の iteration 500 の棋譜で数えると、詰み・入玉宣言の局面は全局面の 44.9%（143,301 / 319,511）で、これが勝った側から見た正解の平均に近い。モデルの value は +0.37〜+0.41 だった（after_gpw_submission.md 5.2 節の測定。この案内書を書くときには計算し直していない）。モデルが誤った正解に合わせて学習したことと合う。
</details>

---

## 2 章　ゲームの規則と入力

### 2.1 9×9 の将棋の合法手と手の番号

- **読む所：** `minizero/environment/shogi/shogi.cpp` の `reset`（11-27 行）、`setLegalAction`（302-319 行）。`shogi.h` の `parseAction`（87-114 行）、`map_dx_dy_to_direction_id`（132-177 行）、`convertAZ`（195 行から）
- 手の候補を作り（307 行）、反則を除き（311 行）、手の番号に直して印を立てる（313-315 行）。打ち歩詰めもこの反則の確かめで除く（`board.cpp` 830-843 行）。
- 手の番号は全部で 11,259 個（shogi.h 24 行）。打つ手は 7 種 × 81 マス ＝ 567 個。動かす手は 567 ＋ 元のマス × 132 ＋ 方向 × 2 ＋ 成り（shogi.h 113 行）。
- 方向は 66 個。桂馬 2 個と、8 方向 × 距離 8。
- 後手番では、マスの番号を 80 − マスに回す（shogi.h 208-209 行）。
- 意味のない不成は作らない（`MoveGenerator.cpp` 39 行）。成れる歩・角・飛の不成と、最後の 2 段への香の不成。

> **問い 8：** 開始局面の先手の 7g7f と、その直後の後手の 3c3d は、手の番号がどうなるか？

<details><summary>答え</summary>

どちらも 8491。後手番ではマスを回すので、手番側から見て同じ手は同じ番号になる。567 ＋ 60 × 132 ＋ 2 × 2 ＋ 0 ＝ 8491（元のマス 60、方向 2 は 1 マス前）。ビルド済みの環境で確かめた。
</details>

### 2.2 9×9 の将棋の終局

- **読む所：** `shogi.cpp` の `act`（156-284 行）、`isTerminal`（325-328 行）。`board.h` の `getHash`（148-150 行）
- 手を指し（166 行）、手番を変え（183 行）、次の手番の合法手を作る（184 行）。そのあと順に調べる。
  1. 合法手がなければ、王手なら詰み、王手でなければステイルメイト（186-197 行）。ステイルメイトは引き分けにしている（公式の規則では負けとされる。規則の原文は確かめていない）。
  2. 同じ局面が 4 回目なら千日手（199-239 行）。片側の手がずっと王手なら、その側の負け。そうでなければ引き分け。
  3. 指した側が入玉の条件を満たせば勝ち（242-273 行）。宣言という手はなく、指した直後に自動で判定する。
  4. 512 手に達したら引き分け（275-281 行）。
- 同じ局面かどうかは、盤・持ち駒・手番のハッシュで見る。開始局面も 1 回と数える（shogi.cpp 24 行）。

> **問い 9：** 512 手目で相手を詰ませたら、結果は勝ちか引き分けか？

<details><summary>答え</summary>

勝ち。詰みを先に調べて `winner_` が決まる。手数の上限は `winner_ == GameResult::UNDECIDED` のときだけ見る（278 行）。
</details>

> **問い 10：** 飛車を往復させて、開始局面に 4 手ごとに戻る。何手目で終局するか？

<details><summary>答え</summary>

12 手目。開始局面が 1 回目で、4 手目が 2 回目、8 手目が 3 回目、12 手目が 4 回目。結果は 0。ビルド済みの環境で確かめた。
</details>

### 2.3 9×9 の将棋の入力

- **読む所：** `shogi.cpp` の `getFeatures`（359-461 行）。一覧は [input_features.md](input_features.md)
- 362 枚 ＝ 8 時点 × 45 枚 ＋ 手番 1 枚 ＋ 手数 1 枚。
- 1 時点の 45 枚：自分の駒 14、相手の駒 14、同じ局面の回数 3、自分の持ち駒 7、相手の持ち駒 7。
- 後手番では盤を 180 度回す（386-389 行）。「自分」「相手」は今の手番で決める（405-406 行）。過去の時点も今の手番の向きで並べる。
- 列 0 は 1 筋（383 行）。381 行の注釈「1(9筋)」は誤りで、`file` は筋の番号のまま（SFEN の読み込みの 88 行でわかる）。
- 履歴が足りない時点は全部 0 のまま（374 行）。
- 持ち駒は枚数をそのまま全マスに敷く（438、444 行）。手数は手数 ÷ 512（456 行）。
- `rotation` の引数は使わない。`getRotatePosition` もそのまま返す（shogi.h 373-374 行）。盤を回して学習データを増やすことはしない。

> **問い 11：** 9×9 の将棋の入力は、後手番のときに盤をどうするか？ value の正解の符号とどう対応するか？（1.7 節の `getValue` と合わせて考える）

<details><summary>答え</summary>

180 度回す。ネットワークはいつも手番側の向きの盤を見るので、value も手番側から見た値を学ぶ必要がある。だから `getValue` は後手番で RE に −1 を掛ける。探索は先手から見た値を持つので、ネットワークの出力を `toFirstPlayerValue` で先手から見た値に戻す（shogi.h 360 行、zero_actor.cpp 87 行）。2026-09-08 のコミット 3cb9abc の前は、同じ入力に反対の正解が付いていた。
</details>

> **問い 12：** 開始局面の 0 枚目（自分の歩）で 1 が立つのは何行目か？ 7g7f を指した直後（後手番）では何行目か？

<details><summary>答え</summary>

どちらも 7 行目（行の番号 6）に 9 個。後手番では後手の歩が盤を回して同じ場所に来る。ビルド済みの環境で確かめた。
</details>

### 2.4 動物将棋（作り直した v2）

- **読む所：** `minizero/environment/dobutsu/dobutsu.cpp` の `decodeAction`（51-71 行）、`encodeMove`（73-83 行）、`isLegalAction`（199-214 行）、`act`（227-266 行）、`isTerminal`（273-282 行）、`getEvalScore`（284-292 行）、`getFeatures`（299-345 行）。`dobutsu.h` の 20-31 行、101 行、137-140 行
- 手の番号は 132 個。打つ手は 3 種 × 12 マス ＝ 36 個。動かす手は 36 ＋ 元のマス × 8 ＋ 方向。後手番ではマスと方向を回す（38-39 行）。
- ライオンを取れば勝ち（239 行）。ライオンが相手の陣に入り、すぐ取られなければ勝ち（252-255 行）。同じ局面が 3 回目なら引き分け（262 行）。手数の上限はない。
- 入力は 19 枚：自分の駒 5、相手の駒 5、同じ局面の回数 2、自分の持ち駒 3、相手の持ち駒 3、先手番 1。後手番では盤を回す（329 行）。履歴はない（dobutsu.h 27 行）。302 行の注釈「20 channels」は古い。
- value は手番側から見た値（dobutsu.h 101、137-140 行）。
- **論文の 11 構成は、作り直す前の環境で学習した。** 入力は 20 枚で盤を回さない。分析のスクリプトでは `features_paper` がこの形を作る（4.1 節）。

> **問い 13：** 開始局面で先手がひよこで相手のひよこを取る手 b2b3 の番号は？ 先手が別の手を指したあと、後手がひよこで取る手 b3b2 の番号は？

<details><summary>答え</summary>

どちらも 92。手番側から見ると元のマス 7、方向 0（前）で、36 ＋ 7 × 8 ＋ 0 ＝ 92。ビルド済みの環境で確かめた。
</details>

> **問い 14：** ライオンが相手の陣に入っても、勝ちにならないのはどんなときか？

<details><summary>答え</summary>

入ったマスを相手がすぐ取れるとき（253 行の `isAttacked`）。対局は続き、相手がライオンを取れば相手の勝ちになる。
</details>

> **問い 15：** 同じ局面の回数の平面は、9×9 では 3 枚、動物将棋では 2 枚である。なぜ違うか？

<details><summary>答え</summary>

終局する回数が違うから。9×9 は 4 回目で終局するので、入力に現れるのは 1〜3 回目。動物将棋は 3 回目で終局するので 1〜2 回目。
</details>

### 2.5 規則の確かめ

- **読む所：** `scripts/shogi_env_check.py` の冒頭の説明（1-19 行）、`check_resign`（86 行）、`check_rules`（96 行）、`check_floodgate`（227 行）。`scripts/dobutsu_env_check.py` の冒頭の説明（1-18 行）、`check_rules`（62 行）、`check_repetition`（125 行）
- 9×9 は別の実装（python-shogi）と floodgate の実際の対局に突き合わせる。動物将棋は作り直す前の環境の対局と、完全解析の記録に突き合わせる。

> **問い 16：** `check_resign` は、修正前のコードで何を報告するか？

<details><summary>答え</summary>

FAIL。7g7f のあとで投了すると +1、3c3d のあとで投了すると −1 が期待の値だが、修正前はどちらも 0 を返す。
</details>

---

## 3 章　ネットワークと Attention

### 3.1 全体の組み立て

- **読む所：** `restnet/learner/network/alphazero_network.py` の `__init__`（12-58 行）、`get_backbone`（65-77 行）、`_init_weights_trunc_normal`（110-117 行）、`forward`（189-198 行）。`embed_unit.py`（6-24 行）
- 流れ：入力 → 3×3 の畳み込み（embed）→ ブロックを順に通す → policy と value。
- `blocks_type`（例 `R_R_R_T_R_R_T_R_R_T`）を `_` で区切ってブロックを並べる（52 行）。
- ヘッドは 4 個（43 行）。チャンネルは 256（設定 `nn_num_hidden_channels`）。
- 全結合層の重みは標準偏差 0.02 の乱数で始まる（112 行）。

> **問い 17：** `R_R_R_T_R_R_T_R_R_T` の T ブロックは、1 から数えて何番目か？

<details><summary>答え</summary>

4、7、10 番目。分析の表の block の番号もこの数え方。
</details>

### 3.2 R ブロックと T ブロック

- **読む所：** `block_unit.py` の `ResidualBlock`（8-27 行）、`TransformerBlock`（31-79 行）
- R ブロック：3×3 の畳み込みを 2 回通して、入力に足す（21-26 行）。T ブロックのあとは形が (batch, マス, チャンネル) なので、盤の形に戻す（18-19 行）。
- T ブロック：LayerNorm → Attention → 入力に足す → LayerNorm → MLP → 足す（69-79 行）。
- `attn`（57-67 行）は `forward` と同じ計算で、Attention の重みも返す。

> **問い 18：** T ブロックの Attention の出力がほぼ 0 だったら、ブロックの入力はどうなるか？

<details><summary>答え</summary>

75 行で入力に足すので、入力はそのまま次へ流れる。そのあとの MLP は働く（77-79 行）。Attention が働かなくても、ネットワークは止まらない。
</details>

### 3.3 Attention の重み

- **読む所：** `block_unit.py` の `MSA_rel`（82-179 行。重みの計算は `attn` の 142-153 行）。`alphazero_network.py` の `get_attn_table`（167-187 行）。`xai_analysis.py` の `load_python_model`（41-97 行）
- 重み ＝ softmax（query と key の内積 × scaling ＋ 相対位置のバイアス）。scaling は (256 / 4)^(−1/2) ＝ 1/8（138 行）。
- query、key は入力を全結合層に通したもの（93-100 行）。
- 相対位置のバイアス（`relative_bias_table`、111-116 行）は 0 で始まり、学習する。2 つのマスの行と列の差ごとに、ヘッドごとに 1 つの値を持つ。盤の内容によらない。
- 重みの形は (batch, ヘッド, query のマス, key のマス)。softmax は最後の軸なので（139 行）、1 つの query のマスから全マスへの重みの合計が 1。均等なら 1 / マスの数。
- `get_attn_table` は保存した `.pt` から呼べない。分析では `load_python_model` で Python のモデルを作り直す。

> **問い 19：** 「位置のバイアスだけの対照」（after_gpw_submission.md 6.2 節）は、Attention の式のどの項だけを残したものか？

<details><summary>答え</summary>

相対位置のバイアスだけ。query と key の内積を捨てて、softmax(バイアス) を重みにする（`scripts/attention_move_rank.py` の `bias_attention`、143-151 行）。盤の内容は入らない。
</details>

> **問い 20：** 動物将棋（4 行 3 列）の `relative_bias_table` の形は？

<details><summary>答え</summary>

(35, 4)。行の差が 7 通り、列の差が 5 通りで 7 × 5 ＝ 35。4 はヘッドの数。保存した重みで確かめた。
</details>

> **問い 21：** マス (0,0) から (1,1) への重みと、(2,1) から (3,2) への重みでは、同じバイアスを使うか？

<details><summary>答え</summary>

使う。行の差と列の差が同じなので、同じ行を指す（129-135 行）。
</details>

### 3.4 出力

- **読む所：** `value_unit.py` の `TValueNetwork`（7-29 行）、`policy_unit.py` の `PolicyNetwork`（36-63 行）。設定は `nn_value_type=TV`、`nn_policy_type=P`
- value：全マスを平均し（26 行）、全結合を 2 回通し、tanh で −1〜+1 にする（28 行）。
- policy：1×1 の畳み込み → BatchNorm → ReLU → 全結合で、全部の手の番号の数だけ出す。合法手だけに絞るのは、この外で行う。

> **問い 22：** value の出力が −1〜+1 なのは、何に合わせているか？

<details><summary>答え</summary>

正解が勝ち +1、負け −1、引き分け 0 だから。1.3 節の投了の判定も、この範囲を前提にしている。
</details>

### 3.5 観察：query と key の重みの大きさ（原因はわかっていない）

**測るもの：** ヘッドごとに、query の重み行列と key の重み行列（どちらも 64 × 256）の積 W_qᵀ W_k の最大特異値に、scaling の 1/8 を掛けた値。ここでは「query と key の重みの大きさ」と呼ぶ。

**予測：** 損失の勾配がなく weight decay だけが効くと、大きさ ≈ 初期値 × exp(−4×10⁻⁵ × ステップ)（学習率 0.02 のとき）。初期値は約 0.022。9×9 は 70,000 と 90,000 ステップで学習率が半分になるので、その分だけ縮みが遅い。

| モデル（自己対局） | ステップ | 測定（全ヘッドの範囲） | 予測 |
|---|---|---|---|
| 動物将棋 v2 の RRTRRT | 0 | 0.0212〜0.0225 | — |
| 同 | 12,000 | 0.0132〜0.0140 | 0.0136 |
| 同 | 40,000 | 0.0043〜0.0046 | 0.0044 |
| 動物将棋 v2 の、R と T を両方含む 9 構成 | 40,000 | 0.0043〜0.0048 | 0.0044 |
| 論文の動物将棋の、R と T を両方含む 9 構成 | 40,000 | 0.0042〜0.0047 | 0.0044 |
| 9×9 の R3(RRT)（論文）の 7・10 番目のブロック | 100,000 | 0.0008〜0.0009 | 0.0008 |
| 9×9 の R3(RRT)（論文）の 4 番目のブロック | 100,000 | 0.0022〜0.0130 | 0.0008 |

比べる相手（R を含まない、または SL）：

| モデル | ステップ | 測定（全ヘッドの範囲） |
|---|---|---|
| 動物将棋 v2 の 6T（T だけ、自己対局） | 40,000 | 0.0047〜0.2483 |
| 論文の 6T（T だけ、自己対局） | 40,000 | 0.0054〜0.2653 |
| 9×9 の SL の R3(RRT) | 150,000 | 0.0001〜0.4469 |

- **観察：** 上の表の、R ブロックを含む自己対局の 19 個のモデル（動物将棋 v2 の 9 構成、論文の動物将棋の 9 構成、9×9 の R3(RRT)）では、query と key の重みは、weight decay だけで予測される大きさのままだった。例外は 9×9 の R3(RRT) の 4 番目のブロックで、予測より大きい。SL から始めた RL のモデルなど、表にないモデルは測っていない。
- **勾配：** 動物将棋 v2 の RRTRRT の 40,000 ステップで、学習に使った棋譜の 1,000 局面の損失の勾配のノルムは、query と key で weight decay の項（0.0001 × 重みのノルム）の 0.29〜0.35 倍だった。同じブロックの value の重みでは 44〜46 倍、6T の query では 2.6〜162 倍（data/dobutsu_all/qk_gradient_v2_selfplay.txt、測り方は attention_map.md 6d）。この案内書を書くときに別の 700 局面で計算し直すと、RRTRRT の query と key は 0.29〜0.40 倍だった。9×9 の勾配は測っていない。
- **原因はわかっていない。** 勾配が小さいことは大きさの観察と合う。しかし、なぜ R ブロックがあると query と key の勾配が小さいのかは確かめていない。
- 「R ブロックがあると Attention が学習しない」とは言えない。SL の R3(RRT) では育っている。
- 動物将棋には投了の不具合がないので、投了の不具合だけでは説明できない。
- 2026-11-11 に保存した重みで計算した。論文の動物将棋の重みの学習率が 0.02 のままだったことは、サーバーの記録で確かめた結果（after_gpw_submission.md 3.3 節）で、この PC の同じフォルダの記録は別の学習のものである。この案内書を書くときには確かめていない。

1 ヘッドを自分で計算するには（この PC のコンテナの中、/workspace で python3 を開く）：

```python
import torch
sd = torch.jit.load("models/dobutsu/v2/RRTRRT/model/weight_iter_40000.pt", map_location="cpu").state_dict()
Wq, Wk = sd["blocks.2.MSA.projq.0.weight"], sd["blocks.2.MSA.projk.0.weight"]
s = slice(0, 64)   # 1 番目のヘッド
print(torch.linalg.matrix_norm(Wq[s].T @ Wk[s], 2) / 8)
```

> **問い 23：** 予測の 4×10⁻⁵ を導く。学習率 0.02、weight decay 1×10⁻⁴、momentum 0.9 の SGD（`train.py` 196-201 行）で、勾配が weight decay の項だけのとき、重みは 1 ステップでどれだけの割合で縮むか？ 2 つの行列の積ではどうなるか？

<details><summary>答え</summary>

速度を v、重みを w とすると、v ← 0.9 v ＋ 1×10⁻⁴ w、w ← w − 0.02 v。落ち着くと v ≈ 1×10⁻⁴ w / (1 − 0.9) ＝ 1×10⁻³ w なので、1 ステップで w の 0.02 × 1×10⁻³ ＝ 2×10⁻⁵ の割合で縮む。積は 2 つとも縮むので 4×10⁻⁵。この式を 40,000 ステップ計算すると w² は 0.2019 で、exp(−1.6) ＝ 0.2019 と合う。
</details>

> **問い 24：** 動物将棋で 28,000 と 36,000 ステップで学習率を半分にしていたら、40,000 ステップの予測はいくつになるか？ 論文の RRTRRT の測定 0.0043〜0.0045 と比べるとどうか？

<details><summary>答え</summary>

指数は 4×10⁻⁵ × 28,000 ＋ 2×10⁻⁵ × 8,000 ＋ 1×10⁻⁵ × 4,000 ＝ 1.32。0.022 × exp(−1.32) ≈ 0.0059。測定はこれより小さく、学習率を下げなかったときの 0.0044 に合う。
</details>

> **問い 25：** この観察から「このモデルの Attention は使われていない」と言ってよいか？

<details><summary>答え</summary>

大きさの観察だけでは言えない。別の証拠はある。動物将棋の論文の RRTRRT では、ヘッドを 1 つ均等に置き換えても、policy の 1 位が最善手である割合の変化は 1×10⁻⁵ 未満だった（data/dobutsu_all/ablate_RRTRRT.csv）。相対位置のバイアスも最大 0.005 程度と小さい。ただし、なぜ query と key の勾配が小さいのかは確かめていない（3.5 節）。
</details>

---

## 4 章　分析の数え方

### 4.1 先生の集計（Attention と手の良し悪し）

- **読む所：** `scripts/attention_move_rank.py` の冒頭の説明（1-23 行）、`features_paper`（48-67 行）、`quality`（83-85 行）、`load_records`（88-96 行）、`peaked`（167-183 行）、`run`（186 行から）、`pair_hits`（420-425 行）、`run_shogi`（611 行から）。方法と表は [attention_map.md](attention_map.md) の 6b・6c
- 局面は完全解析から無作為に選び、4 つの向きで入れる。相手のライオンを取れる局面とトライ済みの局面は除く（`load_records`）。
- `quality` は手の良し悪しの数値。勝ちは早いほど、負けは遅いほど大きい。`left` はその手のあと終局までの手数（`scripts/dobutsu_all.cc` 147 行）。
- 手の重みは、動かす駒のマスから行き先のマスへの重み（249-250 行）。
- 同じ局面の 2 つの手を組にして、良い手の重みが大きければ 1、同じなら 0.5 と数える。局面ごとに割合を出し、局面で平均する（207-215 行）。0.5 が偶然。
- 打つ手には動かす駒のマスがない。行き先が全マスから受ける重みの平均を使い、打つ手どうしだけを比べる（299、303 行）。
- 対照は `control` で選ぶ（190-192 行）：`bias`（位置のバイアスだけ）、`untrained`（学習前の重み）、`reverse`（行き先から駒への重み）、`rollout`。
- 9×9 には完全解析がないので、指された手を仮の正解にする（`run_shogi`）。成る手と成らない手は同じマスの組なので、1 つにまとめる（668-673 行）。
- 論文のモデルか v2 かは入力の枚数で判断する（829 行）。

> **問い 26：** `left` が 3 の勝ち、5 の勝ち、引き分け、3 の負け、5 の負けの `quality` はいくつか？ 良い順に並べる。

<details><summary>答え</summary>

997、995、0、−997、−995。良い順は 997、995、0、−995、−997。
</details>

> **問い 27：** ある局面で、最善手 A の重みが 0.10、他の手 B が 0.20、C が 0.05 だった。この局面の「最善手と他の手」の値は？

<details><summary>答え</summary>

組は (A, B) と (A, C) の 2 つ。B には負け、C には勝ちなので 1 / 2 ＝ 0.5。
</details>

> **問い 28：** 局面ごとに平均するのと、全部の組を足してから割るのでは、何が違うか？

<details><summary>答え</summary>

全部の組を足すと、手が多い局面ほど強く効く。局面ごとに平均すると、どの局面も同じ重さになる。全部の組を足した値は `_pooled` の列に入る。たとえば論文の 6T の 2 番目のブロックの 1 番目のヘッドの `all_pairs` は、局面ごとが 0.681、全部の組が 0.646（data/dobutsu_all/attention_move_rank_paper11.csv）。先生の値は 0.68 で、局面ごとのほうに近い。先生の値は attention_map.md 6b の写しで見ただけで、元の表は確かめていない。
</details>

> **問い 29：** `peaked` の値は、重みが均等のときと、1 マスに全部集まったときで、いくつになるか？

<details><summary>答え</summary>

均等なら 1。1 マスに全部集まればマスの数（動物将棋 12、9×9 は 81）。各 query のマスで最大の重みを取り、マスと局面で平均し、マスの数を掛ける（180 行）。
</details>

### 4.2 IG と比べた方法

- **読む所：** `xai_analysis.py` の `occlusion`（104-158 行）、`pieces_removed`（321-329 行）、`integrated_gradients_inputs`（332-345 行）。`scripts/ig_statistics.py` の冒頭の説明（1-19 行）、`players_of`（52-73 行）、`shapley`（97-113 行）、`analyse`（120-173 行）。基準の問題は gpw_paper/IG_基準.md
- IG：基準から入力までを直線で結び、途中の 301 点で勾配を求めて平均し、（入力 − 基準）を掛ける（340-345 行）。
- value は `sign` を掛けて手番側から見た値にできる（343 行）。policy は選んだ手の確率が対象。
- `ig_statistics.py` の基準は 3 つ（128-130 行）：全部 0、駒だけ 0、データの平均。
- Shapley 値：駒などを「参加者」とし（`players_of`）、全部の組み合わせの出力から厳密に計算する。
- `xai_analysis.py` の `occlusion` は 1 マスの全部の平面を 0 にする。`ig_statistics.py` の occlusion は 1 つの参加者を除く（149-156 行）。名前は同じだが別の計算である。

> **問い 30：** IG を全部の入力で足すと、何に近くなるか？ それをどこで確かめているか？

<details><summary>答え</summary>

出力(入力) − 出力(基準)。`ig_statistics.py` の `summarize` の sum check（245-249 行）で確かめている。動物将棋の 6T の value、全部 0 の基準で、差の平均は 0.0081、最大は 0.0314（data/dobutsu_all/ig_6T.txt）。
</details>

> **問い 31：** 全部 0 の基準では、手番の平面はどうなるか？ 何が問題か？

<details><summary>答え</summary>

手番の平面も 0 になる。どちらの手番でもない入力で、学習に一度も現れない。論文の動物将棋のモデルでは、取れる相手のライオンの符号が手番で変わった（`pieces_removed` の説明、after_gpw_submission.md 3.2 節）。
</details>

> **問い 32：** 厳密な Shapley 値は、動物将棋ではできて 9×9 ではできない。なぜか？

<details><summary>答え</summary>

参加者が n 人なら 2ⁿ 通りの出力が要る（`ig_statistics.py` 102 行）。動物将棋は駒が 8 枚なので、手番などを入れても 10 人ほどで約 1,000 通り。9×9 は駒が 40 枚で、2⁴⁰ 通り以上になる。
</details>

### 4.3 完全解析との一致率

- **読む所：** `scripts/dobutsu_all_agreement.py` の `kind`（36-39 行）、`features`（42-61 行）、`choose`（68-76 行）、`require_v2_records`（85-97 行）、`require_v2_model`（100-110 行）、`full`（143-189 行）。`scripts/dobutsu_viewer.py` の `agreement_figure`（856 行から）。`gpw_paper/paper.tex` 462-465 行
- モデルの手は、探索なしで policy が最大の合法手（75 行）。
- その手が最善手の集合に入っていれば一致（164 行）。
- `full` は局面の種類ごとに数を CSV に書く。除く局面は集計するときに除く（`dobutsu_viewer.py` 870 行）。
- `full` は一致とは別に、勝ちや引き分けを失う手（誤り）も数える（166-169 行）。
- **注意：** 今のスクリプトは v2 用（`scripts/attention_presets.py` 48-49 行）。論文の記録（data/dobutsu_all/full）と v2 の記録は形が同じで、手の番号の付け方が違う。そこで長い計算の前に、各ファイルの先頭 128 件で確かめ、論文の記録（`require_v2_records`）や論文の重み（`require_v2_model`）なら止める。論文の結果は data/dobutsu_all_agreement_full.csv にある。

> **問い 33：** 一致率の分母から除いている局面は何か？ なぜ除くのか？（paper.tex の 4.1 節と `kind` を見る）

<details><summary>答え</summary>

`kind` が 4 の局面、つまり相手のライオンがトライ済みの負けの局面。どの手も同じ評価で、モデルが間違えようがない。論文の記録（data/dobutsu_all/full）を全部数えると、246,803,167 局面のうち 7,018,985 局面で、残りが論文の 239,784,182 局面。除いた局面はすべて、最善手の数と合法手の数が同じだった。
</details>

> **問い 34：** 勝ちの局面で、勝てるが最短ではない手を選んだ。一致率と誤りでは、それぞれどう数えられるか？

<details><summary>答え</summary>

一致率では外れ（最短の手が最善手）。誤りでは正しい（勝ちを失っていない）。
</details>

---

## 5 章　動かす道具

### 5.1 学習を始める：tools/quick-run.sh

- **読む所：** `tools/quick-run.sh` の 154-172 行（`pretrain`）、333-334 行、450-462 行、475-491 行、496-540 行、546-555 行
- 始めるたびにプログラムを作り直す（333-334 行）。
- 学習のフォルダの名前（450-462 行）：`-n` がなければ設定から作り、`models/` の下に置く。
- `--pretrained`（475-491 行）：SL の重みを `weight_iter_0` として新しいフォルダに写し、続きとして始める。
- サーバー（499 行）、自己対局のワーカー（528 行）、学習のワーカー（538 行）を起動する。
- 最後の iteration の学習が終わっていれば成功と判定する（546-555 行）。
- SL の学習（`pretrain`）はサーバーもワーカーも使わず、`supervised_learning_bv_train.py` を直接動かす（168-171 行）。

> **問い 35：** `pretrain` で `DATA=` を付け忘れるとどうなるか？

<details><summary>答え</summary>

古い lishogi のデータ（data/bootstrap/sgf）を読む（167 行）。ファイルがあるので、エラーは出ない。
</details>

> **問い 36：** SL の重みから RL を始める設定では、学習率を下げるステップが 70,000 ではなく 220,000 になっている（configs/9x9_shogi/10T-bootstrap.cfg）。なぜか？

<details><summary>答え</summary>

重みのファイルの `training_step`（SL の 150,000）から数え続けるから（train.py 222 行）。150,000 ＋ 70,000 ＝ 220,000。
</details>

### 5.2 続きから始める：zero-server.sh

- **読む所：** `minizero/scripts/zero-server.sh` の 89-100 行、104-122 行、123-140 行、146-151 行
- フォルダがあれば、やり直すか続けるかを聞く（97 行）。環境変数 `ZERO_RUN_STAGE` で答えを渡せる（93-95 行）。
- やり直し（104-122 行）：フォルダを消し、設定を書き、最初の重みを作る。
- 続き（123-140 行）：学習を終えた iteration の数 ＋ 1 から始める（129 行）。重みは一番新しい `.pt`（130 行）。設定はフォルダの中の `*.cfg`（131-132 行）。

> **問い 37：** 途中で止まったフォルダに sgf が 37 個あり、Training.log の `[Optimization] Finished.` が 36 行ある。何 iteration から再開するか？ なぜ sgf を数えないのか？

<details><summary>答え</summary>

37 から。自己対局を始めると sgf のファイルができるので、学習の前に止まっても sgf が残る。sgf を数えると、その iteration の学習を飛ばしてしまう（124-126 行）。
</details>

> **問い 38：** 続きから始めるときに、`configs/` の設定ファイルを編集していた。その変更は効くか？

<details><summary>答え</summary>

効かない。フォルダの中の `*.cfg` を読む（131-132 行）。変えたいときはフォルダの中の設定を直すか、`-conf_str` で渡す。
</details>

### 5.3 まとめて学習する：scripts/train_archs.sh

- **読む所：** `scripts/train_archs.sh` の 23-37 行（使い方）、51-69 行（`prune_run`）、72 行、82-132 行
- 11 構成を順に学習する。1 つ失敗しても次へ進む（121-122 行）。
- 最後の重みがある構成は飛ばす（97-100 行）。
- 終わった構成の重みは間引く（`KEEP_EVERY`。既定は 10 iteration ごと）。`.pkl` は最後だけ残す。

> **問い 39：** 途中で止まったフォルダがあるときに、`RESUME=1` なしで実行するとどうなるか？

<details><summary>答え</summary>

そのフォルダには触らず、次の構成へ進む（110-114 行）。最後に「left for a person」と表示する。
</details>

### 5.4 どの版で動いたかを確かめる

- **読む所：** `minizero/zero/zero_server.cpp` 30 行、`minizero/scripts/build.sh` 5、46-47 行。`scripts/build.sh` は minizero のものへのリンク
- Training.log の 2 行目の `[Version]` は minizero のコミットの 6 文字。既定のフォルダの名前の末尾も同じ。
- **`[Version]` は minizero のコミットだけを記録する。** build.sh は minizero のフォルダで `git describe` をするからである。
- 本体のコード（`restnet/learner/train.py`、`restnet/learner/network/` など）のコミットは、どの記録にも残らない。たとえば学習率の修正 413025a（train.py、11-05）は `[Version]` からは見えない。
- 保存した `.pt` にはネットワークの構造が入る（train.py 252 行）。学習の手順は入らない。
- Training.log の時刻はコンテナの時計で、日本時間より 1 時間遅い。

**学習を始めるときに、本体のコミットを控える。** 学習を始めるマシンのホストで、本体のフォルダで実行する：

```bash
git rev-parse --short HEAD
git status --short
```

> **問い 40：** サーバーで学習を始めたとき、どの版のプログラムで動いたかは、どこを見ればわかるか？

<details><summary>答え</summary>

minizero の版は、Training.log の最初の `[Version]` の行でわかる。quick-run.sh が始めるたびにプログラムを作り直すので、そのときのコードの版が書かれる。本体の train.py やネットワークの版は書かれない。始めるときに控えた本体のコミットを見る。
</details>

> **問い 41：** `[Version]` が `7a914c-dirty` だった。何を意味するか？

<details><summary>答え</summary>

minizero にコミットしていない変更があるコードで作った（build.sh 47 行の `--dirty`）。コミットの番号だけでは同じコードを再現できない。
</details>

> **問い 42：** 論文の R3(RRT) の `[Version]` は 8783e3 である。このとき使った train.py の版は確定できるか？

<details><summary>答え</summary>

記録からは確定できない。本体の git log で、minizero をその版に指すコミットと学習の日時を見れば、候補を絞れるだけである。
</details>
