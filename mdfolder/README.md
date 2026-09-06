# mdfolder — プロジェクトドキュメント索引

ResTNet将棋拡張研究のドキュメント集。（2026-09-06 更新）

## まず読むもの

| ファイル | 内容 |
|---------|------|
| [research_summary.md](research_summary.md) | 研究の目的・進捗・次の一手 |
| [known_bugs.md](known_bugs.md) | 把握している不具合の一覧（**コードの現状はここが正**） |

## 環境と運用

| ファイル | 内容 |
|---------|------|
| [setup_and_training.md](setup_and_training.md) | 環境構築・ビルド・学習実行・トラブル履歴 |
| [docker_container_usage.md](docker_container_usage.md) | Dockerコンテナの利用方法 |
| [server_kut_wei_ws01.md](server_kut_wei_ws01.md) | 学習サーバーの運用メモ（models/のHDDマウント必須） |
| [additional_training_and_workers.md](additional_training_and_workers.md) | 追加学習とサブワーカーの追加 |

## 学習

| ファイル | 内容 |
|---------|------|
| [bootstrap_pretraining.md](bootstrap_pretraining.md) | 人間棋譜による事前学習（データ収集から self-play への引き継ぎまで） |
| [hyperparameters.md](hyperparameters.md) | 主要ハイパーパラメータの違い（温度・割引率・学習率・ノイズ） |
| [value_perspective_check.md](value_perspective_check.md) | value が学習しない問題の原因切り分け（初学者向け解説つき） |
| [value_overfitting.md](value_overfitting.md) | value の過学習と最適な学習量（調査中） |

## 将棋のルールと表現

| ファイル | 内容 |
|---------|------|
| [minizero_shogi_features.md](minizero_shogi_features.md) | 入力特徴量（362チャンネル）と IG の出力の意味 |
| [entering_king_rule.md](entering_king_rule.md) | 入玉と宣言勝ちルール（AZ論文との差分） |
| [sgf_to_csa.md](sgf_to_csa.md) | 自己対戦棋譜の CSA 変換 |

## XAI・評価

| ファイル | 内容 |
|---------|------|
| [xai_guide.md](xai_guide.md) | 学習の階層構造（MCTS/step/iter）と XAI 各手法の解説 |
| [attention_map.md](attention_map.md) | Attention 均等分散問題の原因分析と改善計画 |
| [board_evaluation_shogi.md](board_evaluation_shogi.md) | 論文の bv（盤面所有権）を将棋に転用する構想＝制圧率（未実装） |
| [usi_eval_weakness_evidence.md](usi_eval_weakness_evidence.md) | 対外エンジン評価「弱さは実力でありバグではない」ことの証拠 |

## 本家との差分

| ファイル | 内容 |
|---------|------|
| [upstream_modifications.md](upstream_modifications.md) | 全ゲーム共通コードへの変更履歴とコミット一覧 |

## 関連（mdfolder外）

- `README.md`（リポジトリ直下）— オリジナル ResTNet の README
- `docs/restnet-visualization-in-GOGUI.md` — 元論文リポジトリ由来（囲碁 GOGUI 可視化）
- `scripts/shogi_eval.py` — モデル間 ELO 測定
- `scripts/extract_endgame_positions.py` — 終盤局面プール抽出
