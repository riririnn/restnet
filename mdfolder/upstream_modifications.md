# minizero / ResTNet の共通コードへの変更履歴（2026-09-05 作成）

将棋対応のために、全ゲーム共通のコードにどのような変更を加えてきたかの一覧。
「共通コード」とは `environment/shogi/` 以外のもの、つまり囲碁・オセロ・ヘックス等にも
影響しうる箇所を指す。

## 0. 比較の基準

**論文そのままの状態は親リポジトリの `39cbebf`（"IJCAI 2025 paper"）で、
これが指す minizero は `rlglab/minizero` の `78660b3`。**

注意点が2つある。

**親の `main` は既に論文の状態ではない。** 2つ目のコミット `dcff763` が submodule の参照先を
`rlglab/minizero` から `riririnn/minizero` に差し替えている（`.gitmodules` と参照先のみ、
親のコードファイルは `39cbebf` と同一）。

**fork 側の `main`（`04a5895`）は論文の状態より進んでいる。** `78660b3` との間に上流の5コミットがある。

```
78660b3   ← 論文（39cbebf）が指す状態。ここが真の基準
  ├ 9ba8eb3  modify stochastic env for supporting stochastic muzero
  ├ 84cb688  fix bugs in 2048 environment
  ├ 2819c31  add tetris block puzzle environment
  ├ 2974f58  add dockerfile && non-Docker installation instructions
  └ 04a5895  specify CMake version 3.25.2 in Dockerfile   ← riririnn/minizero の main
      └ 将棋対応 33コミット → da8dcd1（現在）
```

この文書は **`78660b3` を基準**にしている。`04a5895` を基準にすると、
上流由来の以下が見えなくなる（いずれも我々の変更ではない）。

```
README.md
minizero/environment/stochastic/puzzle2048/puzzle2048.cpp / .h
minizero/environment/stochastic/stochastic_env.h
minizero/environment/stochastic/tetrisblockpuzzle/*（新規3ファイル）
```

**確認範囲**: `environment/shogi/` と新規の研究用ファイル（`mdfolder/` `scripts/` 等）を除いた
変更ファイルを、両リポジトリとも1つずつ差分を読んだ。

```
minizero  変更24ファイル + 新規4
親        変更12ファイル
```

## 1. 全ゲームの挙動を変えうるもち（要注意）

| コミット | 日付 | 内容 | 影響 |
|---|---|---|---|
| `b3588df` | 2026-07-16 | 手数による greedy 切り替え | 設定次第。既定では従来通り |
| `10c3a47` | 2026-07-20 | MCTS プール上限と確保失敗時の `abort` | **後者は設定に関係なく全ゲーム** |
| `9e111a1` | 2026-06-02 | `sampleIndex` が 0 を返す | **設定に関係なく全ゲーム**（3-2） |
| `2fcbe37` | 2026-05-27 | 読み込み例外の握り潰し | **設定に関係なく全ゲーム**（3-3） |
| `80f90d7` | 2026-06-03 | SGF 指し手解釈の分岐 | 数字IDのみ分岐。囲碁等は従来通り（3-1） |
| `3dc354d` | 2026-06-03 | `build.sh` が graphviz を apt install | **設定に関係なく全ゲーム**（4-2） |
| `3dc354d` | 2026-06-03 | `zero-worker.sh` に `-X faulthandler -u` | **設定に関係なく全ゲーム**（4-3） |
| `766846c` | 2026-05-12 | CMake の pybind11 検出方法 | **全ゲームのビルド**（4-5） |
| `da8dcd1` | 2026-08-26 | value を手番視点にする | **将棋以外を壊している（未修正）** |

### `b3588df` — 手数による greedy 切り替え

`GumbelZero::decideActionNode()` に `greedy` 引数を追加し、`zero_actor.cpp` から渡す。

```cpp
- MCTSNode* decideActionNode(const std::shared_ptr<MCTS>& mcts);
+ MCTSNode* decideActionNode(const std::shared_ptr<MCTS>& mcts, bool greedy = false);

+ const bool greedy = config::actor_select_action_softmax_temperature_move_cutoff > 0 &&
+                     env_.getActionHistory().size() >= config::actor_select_action_softmax_temperature_move_cutoff;
```

既定値が 0 なら `greedy` は常に false なので、**設定しなければ従来と同じ**。
ただし引数の既定値が付いた分、シグネチャは全ゲームで変わっている。

### `10c3a47` — MCTS ツリープールの上限と、確保失敗時の停止

プールの大きさ自体は `actor_mcts_tree_max_children` が 0 なら `getActionSize()` を使う従来動作
（`actor_group.cpp`）。**設定しなければ従来と同じ。**

一方 `tree.h` の変更は**設定に関係なく全ゲームで効く。**

