
# 人間棋譜によるブートストラップ事前学習（2026-08-02 作成）

lishogi の高レート帯の棋譜で policy / value を教師あり事前学習し、その重みを self-play の初期モデルにするための手順。
データ収集から学習、self-play への引き継ぎまでをコマンドで管理できるようにまとめる。

## どのコードで学習するのか

`restnet/learner/supervised_learning_bv_train.py`。論文リポジトリに元から入っている教師あり学習器。

**公開されている状態のままでは、囲碁でも実行できない。** スクリプトと pybind の対応表が噛み合っておらず、
未定義変数も残っている。README に教師あり学習の実行手順が無く（配布されているのは学習済みモデルのみ）、
API リファレンスが "WIP" 表記であることとも符合する。著者は手元の別バージョンで実行したと思われる。

将棋で動かすために直した箇所は5点。いずれも新機能ではなく、噛み合っていない部分を繋いだだけ。

| 症状 | 原因 | 対応 |
|---|---|---|
| `ModuleNotFoundError: build.go` | 囲碁固定 | `build.{sys.argv[1]}` にしてゲーム名を第1引数で受ける |
| `ImportError: create_network` | `network/` へ移動済み | `from network.create_network import`（`train.py:9` と同じ） |
| `KeyError: 'bv'` | 将棋に board evaluation が無い | `nn_bv_flag` が false なら policy / value だけ学習 |
| `AttributeError: no attribute 'seed'` | pybind に未登録 | `pybind.cpp` で `utils::Random::seed` を公開 |
| `NameError: training_step` | `__main__` で未初期化 | `model.training_step` に統一（保存ファイル名と同じカウンタ） |

`nn_bv_flag=true` のときの挙動は変えていないので、囲碁の再現性には影響しない。

### policy の教師信号

`minizero/minizero/environment/base/base_env.h:246` の `getPolicy()` は `P[]`（MCTS訪問回数分布）が空なら
**指された手の one-hot** を返す。生成したレコードに `P[]` は無いので、この分岐が働く。

```cpp
if (policy_distribution.empty()) {
    policy[getRotateAction(action_pairs_[pos].first.getActionID(), rotation)] = 1.0f;
}
```

### value の教師信号（要修正だった箇所）

値は `base_env.h:298` の `getReturn()`（`RE` タグを数値として読む）で取る。
しかし読み込み時に `t_data_loader.cpp` が `RE` を上書きしていた。

```cpp
env_loader.addTag("RE", (reold[0] == 'B' ? "1" : "-1"));   // 修正前
```

囲碁 SGF の `RE[B+3.5]` を前提に「先頭が `B` 以外なら -1」としているため、
将棋の `RE[1]`（先手勝ち）は `'1' != 'B'` で **-1 に書き換わり、すべて後手勝ちとして学習されていた**。
`RE[0]`（引き分け）も -1 になる。数値の `RE` はそのまま通すよう直した（`t_data_loader.cpp:30`）。

## 0. 全体の流れ

すべて `tools/quick-run.sh` から実行できる（コンテナ内、`/workspace` から）。

```bash
# 0. ビルド（C++ を変更したときだけ。BUILD_TYPE は release か debug）
scripts/build.sh shogi release

# 1. 棋譜を集めて学習レコードに変換する
tools/quick-run.sh pretrain shogi data --min-rating 1800 --target-games 300000

# 2. 事前学習（NAME STEPS [CFG]）。まず短く回して様子を見る
tools/quick-run.sh pretrain shogi train  shogi_9x9_human 5000

# 3. 続きを足す
tools/quick-run.sh pretrain shogi resume shogi_9x9_human 30000

# 4. self-play へ引き継ぐ（通常の train モードに --pretrained を足すだけ）
tools/quick-run.sh train shogi configs/9x9_shogi/RRTRRT.cfg 500 \
    -n shogi_9x9_from_human --pretrained models/shogi_9x9_human/model/weight_iter_30000.pt
```

`NAME` は出力先ディレクトリ名。**`quick-run.sh` が自動で `models/` 配下に置く**ので、
`shogi_9x9_human` と書けば `models/shogi_9x9_human/` になる（`train` モードの `-n` も同じ）。
`models/` は `.gitignore` 済み。論文の配布モデルを置く `restnet-models/` とは分けてある。

