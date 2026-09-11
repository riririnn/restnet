# 環境構築・学習の実行手順とトラブルシューティング

（旧 `gpu_usage.md` + `train_debug.md` を統合。2026-07-07）

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
# 将棋 本番（サーバー / RTX 6000、AZ論文準拠設定）
LR_BASE=0.075 ./scripts/curriculum_train.sh shogi_9x9_az_paper_v1 0 \
    configs/9x9_shogi/RRTRRT-bigserver.cfg

# 将棋（PC / 16GBカード）
./scripts/curriculum_train.sh shogi_9x9_curriculum_5060ti 0

# 囲碁
tools/quick-run.sh train go 5 -conf_file configs/9x9_go/RRTRRT.cfg
```

- `LR_BASE` = 学習率スケジュールの初期値。論文の0.2をバッチ比で換算する
  （`0.2 × batch/4096`: batch 1536 → **0.075**、batch 512 → 0.02=デフォルト）。
  進捗 1/7・3/7・5/7 の地点で自動的に10分の1ずつ減衰（`scripts/curriculum_train.sh:89-92`）
- 中断は Ctrl+C（進行中の1 iterのみ失われる）。再開は同じコマンドを再実行。
  再開前に `ps aux | grep restnet_shogi` で残プロセス確認
- 追加設定の一時変更はスクリプト内の `-conf_str` に追記

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
# コンテナ内で。gogui-twogtpは将棋非対応（toConsoleStringが空文字スタブ）のため専用スクリプトを使う
python3 scripts/shogi_eval.py \
  --model1 <old>.pt --model2 <new>.pt \
  --conf configs/9x9_shogi/RRTRRT.cfg --games 20 --out result.txt
```

## Configuration File について

- `.cfg` は `.gitignore` 対象なので自分で作成する（`configs/` に置く）
- cfgに記述されていない項目はC++側のデフォルト値で自動補完される
  （起動時ログに全設定値が出力される）

## 過去のトラブルと解決（履歴）

| 問題 | 原因 | 解決 |
|------|------|------|
| train.py が起動しない | `timm`, `einops` 不足 | Dockerfile.gpu に追加 |
| Optimization段階でsegfault / lengthエラー | **将棋のゲーム終了条件が未実装だった** | 終了条件を実装して修正済み |
| iter 12 でOOM | リプレイバッファ+バッチが大きすぎ | `zero_replay_buffer=5:learner_batch_size=512:zero_num_games_per_iteration=1000` |
| GUI起動で学習が停止 | VRAM合計が16GB超過 | GUIを `CUDA_VISIBLE_DEVICES=""` で起動 |
| 評価対戦が0手で終わる | `ShogiAction::toConsoleString()` が空文字スタブ | `scripts/shogi_eval.py` で `game_string` から指し手を読む方式に |
