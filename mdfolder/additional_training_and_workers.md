# 追加学習とサブワーカーの追加

`shogi_9x9_restnet64_v2` など、既存の学習を途中から継続する手順と、
自己対局(sp)ワーカーを後から増やす手順をまとめる。

## 1. 追加学習（続きから学習を再開する）

同じ**学習フォルダ名(`-n`)**・**同じ cfg** を指定し、
**END_ITER を現在のイテレーションより大きい値**にすると、
zero-server が既存の `model/` の最新モデルを起点に続きから再開する。

### 現在のイテレーションを確認

```bash
cd ~/restnet
ls -t shogi_9x9_restnet64_v2/model/*.pt | head -1   # 最新モデルの iter 番号
```

### 追加学習コマンド（例: 100000 まで進める）

```bash
cd ~/restnet
tools/quick-run.sh train shogi \
    shogi_9x9_restnet64_v2/shogi_9x9_restnet64_v2.cfg \
    100000 \
    -n shogi_9x9_restnet64_v2 \
    -g 0
```

| 引数 | 意味 |
| --- | --- |
| `shogi` | GAME_TYPE |
| `...shogi_9x9_restnet64_v2.cfg` | 学習時と同じ cfg（フォルダ内のものを使うのが確実） |
| `100000` | END_ITER（合計到達イテレーション。現在値より大きく） |
| `-n shogi_9x9_restnet64_v2` | 既存フォルダを指定 → 続きから再開 |
| `-g 0` | 使用GPU（複数なら `-g 01` など） |

**注意**
- 別のフォルダ名を指定すると新規学習になる。
- 学習時と cfg が食い違うと設定不整合になるため、フォルダ内の cfg を使う。
- tmux 等の中で実行し、SSH 切断後も継続するようにする。

## 2. サブワーカー（自己対局ワーカー）の追加

`quick-run.sh train` は起動時に「利用可能GPU数ぶんの sp ワーカー」を自動起動する。
後から手動で `zero-worker.sh` を実行すると台数を増やせる。
（出典: `minizero/docs/Training.md` の "Launch the zero worker"）

```bash
scripts/zero-worker.sh GAME_TYPE SERVER SERVER_PORT [sp|op] [OPTION]...
```

- `sp` = 自己対局、`op` = 最適化（op は最大1台。通常は追加不要）
- SERVER/PORT = 稼働中の zero-server の接続先（デフォルトポート **9999**）

### 同じマシンで sp ワーカーを追加（GPU 1台につき1インスタンス）

```bash
cd ~/restnet/minizero
scripts/zero-worker.sh shogi localhost 9999 sp -g 0   # 別ターミナル/tmuxペイン
scripts/zero-worker.sh shogi localhost 9999 sp -g 1
```

### 別マシンから追加（SERVER を学習サーバーのIPに）

```bash
scripts/zero-worker.sh shogi 192.168.1.60 9999 sp -g 0
```

### 主なオプション

| オプション | 意味 |
| --- | --- |
| `-g` | 使用GPU（デフォルト全GPU） |
| `-b` | sp ワーカーのバッチサイズ（デフォルト64） |
| `-c` | GPUあたりCPUスレッド数（デフォルト4） |
| `-conf_str` | 追加の設定文字列 |

**注意**
- ポートを変更している場合（`zero_server_port`）はその番号を指定。
- 接続に成功すると zero-server 側に接続メッセージが出る（`Worker.log` にも記録）。
- ワーカーは別マシンでも可。台数を増やすほど自己対局の生成速度が上がる。
