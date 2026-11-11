# Dockerコンテナの利用方法（サーバーでの学習運用）

（2026-07-20 作成。kut-wei-ws01 / RTX PRO 6000 での運用手順）

> **2026-11-11 注記：** 学習のコマンドとフォルダの場所を今のものに直した。`scripts/curriculum_train.sh` は 9 月以降の学習では使っていない。サーバーの `models/` のマウントは [server_kut_wei_ws01.md](server_kut_wei_ws01.md) を見る。サーバーでの動作は今回は確かめていない。

## 前提

- イメージ名: `restnet`（`docker build -t restnet -f minizero/docker/Dockerfile.gpu .` でビルド）
- コンテナは `--rm` 付きで起動される: **停止すると同時に削除される**。
  学習データは `/workspace`（=ホストの `~/restnet`）にあるので消えない
- コンテナ内の時刻は Asia/Taipei（ホストJSTと1時間ずれて見えるのは正常）

## 起動

```bash
cd ~/restnet
# サーバーでは models/ の実体が HDD にあるので -v を必ず付ける
./scripts/start-container.sh -v /mnt/hdd1/models:/mnt/hdd1/models            # フォアグラウンド起動
./scripts/start-container.sh -v /mnt/hdd1/models:/mnt/hdd1/models --name shogi-train -d   # 名前付き・バックグラウンド
```

## 学習の標準構成（コンテナ内tmux方式）

tmuxセッションはコンテナ内に住むので、ターミナルやSSHをどう閉じても学習は継続する。

```bash
# メインの学習
docker exec -it <コンテナ名> bash
tmux new -s main
cd /workspace
tools/quick-run.sh train shogi 500 -conf_file configs/9x9_shogi/10R-bigserver.cfg -b 512 -c 8
# Ctrl-b → d でデタッチ

# 追加の自己対戦ワーカー（GPU使用率を上げる）
tmux new -s worker2
cd /workspace
./scripts/zero-worker.sh shogi $(hostname) 9999 sp -b 512 -c 8 -g 0
# "connect success" 確認 → Ctrl-b → d
exit   # execシェルは閉じてよい
```

### サブワーカーの本数

- 1プロセス内はCPU/GPUフェーズ交互実行のため、GPU使用率には構造的上限がある
  （設定値では超えられない）。埋めるにはワーカープロセスを足す
- まず**サブ1本（sp合計2本）**で開始し、15分後に `nvidia-smi dmon -s u -c 60` の平均で判断:
  60%以上ならそのまま、未満なら `tmux new -s worker3` で3本目（`-c 6`）を追加
- 7 月の上限は**sp合計3本**としていたが、9 月の 10R と R3(RRT) は **sp 合計 5 本**で学習した（Worker.log）。
  効果測定は `grep -c "GM\[" models/<ラン名>/sgf/<今の iteration>.sgf` の30分あたり増加数で行い、
  増えなければ追加分を撤収（`tmux kill-session -t worker3`）

## 出入りの操作

| したいこと | コマンド / キー |
|---|---|
| セッション一覧 | `docker exec <名前> tmux ls` |
| 学習画面に入る | `docker exec -it <名前> tmux attach -t main` |
| 画面から抜ける | `Ctrl-b` → `d`（**Ctrl+Cは学習停止なので注意**） |
| コンテナ本体にattachした時の脱出 | `Ctrl-p` → `Ctrl-q`（**exitはコンテナごと停止**） |
| 進捗を見るだけ | `docker exec <名前> tail -20 /workspace/models/<ラン名>/Training.log` |
| 対局統計 | `docker exec <名前> sh -c 'cd /workspace && ./scripts/sgf_stats.sh models/<ラン名>'` |
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
./scripts/start-container.sh -v /mnt/hdd1/models:/mnt/hdd1/models
# コンテナ内:
# あとは「学習の標準構成」と同じ。quick-run がプログラムを作り直す
# 同じラン名なら (R)estart / (C)ontinue と聞かれるので C と y で答える
# 既定のラン名には minizero の版が入る。版が変わったら -n で元の名前を渡す
```

## 設定を変えて再学習する場合

イテレーション途中のランは設定変更と相性が悪い（継続時はランディレクトリ内cfgが
優先されるため二重編集が必要になる）。**完了イテレーションが少ないうちは
ランを作り直すのがクリーン**:

```bash
# 1. 全停止（メインCtrl+C → pkill -f zero-worker → ps で確認）
# 2. 未完了ランを削除
rm -rf ~/restnet/models/<旧ラン名>
# 3. 新しいラン名で開始（設定は configs/ のcfgから再生成される）
tools/quick-run.sh train shogi 500 -conf_file configs/9x9_shogi/10R-bigserver.cfg -n <新ラン名> -b 512 -c 8
```

設定を変えたらラン名も変える（例: シミュレーション数を変えたら `_n64` を付ける等）。
後から `sgf_stats` を見比べるときに何のランか分かるようにするため。

## 注意事項

- **継続時はランディレクトリ内のcfgが使われる**（`models/<ラン名>/<ラン名>.cfg`）。
  configs/ のcfgを変更しても継続ランには反映されない。
  設定を変えて継続する場合は**両方のcfgを編集**すること
- 学習中にGUI (`xai_app.py`) を使う場合はGPUを避ける: `CUDA_VISIBLE_DEVICES="" python xai_app.py`
- メモリ監視: `free -h`（リプレイバッファが満杯になる iteration 15 前後で再確認）
- GPU監視: `watch -n 1 nvidia-smi`、平均は `nvidia-smi dmon -s u -c 60`
