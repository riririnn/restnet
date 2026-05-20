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

# 将棋トレーニングのためにしたこと
- 快斗のリポジトリとMinizeroのリポジトリとの変更点が多すぎる
  - `minizero/minizero/environment/shogi`をそのままコピー
  - 将棋以外の編集されたファイルをすべて無視
    - ルールの設定以外で変更されたファイルは33個ぐらいかもしれない
- なぜ将棋のトレーニングができないのか？
  - 将棋の入力数などが多く，将棋の入力数に適した変更をshogiディレクトリの外で行っている(かもしれない)
    - pybind.pyとかが関係しているのかも？
  - Geminiに聞いてみた
    - GDBを使ってデバッグをしてろってさ
    - `gdb --args build/shogi/restnet_shogi -mode console -conf_file shogi_gaz_2R1T2R1T_P_TV_n50-18b820-dirty/shogi_gaz_2R1T2R1T_P_TV_n50-18b820-dirty.cfg -conf_str "nn_file_name=shogi_gaz_2R1T2R1T_P_TV_n50-18b820-dirty/model/weight_iter_0.pt:program_quiet=false"`
    - `run`
    - `genmove black`(先攻後攻の変数名を黒と白で設定されているため)
    - なぜかSegmentfaultは起きなかった
    - ```
      (Version: 18b820-dirty)
      [New Thread 0x7ffed8a06000 (LWP 841)]
      [New Thread 0x7ffcceb4b000 (LWP 842)]
      [New Thread 0x7ffcce34a000 (LWP 843)]
      [New Thread 0x7ffcc5c11000 (LWP 844)]
      Successfully started console mode
      genmove black
      9 8 7 6 5 4 3 2 1
      KyKeGiKiOuKiGiKeKy1
        Hi          Ka  2
      FuFuFuFuFuFuFuFuFu3
                        4
                        5
                        6
      fufufufufufufufufu7
        ka  gi      hi  8
      kyke  kioukigikeky9
      black: 
      white: 
      next: white
      model file name: shogi_gaz_2R1T2R1T_P_TV_n50-18b820-dirty/model/weight_iter_0.pt
      [2026/05/21 02:41:25.010] move number: 0, action:  (10931), reward: 0, player: B
        root node info: p = 0.0000, p_logit = 0.0000, p_noise = 0.0000, v = -0.0038, r = 0.0000, mean = 0.0035, count = 51.0000
      action node info: p = 0.0241, p_logit = 0.1798, p_noise = 0.0962, v = 0.0086, r = 0.0000, mean = 0.0029, count = 5.0000

      Spent Time = 0.216 (s)
      = 
      ```
 - なぜコンソールでsegment faultが起きなかったのか？
   - 学習とコンソールの違い
     - 並列対局数：学習(`zero_num_parallel_games=64`)，コンソールモード(デバッグのため並列数は１)
   - つまり...メモリ不足ということ(快斗が言ってた気がする)
     - 快斗の言ってたこと
       - 学習をするには学習の効率を最大まで下げないといけない
       - 下げなかった場合クラッシュする
       - 限界まで下げても学習は１日以上かかる
 - 解決策バッチサイズを限界まで下げる
   - RRTRRT.cfgを編集したのにできなかった😢
   - quick-run.shで並列数が上書きされている