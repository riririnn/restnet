# ミーティング資料（次回。2026-11-16 作成）

報告する項目を、少しずつ足していく。

---

## 1. 9×9 の将棋：投了した自己対局が引き分けとして記録されていた

### 何が起きたか

9×9 の将棋の自己対局で、投了で終わった対局の結果が 0（引き分け）と記録されていた。その対局のすべての局面で、value の正解が 0 になった。論文の 9×9 の自己対局のモデル（R3(RRT)、10R）の学習に当てはまる。動物将棋には当てはまらない。

論文の R3(RRT) の学習の棋譜（各 iteration 2,000 局）：

| iteration | 10 | 100 | 300 | 500 |
|---|---|---|---|---|
| 投了で終わった対局（すべて結果 0） | 20 | 633 | 875 | 1,126 |
| 512 手で打ち切りの引き分け | 204 | 7 | 6 | 1 |
| 結果 0 の対局の割合 | 0.1120 | 0.3200 | 0.4405 | 0.5635 |

### 直したコード

minizero/minizero/environment/shogi/shogi.cpp:330-335（minizero の commit 1a5361a、2026-11-02）

```cpp
float ShogiEnv::getEvalScore(bool is_resign) const {
    // a resignation is the loss of the side to move (base_actor.cpp writes this as the RE of a
    // self-play game that did not end by the rules); it used to fall through to 0, a draw
    if (is_resign && winner_ == GameResult::UNDECIDED) { return turn_ == Player::kPlayer1 ? -1.0f : 1.0f; }
    return (winner_ == GameResult::BLACK_WON) ? 1.0f : (winner_ == GameResult::WHITE_WON) ? -1.0f : 0.0f;
}
```

直す前は、最後の `return` の 1 行だけだった。331-333 行を足した。投了なら、手番側の負けを返す。

### なぜそうなったか

1. MiniZero は、規則で終わっていない対局を投了とみなし、`getEvalScore(true)` の値を棋譜の結果（RE）に書く（minizero/minizero/actor/base_actor.cpp:48-53。変えていない）。そのため、投了の結果は、ゲームごとの環境の `getEvalScore` が返す必要がある。
2. 将棋の環境の `getEvalScore` は `is_resign` を使わず、勝者（`winner_`）だけを見ていた。投了の時点では勝者が決まっていないので、0 を返した。
3. 動物将棋の環境は、`is_resign` のとき手番でない側を勝ちにする（minizero/minizero/environment/dobutsu/dobutsu.cpp:284-286）。そのため、動物将棋には当てはまらない。
4. この行は、将棋の環境を取り込んだときからあった。取り込んだ commit（minizero 0c35936、2026-05-19、Kaito さんのコードの写し）と、論文の学習に使った版（minizero 8783e3b）の `getEvalScore` は、どちらも上の最後の `return` の 1 行だけである（2026-11-16 に `git show` で確かめた）。
5. 投了した対局の結果が ±1 になるかを確かめる仕組みがなく、Training.log の結果 0 の割合も、予想の値と比べていなかった。そのため、学習の間は気づかなかった。

### 見つけた方法

2026-11-02 に、9×9 の将棋の環境を、独立した実装（python-shogi）と floodgate の実際の対局で突き合わせる確かめのスクリプト（scripts/shogi_env_check.py）を作り、点検したときに見つけた。

### 確かめた方法と使ったスクリプト

| 何を確かめたか | 方法 | スクリプト・コマンド | 結果 |
|---|---|---|---|
| 直したコードが、投了を手番側の負けとして返すか | 1 手指した局面（後手番）と 2 手指した局面（先手番）で `get_eval_score(True)` を呼ぶ | scripts/shogi_env_check.py の `check_resign`（86-93 行） | +1 と −1（期待どおり）。2026-11-16 に、今のビルドで同じ手順を実行し直して同じ結果 |
| 論文の学習で、投了の対局が何局あり、結果がいくつと記録されたか | 棋譜の終局の理由（`RR[resign]`）と結果（`RE[0]`）を数える | 下のコマンド 1 | 上の表。投了の対局はすべて `RE[0]` |
| 学習のすべての iteration で、結果 0 の対局の割合 | Training.log の結果の平均 μ と標準偏差 σ から、1 − (μ² + σ² × 1999/2000) を求める（結果は −1、0、+1 なので、0 でない対局の割合は結果の二乗の平均。σ は 2,000 局の標本標準偏差） | 下のコマンド 2 | 論文の R3(RRT)：iteration 500 で 0.5635、最大 0.6020。棋譜の数と 4 桁まで一致。SL の 10T から始めた RL（11-05 から、直したあとの版で学習）：すべての iteration で 0.0015 以下 |

コマンド 1（この PC、ホスト、/home/rin/restnet。棋譜はサーバーからコピーしたもの）：

```bash
for i in 10 100 300 500; do f=models/9x9_shogi/eval/R3RRT/sgf/$i.sgf; echo "$i: games $(wc -l < $f) resign $(grep -c 'RR\[resign\]' $f) resign_RE0 $(grep 'RR\[resign\]' $f | grep -c 'RE\[0\]')"; done
```

コマンド 2（この PC、ホスト、/home/rin/restnet）：

```bash
python3 - models/9x9_shogi/eval/R3RRT/Training.log <<'EOF'
import sys, re
L = open(sys.argv[1]).read(); n = 2000
m = [float(x) for x in re.findall(r'Avg\. Game Returns\] ([-\d.]+)', L)]
s = [float(x) for x in re.findall(r'Std\. Game Returns\] ([-\d.]+)', L)]
z = [1 - (a * a + b * b * (n - 1) / n) for a, b in zip(m, s)]
print(' '.join('%d:%.4f' % (i + 1, v) for i, v in enumerate(z)))
EOF
```

コマンド 1 と 2 は、スクリプトのファイルとしては残していない。

### 詳しい記録

- mdfolder/known_bugs.md の 9 節（影響した学習の一覧）
- mdfolder/after_gpw_submission.md の 5.2 節
- mdfolder/explain/2026-11-15_投了の不具合.md（value が本当の結果の約 0.6 倍になったこと、第 2・第 3 T ブロックの query と key の重み）
