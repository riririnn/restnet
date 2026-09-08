# 学習サーバー kut-wei-ws01 の運用メモ

このマシン固有の設定と注意点をまとめる。ホスト側で実行するコマンドと
コンテナ内で実行するコマンドを必ず区別すること。コンテナ内の `/workspace` は
ホストの `~/restnet` である。

## マシン構成

| 項目 | 値 |
|---|---|
| CPU | 24コア（`nproc`） |
| RAM | 約126GB（`/dev/shm` が63GBであることからの推定） |
| GPU | 1枚（`nvidia-smi` の index 0） |
| SSD | `/dev/nvme0n1p2` 915GB、`/` にマウント |
| HDD | `/dev/sda` 18TB、`/mnt/hdd1` にマウント |

学習結果はすぐ数百GBに育つ。SSDは一度95%まで逼迫して学習停止の一歩手前になった。
**学習結果は必ずHDDに置く。**

## 最重要: models/ の実体はHDDにある

学習結果の出力先は `tools/quick-run.sh` がリポジトリからの相対パス `models/` に
固定している（`quick-run.sh:236` と `:460`）。この位置を変えずに実体をHDDへ置くため、
**ホスト側のシンボリックリンク + 同一パスのバインドマウント**を使う。

### 構成

```
~/restnet/models        -> /mnt/hdd1/models   ホスト側のシンボリックリンク
/workspace/models       -> /mnt/hdd1/models   同じリンクをコンテナ内から見たもの
/mnt/hdd1/models                              実体（HDD）
```

3つとも同じ場所を指す。ホストからもコンテナからも `models/` で届く。

### 一度だけやる設定（ホスト側）

```bash
mkdir -p /mnt/hdd1/models
ln -s /mnt/hdd1/models ~/restnet/models
```

`models/` は `.gitignore` 済みなので、リンクを置いてもgitの状態は汚れない。

### コンテナ起動（毎回）

```bash
./scripts/start-container.sh -v /mnt/hdd1/models:/mnt/hdd1/models
```

`-v` の書式は「ホスト側:コンテナ側」。**両方に同じパスを書く**のは、
コンテナ内でリンクの向き先 `/mnt/hdd1/models` を実在させるため。
ここを `/workspace/models` にすると、リンクそのものの上に別のものを被せる形になり、
dockerがどう解決するか不確実になる。

**コンテナは `--rm` で起動するため、この `-v` は毎回必要。**
忘れるとコンテナ内で `models/` が壊れたリンクになり、学習は起動時に失敗する。
黙ってSSDに書き続けるより、失敗して気づけるほうが安全。

### 毎回打たずに済ませる

ホストの `~/.bashrc` に別名を定義する。

```bash
alias restnet-container='cd ~/restnet && ./scripts/start-container.sh -v /mnt/hdd1/models:/mnt/hdd1/models'
```

`scripts/start-container.sh` 自体には書かないこと。git管理下のファイルであり、
`/mnt/hdd1` はこのサーバーにしか存在しないパスのため、他マシンで壊れる。

### 起動直後に必ず確認する

```bash
ls /workspace/models
```

**ここが見えなければ学習を始めてはいけない。** マウント指定が効いていない。
一度コンテナを抜けて `-v` 付きで起動し直す。

## 学習の起動

```bash
# コンテナ内
tmux new -s main
cd /workspace
tools/quick-run.sh train shogi 500 -conf_file configs/9x9_shogi/10R-bigserver.cfg -b 512 -c 8
```

デタッチは `Ctrl-b` → `d`。**`Ctrl+C` は学習停止なので注意。**

- `-b` は自己対局ワーカーのバッチサイズ。**既定は64と小さい**（`quick-run.sh:524`）。
  cfg の `zero_num_parallel_games` はここには効かないので、必ず明示する。
- `-c` はGPUあたりのCPUスレッド数。既定は4。
- 出力先は `models/shogi_gaz_10R_P_TV_n64-<git hash>`。同じ名前のフォルダがあれば
  続きから再開される。

## 自己対局ワーカーの追加

1プロセス内はCPU区間とGPU区間を交互に実行するため、GPU使用率には構造的上限がある。
cfg の数値では超えられない。埋めるにはプロセスを足す。

```bash
# コンテナ内、main が動き始めてから
tmux new -s worker2
cd /workspace
./scripts/zero-worker.sh shogi $(hostname) 9999 sp -b 512 -c 8 -g 0
```

**合計4本になるまで足す**（quick-run が1本起動するので、手動で3本）。
`$(hostname)` は quick-run が内部で使う接続先に揃えるため。`localhost` でも同じ。

- **必ずリポジトリのルート（`/workspace`）から `./scripts/zero-worker.sh` を叩く。**
  `minizero/scripts/` 側を直接叩くと、実行ファイルの既定値が素のminizero
  （`build/shogi/minizero_shogi`、`minizero/learner/train.py`）になり動かない。
  ルートのラッパーが `build/shogi/restnet_shogi` と `restnet/learner/train.py` を補う。
