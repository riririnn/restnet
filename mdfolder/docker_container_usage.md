# Dockerコンテナの利用方法（サーバーでの学習運用）

（2026-07-20 作成。kut-wei-ws01 / RTX PRO 6000 での運用手順）

## 前提

- イメージ名: `restnet`（`docker build -t restnet -f minizero/docker/Dockerfile.gpu .` でビルド）
- コンテナは `--rm` 付きで起動される: **停止すると同時に削除される**。
  学習データは `/workspace`（=ホストの `~/restnet`）にあるので消えない
- コンテナ内の時刻は Asia/Taipei（ホストJSTと1時間ずれて見えるのは正常）

## 起動

```bash
cd ~/restnet
./scripts/start-container.sh --image restnet            # フォアグラウンド起動
./scripts/start-container.sh --image restnet --name shogi-train -d   # 名前付き・バックグラウンド
```

## 学習の標準構成（コンテナ内tmux方式）

tmuxセッションはコンテナ内に住むので、ターミナルやSSHをどう閉じても学習は継続する。

```bash
# メインの学習
docker exec -it <コンテナ名> bash
tmux new -s main
cd /workspace
LR_BASE=0.075 ./scripts/curriculum_train.sh <ラン名> 0 configs/9x9_shogi/RRTRRT-bigserver.cfg
# Ctrl-b → d でデタッチ

# 追加の自己対戦ワーカー（GPU使用率を上げる。2〜3本まで）
tmux new -s worker2
cd /workspace
./minizero/scripts/zero-worker.sh shogi localhost 9999 sp -g 0 -b 256 -c 8 \
    --sp_executable_file build/shogi/restnet_shogi \
    --op_executable_file restnet/learner/train.py
# "connect success" 確認 → Ctrl-b → d
exit   # execシェルは閉じてよい
```

## 出入りの操作

| したいこと | コマンド / キー |
|---|---|
| セッション一覧 | `docker exec <名前> tmux ls` |
| 学習画面に入る | `docker exec -it <名前> tmux attach -t main` |
| 画面から抜ける | `Ctrl-b` → `d`（**Ctrl+Cは学習停止なので注意**） |
| コンテナ本体にattachした時の脱出 | `Ctrl-p` → `Ctrl-q`（**exitはコンテナごと停止**） |
| 進捗を見るだけ | `docker exec <名前> tail -20 /workspace/<ラン名>/Training.log` |
| 対局統計 | `docker exec <名前> sh -c 'cd /workspace && ./scripts/sgf_stats.sh <ラン名>'` |
| 稼働プロセス確認 | `docker exec <名前> ps aux \| grep -E "mode sp\|train.py" \| grep -v grep` |

## 止め方

### 学習だけ止める（コンテナは残す）
```bash
docker exec -it <名前> tmux attach -t main   # 入って Ctrl+C
# サブワーカーも止める場合:
docker exec <名前> pkill -f zero-worker
docker exec <名前> pkill -f "mode sp"
```
- Ctrl+C で失われるのは進行中のイテレーションのみ。同じコマンドで再開可能
- サブワーカーは本体停止後、60秒×5回の再接続リトライののち自動終了する。
  **5分以内に本体を再開すればサブワーカーは自動復帰する**

### コンテナごと止める
```bash
docker stop <コンテナ名>     # 学習・tmuxごと終了。--rmによりコンテナは削除される
```
- 止める前に学習をCtrl+Cで正常停止させるのが行儀が良い（どちらでもデータは壊れないが、
  進行中イテレーションは失われる）
- 再開はコンテナ起動からやり直し（tmuxセッションも作り直し）

### 緊急時
```bash
docker ps                    # コンテナIDを確認
docker kill <ID>             # 強制停止
ps aux | grep restnet_shogi  # ホスト側に残骸がないか確認（通常は無い）
```

## 再開の手順（コンテナ停止後・サーバー再起動後）

```bash
cd ~/restnet
git pull && git submodule update
(cd minizero && git checkout shogi && git pull)     # コード更新がある場合
./scripts/start-container.sh --image restnet
# コンテナ内:
./scripts/build.sh shogi     # C++に変更があった場合のみ
# あとは「学習の標準構成」と同じ。同じラン名なら続きから再開される
```

## 注意事項

- **継続時はランディレクトリ内のcfgが使われる**（`<ラン名>/<ラン名>.cfg`）。
  configs/ のcfgを変更しても継続ランには反映されない。
  設定を変えて継続する場合は**両方のcfgを編集**すること
- 学習中にGUI (`xai_app.py`) を使う場合はGPUを避ける: `CUDA_VISIBLE_DEVICES="" python xai_app.py`
- メモリ監視: `free -h`（リプレイバッファが満杯になる iteration 15 前後で再確認）
- GPU監視: `watch -n 1 nvidia-smi`、平均は `nvidia-smi dmon -s u -c 60`
