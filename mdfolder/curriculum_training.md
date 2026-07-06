# カリキュラムトレーニング設計案（2026-07-07 改訂）

## 改訂の背景：引き分けの悪循環（実測データで確認済み）

iter 38 までの学習データ分析で、以下の**悪循環**が定量的に確認された。

| 指標 | iter 1 | iter 38 | 傾向 |
|------|--------|---------|------|
| 引き分け率 | 9.7% | **64.6%** | 単調増加 |
| 平均ゲーム長 | 278手 | **428手**（中央値498手） | 単調増加 |
| ValueLoss | 0.86 | **0.30で停滞** | 「常に0と予測」の理論値0.35に漸近 |

### 悪循環の構造

```
モデルが詰ませられない
  → ゲームが500手上限まで続く（68%が495手以上）
  → 引き分け率が上昇（価値ターゲットの65%が0）
  → 価値ネットが「常に互角」と学習（ValueLoss 0.30 ≈ 全部0と予測）
  → resign_threshold=-0.9 が発動しない
  → ゲームがさらに長引く → 最初に戻る
```

### 時間への影響

- 1 iter の総手数: 囲碁 9x9 の約4〜8倍（1000局×428手 = 42.8万手）
- **学習が遅い主因は実装の遅さではなく「ゲームが終わらない」こと**
- 手/秒の処理速度は囲碁比 約2倍差で妥当（入力362ch・行動空間5000超を考慮）

---

## 対策の全体像（優先度順）

### ★★★ 対策1: 500手上限の短縮（1行変更・即効）

`minizero/minizero/environment/shogi/shogi.cpp` L118 の手数上限を 500→200 に変更。
既実装の27点法判定が早期に発動し、引き分けの大半が勝敗に変わる。

```cpp
// 変更前
if (actions_.size() >= 500 && winner_ == GameResult::UNDECIDED) {
// 変更後
if (actions_.size() >= 200 && winner_ == GameResult::UNDECIDED) {
```

**効果**: SP時間 約2倍短縮 + 価値シグナル（±1）の大幅増加。
**コスト**: C++リビルドのみ。学習は Continue 可能（ただしリプレイバッファの
旧データと混ざるため、新規学習開始を推奨）。

**注意**: 27点法は駒得側が勝ちになるため、序盤モデルには「駒得＝勝ち」という
バイアスがつく。これは将棋の基本原理と整合するので序盤学習にはむしろ好都合。
学習が進んだら上限を 300→500 と戻していく（これ自体がカリキュラム）。

### ★★★ 対策2: 終盤局面からの自己対局開始（本命・要実装）

**現状の制約**: `ShogiEnv::reset()` は常に平手初期配置
（`board_.init(Board::Handicap::Even)`）。開始局面指定の仕組みは存在しない。

**必要な実装**（C++、リビルド必要）:

1. **SFENパーサ**を `board.h/cpp` に追加（`Board::initFromSfen(const std::string&)`）
2. **設定キー追加**: `env_shogi_opening_sfen_file=<path>`（SFENを1行1局面で列挙）
3. **`ShogiEnv::reset()` 改造**: プールが指定されていれば確率的にランダムな
   SFEN局面から開始（`env_shogi_opening_ratio=0.5` のような混合比も設定可能に）

```cpp
void ShogiEnv::reset() {
    if (!opening_pool_.empty() &&
        utils::Random::randReal() < config::env_shogi_opening_ratio) {
        board_.initFromSfen(opening_pool_[utils::Random::randInt() % opening_pool_.size()]);
    } else {
        board_.init(Board::Handicap::Even);
    }
    // ... 以下既存処理
}
```

**局面プールの作り方**（Python、実装容易）:

- 既存の自己対局SGF（38 iter分・数万局）から**決着がついたゲーム**の
  終盤局面（詰みのN手前）を抽出 → 数千局面のプールが即座に作れる
- `tsume_shogi.py` の詰将棋プリセットも加える
- 抽出スクリプト: SGFの行動ID列を `env_py` で再生し、終局M手前の局面を
  SFEN出力（`build/shogi/env_py.so` で可能）

### ★★☆ 対策3: フェーズ制ハイパーパラメータ（従来案・有効なまま）

| フェーズ | iter 範囲 | 開始局面 | 手数上限 | MCTS sim | lr |
|---------|-----------|---------|---------|----------|-----|
| **Phase A: 詰み学習** | 1〜50 | 終盤プール80% | 200 | 50 | 0.02 |
| **Phase B: 中盤学習** | 50〜200 | 中盤プール50% | 300 | 100 | 0.02 |
| **Phase C: 通常学習** | 200〜500 | 平手100% | 500 | 200 | 0.005 |

フェーズ切替は `-conf_str` + Continue で手動実行（従来の方法A）:

```bash
echo "C" | ./minizero/scripts/zero-server.sh shogi CFG 200 -n NAME \
  -conf_str "actor_num_simulation=100:env_shogi_opening_ratio=0.5"
```

### ★☆☆ 対策4: resign関連の調整

- `actor_resign_threshold=-0.9` は価値が0に張り付いている現状では発動しない。
  対策1・2で価値シグナルが健全化した後、`-0.8` への緩和を検討。
- `zero_disable_resign_ratio=0.1`（resign無効化率）は現状維持で良い。

---

## 強さの検証：ELO測定（実装済み）

`scripts/shogi_eval.py` でモデル間対戦が可能（gogui-twogtpは
`ShogiAction::toConsoleString()` が空文字スタブのため将棋では機能しない）。

```bash
# コンテナ内で実行
python3 scripts/shogi_eval.py \
  --model1 <old>.pt --model2 <new>.pt \
  --conf configs/9x9_shogi/RRTRRT.cfg --games 20 --out result.txt
```

カリキュラム導入後は **10 iter ごとに前バージョンと20局対戦**して
ELO推移を記録する（勝率停滞＝カリキュラム見直しのシグナル）。

---

## AttentionMapへの期待効果

| 対策 | Attention への効果 |
|------|-------------------|
| 引き分け削減 | 価値勾配が復活 → Q·K重みへの学習圧力が増加 |
| 終盤局面開始 | 「詰み筋への注目」という明確なパターンが学習される |
| relative_bias randn初期化（再学習時） | 位置依存パターンの学習が加速 |

→ 悪循環の解消は AttentionMap 可視化の品質改善にも直結する。

---

## 推奨実行順序

1. **今すぐ（学習停止中）**: ELO測定で現行モデルの強さ推移を確認（実行中）
2. **次**: SGFから終盤局面プールを抽出するスクリプト作成（Python・リビルド不要）
3. **その次**: SFENパーサ + opening pool 対応をC++に実装 → リビルド
4. **再学習開始**: Phase A 設定（手数上限200・終盤プール80%）+ relative_bias randn初期化
5. **10 iter ごと**: ELO測定 + AttentionMap確認 + 引き分け率モニタリング