`STEPS` は**到達する累計ステップ数**。`supervised_learning_bv_train.py:183` が
`range(model.training_step, training_step_limit)` で回すため、再開時は現在のステップ数から数える。
5,000 から始めるのは、**モデルの保存が 5,000 ステップ単位**だから
（`supervised_learning_bv_train.py:274` の `if training_step % 5000 == 0`）。
これ未満で終えると学習は走るが重みが1つも残らない。

CFG を省くと `configs/9x9_shogi/RRTRRT-bootstrap.cfg` を使う。

ログは `models/NAME/pretrain.log` に追記される（`quick-run.sh` が `tee -a` を挟む）。
resume しても同じファイルに続けて書かれる。

## 1. データ収集

### コマンド

```bash
tools/quick-run.sh pretrain shogi data --min-rating 1800 --target-games 300000

# 引数はそのまま build_dataset.py に渡る。直接叩いてもよい:
# レート分布だけ見る（データセットは作らない）
python3 scripts/bootstrap/build_dataset.py --stats --target-games 500
# 生データはそのままに、閾値だけ変えて作り直す（ダウンロード無し・数秒）
python3 scripts/bootstrap/build_dataset.py --no-fetch --min-rating 2100
```

### 主なオプション

| オプション | 既定 | 意味 |
|---|---|---|
| `--min-rating` | 2000 | **両者**がこのレート以上の対局だけ採用 |
| `--target-games` | 10000 | 採用可能な局数がこれに達したら収集を打ち切る |
| `--games-per-user` | 300 | 1プレイヤーあたり取得する対局数の上限 |
| `--min-moves` | 20 | これ未満の手数の対局を除外 |
| `--pause` | 1.0 | リクエスト間隔（秒）。下げすぎない |
| `--stats` | - | レート分布と閾値ごとの残存局数だけ表示 |
| `--no-fetch` | - | ダウンロードせず、手元の生データから作り直す |

### 収集の仕組み

lishogi API に「両者◯◯以上の対局」を返す機能は無い。指定できるのは**プレイヤー単位**だけなので、次の順で絞る。

1. `https://lishogi.org/player/top/200/realTime` からレート付きで上位200人を取得
2. レート降順（= lishogi の段位バッジ順。段位はレートの区分表示）で処理
3. 採用された対局に現れた相手のうち、レート条件を満たす者をキューに追加して探索を広げる
4. `--target-games` に達するか、キューが尽きたら終了

対局相手のレートは取得後にしか分からないため、最終的な絞り込みは変換時に行う。
強い人ほど格下と多く対局するので、**取得数の 1〜2 割しか残らない**のは正常。

### Bot の除外

lishogi はエンジンのアカウントに `title: "BOT"` を付ける。API のレスポンスにそのまま入っているので、
どちらかが BOT の対局は変換時に落とす（`build_dataset.py` の `is_bot()`）。
「人間の棋譜で事前学習した」と書く以上、ここは外せない。実測で全体の 3.2% にあたる。

```json
{"user": {"name": "Tayayan-BOT", "title": "BOT", "id": "tayayan-bot"}, "rating": 2082}
```

`PRO`（棋士）、`BgM`、`LP` といったタイトルも同じ場所に入る。除外しているのは `BOT` のみ。

### 利用条件について

論文でデータソースを説明するときに必要になるので、確認した事実を残しておく（2026-08-24 時点）。

- **利用規約**（`/terms-of-service`）に自動アクセス・スクレイピングの禁止条項は無い。
  「personal, educational, charitable, or developmental purposes」での利用を認める記述があり、
  「インフラに不合理な負荷をかけない」という一般条項がある。棋譜の権利は投稿者が保持する。
- **robots.txt に `Disallow: /api/` がある。** 使用している `/api/games/user/{name}` はこれに該当する。
  一方で開発者向けページには "Lishogi exposes a RESTish HTTP/JSON API that you are welcome to use." とあり、
  API リファレンス（`/api`）は WIP でレート制限も明記されていない。
- lichess にある公式データベース配布（CC0）に相当するものは lishogi には無い。

負荷への配慮として、リクエスト間隔 1 秒（`--pause`）、429 で指数バックオフ、
User-Agent に用途と連絡先を明記している。

## 2. データの場所と形式

