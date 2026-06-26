# カリキュラムトレーニング設計案

## 現状の MiniZero における自動カリキュラム

以下はすでに実装済み：

```cfg
actor_select_action_softmax_temperature_decay=true
# iter 0-50%   : temperature=1.0  （ランダム探索重視）
# iter 50-75%  : temperature=0.5  （中間）
# iter 75-100% : temperature=0.25 （最善手重視）
```

---

## 段階的カリキュラムの提案

### フェーズ構成

| フェーズ | iter 範囲 | 目的 | 主な変更 |
|---------|-----------|------|----------|
| **Phase 1: 速習期** | 1〜50 | 基本的な駒の動き・価値を学ぶ | MCTS少・ゲーム多・lr高 |
| **Phase 2: 深化期** | 50〜200 | 中盤の判断力・定跡を学ぶ | MCTS増・品質向上 |
| **Phase 3: 精練期** | 200〜500 | 終盤・詰みの読みを精緻化 | MCTS最大・lr低 |

### 各フェーズの設定値

```
# Phase 1 (iter 1-50): 速度優先
actor_num_simulation=50
zero_num_games_per_iteration=1000
learner_learning_rate=0.02
learner_training_step=200

# Phase 2 (iter 50-200): バランス
actor_num_simulation=100
zero_num_games_per_iteration=1000
learner_learning_rate=0.02
learner_training_step=400

# Phase 3 (iter 200-500): 品質優先
actor_num_simulation=200
zero_num_games_per_iteration=500
learner_learning_rate=0.005
learner_training_step=800
```

---

## MiniZero での実装方法

### 方法 A: 手動フェーズ切り替え（最も簡単）

各フェーズが終わったら `-conf_str` を変えて Continue する：

```bash
# Phase 1 → Phase 2 切り替え（iter50で手動実行）
./minizero/scripts/zero-server.sh shogi cfg_v2.cfg 500 \
  -n shogi_9x9_gaz_2R1T2R1T_P_TV_n50 \
  -conf_str "actor_num_simulation=100:learner_training_step=400"
# → プロンプトで "C" (Continue)
```

### 方法 B: スクリプトで自動切り替え

```bash
#!/bin/bash
# curriculum_train.sh

GAME=shogi
CFG=shogi_9x9_gaz_2R1T2R1T_P_TV_n50_v2.cfg
NAME=shogi_9x9_gaz_2R1T2R1T_P_TV_n50

# Phase 1: iter 1-50
echo "C" | ./minizero/scripts/zero-server.sh $GAME $CFG 50 -n $NAME \
  -conf_str "actor_num_simulation=50:learner_training_step=200"

# Phase 2: iter 50-200
echo "C" | ./minizero/scripts/zero-server.sh $GAME $CFG 200 -n $NAME \
  -conf_str "actor_num_simulation=100:learner_training_step=400"

# Phase 3: iter 200-500
echo "C" | ./minizero/scripts/zero-server.sh $GAME $CFG 500 -n $NAME \
  -conf_str "actor_num_simulation=200:learner_training_step=800:learner_learning_rate=0.005"
```

### 方法 C: train.py を改造して自動スケジューリング（高度）

```python
# restnet/learner/train.py に追加
def get_curriculum_params(current_iter, total_iter):
    ratio = current_iter / total_iter
    if ratio < 0.1:      # Phase 1
        return {"num_simulation": 50,  "lr": 0.02}
    elif ratio < 0.4:    # Phase 2
        return {"num_simulation": 100, "lr": 0.02}
    else:                # Phase 3
        return {"num_simulation": 200, "lr": 0.005}
```

---

## Attention Map への効果

カリキュラムトレーニングが Attention Map に与える効果：

| フェーズ | Q·K logit の変化 | 期待されるAttentionパターン |
|---------|-----------------|--------------------------|
| Phase 1 | 小さい（現在と同程度） | 均等分散 |
| Phase 2 | 中程度 | 局所的なパターンが出始める |
| Phase 3 | より大きい | 玉・大駒への集中が鮮明になる |

→ iter 200以降でAttentionMapの集中度が向上すると期待できる。

---

## 推奨手順（現状から）

1. **今すぐ**: v2.cfg + Continue で iter 12 の OOM を解消して学習を再開
2. **iter 50 到達後**: `-conf_str` で `actor_num_simulation=100` に引き上げ
3. **iter 200 到達後**: `-conf_str` で `actor_num_simulation=200:learner_learning_rate=0.005`
4. **各ステップ後**: XAI アプリでAttentionMapを確認して集中度の変化を観察
