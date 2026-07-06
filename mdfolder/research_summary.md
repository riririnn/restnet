# 研究概要：ResTNetの将棋への拡張とAttention可視化

## 1. 研究の背景とベース技術
本研究は、IJCAI 2025で発表された論文 **"Bridging Local and Global Knowledge via Transformer in Board Games" (ResTNet)** を基盤としています。
元の研究では、AlphaZero/MuZeroの実装である `MiniZero` をベースに、局所的な特徴抽出に優れる **ResNet (CNN)** と、大局的な盤面情報の統合に優れる **Transformer** を組み合わせたハイブリッドアーキテクチャ（例：RRTRRTモデル）を提案し、囲碁やHexにおいて Cyclic-Adversary（循環攻撃）への耐性や、シチョウ（Ladder）・巡回パターンの認識精度を向上させました。

## 2. 本研究の目的
オリジナルのResTNetが対象としていた囲碁・Hexに加えて、本研究ではアーキテクチャを **将棋 (9x9)** の環境へと拡張適用します。将棋特有の複雑なルールや長手数のゲーム進行において、ResTNetがどのように局所・大局の知識を獲得するかを検証し、Transformerの Attention Mechanism が将棋の盤面上で何を注視しているのかを分析・可視化することを目的とします。

## 3. 現在の進捗と達成事項

### 環境構築とビルド問題の解決
- カスタムDockerイメージの構築および依存関係の修正を実施。元の実装に不足していたライブラリ (`timm`, `einops`) を `Dockerfile.gpu` に追加し、Pythonスクリプトの単体テストを通過させました。

### デバッグと将棋ルールの実装修正
- 最適化（Optimization）プロセスにおいて発生していた Segmentation Fault や Length エラーの原因を追究するため、デバッグモード（`./scripts/build.sh shogi debug`）で詳細な解析を実施しました。
- ミーティングでの議論を通じて、**「将棋のゲーム終了条件が正しく実装されていない」** という根本的な不具合を特定し、修正を完了しました。

### 学習パイプラインの稼働
- 修正後、複数のモデルアーキテクチャ（例：`2R1T2R1T_P_TV` など）やパラメータセットを用いて、将棋環境（9x9）でのトレーニング（Self-play, Optimization）を正常に実行・完了できることを確認しました。

### XAI可視化GUIの完成（2026年6月〜7月）
- Gradio製のWeb GUI（`xai_app.py`）を作成。Integrated Gradients / Occlusion /
  Attention Rollout / 単一ヘッドAttention Map / **Pre-softmax logit** /
  **Relative Position Bias** の可視化に対応しました。
- 詰将棋・実戦型の局面プリセット15種（SFEN入力）を整備しました。
- Attention均等分散問題の原因を特定（詳細: [attention_map.md](attention_map.md)）。

### 学習の定量評価（2026年7月）
- ELO測定パイプライン（`scripts/shogi_eval.py`）を作成。
  iter 5 → iter 39 で **+512 ELO**、iter 22 → 39 で +269 ELO と、学習が機能していることを確認しました。
- 一方で**引き分けの悪循環**を発見：引き分け率が9.7%→64.6%へ単調増加し、
  ValueLossが0.30で停滞（「常に互角と予測」状態）。学習速度低下の主因は
  実装の遅さではなく「ゲームが終局しない」ことと特定しました
  （詳細: [curriculum_training.md](curriculum_training.md)）。

## 4. 今後の課題とToDo (Next Steps)

1. **カリキュラムトレーニングの実装**（最優先）
   - 終盤局面プール3000件は抽出済み（`endgame_pool.sfen`）
   - C++側の実装（SFENパーサ + 開始局面設定 + 手数上限短縮）とリビルドが必要
2. **再学習**（relative_bias初期化変更 + カリキュラム設定で）
3. **AttentionMapの再評価** — 学習が進んだモデルで集中度を再確認
4. **外部エンジンとのELO校正** — Lesserkai等のUSIエンジンとの対戦ブリッジ
5. **研究発表の準備** — 可視化アルゴリズムと結果をスライドに整理