```
data/bootstrap/raw/*.ndjson   lishogi の生レスポンス（1プレイヤー1ファイル、1行1局）
data/bootstrap/sgf/train.sgf  学習レコード（1行1局）
data/bootstrap/sgf/test.sgf   検証レコード（学習に使わない 3,000局）
data/bootstrap/logs/          収集・学習ログ
```

生データを残してあるので、閾値を変えても再ダウンロードは不要。`data/bootstrap/` は `.gitignore` 済み。

学習レコードの形式（`base_env.h:219` の `toString()` と同形）:

```
(;GM[shogi]SZ[9]RE[1]EV[lishogi]BR[2209]WR[2135];B[7831];W[8491];...)
```

`RE` は先手視点で勝ち +1 / 負け -1 / 引き分け 0。`P[]` を付けないことで one-hot policy 教師になる。

## 3. 品質チェック

```bash
python3 - <<'EOF'
import collections, re
recs=[l.strip() for l in open("data/bootstrap/sgf/train.sgf") if l.strip()]
print("レコード数:", len(recs))
print("完全重複:", sum(v-1 for v in collections.Counter(recs).values() if v>1))
print("指し手列の重複:", sum(v-1 for v in collections.Counter(
    re.sub(r'^\([^;]*','',r) for r in recs).values() if v>1))
ids=[int(x) for r in recs for x in re.findall(r';[BW]\[(\d+)\]',r)]
print("action id 範囲外:", sum(1 for i in ids if i<0 or i>11258), f"(全{len(ids):,}手)")
print("RE分布:", collections.Counter(re.search(r'RE\[(-?\d+)\]',r).group(1) for r in recs))
EOF
```

指し手が実際に盤面上で成立するかは、レコードを CSA に戻して確認できる。

```bash
head -1 data/bootstrap/sgf/train.sgf > /tmp/one.sgf
python3 scripts/sgf_to_csa.py /tmp/one.sgf | head -20
```

`sgf_to_csa.py` は盤面を再生して駒種を判定するため、action id が誤っていれば破綻する。独立した検証になる。

判断基準: 先手勝率が 50% 付近から大きく外れていたら変換ミスを疑う。

## 4. 事前学習の実行

```bash
tools/quick-run.sh pretrain shogi train shogi_9x9_human 5000
```

`models/shogi_9x9_human/model/` を作り、次を実行して出力を `models/shogi_9x9_human/pretrain.log` に残す。

```bash
PYTHONPATH=. python3 -u restnet/learner/supervised_learning_bv_train.py \
    shogi models/shogi_9x9_human "" configs/9x9_shogi/RRTRRT-bootstrap.cfg 5000 \
    data/bootstrap/sgf/train.sgf data/bootstrap/sgf/test.sgf
```

第3引数の `""` は「初期モデル無し（ゼロから）」の意味。
保存先は `model/weight_iter_<累計ステップ>.pkl|.pt` で、`supervised_learning_bv_train.py:274` により
**5,000ステップごと**に書かれる。

**リプレイバッファの上限は無い。** `t_data_loader.cpp` の `loadDataFromEnvFile()` はファイルの全行を
`env_loaders_` に読むだけで、破棄処理を持たない。`zero_replay_buffer` はこの経路では使われない。

### ステップを追加する

`training_step` と optimizer の状態は `.pkl` に保存されるので、続きから回せる。

```bash
tools/quick-run.sh pretrain shogi resume shogi_9x9_human 30000
```

`model/` の最新チェックポイントを自動で選び、**累計で** 30,000 ステップに達するまで回す。

### 進捗の確認

`learner_training_display_step`（既定 100）ごとに、学習データと検証データの両方が出る。

```
[2026-08-24 10:15:44] nn step 100, lr: 0.1.
	loss_policy: 6.12345
	accuracy_policy: 0.02341
	loss_value: 1.00012
	test_loss_policy: 6.13012
	test_accuracy_policy: 0.02198
	test_loss_value: 0.99987
```

`test_` 付きが検証データ（学習に使っていない3,000局）での値。
最後に `Optimization_Done <step>` が出れば正常終了。

```bash
tail -f models/shogi_9x9_human/pretrain.log
grep -E "nn step|accuracy_policy|loss_value" models/shogi_9x9_human/pretrain.log | tail -20
```

