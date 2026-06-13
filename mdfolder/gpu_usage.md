## MinizeroのDockerイメージのBuildから(どっちのほうがいいんだろうね)
- カスタムイメージの場合：
  - `docker build -t my-image-name -f minizero/docker/Dockerfile.gpu . `
- デフォルトのrestnetの場合：いらない
### コンテナの起動
- カスタムのDockerイメージを利用する場合：
  - `./scripts/start-container.sh --image my-image-name`
- デフォルトのDockerイメージを利用する場合：
  - `./scripts/start-container.sh`

## プログラムのビルド(コンテナ内)
- go
  - `./scripts/build.sh go`
- shogi
  - `./scripts/build.sh shogi`

## 学習の開始(コンテナ内)
- go
  - `tools/quick-run.sh train go 5 -conf_file configs/9x9_go/RRTRRT.cfg`
- shogi-test
  - `tools/quick-run.sh train shogi 5 -conf_file configs/9x9_shogi/RRTRRT-test.cfg`
- shogi
  - `./tools/quick-run.sh train shogi 10 -n shogi_9x9_gaz_2R1T2R1T_P_TV_n10 -conf_file configs/9x9_shogi/RRTRRT.cfg -b 256 -c 8 `


### GPU使用率確認コマンド(１秒間隔)
`watch -n 1 nvidia-smi`