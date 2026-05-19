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