test 側が改善しなくなったら過学習の開始なので、そこで止める。

## 5. self-play への引き継ぎ

通常の train モードに `--pretrained` を付けるだけで、以降は普段どおりの self-play になる。

```bash
tools/quick-run.sh train shogi configs/9x9_shogi/RRTRRT.cfg 500 \
    -n shogi_9x9_from_human --pretrained models/shogi_9x9_human/model/weight_iter_30000.pt
```

**モデルを外から指すことはできない。** `zero-server.sh:131` は `nn_file_name` を学習ディレクトリ内のs
ファイル名で常に上書きするので、ユーザーが `-conf_str nn_file_name=...` を渡しても効かない。
さらに `zero_server.cpp:180` はその名前の `weight_iter_<N>` を開始 iteration として読み、
以降 `zero_training_directory/model/weight_iter_<N>.pt` を参照する。
`weight_iter_30000.pt` のまま置けば **「30000 イテレーション完了済み」と誤認される**。

そのため `--pretrained` は、新しい学習ディレクトリを作って重みを **`weight_iter_0`** として置き、
`(C)ontinue` を自動で答えて self-play を始める。config は指定した `-conf_file` から作り直すので、
事前学習用に `learner_training_step` を書き換えた config は引き継がれない。
既存ディレクトリを指定した場合は上書きせずエラーになる。

引き継ぎが成功していれば、`Training.log` に `[SelfPlay] Start 0` が出て、
生成される棋譜のヘッダが `EV[weight_iter_0.pt]` になる。

## 6. 実測値（2026-08-02、旧経路 `train.py`、8,939局 894,348手、RRTRRT、batch 512、lr 0.02）

| step | accuracy_policy | loss_value |
|---|---|---|
| 250 | 3.0% | 1.0006 |
| 1000 | 17.2% | 0.9954 |
| 2000 | 26.9% | 0.9949 |
| 3000 | **31.3%** | 0.9950 |

policy は明確に学習する。行動空間 11,259 に対しランダムは 0.01% 程度なので、31.3% は十分な事前学習効果。

**value は 3000 ステップでは動かない。** これは実装の問題ではない。50局（4,372局面）に絞った過学習診断では
2000 ステップで `loss_value` 0.995 → **0.089**、`accuracy_policy` 97.3% まで下がるため、
データ経路も value 教師信号も正しく届いている。

`loss_value ≈ 0.995` は「常に 0 を出力している」状態に対応する（教師が ±1 の MSE なので分散 ≒ 1）。
89万局面に対し 3000 ステップ（約1.7周）では足りず、かつ人間の棋譜からの勝敗予測は本質的に難しい。
value まで学習させるなら桁違いのステップ数（3万〜10万）が要る。

### 実測値（2026-08-25、本家経路、68,203局 6,443,538局面、RRTRRT、batch 1024、lr 0.1）

| step | accuracy_policy | test_accuracy_policy | loss_value | test_loss_value |
|---|---|---|---|---|
| 100 | 2.6% | 2.4% | 1.0537 | 1.1358 |
| 5000 | **39.5%** | **38.3%** | 0.9975 | 0.9964 |

**policy は旧経路を上回る。** 5000ステップ（0.79周）で 39.5%。ランダムは 1/11259 = 0.009% なので約4,400倍。

**過学習していない。** 学習 39.5% に対し検証 38.3% で、差は1.2ポイント。検証データは学習に使っていない。
当初懸念した「データ量不足による暗記」は起きていない。

step 100 で `test_loss_policy` が 63.9（学習側の9.5倍）と乖離したが、5000 では 2.43 対 2.35 まで縮んだ。
BatchNorm の移動平均が追いついていないための一時的な現象で、精度は当初から乖離していない。

**value は動かない。** データ7倍・batch 2倍・lr 5倍（0.02→0.1）でも 0.997 のまま。
**学習率が原因ではないことが判明した。**

速度は 2.66 ステップ/秒（実測）。150,000 ステップで 23.8周、約15時間。

## 7. 落とし穴

### 設定ファイルの読み込み失敗

`load_config_file` は**未知のキーが1つでもあると全設定を破棄**して `false` を返す
（`minizero/minizero/config/configure_loader.cpp:106`）。
以前は戻り値を確認しておらず、警告なくデフォルト設定（`training_step=500`, `batch_size=1024`, 既定ネットワーク）で
学習が走っていた。現在は `restnet/learner/train.py` と `minizero/minizero/learner/train.py` の両方に警告を追加済み。