- ポート9999は cfg の `zero_server_port`。変更したら合わせる。
- `sp` は自己対局、`op` は最適化で `op` は最大1台。quick-run が既に1台起動しているので
  追加するのは `sp` だけ。

### スレッド数は制約にならない（2026-09-05 実測）

`-c` の合計が24コアを超えても問題にならない。理由は2つ。

- **自己対局と最適化は交互に動く。** 自己対局が回っている間、最適化ワーカー
  （`train.py`、41スレッド）のCPU使用率は0%。両者の `-c` と `learner_num_thread` を
  足して24と比べるのは意味がない。
- **ボトルネックはプロセス内の単一スレッド。** `-c 8` の自己対局プロセスを `top -H` で
  見ると、1本が98.7%で張り付き、残り7本は各10%程度で待っている。`-c` を増やしても
  待ち手が増えるだけ。

したがって**性能を上げる手段はプロセスを増やすこと**で、`-c` の調整ではない。
プロセスごとに独立したボトルネックスレッドを持つので、そこは並列に回る。
2本目以降も `-c 8` でよい。

確認方法（コンテナ内。`--pid=host` が無いのでホストからは見えない）:

```bash
ps -eo pid,nlwp,etime,args --sort=-nlwp | head -20
top -H -p $(pgrep -d, -f "restnet_shogi|train.py")
uptime
```

## 効果測定

使用率だけで判断しない。**対局生成数で判断する。**

```bash
nvidia-smi dmon -s u -c 60
grep -c "GM\[" /workspace/models/<ラン名>/sgf/*.sgf | tail -3
```

2026-09-05 の実測（`-b 512 -c 8`、GPU 1枚）。

| 自己対局プロセス数 | GPU使用率 平均 | 最大 | ロードアベレージ |
|---|---|---|---|
| 1本 | 約61% | 77 | 2.2 |
| 3本 | 約72% | 85 | 5.0 |
| 4本 | 約88% | 96 | 6.4 |

**4本でGPUはほぼ飽和する。** VRAMは98GB中13GB、CPUは24コア中6しか使っておらず、
残る制約はGPUの演算そのもの。メモリコントローラ使用率は14〜20%で帯域は余っている。
4本のときの生成速度は毎分33.4局。

判断の注意点。

- **SM使用率で微妙な差を判断しない。** これは「カーネルが1つ以上動いていた時間の割合」で、
  演算資源をどれだけ使い切ったかではない。90%と88%の差からは何も言えない。
- **1本ずつ足して1回ずつ測る。** まとめて足すとどれが効いたか分からない。
- **足した直後の2分は測らない。** モデル読み込みで速度が安定しない。
- **イテレーションを跨いだら測り直す。** 切り替わると `1.sgf` が止まり `2.sgf` が始まる。
  切り替え直後はモデル更新で自己対局が一時止まるため、含めると低く出る。
- 生成数の増加が変わらなければ、GPU使用率が上がっても意味がない。
  追加分は `tmux kill-session -t worker4` で撤収する。

生成速度は次の1行で測る。コメント行を挟んで2行に分けて貼ると、シェルはコメントを無視して
即座に2行目を実行してしまい、同じ数字が2回出るだけになる。

```bash
grep -c "GM\[" /workspace/models/<ラン名>/sgf/1.sgf; date; sleep 600; \
grep -c "GM\[" /workspace/models/<ラン名>/sgf/1.sgf; date
```

## 停止

```bash
# コンテナ内
tmux attach -t main    # Ctrl+C
pkill -f zero-worker
pkill -f "mode sp"
```

失われるのは進行中のイテレーションのみ。同じコマンドで再開できる。
`exit` するとコンテナは `--rm` により削除される。

## 既知の落とし穴

- **`-v` の付け忘れ**。最も起きやすく、気づきにくい。起動直後に `ls /workspace/models`。
- **`additional_training_and_workers.md` のワーカー起動手順は誤り**。
  `cd ~/restnet/minizero` してから `scripts/zero-worker.sh` を叩いているが、
  そこには `build/` も `minizero/learner/` も無いため動かない。
  上流の `minizero/docs/Training.md` の例をディレクトリごと写したことによる誤記。
  ルートから叩くこと。
- **ラン名を変えたつもりが同じ**。既存フォルダ名を指定すると新規学習ではなく再開になる。
  設定を変えたらラン名も変える。
- **`-b` の指定忘れ**。既定64のまま走り、GPUが遊ぶ。

## 関連ドキュメント

- [docker_container_usage.md](docker_container_usage.md) — コンテナ運用全般
- [additional_training_and_workers.md](additional_training_and_workers.md) — 追加学習（ワーカー起動手順は上記の通り誤り）
- `minizero/docs/Training.md` — 上流のサーバー/ワーカー起動の公式説明