```cpp
- assert(current_node_size_ + size <= 1 + tree_node_size_);
+ if (current_node_size_ + size > 1 + tree_node_size_) {
+     std::cerr << "[Tree::allocateNodes] node pool exhausted: ..." << std::endl;
+     std::abort();
+ }
```

`assert` は Release ビルドで消えるため、従来はプールが溢れても**検査されずメモリを破壊**していた。
現在は必ず検査し、溢れたらメッセージを出して `abort()` する。

安全側の変更だが、**従来なら（破壊されながらも）走り続けた学習が、今は停止する。**
囲碁のように行動空間が小さいゲームでは溢れないはずだが、未検証。

### `da8dcd1` — value を手番視点にする（**未解決の不具合**）

将棋の `getValue()` を手番視点に変えた一方、`zero_actor.cpp`（全ゲーム共通）で
無条件に符号を反転させている。

```cpp
// zero_actor.cpp — 全ゲームが通る
float value = alphazero_output->value_;
if (env_transition.getTurn() == env::Player::kPlayer2) { value = -value; }
```

囲碁・オセロ・ヘックス・五目並べの `getValue()` は先手視点のままなので、
**それらのネットワークは後手番で符号が逆転する。**

```
go       getValue → getReturn()                 先手視点のまま
othello  getValue → getReturn()                 先手視点のまま
hex      getValue → getReturn()                 先手視点のまま
gomoku   getValue → getReturn()                 先手視点のまま
shogi    getValue → getReturn() * 符号反転        手番視点
```

**対処案**: `BaseEnv` に既定が恒等の仮想関数を足し、将棋だけ上書きする。

```cpp
// base_env.h
virtual float toFirstPlayerValue(float value) const { return value; }
// shogi.h
float toFirstPlayerValue(float value) const override
    { return turn_ == Player::kPlayer2 ? -value : value; }
```

## 2. 設定項目の追加（既定値では従来通り）

| コミット | 日付 | 追加した設定 | 既定値 |
|---|---|---|---|
| `f562e3f` | 2026-07-07 | `env_shogi_max_moves` | 500 |
| `f562e3f` | 2026-07-07 | `env_shogi_adjudication_no_draw` | false |
| `d274cac` | 2026-07-13 | `env_shogi_draw_value` | 0.0 |
| `3e444c8` | 2026-07-20 | 千日手・入玉宣言関連 | — |
| `4117ca4` | 2026-07-19 | 打ち切り局を引き分け扱い | — |

いずれも `configuration.cpp` / `configuration.h` にキーを足すもので、
`#elif SHOGI` で囲まれているか将棋専用の名前が付いている。**他ゲームには影響しない。**

ただし設定キーが増えると、`load_config_file` が未知キーで全設定を破棄する挙動
（`configure_loader.cpp:106`）に関わるため、**古い cfg との互換性には注意が要る**。

## 3. データ読み込み・学習まわり（**全ゲームの挙動が変わる**）

`sgf_loader.cpp` と `data_loader.cpp` は全ゲーム共通の経路。中身を確認した結果、
**設定に関係なく挙動が変わる箇所が3つある。**

### 3-1. `sgf_loader.cpp` — 指し手の解釈に分岐が入った

```cpp
+ if (!value.empty() && value[0] >= '0' && value[0] <= '9') {
+     action_str = value;                                    // 数字ID（将棋）はそのまま
+ } else {
+     action_str = actionIDToBoardCoordinateString(...);     // 従来（囲碁など）
+ }
```

囲碁・オセロ・ヘックスの SGF 座標は英字（`dd` 等）なので `else` に入り**従来通り**。
数字で始まる指し手を持つゲームがあれば挙動が変わるが、現状該当なし。

### 3-2. `data_loader.cpp` — `sampleIndex` が 0 を返すようになった

```cpp
+ float sum = std::accumulate(weight.begin(), weight.end(), 0.0f);
+ if (weight.empty() || sum <= 0.0f) { return 0; }
```

重みの合計が 0 以下のとき、従来は `std::discrete_distribution` がクラッシュしていた。
**全ゲームで、クラッシュの代わりに常にインデックス 0 が返る。**
異常を握り潰すため、サンプリングが偏っていても気付けない。

### 3-3. `data_loader.cpp` — 読み込み例外を握り潰すようになった

```cpp
+ try {
      if (env_loader.loadFromString(env_string)) { ... }
+ } catch (const std::length_error& e) { std::cerr << "[Parse Error] ..." }
+ catch (const std::exception& e) { std::cerr << "[Parse Error] ..." }
```

**全ゲームで、壊れたレコードは例外を出さずスキップされる。** 従来は落ちていた。
データが黙って減るため、学習データが想定より少なくても気付けない。