```
WARNING: failed to load <cfg>; using default settings
```

このメッセージが出たら学習を止めて config を直すこと。直前に `Invalid key "..."` が出るのでキー名が分かる。

### 再開時にメトリクスが実際より小さく表示される

`supervised_learning_bv_train.py:236` は累積した損失を、実際に累積したステップ数ではなく
**常に `learner_training_display_step` で割る**。表示は通算ステップ数が間隔の倍数になった時点で出るので、
間隔の倍数でないチェックポイントから再開すると、最初の行だけ値が一律に縮む。
チェックポイントは 5,000 ステップごと、表示間隔の既定は 100 なので通常は割り切れる。

### GPU メモリが解放されない

`docker exec` で起動したプロセスには端末を閉じても SIGHUP が届かず、コンテナ内に残り続ける。
過去に `xai_app.py` が8個積み上がり 13.7GB を占有していた。

```bash
# 何が使っているか確認
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | while IFS=, read p m; do
  echo "$m | $(ps -o etime=,args= -p $(echo $p|tr -d ' ') 2>/dev/null | cut -c1-80)"
done

# 掃除
docker exec $CONTAINER pkill -f xai_app.py
```

XAI を起動するときは `docker exec -d` で起こして、後から `pkill` で確実に落とす運用が安全。

### ビルドの取り違え

`minizero/build/`（2026-06-03 の古いビルド）は削除済み。使うのは `build/shogi/` のみ。
古いビルドは現在の config を受け付けず、上記の「設定読み込み失敗」を引き起こしていた。

## 8. 決定の経緯

論文（4.1.2節）は 19×19 囲碁だけを教師あり学習している。Tygem の人間棋譜100万局（7〜9段）を
150,000 ステップ。理由は "to reduce the computational costs of training models from scratch"。
9×9 囲碁と 19×19 ヘックスは自己対局なので、**教師あり学習の前例は 19×19 囲碁しかない**。

### データソースに lishogi を選んだ理由

floodgate（wdoor）も検討し、2019〜2025年の859,948局を展開して比較した。

| | lishogi | floodgate |
|---|---|---|
| 対局者 | 人間 | エンジン |
| レート付与率 | 100% | 78% |
| プールの上限 | 2506 | 4624 |
| 弱い対局の混入 | 少ない | 多い（テスト用エンジンが418など） |

**論文が人間の棋譜を使っているので lishogi を採用した。** 研究目的が XAI であり、
「人間の棋譜で事前学習した」という記述の方が論文で筋が通るという判断。
floodgate 版のデータセット（3650以上、158,397局）も `data/floodgate/` に残してある。

どちらのレートも**プール内の相対値**で、絶対的な棋力を意味しない。Elo は差分しか定義されず、
共通の対戦相手がいないプール間の数値は比較できない。棋力を主張するなら、
`scripts/run_elo.sh` で固定した参照相手と直接対戦させて測るしかない。

### レート閾値を 1800 にした理由

論文の「7〜9段」を lishogi の段位バッジ（レートの区分表示）に当てはめると 2245 以上になるが、
**該当する対局は105局しかない**。lishogi は将棋のプラットフォームとしてはマイナーで、
7段は4人、8段は1人しかいない。

| 閾値 | 段位 | 棋譜数 | 局面数 |
|---|---|---|---|
| 2245 | 7段以上（論文と同条件） | 105 | 1万 |
| 2118 | 6段以上 | 1,453 | 14万 |
| 1975 | 5段以上 | 13,479 | 130万 |
| 1849 | 4段以上 | 47,082 | 448万 |
| **1800** | **採用** | **71,203** | **673万** |

段位を論文に合わせると棋譜数が壊滅し、棋譜数を確保すると段位が下がる。両立できないので、
**棋譜数を優先した**。論文には段位ではなくレート値で記述する（1800 は段位の境界と一致せず、
3段の一部が混じるため）。

### ネットワーク構成を RRTRRT のままにした理由

論文は盤面サイズごとに構成を変えている。**9路盤は RRTRRT（6ブロック）で、これが最良の構成**
（勝率60.80%）。10ブロックの R3(RRT) は 19×19 用。現在の将棋設定は 9路 の構成と一致しており、
変更不要だった。

