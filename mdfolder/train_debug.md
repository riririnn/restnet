# Start the container
./scripts/start-container.sh
上記のファイルにGPU付きでコンテナを実行するように設定してある

# Configuration Fileについて
- もともとないから自分で作らないといけない
  - .gitignoreに.cfgが設定されている
  - じゃああるわけないじゃんね
- cfgに記述されていない項目はすべて自動的にC++側のデフォルト値で保管される使用になっているらしい(ログに出力されている大量の設定値)(どこでそのようになっているかは知らない)
- 
# トレーニングが実行できなかった件
- これ実行して足りないライブラリを確認# 環境変数をセットしてPythonスクリプトを単体でテスト
  - `PYTHONPATH=build/go python restnet/learner/train.py -h`
  - `timm`というライブラリーがないらしいのでminizeroのDockerFileに追加した
  - `einops`も追加
  - 結果：囲碁などの論文で示されているゲームはトレーニングできた

# 現状の進歩
* optimizationの段階になるとsegmentation faluteやlength何とかエラーが出る
  * 原因がわからない(エラーが起きた個所もわからない)ためDebugモードでビルド
```
./script/build.sh shogi debug
```

## 先生とのミーティングで分かったこと
* 将棋のゲームが終了する定義が正常に実装されていなかった😢
* 修正済み