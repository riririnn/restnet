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

## 最重要: models/ のマウント

学習結果の出力先は `tools/quick-run.sh` がリポジトリからの相対パス `models/` に
固定している（`quick-run.sh:236` と `:460`）。ここをHDDに向けるには、
コンテナ起動時に `models` の位置へHDDをバインドマウントする。

```bash
./scripts/start-container.sh -v /mnt/hdd1/models:/workspace/models
```

**コンテナは `--rm` で起動するため、この `-v` は毎回必要。**
忘れるとSSD上に空の `models/` が作られ、過去のランが見えなくなる。

### 毎回打たずに済ませる

ホストの `~/.bashrc` に別名を定義してある（していなければ追加する）。

```bash
alias restnet-container='cd ~/restnet && ./scripts/start-container.sh -v /mnt/hdd1/models:/workspace/models'
```

`scripts/start-container.sh` 自体には書かないこと。git管理下のファイルであり、
`/mnt/hdd1` はこのサーバーにしか存在しないパスのため、他マシンで壊れる。

### 起動直後に必ず確認する

```bash
ls /workspace/models
```

**ここが空なら学習を始めてはいけない。** マウント指定が効いていない。
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
./scripts/zero-worker.sh shogi $(hostname) 9999 sp -b 512 -c 6 -g 0
```

- **必ずリポジトリのルート（`/workspace`）から `./scripts/zero-worker.sh` を叩く。**
  `minizero/scripts/` 側を直接叩くと、実行ファイルの既定値が素のminizero
  （`build/shogi/minizero_shogi`、`minizero/learner/train.py`）になり動かない。
  ルートのラッパーが `build/shogi/restnet_shogi` と `restnet/learner/train.py` を補う。
- ポート9999は cfg の `zero_server_port`。変更したら合わせる。
- `sp` は自己対局、`op` は最適化で `op` は最大1台。quick-run が既に1台起動しているので
  追加するのは `sp` だけ。

### スレッド配分（24コア）

| プロセス | スレッド |
|---|---|
| 最適化ワーカー | 16（cfg の `learner_num_thread`） |
| 自己対局 1本目 | 8（`-c 8`） |
| 自己対局 2本目 | 6（`-c 6`） |
| 合計 | 30（**24コアを超過**） |

超過状態なので、追加しても伸びない場合は `learner_num_thread` を12程度に下げる。
ただしこれは cfg 変更なのでラン作り直しが絡む。まず実測してから判断する。

## 効果測定

使用率だけで判断しない。**対局生成数で判断する。**

```bash
nvidia-smi dmon -s u -c 60
grep -c "GM\[" /workspace/models/<ラン名>/sgf/*.sgf | tail -3
```

- 2026-09-05 の実測: `-b 256 -c 8` の自己対局1本で SM使用率の平均は約61%、
  範囲は48〜77。メモリコントローラ使用率は10〜15%と低く、帯域は飽和していない。
  カーネルが小さく起動オーバーヘッドが目立つ状態で、バッチ増が効く見込み。
- 判断基準は平均60%。未満ならワーカー追加、以上ならそのまま。
- 30分あたりの対局数の増加が変わらなければ、GPU使用率が上がっても意味がない。
  追加分は `tmux kill-session -t worker2` で撤収する。

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