### 学習率と batch を論文値にした理由

将棋の既存 config は自己対局用に調整された値（lr 0.02 / batch 512）だった。
教師あり学習は別の工程なので、論文 Table 4 の値（lr 0.1 / batch 1024）に合わせた。
サーバー負荷に関わる設定（スレッド数、並列数）は `RRTRRT-bigserver.cfg` のまま維持している。
差分は2行だけ（`configs/9x9_shogi/RRTRRT-bootstrap.cfg`）。

## 9. floodgate の棋譜（2026-11-02 追加）

自己対局の初期値を強くする目的で、人間の lishogi より局数の多い floodgate（エンジンの対局）を
使う。手元の生データ（`data/floodgate/raw/<年>/*.csa`、2019〜2026 年、971,913 局）から作る。
両者のレートが 2250 以上の 556,309 局（train 553,309、test 3,000）、74,403,735 局面、
1 局平均 133.7 手。結果は先手勝ち 52.4%、後手勝ち 44.5%、引き分け 3.0%。

```bash
# ローカルのコンテナ内、/workspace。python-shogi（CSA の読み込み）が要る。CPU 8 並列で約 10 分
pip install python-shogi
PYTHONPATH=build/shogi python3 scripts/bootstrap/build_floodgate.py data/floodgate/raw data/floodgate/sgf_2250 --min-rating 2250 --jobs 8
# 確認（records：全 ID が合法で、終局前に終わる）
PYTHONPATH=build/shogi python3 scripts/shogi_env_check.py '' 0 data/floodgate/sgf_2250/test.sgf
# 事前学習はデータの場所を DATA で渡す（既定は data/bootstrap/sgf）。構成ごとに *-bootstrap.cfg
DATA=data/floodgate/sgf_2250 tools/quick-run.sh pretrain shogi train shogi_9x9_fg_10T 5000 configs/9x9_shogi/10T-bootstrap.cfg
```

- 残す終局は toryo・sennichite・oute_sennichite・kachi で、結果は `'summary` 行から取る。
  time up・abnormal・illegal・古い 256 手打ち切りは捨てる
- 全局を環境で再生し、環境が生成しない手（角・飛・歩の不成、香の下 2 段への不成）と、環境が
  規則で終局にしたところ（実戦では宣言が遅れただけの入玉宣言）で打ち切る。2250 以上では
  不成で切れた局 13,670、規則上の終局で切れた局 5,874
- 1 エポック ≈ 72,700 ステップ（batch 1024）。train.sgf は 608 MB で、読み込みは 7 秒、
  メモリは 3.8 GB（1 局 6.8 KB）。それまでは 1 局 92 KB（55 万局で約 51 GB、再確保時はその 2 倍）
  だった。原因は `minizero/utils/vector_map.h` の入れ物が std::deque で、1 手ごとの付加情報が
  空でも約 600 バイトを確保していたこと。2026-11-02 に std::vector に戻した
- `*-bootstrap.cfg` は `RRTRRT-bootstrap.cfg` の `nn_num_blocks` と `nn_blocks_type` だけを
  サーバー用の `*-bigserver.cfg` に合わせたもの（10T、R3RRT、10R）。Network の節が同じでないと
  `--pretrained` で重みを読めない

### 学習率 0.1 では value の頭が飽和する（2026-11-02 測定）

サーバーで 10T（lr 0.1、batch 1024）を 5,000 ステップ回したところ、loss_value が最初の
100 ステップで 1.87、以後 1.99 のまま動かなかった。value の出力は tanh で −1〜1、正解は
±1（引き分け 0 が 3%）なので、常に +1（または −1）を出すと 0.485×4 + 0.03 = 1.97 になる。
つまり最初の数ステップで tanh が張り付き、勾配が消えて戻れない。policy もステップ 2,200 で
損失 4.7 → 6.5 に跳ねた。

ローカル（16 GB の GPU）で 300 ステップずつ切り分けた：