### その他

| コミット | 日付 | ファイル | 内容 |
|---|---|---|---|
| `a798ccf` | 2026-08-02 | `learner/train.py` | 設定読み込み失敗時の警告。全ゲーム。警告のみ |
| `b7a953a` `a141043` | 2026-06-03 | `zero/zero_server.cpp` | 空白の変更とコメント1行の追加のみ。挙動は不変 |
| `766846c` | 2026-05-12 | `utils/vector_map.h` | `#include <stdexcept>` の追加のみ |
| `0d9163b` `d233e2d` | 2026-05-19/06-02 | `environment/environment.h` | `#elif SHOGI` の分岐追加。他ゲームは不変 |
| `c4687c6` | 2026-07-29 | `console/console.h` | `cmdLoadSFEN` の宣言追加のみ |

## 4. コンソール・ツール・ビルドスクリプト

### 4-1. `console.cpp` / `console.h` — `load_sfen` コマンドの追加

`load_sfen` は将棋の SFEN を読むコマンドだが、`console.cpp` は共通ファイル。
他ゲームでは `setFromSFEN` が未実装なら失敗するだけで、既存コマンドには影響しない。

### 4-2. `scripts/build.sh` — **graphviz を勝手に導入する**（全ゲーム）

```bash
+ # mcts-dump: 探索木の図生成に graphviz が必要
+ if (( $(dpkg -l | grep graphviz | wc -c) == 0 )); then
+     apt -y update && apt -y install graphviz && pip install graphviz
+ fi
```

**ビルドするたびに `apt update` と `apt install` が走る。** 将棋に限らず全ゲームのビルドで実行され、
ネットワークアクセスとパッケージ導入を伴う。オフライン環境や権限の無い環境ではビルドが失敗しうる。

あわせて、git コマンドを `git -C "$repo_root"` に変えて別ディレクトリからでも動くようにし、
失敗時は `xxxxxx` にフォールバックするようにしている（`3dc354d`）。

### 4-3. `scripts/zero-worker.sh` — Python の起動オプション追加（全ゲーム）

```bash
- python ${op_executable_file} ...
+ python -X faulthandler -u ${op_executable_file} ...
```

`-X faulthandler` はクラッシュ時のスタックトレース出力、`-u` は出力のバッファ無効化。
**全ゲームの学習ワーカーに効く。** 挙動を壊すものではないが、出力のタイミングが変わる。

### 4-4. `tools/quick-run.sh` — 作業ディレクトリの固定（全ゲーム）

```bash
+ script_dir="$(dirname $(readlink -f "$0"))"
+ repo_root="${script_dir}/.."
+ cd "$repo_root"
```

どこから実行してもリポジトリ直下に移動する。**全ゲームで効く**が、
従来もリポジトリ直下からの実行が前提だったので実害は考えにくい。

### 4-5. CMake

| ファイル | 内容 |
|---|---|
| `minizero/learner/CMakeLists.txt` | pybind11 の検出方法を `CONFIG` モードに変更。全ゲーム |
| `minizero/environment/CMakeLists.txt` | `shogi` をビルド対象に追加。他ゲームは不変 |

pybind11 の検出方法変更は**全ゲームのビルドに効く**。環境によっては従来の書き方で
見つかっていたものが見つからなくなる可能性があるが、現環境では動作している。

### 4-6. Docker

| ファイル | 内容 |
|---|---|
| `docker/Dockerfile` | timm・einops・graphviz 等の追加。全ゲーム |
| `docker/Dockerfile.gpu` | 新規追加 |
| `scripts/start-container.sh`（親） | 既定イメージを `yanrudocker/restnet-go` → `restnet` に変更 |

**親リポジトリの `start-container.sh` は既定イメージ名を変えている。**
論文のイメージ（`yanrudocker/restnet-go`）ではなく自前ビルドの `restnet` を使う。

## 5. 親リポジトリ側（`restnet/`）

損失計算そのものは `nn_bv_flag=true`（囲碁の設定）で変えていないが、
**それ以外の箇所では囲碁のコード経路にも触れている。** 内訳を分けて記す。

### 5-1. 囲碁の起動方法が変わるもの（**要注意**）

| コミット | 日付 | 内容 |
|---|---|---|
| `e1daf0c` `460143e` | 2026-08-23/24 | `supervised_learning_bv_train.py` の引数を7個→8個に変更 |

```python
- if len(sys.argv) == 7:      # <training_dir> <model_file> <conf_file> ...
+ if len(sys.argv) == 8:      # <game_type> <training_dir> <model_file> <conf_file> ...
```

`build.go` 固定を `build.{sys.argv[1]}` にしたため、ゲーム名を第1引数で受ける必要が生じた。
**従来の呼び出し方では動かない。** 囲碁で使う場合は先頭に `go` を足す。

