# 将棋版 board evaluation（先手の利きが多い割合）の構想（2026-08-03 作成・未実装）

ResTNet 論文が XAI の定量的証拠として使っている board evaluation（bv）は囲碁固有の仕組みで、
将棋には直接の対応物がない。将棋で同等の役割を果たすものを定義できないか検討した記録。

**現状は構想のみで、実装していない。** ブートストラップ事前学習は bv なしで進める。

## 1. 論文における bv の位置づけ

bv は補助的な機能ではなく、**「ResTNet は大局的なパターンを認識している」ことを数値で示すための主な方法**。

論文 4.2 節「Recognize Circular Patterns」の主張（循環パターン認識の MSE 2.58 → 1.07）は、
attention map ではなく **board ownership 予測の誤差**で測られている。README の該当箇所:

```bash
# This command evaluates board ownership predictions on
# the 24-game dataset located at ./experiments-datasets/go_19x19_24_circular_patterns
./scripts/recognize-circular-patterns.sh
```

attention map は「どこに重みを向けているか」しか示さず、それでモデルの評価が正しいかは分からない。
bv は評価そのものを出力するので、正解と比較して誤差を測れる。ここが決定的な差になっている。

## 2. bv の中身

`restnet/learner/t_data_loader.cpp` の `getAlphaZeroBVData()`。
盤の広さと同じ長さのベクトル（19路なら361、9路なら81）を出し、各点が 0.0〜1.0 を取る。

```
1.0 = 黒が確保 / 0.5 = 未確定 / 0.0 = 白が確保
```

教師信号は**対局を最後まで進めて**作る。

```cpp
// 現在位置 pos 以降の手を全部進めて終局させる
for (size_t i = pos; i < env_loader.getActionPairs().size(); ++i)
    env.act(env_loader.getActionPairs()[i].first);

data.board_evaluation_.resize(board_size * board_size, 0.5f);   // 既定は未確定
// Benson の完全生存判定 → 石の有無 → 眼が1目か、の順に所有者を確定
if (env.getBensonBitboard().get(kPlayer1).test(pos))  → 1.0f
else if (grid.getPlayer() == kPlayer1)                → 1.0f
...
```

`getBensonBitboard` は Benson のアルゴリズム（相手がどう打っても取られない石の数学的判定）。

## 3. bv が成立している条件

囲碁の bv は3つを同時に満たしている。将棋版を考えるときの要件になる。

| | 条件 | 意味 |
|---|---|---|
| ① | マス単位で値を持つ | 盤の形に並ぶマスごとの値になる |
| ② | その後の局面から作られる | 現局面から計算できない = 予測課題になる |
| ③ | 客観的な正解が定義できる | 誤差を測れる |

②が重要。現局面から計算できる量を予測させても学習課題にならない。

## 4. 将棋で成立しない理由

囲碁は**石が動かない**ので「この交点は最終的に誰の地か」が定義できる。
将棋は**駒が動き続ける**ため、終局図でも「このマスは誰のもの」が成立しない。
終局時に駒が乗っているマスは盤の一部だけで、残りは空白になる。

## 5. 候補の比較

| 候補 | ①空間 | ②その後の局面 | ③客観 | 評価 |
|---|---|---|---|---|
| 現局面のマスごとの利き | ✓ | **✗** | ✓ | 現局面から計算できるので予測課題にならない |
| 終局図の駒配置 | ✓ | ✓ | ✓ | 大半が空マスで情報が少ない |
| **残り手数を通じた先手の利きが多い割合** | ✓ | ✓ | ✓ | **有力** |
| 玉の最終位置・詰み筋 | △疎 | ✓ | ✓ | 疎すぎて密な信号にならない |

## 6. 提案：先手の利きが多い割合

現局面から終局までの各局面で「そのマスに先手の利きが多いか後手が多いか」を数え、平均を取る。

```
1.0 = 残りの対局を通じて常に先手の利きが多い
0.5 = 拮抗、または双方の利きがない
0.0 = 常に後手の利きが多い
```

囲碁の ownership が「最終的に誰の地か」なのに対し、これは「**今後そのマスにどちらの利きが多いか**」。
将棋でいう、マスへの利きの数の多い少ないに対応する。

### 実装に使える既存のコード

利きを計算するコードは既にある。sunfish 由来の Bitboard 実装が入っているので、
新規にルール実装をする必要はなく、既存の利き計算を呼んで集計するだけで済む。

- `minizero/minizero/environment/shogi/MoveTable.h` — 利き計算テーブル
- `minizero/minizero/environment/shogi/Data.h:57` — `AttackableTables`
- `minizero/minizero/environment/shogi/MoveGenerator.h` — 合法手生成

囲碁側のコードは `#if GO` で囲まれているので（`restnet/learner/pybind.cpp:91-109`）、
**既存機能を削除せず**、将棋用の経路を並べて追加する形にできる。

### 決めていない設計事項

やることは mdfolder/計画.md に移した（2026-11-16）。

## 7. 期待される効果

**1. 密な教師信号による学習効率の向上**

policy は「11,259手のうち1つ」、value は「1つの数値」しか正解を与えないが、bv は 81マス分の正解を毎局面与える。
KataGo は ownership head の追加で学習速度が大きく改善したと報告している。
今回の棋譜は 73,540 局と ResTNet 19×19（100万局）の 7% しかないので、
限られたデータから多くを学ばせるという点で効きうる。

**2. attention map とは別種の XAI 手段**

出力そのものを正解と比較して誤差を測れる。attention map だけでは出せない定量的証拠になる。

**3. 論文と同じ形式の実験が将棋で構成できる**

論文 4.2 節は「10R は認識できず ResTNet は認識できる大局的パターン」を bv の誤差で示した。
将棋で同じ比較を作れる。近くのマスだけを調べると影響が小さく見えるが、盤の反対側のマスに利きが届く配置として、
遠見の角、香車の睨み、端攻めの利きなどが候補になる。

## 8. 留意点

これは**論文の再現ではなく新規提案**になる。「囲碁の bv に相当するものを将棋で定義した」という
主張とその妥当性の説明が要る。工数も bv なしの場合より明確に増える。

一方、XAI が研究の主題である以上、attention map だけで論を立てるより主張は強くなる。

## 関連

- `mdfolder/attention_map.md` — attention map による分析
- `mdfolder/xai_guide.md` — XAI 全体の手引き
- `mdfolder/bootstrap_pretraining.md` — 事前学習（bv なしで進行中）
