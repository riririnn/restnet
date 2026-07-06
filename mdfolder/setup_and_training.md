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
# 将棋 本番（50 iter）
./tools/quick-run.sh train shogi 50 -n shogi_9x9_gaz_2R1T2R1T_P_TV_n50 \
  -conf_file configs/9x9_shogi/RRTRRT.cfg -b 256 -c 8

# 将棋 テスト設定
tools/quick-run.sh train shogi 5 -conf_file configs/9x9_shogi/RRTRRT-test.cfg

# 囲碁
tools/quick-run.sh train go 5 -conf_file configs/9x9_go/RRTRRT.cfg
```

- 学習の継続は同名 `-n` で再実行し、プロンプトで「C」（Continue）
- フェーズ切替（カリキュラム）は `-conf_str "key=val:key2=val2"` を追加

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