| 構成 | lr | batch | loss_value（ステップ 20 → 260） | 正解率（260） |
|---|---|---|---|---|
| 10T | 0.1 | 512 | 1.77 → 1.94（飽和） | 1.7% |
| 10T | 0.02 | 512 | 0.96 → 0.92（学習している） | 4.6% |
| R3(RRT) | 0.1 | 1024 | 1.84 → 1.99（飽和） | 3.7% |
| R3(RRT) | 0.1 | 512 | 1.58 → 1.12 → 0.95（境界上） | 2.9% |
| R3(RRT) | 0.02 | 1024 | 1.00 → 0.92（学習している） | 4.2% |
| 10R | 0.1 | 1024 | 1.90 → 1.96（飽和） | 3.6% |
| 10R | 0.02 | 1024 | 1.02 → 0.92（学習している） | 4.4% |

lr 0.1 は論文が 19×19 囲碁の 10R・R3(RRT) で使った値だが、ここでは batch 1024 で 10R・R3(RRT)・
10T のすべてが飽和する（R ブロックがあれば安定、という仮説は 10R の結果で否定された）。
lr 0.02 は 3 構成とも学習する。`*-bootstrap.cfg` の学習率を 0.02（自己対局と同じ）にした。
10T × lr 0.02 × batch 1024 の組だけは手元に載らず未測定で、サーバーの試しの最初の 100 ステップで
loss_value が 1.0 付近に留まることを見て確認する。

8 月の lishogi の RRTRRT（lr 0.1）で飽和しなかった理由は未確認（当時は value の正解が
先手視点で入力と食い違っていたので、同じ条件ではない）。

lishogi の builder も同じ打ち切りをするようにした（それまでは合法性を見ておらず、
`known_bugs.md` の #11）。

### self-play への引き継ぎで見つけた 2 つの不具合（2026-11-05）

サーバーで 10T の `--pretrained` を始めたところ、`Failed to start zero training server` で止まった。

1. **サーバーの起動スクリプトが何も言わずに終わる。** `minizero/scripts/zero-server.sh` は `set -e` で動く。
   続きから始めるとき `ls sgf/ | grep -c ".sgf$"` で棋譜の数を数えるが、`grep -c` は 0 件のとき終了コード 1 を返す。
   `--pretrained` で作った学習フォルダには棋譜がまだないので、ここで終わる（2026-10-05 にこの行を足した後、引き継ぎを
   試していなかった）。`|| true` を足した。
2. **学習率の減衰の倍率が 0.1 になる。** 学習器は事前学習の .pkl を一度だけ読み、その scheduler の状態も読む。
   事前学習の scheduler は `StepLR(gamma=0.1)` なので、self-play の `MultiStepLR` の gamma が 0.1 に置き換わる。
   本物の 10T の .pkl で確かめると、減衰の位置で 0.02 → 0.002 になった（0.01 のはず）。`restnet/learner/train.py` で、
   読んだ後に設定の減衰の位置と倍率を入れ直すようにした。

減衰の位置：self-play は事前学習の 150,000 ステップから数え続けるので、論文の 70,000・90,000 は 220,000・240,000 になる。
3 つの `*-bootstrap.cfg` に `learner_lr_decay_steps=220000,240000` と `learner_lr_decay_gamma=0.5` を足した。

ローカルで本物の 10T の重みから 2 iteration（8 局、20 ステップ、減衰の位置は試しに 150,010・150,030）を回して確かめた：
1 iteration 目の 8 局はすべて `EV[weight_iter_0.pt]`、学習器は 150,005 ステップで 0.02、150,010 で 0.01、150,030 で 0.005、
モデルは weight_iter_150020 と 150040。

**self-play の棋譜が短い（判断が要る）。** この試しの 16 局は 12〜32 手（平均 19.5・28.5 手）で、すべて投了だった。
論文の self-play（R3(RRT)、ゼロから）は 1 iteration 目 180 手、500 iteration 目 160 手。理由：self-play では手を
探索の結果から確率的に選ぶので、指した手の 45% は policy の確率 0.05 未満の手で、早い段階で駒を落とした側が
value −0.9 未満になり投了する（勝つ側の value は +0.34〜+0.93 で、符号は正しい）。1 iteration あたりの局面が
論文の 1/8 ほどになる。論文と同じ設定（投了 −0.9、10% は投了なし）のまま始め、最初の数十 iteration の
`[SelfPlay Avg. Game Lengths]` を見る。

