
# 人間棋譜によるブートストラップ事前学習（2026-08-02 作成）

lishogi の高レート帯の棋譜で policy / value を教師あり事前学習し、その重みを self-play の初期モデルにするための手順。
データ収集から学習、self-play への引き継ぎまでをコマンドで管理できるようにまとめる。

## どのコードで学習するのか

`restnet/learner/supervised_learning_bv_train.py`。論文リポジトリに元から入っている教師あり学習器で、
囲碁専用だったので将棋で動くよう手を入れた。変更は3点。

- `__import__("build.go")` を `build.{sys.argv[1]}` にし、ゲーム名を第1引数で受ける
- `from create_network import` → `from network.create_network import`
  （`restnet/learner/network/create_network.py` にあり、`train.py:9` も同じ書き方）
- `nn_bv_flag` が false なら board evaluation を計算せず policy / value だけ学習する

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
    -n shogi_9x9_from_human --pretrained shogi_9x9_human/model/weight_iter_30000.pt
```

`STEPS` は**到達する累計ステップ数**。`supervised_learning_bv_train.py:183` が
`range(model.training_step, training_step_limit)` で回すため、再開時は現在のステップ数から数える。
CFG を省くと `configs/9x9_shogi/RRTRRT-bootstrap.cfg` を使う。

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

`shogi_9x9_human/model/` を作り、次を実行する。

```bash
PYTHONPATH=. python3 -u restnet/learner/supervised_learning_bv_train.py \
    shogi shogi_9x9_human "" configs/9x9_shogi/RRTRRT-bootstrap.cfg 5000 \
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

学習データと検証データの両方が記録される。

```
loss_policy / accuracy_policy / loss_value                学習データ
test_loss_policy / test_accuracy_policy / test_loss_value 検証データ（学習に不使用）
```

test 側が改善しなくなったら過学習の開始なので、そこで止める。

## 5. self-play への引き継ぎ

通常の train モードに `--pretrained` を付けるだけで、以降は普段どおりの self-play になる。

```bash
tools/quick-run.sh train shogi configs/9x9_shogi/RRTRRT.cfg 500 \
    -n shogi_9x9_from_human --pretrained shogi_9x9_human/model/weight_iter_30000.pt
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

## 8. 残課題

- value の事前学習には桁違いのステップ数が必要。policy 重視で self-play に渡すか、長時間回すかの判断が要る。
- 同一対戦ペアの偏りがある（最多で87局）。序盤が似た棋譜が偏る可能性があり、必要なら
  「同一ペアあたり上限N局」のフィルタを足す。
- 事前学習の効果は、最終的に `scripts/run_elo.sh` で「事前学習あり vs ランダム初期化」を直接対戦させて測る。
  lishogi のレート値そのものは相対値なので、棋力の主張には使えない。
