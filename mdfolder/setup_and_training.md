# 環境構築・学習の実行手順とトラブルシューティング

（旧 `gpu_usage.md` + `train_debug.md` を統合。2026-07-07）

> **2026-11-11 注記：** 学習のコマンドを今のものに直した。`scripts/curriculum_train.sh` は 7 月の手順で、9 月以降の学習では使っていない。

## Dockerイメージとコンテナ

```bash
# カスタムイメージのビルド（timm, einops追加済みのDockerfile.gpu）
docker build -t my-image-name -f minizero/docker/Dockerfile.gpu .

# コンテナ起動（GPU付き設定済み）
./scripts/start-container.sh                        # デフォルト（restnetイメージ）
./scripts/start-container.sh --image my-image-name  # カスタムイメージ
```

## ビルド（コンテナ内）

```bash
./scripts/build.sh go      # 囲碁
./scripts/build.sh shogi   # 将棋
./scripts/build.sh shogi debug   # デバッグビルド（segfault調査用）
```

## 学習の開始（コンテナ内）

```bash
# 9×9 将棋の自己対局、ゼロから（サーバー）
tools/quick-run.sh train shogi 500 -conf_file configs/9x9_shogi/10R-bigserver.cfg -b 512 -c 8
# 自己対局のワーカーを足す（別のセッション）
./scripts/zero-worker.sh shogi $(hostname) 9999 sp -b 512 -c 8 -g 0

# 9×9 将棋の SL（教師あり学習）。DATA を付けないと古い lishogi のデータを読む
DATA=data/floodgate/sgf_2250 tools/quick-run.sh pretrain shogi train <名前> <ステップ数> configs/9x9_shogi/10T-bootstrap.cfg

# SL の重みから自己対局を始める（同じ名前の .pkl も要る）
tools/quick-run.sh train shogi configs/9x9_shogi/10T-bootstrap.cfg 500 -n <新しいフォルダ> --pretrained <SL の重み>.pt -b 512 -c 8

# 動物将棋の 11 構成（5五将棋は dobutsu を minishogi に）
./scripts/train_archs.sh dobutsu 200

# 囲碁
tools/quick-run.sh train go 5 -conf_file configs/9x9_go/RRTRRT.cfg
```

- 学習率は cfg の `learner_learning_rate`、`learner_lr_decay_steps`、`learner_lr_decay_gamma` で決まる（2026-09-10 から）
- 学習のフォルダは `models/` の下にできる。`-n` の名前も `models/` の下になる
- `quick-run.sh train` は始めるたびにプログラムを作り直す。Training.log の `[Version]` がそのときの minizero の版である
- 中断は Ctrl+C（進行中の1 iterationのみ失われる）。再開は同じコマンドを再実行し、`C` と `y` で答える。
  再開前に `ps aux | grep restnet_shogi` で残プロセス確認
- 一時的な設定の変更は `-conf_str` で渡す

## GPU監視

```bash
watch -n 1 nvidia-smi   # 1秒間隔で使用率確認
```

**注意（VRAM）**: 学習中は約10GB使用。GUI（xai_app.py）を同時に使うと
OOMで学習が落ちるため、GUIは必ずCPUで起動する：

```bash
CUDA_VISIBLE_DEVICES="" python xai_app.py
```

## モデル評価（ELO測定）

```bash
# コンテナ内で。gogui-twogtp は手を囲碁の座標として読むので将棋に使えない。専用スクリプトを使う
python3 scripts/shogi_eval.py \
  --model1 <old>.pt --model2 <new>.pt \
  --conf configs/9x9_shogi/RRTRRT.cfg --games 20 --out result.txt
```

## Configuration File について

- `configs/` の `.cfg` は git に入っている
- cfgに記述されていない項目はC++側のデフォルト値で自動補完される
  （起動時ログに全設定値が出力される）

## 過去のトラブルと解決（履歴）

| 問題 | 原因 | 解決 |
|------|------|------|
| train.py が起動しない | `timm`, `einops` 不足 | Dockerfile.gpu に追加 |
| Optimization段階でsegfault / lengthエラー | **将棋のゲーム終了条件が未実装だった** | 終了条件を実装して修正済み |
| iter 12 でOOM | リプレイバッファ+バッチが大きすぎ | `zero_replay_buffer=5:learner_batch_size=512:zero_num_games_per_iteration=1000` |
| GUI起動で学習が停止 | VRAM合計が16GB超過 | GUIを `CUDA_VISIBLE_DEVICES=""` で起動 |
| 評価対戦が0手で終わる | `ShogiAction::toConsoleString()` が空文字スタブ | `scripts/shogi_eval.py` で `game_string` から指し手を読む方式に。2026-10-08 に USI を返すように直した |