### 5-2. 囲碁でも修正として働くもの

| コミット | 日付 | 内容 |
|---|---|---|
| `e1daf0c` `460143e` | 08-23/24 | `from create_network` → `from network.create_network`（囲碁でも ImportError だった） |
| `2fac045` | 08-25 | `pybind.cpp` に `seed` を公開（囲碁でも AttributeError だった） |
| `e51738f` | 08-25 | `training_step` の未初期化を修正（囲碁でも NameError だった） |
| `af09fb5` `a9bc700` | 08-25/26 | `t_data_loader.cpp` の `RE` タグ解釈 |

**`RE` タグの修正は囲碁にも及ぶ。** `loadDataFromEnvFile` は全ゲーム共通の経路で、
元の実装は「先頭が `B` 以外なら -1」としていた。

```cpp
- env_loader.addTag("RE", (reold[0] == 'B' ? "1" : "-1"));
+ if (reold[0] == 'B') { ... "1" } else if (reold[0] == 'W') { ... "-1" }   // 数値はそのまま
```

minizero が自己対局で書く `RE` は `std::to_string(getEvalScore())` による**数値**（`RE[1.000000]` 等）。
手元の囲碁棋譜を確認したところ、実際に `RE[1.000000]` / `RE[-1.000000]` だった。

```
修正前: '1.000000' の先頭 '1' != 'B' → -1 に書き換え = 先手勝ちが後手勝ちに
修正後: 数値はそのまま                                = 正しい
```

**囲碁でも同じ破損が起きていた。** ただし論文の 19×19 囲碁が Tygem の SGF を
`loadDataFromBVFile`（SGF 用・`#if GO`・未変更）で読んでいたなら影響しない。
公開スクリプトは `load_data_from_env_file` しか呼んでおらず、どちらの経路を使ったかは不明。

### 5-3. 影響が無い、または限定されるもの

| コミット | 日付 | 内容 | 影響 |
|---|---|---|---|
| `1302b68` | 05-18 | `CMakeLists.txt` の pybind11 検出方法 | ビルド設定。全ゲーム |
| `0afc512` | 08-02 | `learner/train.py` に設定読み込み失敗の警告 | 全ゲーム。警告のみ |
| `e1daf0c` `460143e` | 08-23/24 | `#if GO` ガードの位置を移動 | `getDataSize` 等が全ゲームでコンパイルされるだけ |
| `e1daf0c` `460143e` | 08-23/24 | `getAlphaZeroSLData` の追加 | 新規関数。囲碁は呼ばない |
| `ef88938` `50dc2b3` `928bd86` | 08-23/24 | `tools/quick-run.sh` に `pretrain` モード | 既存モードは不変 |

`getValue()` を使うよう変えた `a9bc700` は `getAlphaZeroSLData` 内なので、囲碁は通らない。

## 6. 検証の状況

| 項目 | 状態 |
|---|---|
| 将棋での動作 | 確認済み（教師あり学習・自己対局とも） |
| **囲碁での動作** | **未検証** |
| オセロ・ヘックス・五目並べ | **未検証** |

囲碁に及ぶ変更は次の3種類。実行して確かめたものは無い。

1. `da8dcd1` の value 符号反転 — **壊している**（コードから確実）
2. `supervised_learning_bv_train.py` の引数仕様 — 呼び出し方が変わる
3. `RE` タグ解釈・`seed` 公開・import パス — いずれも囲碁でも修正として働くはず

`da8dcd1` が他ゲームを壊していることは**コードから確実**だが、それ以外の変更が
他ゲームに実害を与えているかは確かめていない。

論文の数値を再現する必要が生じた場合は、`origin/main`（`04a5895`）に戻して
検証するのが確実。

## 7. 論文の状態に戻す方法

囲碁の数値を再現する必要が生じたときは、submodule ごと戻す。

```bash
git checkout 39cbebf              # 親（IJCAI 論文そのまま）
git submodule update --init       # minizero を 78660b3 に戻す
```

`main` を使うと `dcff763` の submodule 差し替えが入るので、論文の再現には `39cbebf` を使う。

## 8. 次にやるべきこと

1. `da8dcd1` の影響を将棋に限定する（`toFirstPlayerValue` の導入）
2. 囲碁で `restnet-models/10B-go-19-models/` を使い、value の視点問題が実在するか実測する
3. `sgf_loader.cpp` / `data_loader.cpp` の変更が他ゲームの読み込みを壊していないか確認する

## 関連

- `mdfolder/value_perspective_check.md` — value の視点の不一致
- `mdfolder/value_overfitting.md` — value の過学習
- `mdfolder/bootstrap_pretraining.md` — 事前学習の手順
