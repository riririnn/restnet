# 人間棋譜によるブートストラップ事前学習（2026-08-02 作成）

lishogi の高レート帯の棋譜で policy / value を教師あり事前学習し、その重みを self-play の初期モデルにするための手順。
データ収集から学習、self-play への引き継ぎまでをコマンドで管理できるようにまとめる。

## なぜ新規の学習コードが要らないのか

既存の仕組みだけで成立する。

- `restnet/learner/train.py` は stdin で `train <model> <start> <end>` を受け、`TRAIN_DIR/sgf/{i}.sgf` を読んで学習する。
  self-play サーバ抜きで単体起動できるので、そのまま教師あり学習器になる。
- `minizero/minizero/environment/base/base_env.h:244` の `getPolicy()` は `P[]`（MCTS訪問回数分布）が空なら
  **指された手の one-hot** を返す。人間の棋譜に MCTS 分布が無くても policy 教師信号が成立する。
- `minizero/minizero/environment/shogi/shogi.h:327` の `getValue()` は `RE` タグ（先手視点 +1/-1/0）を返す。
  レコードに `RE[...]` を書けば value 教師信号になる。

## 1. データ収集

### コマンド

```bash
# レート分布だけ見る（データセットは作らない）
python3 scripts/bootstrap/build_dataset.py --stats --target-games 500

# 本収集（既に取得済みのプレイヤーは再ダウンロードされない）
python3 scripts/bootstrap/build_dataset.py --min-rating 2000 --target-games 10000 --games-per-user 600

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
data/bootstrap/sgf/1.sgf      学習レコード（1行1局）
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
recs=[l.strip() for l in open("data/bootstrap/sgf/1.sgf") if l.strip()]
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
head -1 data/bootstrap/sgf/1.sgf > /tmp/one.sgf
python3 scripts/sgf_to_csa.py /tmp/one.sgf | head -20
```

`sgf_to_csa.py` は盤面を再生して駒種を判定するため、action id が誤っていれば破綻する。独立した検証になる。

判断基準: 先手勝率が 50% 付近から大きく外れていたら変換ミスを疑う。

## 4. 事前学習の実行

### 準備

```bash
mkdir -p shogi_9x9_bootstrap/{model,sgf,analysis}
cp configs/9x9_shogi/RRTRRT.cfg shogi_9x9_bootstrap/bootstrap.cfg
cp data/bootstrap/sgf/1.sgf shogi_9x9_bootstrap/sgf/1.sgf
touch shogi_9x9_bootstrap/op.log

# ステップ数と表示間隔を設定
sed -i 's/^learner_training_step=.*/learner_training_step=3000/' shogi_9x9_bootstrap/bootstrap.cfg
sed -i 's/^learner_training_display_step=.*/learner_training_display_step=250/' shogi_9x9_bootstrap/bootstrap.cfg
```

**リプレイバッファの上限に注意。** 読み込める局数は `zero_replay_buffer × zero_num_games_per_iteration` で決まる
（`data_loader.cpp:45`）。既定は 5 × 2000 = 10,000 局。これを超える棋譜を入れると古い分が捨てられる。

### 実行

```bash
CONTAINER=$(docker ps --filter ancestor=restnet --format '{{.Names}}' | head -1)

docker exec $CONTAINER bash -c "cd /workspace && \
  printf 'train \"\" 1 1\nquit\n' | PYTHONPATH=. python3 -u \
  restnet/learner/train.py shogi shogi_9x9_bootstrap shogi_9x9_bootstrap/bootstrap.cfg" \
  > data/bootstrap/logs/pretrain.log 2>&1 &
```

`train "" 1 1` の引数は「初期モデル無し・iteration 1 から 1 まで」の意味。
`sgf/1.sgf` だけを読み、`learner_training_step` 回学習して `model/weight_iter_<累計ステップ>.pkl|.pt` を保存する。

**実行スクリプトは `restnet/learner/train.py`。** `minizero/minizero/learner/train.py` ではない
（`scripts/zero-worker.sh:13` が指定しているのはこちら）。ResTNet 固有の設定キー（`nn_embed_kernel_size` など）は
`restnet_py` しか解釈できないため、minizero 側で起動すると設定が読めない。

### ステップを追加する

`training_step` と optimizer の状態は `.pkl` に保存されるので、続きから回せる。

```bash
docker exec $CONTAINER bash -c "cd /workspace && \
  printf 'train weight_iter_3000.pkl 1 1\nquit\n' | PYTHONPATH=. python3 -u \
  restnet/learner/train.py shogi shogi_9x9_bootstrap shogi_9x9_bootstrap/bootstrap.cfg"
```

`weight_iter_6000.pkl` が新たに保存される。学習率は毎回 config から読み直される。

### 進捗の確認

```bash
grep -E "nn step|loss_policy|accuracy_policy|loss_value" data/bootstrap/logs/pretrain.log | tail -20
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
```

## 5. self-play への引き継ぎ

`zero_server.cpp:179` が `nn_file_name` の `weight_iter_<N>` から開始 iteration を読む。

```bash
tools/quick-run.sh train shogi 500 -conf_file configs/9x9_shogi/RRTRRT.cfg \
  -conf_str nn_file_name=shogi_9x9_bootstrap/model/weight_iter_3000.pt
```

## 6. 実測値（2026-08-02、8,939局 894,348手、RRTRRT、batch 512、lr 0.02）

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

### `Training.log` が無いというエラー

学習完了後に出るが**無害**。self-play 学習用の集計処理が `Training.log` を探しているだけで、
`Optimization_Done <step>` が出ていればモデルの保存は完了している。

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
