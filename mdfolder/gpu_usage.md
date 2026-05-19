# MinizeroのDockerイメージのBuildから(場合による)
- 基本ビルド（リポジトリルートで実行）:
  - `docker build -f minizero/docker/Dockerfile.gpu -t minizero-gpu-full:latest .`
- Docker コンテキストを明示してビルドする（任意）:
    - `docker build -f /home/rin/restnet/minizero/docker/Dockerfile.gpu -t minizero-gpu-full:latest /home/rin/restnet`

# コンテナの起動
- `./scripts/start-container.sh`

## プログラムのビルド(コンテナ内)
- go
  - `./scripts/build.sh go`
- shogi
  - `./scripts/build.sh shogi`

## 学習の開始(コンテナ内)
- go
  - `tools/quick-run.sh train go 5 -conf_file configs/9x9_go/RRTRRT.cfg`
- shogi
  - `tools/quick-run.sh train shogi 5 -conf_file configs/9x9_shogi/RRTRRT.cfg`


### GPU使用率確認コマンド(１秒間隔)
`watch -n 1 nvidia-smi`