**3 つ目（2026-11-05 夜、見直しで見つけた）：再開すると、止まった iteration の学習を飛ばす。** self-play はその iteration の
sgf を始めに開くので、self-play か学習の途中で止まると、終わっていない iteration の sgf が残る。再開のときに sgf の数を
数えると、その iteration を終わったものと数え、学習（200 ステップ）をせずに次へ進む。`zero-server.sh` を、Training.log の
`[Optimization] Finished.` を数えるように直した。例：v2 の 3R3T は学習を終えた iteration が 125、sgf が 126 で、
前の数え方では 127 から再開して 126 の学習を飛ばす。今サーバーで動いている学習には、再開しない限り関係しない。

### 事前学習のモデルは self-play を始めてよいか（2026-11-05）

AlphaGo（2016）も AlphaGo Zero（2017）も、事前学習の止め時の規則は書いていない。決まった日程で学習し、
見ていない棋譜での一致率、過学習がないこと、対局の強さを示している。同じ 3 つを確かめた
（`scripts/sl_model_check.py`、floodgate の test.sgf 3,000 局の 10%、39,654 局面）。

| | 最後の 50,000 ステップの test の policy の損失 | 一致率（1 位） | 上位 5 位に入る | value の符号が勝敗と合う | 二乗誤差 | \|value\| > 0.99 の割合（その符号が合う割合） |
|---|---|---|---|---|---|---|
| 10T | 1.791 → 1.729 | 0.474 | 0.842 | 0.752 | 0.621 | 9.5%（99.8%） |
| R3(RRT) | 1.625 → 1.591 | 0.504 | 0.866 | 0.755 | 0.614 | 8.6%（99.9%） |
| 10R | 1.626 → 1.592 | 0.502 | 0.867 | 0.760 | 0.608 | 12.0%（99.7%） |
| 論文の R3(RRT)（self-play 500） | — | 0.195 | 0.445 | 0.595 | 0.915 | 0% |
| self-play の 10R（500 iteration、論文と同じ設定。論文にはない） | — | 0.220 | 0.460 | 0.573 | 0.932 | 0% |

- 3 つとも test の損失は下がり続けている。train との差は 0.03〜0.05 で、最後の 50,000 ステップで 0.005〜0.011 広がった（10T 0.029 → 0.040、R3(RRT) 0.040 → 0.045、10R 0.041 → 0.046）。test の損失が上がっていないので過学習ではない。
- 一致率はログの test の値（最後の 5,000 ステップで 10T 0.483、R3(RRT) 0.509、10R 0.509）より 0.005〜0.009 低い（数え方と局面が違う。差の理由は確かめていない）。test の 3,000 局のうち 115 局（手の 3.4%）は同じ手順の棋譜が train にもあり（そのうち 28 局は行ごと同じ）、一致率はこれらを含めて数えた。
- value の符号の一致は手数とともに上がる（10T：30 手まで 0.625、101 手以降 0.898）。
- 対局の強さ（`scripts/usi_bridge.py`、1 手 1 秒、data/openings.tsv の序盤から先後を入れ替えて 40 局、結果は `models/9x9_shogi/sl_check/`）：
  SL の R3(RRT) 対 論文の R3(RRT) 40 勝 0 敗、SL の 10R 対 self-play の 10R（論文と同じ設定。論文にはない）40 勝 0 敗、SL の 10T 対 論文の R3(RRT) 40 勝 0 敗（論文の 9×9 は R3(RRT) だけ）。

## 10. 残課題

- value の視点は 2026-09-08 に手番視点へ直した（`known_bugs.md` の #1、`shogi.h` の `getValue`）。
  `scripts/shogi_env_check.py` の value の確認で、記録から作る正解が手番側の値であることを見る。
- 学習率が減衰しない。`StepLR(step_size=1000000)` なので現実的な範囲では 0.1 のまま。
  精度を詰める段階になったら減衰の導入を検討する。
- 同一対戦ペアの偏りがある（最多で87局）。序盤が似た棋譜が偏る可能性があり、必要なら
  「同一ペアあたり上限N局」のフィルタを足す。
- 持ち時間の偏りは未対応。180秒未満の早指しが35.9%を占める。論文が持ち時間を指定していないので
  今回は絞っていない。
- 事前学習の効果は、最終的に `scripts/run_elo.sh` で「事前学習あり vs ランダム初期化」を直接対戦させて測る。
