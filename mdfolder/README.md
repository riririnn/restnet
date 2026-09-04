# mdfolder — プロジェクトドキュメント索引

ResTNet将棋拡張研究のドキュメント集。（2026-07-07 整理）

| ファイル | 内容 |
|---------|------|
| [research_summary.md](research_summary.md) | 研究概要・進捗・ToDo（まずこれを読む） |
| [setup_and_training.md](setup_and_training.md) | 環境構築・ビルド・学習実行・トラブル履歴 |
| [attention_map.md](attention_map.md) | Attention均等分散問題の原因分析と改善計画・実装状況 |
| [curriculum_training.md](curriculum_training.md) | 引き分け悪循環の実測データとカリキュラム学習設計 |
| [xai_guide.md](xai_guide.md) | 学習の階層構造（MCTS/step/iter）とXAI各手法の解説 |
| [board_evaluation_shogi.md](board_evaluation_shogi.md) | 論文のbv（盤面所有権）を将棋に転用する構想＝制圧率（未実装） |
| [value_perspective_check.md](value_perspective_check.md) | valueが学習しない問題の原因切り分け（初学者向け解説つき） |
| [value_overfitting.md](value_overfitting.md) | valueの過学習と最適な学習量（調査中） |

## 関連（mdfolder外）

- `README.md`（リポジトリ直下）— オリジナルResTNetのREADME
- `docs/restnet-visualization-in-GOGUI.md` — 元論文リポジトリ由来（囲碁GOGUI可視化）
- `scripts/shogi_eval.py` — モデル間ELO測定
- `scripts/extract_endgame_positions.py` — 終盤局面プール抽出
