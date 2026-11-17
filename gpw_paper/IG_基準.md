# GPW 2026 論文の IG の基準について（2026-11-01）

## 結論

- 提出版の IG の記述に、事実と違うものは見つからなかった。訂正版は出さない。
- 提出版では、全部 0 の入力を基準にした。この基準での value は、ほぼ 0（中立）である。
  - 動物将棋の 6T で +0.06、9×9 の将棋の R3(RRT) で +0.04。
  - これは、引用した IG の原論文が勧める「基準での予測がほぼ 0」に合っている。
- 提出後にわかったこと：全部 0 の基準では、手番の平面も 0 になる。そのため、動物将棋の value の IG では、駒の符号が手番で反対になることがある。
  - 例：取れる局面で、相手のライオンが青になる割合。先手番 2.5%、後手番 84.3%。同じ局面を 2 つの向きで入れた 400 組でも、6 割のマスで符号が反対だった。
  - policy（手の確率）の IG では、この基準による反転は起きていない。9×9 の将棋では、value でも policy でも起きていない（「policy でも起きるか」の節）。
  - これは論文の記述と食い違わない。発表で伝える限界とする。
- 提出後に試した「駒だけ 0」の基準は、動物将棋では基準での value が手番側から見て −0.95 や −0.85 で、原論文の勧めに合わない。
  - なので、提出版を正すものではなく、比べるための別の基準として扱う。
- 動物将棋では、実際に現れる手番・回数の組み合わせのまま駒だけ 0 にすると、value はどれも中立にならない（絶対値 0.58 以上）。データの平均も中立にならない。
- 9×9 の将棋では、全部 0 の盤で手番の平面を変えても、value はほとんど変わらない（+0.040 と +0.007）。

## 経緯

| 日時（日本時間） | 出来事 |
|---|---|
| 2026-06-23 | 9×9 の将棋の GUI（xai_app.py）に IG を入れ、全部 0 の入力を基準にした。mdfolder/xai_guide.md には「空盤は自然な基準」とあるだけで、引用はない |
| 2026-10-22 09:39 | IG を動物将棋の GUI（scripts/dobutsu_viewer.py）に広げた（コミット d475e26、961020c）。基準は全部 0 のまま |
| 2026-10-22 10:19 | 「IG の画像は論文でどう使われているか」に答えて、IG を使った例として Czech らを初めて紹介した。このとき「Czech らの基準は全部 0 ではなく、検証データの全入力の平均」と伝えていた |
| 2026-10-23 | 「IG を利用した研究を関連研究で紹介してほしい」という依頼で、2.3 節に IG の原論文と Czech らを入れた（コミット 5a75c52） |
| 提出 | 提出版（コミット 1334a06、gpw_paper/paper_submitted.pdf） |
| 提出後 | 図 2（後手番の局面）の value の IG で、a3 の先手のライオンが青だった。その理由を調べ、手番による違いを見つけた |
| 提出後 | 「駒だけ 0」の基準でコードと論文を変更した（コミット 625eccd、a7c6b72、7ee25af、fdca326） |
| 2026-11-01 | 引用した 2 本を全文読み、基準での出力を計算した。そのうえで、提出版に誤りはないと判断した |
| 2026-11-01 | 動物将棋の環境を実装し直した：後手番は盤を回し、value は手番側の値、行動 ID は手番側の座標、入力は 19 枚（同じ日に手数の平面を外した）で、並びは 9×9 と同じ（mdfolder/known_bugs.md の #8）。重みは学習し直す（models/dobutsu/v2） |

全部 0 の基準は、Czech らを読む前に決めていた。論文でも、基準の根拠として Czech らは挙げていない。

## 本研究の入力と、全部 0 の基準で 0 になるもの

### 動物将棋（20 平面、4×3）

minizero/minizero/environment/dobutsu/dobutsu.cpp の getFeatures で確かめた。

| 平面 | 中身 |
|---|---|
| 0–4 | 手番側の盤上の駒（きりん、ぞう、ひよこ、にわとり、ライオン）。駒のあるマスが 1 |
| 5–9 | 相手の盤上の駒 |
| 10–12 | 手番側の持ち駒の数（きりん、ぞう、ひよこ）。平面全体に同じ数 |
| 13–15 | 相手の持ち駒の数 |
| 16 | 先手番なら 1 |
| 17 | 後手番なら 1 |
| 18 | その局面が初めてなら 1 |
| 19 | 2 回目以上なら 1 |

- 実際の局面では、16・17 のどちらか一方と、18・19 のどちらか一方が必ず 1 である。
- 駒は手番側と相手に分けて入れるが、盤は手番側の向きに回していない。マスの位置は先手から見たまま。
- value は先手から見た値である。ライオンを取れる勝ちの局面で、value の平均は先手番 +0.976（5,696 局面）、後手番 −0.924（5,579 局面）。
- GUI の IG（scripts/dobutsu_viewer.py の ig_figure）と、この文書の集計は、どちらも scripts/dobutsu_all_agreement.py の features で入力を作る。
  - features は、同じ局面が初めてのとき（平面 18 が 1）の入力を作る。
  - C++ の環境で無作為に 300 局指した 4,371 局面で、features の入力と C++ の getFeatures の入力は、全局面で全平面が同じだった。駒だけ 0 の基準も同じだった。
  - 2 回目以上の局面（14 局面）は、平面 0〜17 だけ比べて同じだった。
- value は先手から見た値で、GUI では符号を掛けて手番側から見た値にしている。
- 全部 0 の基準では、平面 16・17 も 0 になる。これは「先手番でも後手番でもない」入力で、学習には一度も現れない。

### 9×9 の将棋（362 平面、9×9）

minizero/minizero/environment/shogi/shogi.cpp の getFeatures で確かめた。

| 平面 | 中身 |
|---|---|
| 45k + 0〜27（k = 0〜7、直近 8 局面） | 手番側と相手の盤上の駒 |
| 45k + 28〜30 | 同じ局面の回数（1〜3 回目）。初めてなら 28 が 1 |
| 45k + 31〜44 | 手番側と相手の持ち駒の数 |
| 360 | 先手番なら 1、後手番なら 0 |
| 361 | 手数 ÷ 512 |

- 後手番では盤を 180 度回して、手番側から見た向きにしている。
- value は手番側から見た値（xai_app.py の IG は符号を掛けていない）。
- 全部 0 の基準では、回数・手番・手数の平面も 0 になる。ただし後手番では、手番の平面はもともと 0 である。

## 提出後にわかったこと

調べた局面：動物将棋の無作為な 2,000 局面のうち、相手のライオンを取れる 1,166 局面。モデルは 6T、出力は value（手番側から見た値）。

| 基準 | 先手番：相手のライオンが青の割合 | 後手番：青の割合 |
|---|---|---|
| 全部 0（提出版） | 2.5% | 84.3% |
| 駒だけ 0（手番などは今の局面のまま） | 46.5% | 53.7% |

- 先手番と後手番の局面は、同じ母集団から別々に取り出したもので、同じ局面の組ではない。
- 手番の平面を基準に残すと、手番による差はほぼ消えた。
- 考えられる理由：手番と駒の組み合わせの効果（入力どうしの相互作用）が、駒の値に入るため。ただし確かめていない。
- 「相手のライオンがいること自体が value を下げる」という前回のミーティングでの説明は、どちらの基準でも成り立たなかった。
- 駒だけ 0 の基準で、取れる局面で value を一番押し上げた駒は次のとおり。
  - 59% が、相手のライオンを取れる自分の駒（ライオン以外 35.8%、ライオン 23.2%）。
  - 相手のライオンが一番押し上げたのは 19.6%。
- 図 2 の局面そのものでは、a3 のライオンは、どちらの基準でも value を押し下げた（全部 0 で −1.45、駒だけ 0 で −2.22）。

## 無作為な局面で基準と方法を比べた（2026-11-05）

`scripts/ig_statistics.py run`（`scripts/gpw_statistics.sh` の ig）。相手のライオンを取れる局面と、ほかの終わっていない局面を同じ数ずつ、4 つの向きで入れた（6T は 1,000 局面ずつで 8,000 入力、RRTRRT と 6R は 500 局面ずつで 4,000 入力）。基準は全部 0、駒だけ 0、データの平均。方法は IG（300 ステップ）、同じ基準での厳密な Shapley 値、1 つの駒を除く、勾配 × 入力。結果は data/dobutsu_all/ig_{6T,RRTRRT,6R}.txt、表は gpw_paper/poster_parts.md の 8 節。

| 取れる相手のライオンが負になる割合（value、先手番／後手番） | 6T | RRTRRT | 6R |
|---|---|---|---|
| IG・全部 0（提出版） | 2.9%／87.5% | 11.2%／22.6% | 2.7%／25.5% |
| Shapley 値・全部 0 | 10.0%／66.8% | 13.4%／38.4% | 2.0%／67.0% |
| IG・駒だけ 0 | 53.8%／52.8% | 10.6%／13.1% | 2.2%／25.7% |
| Shapley 値・駒だけ 0 | 30.1%／39.0% | 4.4%／4.8% | 0.9%／8.9% |

- 全部 0 の基準での手番による違いは、同じ基準の厳密な Shapley 値でも 3 つの構成すべてで起きるので、IG だけの性質ではない。手番と回数の平面を残すと、Shapley 値の差は小さくなる（6T で 57 → 9 ポイント、RRTRRT で 25 → 0.4、6R で 65 → 8）。「手番と駒の相互作用が駒の値に入る」という考えに合う（相互作用そのものは数えていない）。ただし 6R の IG では、残しても差は変わらない（全部 0 で 2.7% と 25.5%、駒だけ 0 で 2.2% と 25.7%）。
- 同じ局面で先後を入れ替えたとき、6T の value で符号が反対になる駒（両方で |値| > 0.02）は、IG・全部 0 で 58.4%、IG・駒だけ 0 で 7.4%、Shapley 値・駒だけ 0 で 3.6%。
- 全部 0 の基準での value が中立なのは 6T だけ（+0.058）。RRTRRT は −0.945、6R は −0.983（先手番、手番側から見て）。
- 手の確率では方法の間の一致が高い（6T で、IG・全部 0 と Shapley 値・全部 0 の最大の駒が同じ割合 87%。value では 43%）。
- 6T の value の IG（全部 0）の絶対値の上位 3 マスと、手番側のライオンからの重みの上位 3 マスの重なりは 1.19（第 5 T ブロック第 4 ヘッド）と 1.31（第 4 T ブロック第 1 ヘッド）。駒のあるマスから無作為に 3 つ選んだとき（1.30）と同じか低い（どのマスでも無作為なら 0.75）。

## 基準での出力

IG の原論文は、基準での予測がほぼ 0 になるかを確かめるよう勧めている（下の「引用した論文に書いてあること」）。value の範囲は −1〜+1。
計算は CPU で行い、使い終えたら消える一時的なコンテナで動かした。

### 動物将棋 6T：駒をすべて 0 にし、平面 16〜19 を変えたとき

| 16 先手番 | 17 後手番 | 18 初めて | 19 2 回目以上 | value（先手から見た値） | 実際に現れる組み合わせか |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | +0.058 | 全部 0（提出版の基準） |
| 0 | 0 | 0 | 1 | −0.290 | |
| 0 | 0 | 1 | 0 | +0.535 | |
| 0 | 0 | 1 | 1 | −0.012 | |
| 0 | 1 | 0 | 0 | +0.772 | |
| 0 | 1 | 0 | 1 | +0.583 | 現れる |
| 0 | 1 | 1 | 0 | +0.853 | 現れる（後手番の局面の「駒だけ 0」） |
| 0 | 1 | 1 | 1 | +0.645 | |
| 1 | 0 | 0 | 0 | −0.986 | |
| 1 | 0 | 0 | 1 | −0.919 | 現れる |
| 1 | 0 | 1 | 0 | −0.949 | 現れる（先手番の局面の「駒だけ 0」） |
| 1 | 0 | 1 | 1 | −0.602 | |
| 1 | 1 | 0 | 0 | −0.859 | |
| 1 | 1 | 0 | 1 | +0.578 | |
| 1 | 1 | 1 | 0 | +0.614 | |
| 1 | 1 | 1 | 1 | +0.800 | |

- value がほぼ 0 になるのは、全部 0（+0.058）と「手番なし・回数の平面が両方 1」（−0.012）だけ。どちらも実際には現れない。
- 実際に現れる 4 つの組み合わせでは、value の絶対値がどれも 0.58 以上。手番側から見ると −0.95〜−0.58 で、駒のない盤では手番側が負けと出る。
- 駒のない盤は学習に現れない入力なので、これは将棋として意味のある評価ではない。

### 動物将棋 6T：ほかの基準

無作為な 19,434 局面（先手番 9,728）を使った。

| 基準 | value（先手から見た値） |
|---|---|
| 駒なし、手番の平面を 0.5 ずつ、平面 18 が 1 | −0.524 |
| 全局面の平均（Czech らの主な結果と同じ考え方） | −0.921 |
| 先手番の局面の平均 | +0.346 |
| 後手番の局面の平均 | +0.783（後手から見て −0.783） |

- 実際の局面の value は、平均 +0.023、絶対値の平均 0.894。勝ち負けのはっきりした局面が多い。
- データの平均を基準にしても、value は中立にならない。

### 動物将棋 6T：全部 0 の基準で、手番の平面の IG はどれだけか

無作為な 300 局面で、value（手番側から見た値）の IG を、平面の種類ごとに足して平均した。

| 手番 | 局面数 | 駒（0〜15） | 手番（16、17） | 回数（18、19） | 合計 |
|---|---|---|---|---|---|
| 先手番 | 146 | +0.987 | −0.365 | +0.051 | +0.672 |
| 後手番 | 154 | +0.959 | −0.184 | −0.140 | +0.634 |

- 全部 0 の基準でも、手番の効果は、手番の平面そのものの値として表れる（先手番で −0.37、後手番で −0.18）。
- それでも駒の値の符号が手番で変わるのは、手番と駒の組み合わせの効果が駒の値に入るためと考えられる（推測）。

### 9×9 の将棋 R3(RRT)

重みは models/9x9_shogi/eval/R3RRT/model/weight_iter_100000.pt（SHA-256 の先頭 5c3301278dae16ef）。value は手番側から見た値。

| 基準 | value |
|---|---|
| 全部 0（提出版の基準） | +0.040 |
| 全部 0 で、手番の平面だけ 1 | +0.007 |
| 駒だけ 0、80 手目までの局面（先手番） | −0.204 |
| 駒だけ 0、103 手目までの局面（後手番） | −0.161 |
| 駒だけ 0、118 手目までの局面（先手番） | −0.199 |

- 全部 0 の盤で手番の平面を変えても、value はほとんど変わらない。盤を手番側の向きに回しているためと考えられる。

### 9×9 の将棋：手番の平面を変えても駒の IG の符号は変わらない（turn9.py）

9×9 は盤を手番側の向きに回すので、実際の局面の入力で手番の平面（360）だけを 1 ↔ 0 に変えた入力は、先後を入れ替えた同じ形の局面（これも実際にありうる局面）の入力になる。floodgate 2026 の棋譜（両者レート 3000 以上、投了で終わった 60 手以上の対局）30 局から 20 手ごとに取った 185 局面で、この 2 つの入力の value の IG を比べた。

| 基準 | 駒のあるマスで符号が違う割合 | \|IG\| > 0.02 のマスで符号が違う割合 | \|IG\| が最大のマスが同じ割合 | 相手の玉が青の割合（元 / 入れ替え） |
|---|---|---|---|---|
| 全部 0 | 3.5% | 0.0% | 88.1% | 62.7% / 66.5% |
| 駒だけ 0 | 4.8% | 0.1% | 87.6% | 63.8% / 64.9% |

- value の差は平均 0.027（最大 0.091、value の絶対値の平均 0.216）。
- IG の差の絶対値の平均は 0.0036（全部 0）で、IG の絶対値の平均 0.028 の 13%。
- つまり 9×9 では、動物将棋で起きた手番による符号の反転は起きていない。盤を回して手番側から見た入力にするので、手番の平面は出力にほとんど効かないため。

GUI の入力との一致（check9.py）：
- GUI は論文の 3 局面の入力を、tsume_shogi.py の sfen_to_tensor で作る。藤井－羽生戦の棋譜を初手から C++ の環境で指し直して、getFeatures を呼ぶ。
- 指し直した入力の今の局面の平面（0〜44）と手番の平面は、SFEN から直接作った入力と同じだった。3 局面とも。
- 手数の平面（80 ÷ 512 = 0.1562 など）も同じだった。
- GUI の「駒だけ 0」の基準（pieces_removed）は、上の表の値を出した手作りの入力と、3 局面とも全平面で同じだった。
  - 0 でない平面：各局面の同じ局面の回数（28、73、…、343）、手番（360、先手番のみ）、手数（361）。
- 組み立て直した Python のモデルと保存されたモデルの出力の差は 0。

| 局面 | value | IG の合計（全部 0 の基準） | 出力 − 基準での出力 | IG の合計（駒だけ 0 の基準） | 出力 − 基準での出力 |
|---|---|---|---|---|---|
| 80 手目まで（先手番） | −0.273 | −0.308 | −0.313 | −0.074 | −0.070 |
| 103 手目まで（後手番） | −0.495 | −0.532 | −0.535 | −0.334 | −0.334 |
| 118 手目まで（先手番） | +0.016 | −0.018 | −0.023 | +0.207 | +0.216 |

- 合計と差のずれは、全部 0 の基準で 0.006 以内（提出版に書いた値と合う）、駒だけ 0 の基準で 0.009 以内。

全部 0 の基準で、駒以外の平面の IG：

| 局面 | 駒（盤上と持ち駒） | 同じ局面の回数 | 手番 | 手数 |
|---|---|---|---|---|
| 80 手目まで（先手番） | −0.236 | −0.052 | −0.014 | −0.007 |
| 103 手目まで（後手番） | −0.433 | −0.086 | 0（後手番は基準と同じ 0） | −0.014 |
| 118 手目まで（先手番） | +0.077 | −0.048 | −0.046 | −0.001 |

## policy（手の確率）でも起きるか（2026-11-01）

### 動物将棋 6T：同じ局面を 2 つの向きで入れた組（pair_dobutsu.py、pair_strata.py）

完全解析の同じ局面番号の「先手番として入れた記録」と「180° 回して後手番として入れた記録」は、同じ局面である（2,000 組で、マスは 11 − s に先後を入れ替えて対応し、持ち駒・合法手・最善手も対応することを確かめた。orient_map.py）。
無作為な 400 組（両方のライオンが盤上にある局面。うち取れる局面 235）で、対応する駒の IG の符号を比べた。
value は手番側から見た値、policy は先手番の向きでモデルが選んだ手（と、それを回した手）の確率。

| 出力 | 基準 | 駒のあるマスで符号が違う | \|IG\| > 0.05 のマスで | \|IG\| 最大のマスが同じ | 取れる局面で相手のライオンが青（先手番 / 後手番） | 動かす駒が赤（先手番 / 後手番） |
|---|---|---|---|---|---|---|
| value | 全部 0 | 58.5% | 58.6% | 37.5% | 4.7% / 85.1% | 67.0% / 99.5% |
| value | 駒だけ 0 | 10.5% | 9.3% | 57.3% | 47.7% / 46.8% | 98.0% / 99.2% |
| policy | 全部 0 | 21.4% | 18.5% | 83.8% | 11.5% / 9.8% | 99.5% / 99.5% |
| policy | 駒だけ 0 | 21.5% | 18.1% | 81.2% | 6.8% / 4.7% | 100% / 99.7% |

モデル自身の出力が 2 つの向きでほぼ同じ組（差 0.02 未満）だけで数えても：

| 出力 | 組の数 | 全部 0 で符号が違うマス（\|IG\| > 0.05） | 駒だけ 0 で（\|IG\| > 0.05） |
|---|---|---|---|
| value | 236 | 60.1%（60.2%） | 9.8%（9.0%） |
| policy | 157 | 16.9%（12.8%） | 18.8%（14.2%） |

- **value：** 全部 0 の基準では、同じ局面でも向き（手番）で 6 割のマスの符号が反対になる。駒だけ 0 では 1 割。モデルの出力が両方の向きで同じ組でも同じなので、原因は基準（手番の平面も 0 にすること）である。前に見つけた「相手のライオンが青になる割合が手番で反対（2.5% と 84.3%）」を、同じ局面の組で確かめた形（4.7% と 85.1%）。
- **policy：** 2 つの向きで符号が違うマスは 2 割ほどあるが、全部 0 と駒だけ 0 でほぼ同じで、手番の側に偏ってもいない（動かす駒が赤は両方の向きで 99.5%）。なので、value のような基準による反転ではない。
  - 符号の違いは、モデルの手の確率が 2 つの向きで違うほど多い（確率の差 0.02 未満の組で 13〜14%、0.1 以上の組で 21〜23%。|IG| > 0.05 のマス）。動物将棋は盤を回さずに入れるので、モデルは 2 つの向きを別の入力として計算している。
  - 手の確率の差は平均 0.13（同じ局面・同じ手でも、向きで確率が違う）。value の差は平均 0.10。
- 基準での手の確率は、全部 0 で平均 0.011（最大 0.049）、駒だけ 0 で平均 0.011（最大 0.058）で、どちらもほぼ 0。value と違い、policy では 2 つの基準とも原論文の勧め（基準での出力がほぼ 0）に合う。
- value だけで基準の影響が大きい理由（推測、確かめていない）：6T の value は先手から見た値なので、後手番では手番の平面に応じて符号を逆にする計算がネットワークの中にあるはずである。全部 0 の基準では、手番の平面が駒と一緒に 0 から 1 へ増えるので、この符号の切り替えが駒の値に入る。policy は盤の上の位置で手を表すので、この切り替えが要らない。

### 9×9 の将棋 R3(RRT)：手番の平面だけを入れ替えた組（turn9_policy.py）

floodgate 2026 の棋譜 30 局から 40 手ごとに取った 87 局面で、実際に指された手の確率の IG を、元の局面と先後を入れ替えた局面（手番の平面だけを入れ替えた入力）で比べた。

| 基準 | 駒のあるマスで符号が違う | \|IG\| > 0.02 のマスで | \|IG\| 最大のマスが同じ |
|---|---|---|---|
| 全部 0 | 3.6% | 0.0% | 96.6% |
| 駒だけ 0 | 6.0% | 0.0% | 93.1% |

- 手の確率の差は平均 0.003（最大 0.032）。基準での手の確率は全部 0 で平均 0.002、駒だけ 0 で 0.0001。
- 9×9 の将棋では、value と同じく policy でも、手番による符号の反転は起きていない。

### まとめ

| | value | policy |
|---|---|---|
| 動物将棋（盤を回さない） | 全部 0 の基準で、手番によって符号が反対になる（基準が原因） | 向きで 2 割ほどのマスの符号が違うが、基準によらない（モデルが向きで違う計算をしているため） |
| 9×9 の将棋（盤を回す） | 起きない | 起きない |

## IG の「少しずつ」と、駒を 1 つずつ足すやり方（図 2 の局面で試した。one_by_one.py）

図 2 の局面（6T、後手番、value は手番側から見た値）。今の局面の value +0.993、全部 0 の入力 −0.058、差 +1.052。
「駒」は盤上の 6 枚と持ち駒 2 種、加えて手番・回数の平面を 1 つにまとめたもの（9 個）。

| 駒 | IG | 勾配 × 入力（今の局面の勾配だけ） | 1 つずつ足す：順番による値の範囲 | 負になる順番の割合 | 最初に足す | 最後に足す（1 つだけ除く） | 全順番の平均（Shapley 値） |
|---|---|---|---|---|---|---|---|
| a3 の先手ライオン | −1.45 | −0.01 | −1.94〜+1.79 | 60.0% | −0.72 | +0.00 | −0.28 |
| c2 の後手ライオン | +1.47 | +0.00 | −0.94〜+1.99 | 27.4% | −0.20 | +0.02 | +0.30 |
| a2 の後手にわとり | +0.70 | +0.02 | −1.44〜+1.99 | 13.1% | +0.55 | +0.88 | +0.54 |
| c1 の後手きりん | +0.70 | +0.00 | −1.93〜+1.92 | 50.2% | +0.23 | −0.00 | +0.10 |
| b4 の先手にわとり | −0.43 | −0.00 | −1.49〜+1.10 | 74.7% | −0.71 | −0.00 | −0.13 |
| b1 の先手ぞう | −0.07 | +0.00 | −1.34〜+1.15 | 75.1% | −0.08 | −0.00 | −0.03 |
| 後手の持ち駒のぞう | +0.76 | −0.00 | −0.47〜+1.52 | 12.1% | +0.65 | +0.00 | +0.31 |
| 先手の持ち駒のきりん | −0.33 | +0.00 | −1.22〜+0.65 | 69.9% | −0.12 | +0.00 | −0.10 |
| 手番・回数の平面 | −0.30 | +0.00 | −1.28〜+1.91 | 34.4% | −0.79 | +1.05 | +0.34 |
| 合計 | +1.045 | +0.016 | | | | | +1.052 |

- 少しずつ増やさず、今の局面の勾配だけを使うと（勾配 × 入力）、合計は +0.016 で、実際の差 +1.052 をほとんど説明しない。value が 0.993 で飽和し、今の局面では勾配がほぼ 0 のため。IG は基準から今の局面までの途中の勾配を集めるので、合計が差と合う（IG の原論文の Sensitivity の議論と同じ）。
- 駒を 1 つずつ足すと、合計はどの順番でも差と合うが、それぞれの駒の値は足す順番で大きく変わる（a3 のライオンは −1.94〜+1.79）。駒どうしの相互作用があるため。
- 全ての順番の平均（Shapley 値。IG の原論文 4 章 Remark 5 の Shapley–Shubik）なら順番によらない。動物将棋は駒が 8 枚なので、2^9 = 512 通りの入力で厳密に計算できる。9×9 の将棋は駒と履歴が多く、厳密には計算できない。
- この局面の Shapley 値では、相手のライオンを取れる a2 の後手にわとりが最も押し上げた（+0.54）。a3 のライオンは −0.28。
- どのやり方も、途中の入力（駒が欠けた盤、駒が半分だけある盤）は学習に現れない入力である。

## 引用した論文に書いてあること（全文を読んで確かめた）

### Sundararajan ら：IG の原論文（ICML 2017、論文の [5]）

- 基準は、「原因がない状態」を表す 1 つの入力である。多くのネットワークには、予測が中立になる自然な基準がある。画像なら黒い画像（1 章 Remark 1）。
- 基準での予測をほぼ 0 にできれば、IG は出力を各入力に分けたものとして読める。黒い画像はこれを満たす（3 章）。
- IG を使うときは、基準での点がほぼ 0 になるかを確かめることを勧める。加えて、基準は「信号がまったくない状態」を表すとよい。そうすれば、IG に表れるものは入力の性質であって、基準の性質ではなくなる（5 章）。
- 文章のモデルでは、全部 0 の埋め込みがよい基準だった。全部 0 の埋め込みは実際には現れない入力だが、数学的な理由でうまくいく（5 章）。
- IG の合計が「入力での出力 − 基準での出力」と合うかを確かめ、合わなければ分割を増やすよう勧める。20〜300 分割で十分なことが多い（5 章）。
- 使った例は画像の分類、網膜の画像、質問文の分類、翻訳、化学（6 章）。基準は次のとおり。
  - 画像：黒い画像。
  - 文章：全部 0 の埋め込み。
  - 翻訳：文の始まりと終わりの印以外を 0 にした。
  - 化学：原子と原子の組の特徴を 0 にした。
- ゲーム、強化学習、value の出力の例はない。
- attention を IG の代わりに使うのは、ほかの影響の経路が入らないので不完全、と書いている（7 章）。
- 入力どうしの相互作用は扱っていない（8 章）。

### Czech ら：チェスの AlphaZero の入力表現（arXiv 2023、ECAI 2024、論文の [6]）

- 本文 4.3 節・図 5：平面ごとの value への寄与を、IG で測って平均した。
  - 基準は、検証データの全入力の平均。
  - 「適切な基準を決めることが決定的に大事」と書いている。
- 付録 A.5・図 7・図 8：2 局面の事例。
  - 標準の AlphaZero と、手番の平面を除いた FX 版の両方で、全部 0 を基準にした。
  - 全部 0 を選んだ理由も、基準を変えた比較も書いていない。
- 手番の平面は、黒番は全部 0、白番は全部 1（表 3）。
  - 図 8 は黒番なので、手番の平面は基準と同じ 0 で、IG はちょうど 0 になる。図 7 は白番。
  - この違いに論文は触れていない。
- FX 版で手番の平面を除いた理由は、局面と関係なく白の評価を高めてしまうから、という学習・評価の理由である。IG の基準の話ではない。
- 駒の平面は手番側と相手に分け、value は手番側から見た値（盤を回しているかは論文に書いていない）。

## 引用していない論文

### Kindermans ら（arXiv 2017、"The (Un)reliability of Saliency Methods"）

- MNIST で、入力に定数を足しても予測は変わらないように、ネットワークのバイアスで打ち消した。
  - この操作で、全部 0 を基準にした IG は結果が変わった。
  - データの最小値で埋めた画像（黒い画像）を基準にした IG は、結果が変わらなかった。
- 基準の選び方で結果は大きく変わる。どの基準が妥当かは分野と課題による。意図せずモデルを誤って伝えることは十分ありうる、と書いている。
- 本研究の入力の平面は 0 以上なので、各平面の最小値が 0 なら、全部 0 は「データの最小値」の基準と同じになる。ただし、データ全体で各平面の最小値が 0 かは確かめていない。
- Sturmfels ら（Distill 2020）は 11-10 に読んだ（mdfolder/after_gpw_submission.md:65）。

## 提出版の記述の点検

| 場所 | 記述 | 判定 |
|---|---|---|
| 2.3 節 | IG [5] は出力を入力の各要素に割り当てる手法として提案され、画像・文章・化学のモデルに適用された | 原論文の内容と合う |
| 2.3 節 | Czech ら [6] は AlphaZero のチェスのネットワークで、入力の平面ごとの value への寄与を IG で測った | Czech らの図 5 と合う |
| 3.4 節 | 全部 0 の入力（盤上の駒も持ち駒もなく、手番などの平面も 0）を基準とした | したとおり。この文に引用はなく、誰かに従ったとは書いていない |
| 3.4 節 | 全部の入力の値を足すと「今の局面の出力 − 基準での出力」になる | 合計の差は 0.006 以内 |
| 3.4 節 | 300 分割の和で近似 | 論文の 5 局面の value と手の確率で、1,000 分割との差は、図に描く値（マスごと、持ち駒の種類ごと）で最大 0.0084（図 8 の局面の value）、ほかは 0.0041 以下（steps_check.py） |
| 3.4 節 | 出力に手の確率を用いる | 確率はネットワークの softmax の後の値で、動物将棋は 132 手、9×9 の将棋は 11,259 手（合法でない手も含む）の中での確率（restnet/learner/network/alphazero_network.py の forward） |
| 4.2〜4.4 節 | 各局面の IG の値 | 書いた基準での正しい値 |
| 4.2 節 | 重みが集まったマスは value にも大きく効いている | 駒だけ 0 の基準でも成り立つ（a3 は −2.22） |
| 5 章 | 図の局面では両ゲームとも、打つ駒が手の確率を最も押し上げた | 書いた基準では正しい。範囲を「図の局面」に限っている |
| 5 章 | 例の局面は説明しやすいものを選んだ | 書いてある |
| 5 章 | IG の値は基準の選び方で変わり、本稿の基準は実際に現れない局面である | 書いてある |

書いていないこと（誤りではないが、聞かれうること）：
- 全部 0 の基準を選んだ理由。
- 手番の平面を 0 にすることの影響。

## 基準による値の違い（提出版と、駒だけ 0 の基準）

| 場所 | 全部 0（提出版） | 駒だけ 0 |
|---|---|---|
| 4.2 節 value | a3 の先手のライオン −1.45、c2 の後手のライオン +1.47、持ち駒のぞう +0.76 | −2.22、+2.53、+1.28 |
| 4.2 節 c2b1 の確率 | c2 のライオン +1.89、c1 のきりん −0.84、a3 のライオン −0.60（盤上で 4 番目） | +1.39、−0.52、−0.16（盤上で 5 番目） |
| 4.3 節 ▲4七桂打 | 持ち駒の桂 +0.06 が最大、盤上はどれも 0.03 以下 | 桂 +0.11 が最大、盤上はどれも 0.05 以下 |
| 4.3 節 value | 2二 の先手のと金 +0.20 が最も押し上げ、7七 の後手のと金 −0.16 が最も押し下げ | 1一 の先手の龍 +0.13、9八 の先手の金 −0.18 |
| 4.3 節 持ち駒 | 先手の銀・金 +0.14、+0.10、後手の銀・歩 −0.22、−0.18 | +0.16、+0.15、−0.17、−0.14 |
| 4.3 節 ほかの 2 局面 | 銀 5六 +0.64、玉 4四 +0.48 | +0.76、+0.35 |
| 4.4 節 ▲キ a3 打 | 持ち駒のきりん +1.08 が最大 | 盤上の b3 の後手のライオン +0.54 が最大、持ち駒のきりん +0.49 |

- 図 10 の value は、8 つの駒のうち 6 つの色が反転する。
- 駒だけ 0 の基準では、手番などの平面は基準と同じ値なので、持ち駒の棒の図にある「手番などの IG の合計」は 0 になる。
- 値は、どちらもその基準での正しい値である。違いは基準の選び方によるもので、どちらかが誤りというものではない。
- 駒だけ 0 の基準で作った図 10 枚は /home/rin/gpw_figs_not_submitted/figs_pieces_removed/ にある（11-15 にリポジトリの外へ移した）（GUI を駒だけ 0 のコードで動かして作ったもの。そのコードは取り消した）。

## 判断：訂正版は出さない

1. 提出版に事実と違う記述がない（上の点検）。
2. 提出版の基準は、引用した IG の原論文の考え方に合っている。
   - 基準での value がほぼ 0（+0.06、+0.04）。
   - 原論文は「実際に現れない入力」でも基準として使えるとしている（文章の全部 0 の埋め込み）。
3. 駒だけ 0 の基準は、動物将棋では基準での value が手番側から見て −0.95、−0.85 で、原論文の勧めに合わない。訂正版を出すことは誤りを正すことではなく、別の基準への取り替えになる。
   - 動物将棋では、実際に現れる手番・回数の組み合わせのまま駒だけ 0 にすると、どれも中立にならない。データの平均も中立にならない。
   - なので、「基準での出力が中立」と「駒の値が手番に左右されない」の両方を満たす基準は、今回試した中にはない。
4. 提出後にわかった手番による違いは、入力どうしの相互作用に関わるもので、原論文も扱っていない。論文はこの傾向を主張していないので、記述とは食い違わない。
5. 9×9 の将棋では、盤を手番側の向きに回しており、手番の平面を変えても駒の IG の符号はほぼ変わらない（185 局面で、|IG| > 0.02 のマスの符号が違う割合 0.0%）。動物将棋のような手番による違いは起きていない。

提出版の全体の点検（gpw_paper/点検_提出版.md）でも誤りは見つからず、EasyChair に上げたファイルが点検した PDF と同じことも 11-01 に確かめた。訂正版は出さない。

## 発表で伝えること

- 全部 0 の基準では、取れる局面で相手のライオンの符号が手番で反対になる傾向があった（2.5% と 84.3%。取れる 1,000 局面の 4,000 入力では 2.9% と 87.5%）。同じ基準の厳密な Shapley 値でも起きる（10.0% と 66.8%）ので、IG だけの性質ではない。
- 基準を変えると値が変わる。駒だけ 0 の基準では、6T の IG で手番による差はほぼ消えた（53.8% と 52.8%）。同じ基準の Shapley 値では 9 ポイント残り（30.1% と 39.0%）、6R の IG では消えない（2.2% と 25.7%）。ただし、この基準は基準での value が中立でない（手番側から見て −0.95、−0.85）。
- Attention Map の結果と、モデルの精度と強さ（4.1 節）は、IG を使っていないので影響しない。
- 同じ局面で基準どうし（全部 0、駒だけ 0、Czech らの主な結果のようなデータの平均）を比べた（上の「無作為な局面で基準と方法を比べた」）。今後：引用する論文として Kindermans らを加える。

## 今の状態（2026-11-01）

提出版に合わせて、基準を駒だけ 0 にした変更（コミット a7c6b72、7ee25af、fdca326）を取り消した。

| もの | 今の状態 |
|---|---|
| 提出版の原稿・PDF・図 | コミット 1334a06、gpw_paper/paper_submitted.pdf、gpw_paper/figs/ |
| gpw_paper/paper.tex、paper copy.tex | 提出版と同じ本文。組み直した PDF は、提出した PDF と文字・全 8 ページの画像が同じ |
| gpw_paper/figs/ | 提出版の図 18 枚だけ |
| /home/rin/gpw_figs_not_submitted/figs_pieces_removed/ | 駒だけ 0 の基準で作った IG の図 10 枚（基準を比べるため。リポジトリの外） |
| xai_analysis.py | 基準を渡せる（コミット 625eccd）。渡さなければ全部 0 |
| 動物将棋の GUI（scripts/dobutsu_viewer.py）、9×9 の将棋の GUI（xai_app.py） | 全部 0 の基準（提出版と同じ） |
| 研究室で動いている GUI（dobutsu_gui は 10-23、xai_gui は 11-03 に起動） | どちらも全部 0 の基準（xai_app.py は 11-01 に全部 0 に戻した）。再起動しても同じ |
| 訂正_IG.md | 中身をこのファイルと点検_提出版.md に取り入れて消した |

## 確かめていないこと

確かめていないことは mdfolder/計画.md に移した（2026-11-16）。

## 使ったもの

- 論文の写し（作業用の一時フォルダ /tmp/claude-1000/-home-rin-restnet/49ea850f-dbdd-40f1-a6d5-c8383149e121/scratchpad/papers_dl/）
  - ig.txt（IG の原論文、arXiv 1703.01365v2）
  - czech.txt（arXiv 2304.14918v2）
  - kind.txt（arXiv 1711.00867v1）
- 2,000 局面の集計と、基準での出力の計算に使ったスクリプトも、同じ一時フォルダにしかない。
  - ig_lion.py、ig_lion2.py、zero_out.py、zero_out9.py、base_combo.py、base9.py、check9.py、check_dfeat.py、turn9.py（結果 turn9.log）
  - audit/ の one_by_one.py、steps_check.py、orient_map.py、pair_dobutsu.py（結果 pair_dobutsu_400.log、pair_dobutsu_rows_400_7.npy）、pair_strata.py、turn9_policy.py（結果 turn9_policy.log）、ig_one_input.py
  - zero_out.py の「駒だけ 0」の値（−0.99、+0.77）は、平面 18 を 0 のまま計算した誤りだった。base_combo.py の値（−0.949、+0.853）が正しい。
  - 数字はこのファイルに写した。

## ミーティング後にすること
- それでは動物将棋を再トレーニングしたいです．理由としてはこの将棋は盤面を回転しないなどほかの動物将棋の実装と一致しないことによってほかの人には合わられない特有のデメリットがありました．最新の信頼のある人の動物将棋の実装をまねして再度実装してほしいです．また実装する前は今の動物将棋との違いを列挙したうえで私が許可を出します．

## IG の基準の文献（2026-11-16 の調査）

原論文、先行研究、最近の研究、ゲームと強化学習の研究での基準の選び方。エージェントがインターネットで原文を開いて調べた報告のまま（「読んだ」は原文を開いて引用を確かめたもの）。

### 文献ごとの基準と理由

すべての項目に、読んだ範囲を書いた。「読んだ」は、原文（PDF をテキストにしたもの、または HTML）を開いて引用部分を確かめたことを表す。

#### 原論文と、IG の著者による指針

**1. Sundararajan, Taly, Yan（2017）「Axiomatic Attribution for Deep Networks」**
- 発表先：ICML 2017（PMLR 70）。URL：https://arxiv.org/abs/1703.01365 。読んだ（arXiv 版の本文。会議名は本文の脚注で確かめた）。
- 使った基準：画像の 2 つのモデル（GoogleNet、糖尿病網膜症）では黒い画像を使った。質問分類のモデルでは全ゼロの埋め込みを使った。翻訳のモデルでは、開始と終了の記号を除くすべての語の埋め込みをゼロにした。化学のモデルでは、原子と原子対の特徴ベクトルをゼロにした。
- 書かれている条件：(1) 基準での出力がゼロに近いこと。(2) 基準が信号の完全な不在を表すこと（出力がゼロでも、adversarial example のように信号を含む基準は避ける）。(3) 帰属の和が「入力での出力 − 基準での出力」に一致することを確かめ、一致しなければ刻みの数を増やすこと（20〜300 刻みで 5% 以内）。
- Sundararajan らは、雑音の画像も黒い画像と同じく信号がないと書いている。Sundararajan らは、テキストの全ゼロの埋め込みは有効な入力ではないが、重要でない語の埋め込みのノルムが学習で小さくなるので使えると説明している。
- 引用："We recommend that developers check that the baseline has a near-zero score"／"we would additionally like the baseline to convey a complete absence of signal, so that the features that are apparent from the attributions are properties only of the input, and not of the baseline."／"we recommend that developers check that the attributions approximately adds up to the difference beween the score at the input and that at the baseline"（"beween" は原文の綴り）

**2. IG の著者のリポジトリにある文書「howto.md」（ankurtaly/Integrated-Gradients）**
- 発表先：GitHub の文書で、論文ではない。URL：https://github.com/ankurtaly/Integrated-Gradients/blob/master/howto.md 。読んだ。
- 勧める基準：画像には黒い画像か雑音の画像を勧めており、複数の雑音の基準の平均も勧めている。テキストには全ゼロの埋め込みを勧めている。2 値と連続の特徴には、埋め込みならテキストと同じ扱いを勧め、別の方法として学習データの入力を複数とって平均することを勧めている。
- 書かれている条件：分類モデルでは、基準でのクラス確率のエントロピーが高いことを確かめる。著者たちは、エントロピーが高いことは必要条件にすぎないと書いている。2 つのクラスを対称に扱うモデルでは、両方のクラスの中間（シグモイドで 0.5）の出力を出す基準がよいと書いている。著者たちの 2 クラスの画像モデルでは黒い画像がクラス A に 70% を出したので、「何もない」を表す 3 つ目のクラスを加えて学習し直した、と書いている。
- 引用："Binary and continuous features: ... The other alternative is to use several training data inputs as a baseline and to average the attributions over these."／"For such a model a good baseline would be one with a sigmoid score of 0.5 that is balanced between the two classes."

#### IG より前の研究と、関連する研究

**3. Shrikumar, Greenside, Kundaje（2017）「Learning Important Features Through Propagating Activation Differences」（DeepLIFT）**
- 発表先：ICML 2017 とされる（arXiv 版を読んだ。会議名は arXiv 版の本文では確かめられなかった）。URL：https://arxiv.org/abs/1704.02685 。
- 使った基準：MNIST では背景の色である全ゼロを使った。one-hot の DNA 配列では、各位置での ACGT の期待頻度（0.3, 0.2, 0.2, 0.3）を使い、もう一つの方法として、元の配列をシャッフルした複数の配列を基準にして平均した。比較のための IG にも、同じ期待頻度の基準を使った。CIFAR10 では、ぼかした画像を使った。
- 書かれている条件：何との差を測りたいかで決める、と書いている。
- 引用："The choice of a reference input is critical for obtaining insightful results from DeepLIFT."／"As a guiding principle, we can ask ourselves 'what am I interested in measuring differences against?'"

**4. Kindermans, Hooker, Adebayo, Alber, Schütt, Dähne, Erhan, Kim（2017、2019）「The (Un)reliability of Saliency Methods」**
- 発表先：arXiv 2017（検索結果では NIPS 2017 のワークショップ）。Springer の書籍（LNCS 11700、2019）の章としての収録は、検索では確かめられなかった。URL：https://arxiv.org/abs/1711.00867 。読んだ（arXiv 版）。
- 比べた基準：IG では、データの最小の画素値で埋めた画像（黒い画像）と、ゼロベクトルを比べた。
- 書かれていること：入力に定数を足して、同じ出力を出すネットワークを 2 つ作った。黒い画像の基準は、平均をずらす変換に対して帰属が変わらなかった。ゼロベクトルの基準は、帰属が変わった。Kindermans らは、黒い画像の基準でも、うまく作った定数ベクトルを足すと帰属が壊れることを示した。Kindermans らは、どの基準も前処理の仕方と結び付いて結果を左右すると結論している。
- 引用："The choice of reference point determines all subsequent attribution."／"A reasonable reference point choice will naturally depend upon domain and task."／"If we cannot determine the implications of reference point choice, we are limited in our ability to say anything about the reliability of the method."

**5. Sturmfels, Lundberg, Lee（2020）「Visualizing the Impact of Feature Attribution Baselines」**
- 発表先：Distill 2020。URL：https://distill.pub/2020/attribution-baselines/ 。読んだ。
- 比べた基準：一定の色（黒）、maximum distance（有効な画素の範囲で L1 距離が最も遠い画像）、ぼかした画像（Fong と Vedaldi に基づく）、一様な雑音、入力を中心とするガウス雑音（範囲に切り詰める）、学習データ（expected gradients）。
- 結論：上位 k 個を消す ablation test では、学習データの基準と一様な雑音の基準がほかの多くの方法を上回った。ぼかしで消す test では、ぼかした基準が同じくらいよかった。重心の周りを消す test では、すべての方法がほぼ同じだった。Sturmfels らは、ablation test では入力が学習の分布の外に出ると注意している。Sturmfels らは、IG の補間した入力も学習の分布の外にあると書いている。Sturmfels らは、maximum distance は入力の情報を多く含むので「不在」を表さないと書いている。
- 引用："If you use a constant black image as a baseline, integrated gradients will not highlight black pixels as important even if black pixels make up the object of interest."／"We have many baselines and no conclusion about which one is the “best.”"／"At the heart of each baseline is an assumption about missingness in our model and the distribution of our data."／"those interpolated images don’t belong to the original training distribution either."

**6. Erion, Janizek, Sturmfels, Lundberg, Lee（2021）「Improving performance of deep learning models with axiomatic attribution priors and expected gradients」**
- 発表先：Nature Machine Intelligence 3, 620–631（2021）。掲載は検索で確かめた。URL：https://arxiv.org/abs/1906.10670 。読んだ（arXiv v2）。
- 使った基準：expected gradients。基準を学習データから引き、補間の位置 α を一様分布から引き、勾配の項を平均する。
- 書かれている条件：基準は「特徴の値を知らないこと」を表す情報のない入力であるべきだが、多くの分野で選び方が明らかでない、と書いている。expected gradients の完全性は、入力での出力と、すべての基準での出力の平均との差に対して成り立つ。
- 引用："In many domains, it is not clear how to choose a baseline that correctly represents a lack of information."／"This is true for any constant baseline input."（一定の基準と同じ値の画素は重要とされない、という文に続く文）

**7. Sundararajan, Najmi（2020）「The Many Shapley Values for Model Explanation」**
- 発表先：ICML 2020 とされる（arXiv v2 を読んだ。会議名は確かめていない）。URL：https://arxiv.org/abs/1908.08474 。
- 書かれていること：Baseline Shapley（BShap）は、特徴の不在を基準の値で表す。Random Baseline Shapley（RBShap）は、分布 D から引いた基準での BShap の期待値である。条件付き期待値の Shapley（CES）は、Dummy などの公理を満たさない。特徴が独立な分布では、CES と RBShap は一致する。モデルが線形で特徴が独立なら、特徴の平均を基準にした BShap は CES と同じ帰属になる。
- 書かれている条件：基準を使うと、説明の文脈を表せる。たとえば変えられない特徴を説明される入力と同じ値にした基準を選べば、変えられる特徴だけに帰属が割り振られる。どの基準を選ぶべきかの決め手がない場合は、RBShap が代わりになる。
- 引用："we model a feature’s absence using its value in the baseline."／"Such an explanation is achievable by selecting a baseline that coincides with the explicand on immutable features."／"There are also situations where there is no compelling choice of one baseline over another. In this situation, RBShap presents an alternative."

#### 基準を比べた研究と、基準の選び方を提案する研究

**8. Haug, Zürn, El-Jiz, Kasneci（2021）「On Baselines for Local Feature Attributions」**
- 発表先：AAAI-21 Workshop on Explainable Agency in AI（掲載は検索で確かめた）。URL：https://arxiv.org/abs/2101.00905 。読んだ。
- 比べた基準：一定（ゼロ）、maximum distance、ぼかし、ガウス、一様、期待値（学習データ）。表形式のデータで比べた。基準は、static か dynamic か、deterministic か stochastic かで分類した。
- 結論：一定、ぼかし、ガウス、期待値の基準はよい結果だった。一様と maximum distance の基準は、ランダムな順位付けをしばしば上回れなかった。Haug らは、基準がデータを生成する分布に近いほど帰属がよく区別できると示唆している。Haug らは、名義尺度の特徴ではゼロが不在を表さないと書いている。
- 引用："In practice, a baseline should be selected with respect to the data distribution at hand."／"Note that the blurred, Gaussian and uniform baseline assume continuity of features."

**9. Covert, Lundberg, Lee（2021）「Explaining by Removing: A Unified Framework for Model Explanation」**
- 発表先：JMLR とされる（arXiv v2 を読んだ。誌名は確かめていない）。URL：https://arxiv.org/abs/2011.14878 。
- 書かれていること：特徴を既定値に置き換える方法は、既定値にすべての確率を置く一定の分布と矛盾しない。平均で置き換える方法は、特徴の独立とモデルの線形性を仮定して、条件付き分布を近似したものとみなせる。
- 引用："marginalizing out features using their conditional distribution is the only approach that is consistent with standard probability axioms"／"replacing features with their mean can be interpreted as an additional assumption of model linearity"

**10. Izzo, Lipani, Okhrati, Medda（2021）「A Baseline for Shapley Values in MLPs: from Missingness to Neutrality」**
- 発表先：arXiv v3（2021）。会議名は確かめていない。URL：https://arxiv.org/abs/2006.04896 。要旨だけを読んだ。
- 提案する基準：意思決定者が決める中立の値（判断が分かれる出力の値）を出す点を基準にする。
- 引用："An arbitrary choice of baseline could negatively impact the explanatory power of the method and possibly lead to incorrect interpretations."

**11. Mamalakis, Barnes, Ebert-Uphoff（2023）「Carefully choose the baseline: Lessons learned from applying XAI attribution methods for regression tasks in geoscience」**
- 発表先：Artificial Intelligence for the Earth Systems 2(1)、DOI 10.1175/AIES-D-22-0058.1（掲載は検索で確かめた）。URL：https://arxiv.org/abs/2208.09473 。読んだ（arXiv 版）。
- 使った基準：気温の地図から全球の平均気温を予測する回帰で、ゼロの入力、1850〜1880 年の平均、2025 年の地図などを比べた。
- 書かれている条件：基準ごとに、帰属が答える科学の問いが違う。回帰では、複数の基準が異なる問いに答える。分類では、クラスがすでに決定境界を決めているので、情報のない基準が 1 つあれば足りる。どの応用でも、基準を注意して選び、明記すべきである。Mamalakis らは、ゼロの基準はゼロの入力に必ずゼロの帰属を割り振ると注意している。
- 引用："In fact, for classification tasks, a single baseline should suffice."／"Nevertheless, in all XAI applications, the baseline needs to be carefully chosen and explicitly stated."

**12. Kapishnikov, Bolukbasi, Viégas, Terry（2019）「XRAI: Better Attributions Through Regions」**
- 発表先：ICCV 2019（検索で確かめた）。URL：https://arxiv.org/abs/1906.02825 。読んだ。
- 使った基準：黒と白の 2 つの基準の IG を平均する。
- 書かれている理由：基準が 1 つの IG は、基準に等しい画素や近い画素に反応しない。複数のランダムな基準は、実行のたびに結果が変わり、ランダムな重みによる偽の帰属を生みやすい。x ∈ [0,1] では |x − 1| + |x − 0| = 1 なので、黒と白の基準を使うと、すべての画素が基準との距離に関係なく等しく寄与しうる。
- 引用："any single baseline integrated gradient will be insensitive to pixels that are equal or close to the baseline image."／"the resulting saliency maps are not consistent and change at every run due to the randomness of the baseline."

**13. Xu, Venugopalan, Sundararajan（2020）「Attribution in Scale and Space」（Blur IG）**
- 発表先：CVPR 2020（検索結果による）。URL：https://arxiv.org/abs/2004.03383 。読んだ。
- 使った方法：基準の代わりに、ぼかしの強さの方向に経路をとる。
- 書かれている理由：黒い基準は、明るさの低い重要な特徴を抑える。雑音の基準は新しい極値を作り、偽の特徴を生む。Xu らは、複数回の平均はその場しのぎの修正だと書いている。
- 引用："it eliminates the need for a ‘baseline’ parameter for Integrated Gradients [31] for perception tasks."／"But this is a heuristic fix, and involves a computational hit."

**14. Kapishnikov, Venugopalan, Avci, Wedin, Terry, Bolukbasi（2021）「Guided Integrated Gradients: an Adaptive Path Method for Removing Noise」**
- 発表先：CVPR 2021 とされる（会議名は確かめていない）。URL：https://arxiv.org/abs/2106.09788 。読んだ。
- 比べた基準：黒、黒と白の平均、2 つのランダムな基準の平均。
- 結論：黒と白の基準がおおむねよい選択だった。Guided IG では、黒い基準 1 つでも改善の多くが得られた。
- 引用："While a black+white baseline is generally a better choice, ... much of the improvement (over IG) is observed on a single black baseline itself."／"Guided IG performs well irrespective of the choice of baseline."

**15. Pan, Li, Zhu（2021）「Explaining Deep Neural Network Models with Adversarial Gradient Integration」**
- 発表先：IJCAI 2021、pp. 2876–2883。URL：https://www.ijcai.org/proceedings/2021/0396.pdf 。読んだ。
- 使った方法：基準の代わりに、ほかのクラスへの adversarial example から入力まで勾配を積分する。比べた IG には、原論文の既定の黒い画像を使った。
- 引用："If both white noise image and black image convey no signal, why prefer the latter to the former in simpler tasks?"

**16. McCloskey ほか（2019）「Using Attribution to Decode Dataset Bias in Neural Network Models for Chemistry」**
- 発表先：arXiv v3（2019）。誌名は確かめていない。URL：https://arxiv.org/abs/1811.11310 。読んだ（補足資料の基準の節）。
- 使った基準：原子と原子対の特徴をゼロにした分子。McCloskey らは、基準での予測を中立の 0.5 にするために、ラベル 1.0 とラベル 0.0 を付けた基準の分子を学習データに加えた。
- 引用："Ideally, the baseline input must be an uninformative input with a neutral prediction."／"we found it necessary to augment the training data with examples of the baseline molecule."

**17. Ren, Zhou, Chen, Zhang（2023）「Can We Faithfully Represent Absence States to Compute Shapley Values on a DNN?」**
- 発表先：ICLR 2023。URL：https://arxiv.org/abs/2105.10719 。読んだ（序論と、既存の基準を比べた節）。
- 書かれていること：平均の基準もゼロの基準も、入力に新しい信号を加える（平均は画像に灰色の点を加え、ゼロは黒い点を加える）。最適な基準は、因果パターンをできるだけ減らし、新しい因果パターンを加えない基準である。Ren らは、条件付き分布に基づく方法がやや良かったと書いている。
- 引用："there is no theory to examine whether baseline value faithfully represents the absence of an input variable"／"seemingly OOD baseline values do not necessarily generate OOD features."

**18. Zhuo, Ge（2024）「IG2: Integrated Gradient on Iterative Gradient Path for Feature Attribution」**
- 発表先：arXiv 2024。arXiv 版には IEEE TPAMI に採録と書かれている。URL：https://arxiv.org/abs/2406.10852 。読んだ（基準の性質の節）。
- 書かれている条件：counterfactual な基準は 3 つの性質を満たすべきである。(1) Validity は、説明される入力と違うクラスに分類されること。(2) Data manifold closeness は、学習データに近いこと。(3) Explicand relevance は、説明される入力と関係していること。Zhuo らは、expected gradients は (1) と (2) を満たすが、引く基準が入力に関係しないと書いている。
- 引用："The commonly used uninformative baselines (black and white) violate all three properties"

**19. Morasso, Dolci, Boscolo Galazzo, Plis, Menegaz（2025）「Guidelines For The Choice Of The Baseline in XAI Attribution Methods」**
- 発表先：arXiv 2025。URL：https://arxiv.org/abs/2503.19813 。読んだ（定義と結論）。
- 書かれている条件：最適な基準は、(i) ネットワークにとって中立で決定境界の上にあり、(ii) データの分布の中にあり、(iii) 決定境界の上で入力に最も近い点である。Morasso らは、基準から入力までの経路が決定境界を何度も横切らないようにすべきだと書いている。Morasso らの実験は、人工データに限られている。
- 引用："we define the optimal BL as a sample that holds the following properties: i) being neutral to the network, thus lying on the DB; ii) sitting within the data distribution domain; and iii) being the closest sample of the DB to the datapoint under analysis."

**20. Kien, Tam, Son, Than, Nguyen（2025、v4 は 2026）「Enhancing Visual Feature Attribution via Weighted Integrated Gradients」**
- 発表先：arXiv。URL：https://arxiv.org/abs/2505.03201 。要旨と序論だけを読んだ。
- 提案する方法：基準の候補ごとに、入力ごとの重みを教師なしの基準で付ける。Kien らは、expected gradients が基準を等しい重みで扱う仮定を批判している。
- 引用："WG introduces an unsupervised criterion for baseline suitability, enabling adaptive selection and weighting of baselines on a per-input basis."

**21. Geiger, Wagner, Rueckert, Wilhelm, Jell（2025、v3 は 2026）「On the notion of missingness for path attribution explainability methods in medical settings」**
- 発表先：arXiv。URL：https://arxiv.org/abs/2508.14482 。要旨だけを読んだ。
- 提案する基準：病変のない、臨床的にありうる counterfactual（生成モデルで作る）。
- 引用："a baseline must not merely lack signal, but must represent a clinically plausible state in which the disease-related features are absent."

**22. Higgs, Jones, Hunt, Ellis（2026）「Explainable AI for Geoscientific Regression: Evaluating Sensitivity and Attribution Methods with the Lorenz-63 System and Applications」**
- 発表先：arXiv v3（2026-11-04）、AIES に投稿中。URL：https://arxiv.org/abs/2608.07406 。IG の節と議論の節だけを読んだ。
- 使った基準：系の平均の状態。
- 引用："An explicit baseline can be an advantage, as it states the question being asked"／"A non-physical baseline, such as a mean state that is never realised (common in high dimensions), may be problematic for models trained on realistic states"

#### ゲームと強化学習の文献（どの基準をなぜ使ったかは、次の節の「ゲーム・強化学習での使われ方」にまとめた）

**23. Czech, Blüml, Kersting, Steingrimsson（2024）「Representation Matters for Mastering Chess: Improved Feature Representation in AlphaZero Outperforms Switching to Transformers」**：ECAI 2024（DFKI の一覧を検索で確かめた）。URL：https://arxiv.org/abs/2304.14918 。読んだ（v2 の IG の節と付録）。
**24. McGrath ほか（2022）「Acquisition of Chess Knowledge in AlphaZero」**：PNAS とされる（誌名は確かめていない）。URL：https://arxiv.org/abs/2111.09259 。読んだ（v3 の activation-input covariance の節）。
**25. Puri ほか（2020）「Explain Your Move: Understanding Agent Actions Using Specific and Relevant Feature Attribution」（SARFA）**：ICLR 2020。URL：https://arxiv.org/abs/1912.12191 。読んだ（方法の節）。囲碁と Atari にも使ったことは、検索結果だけで確かめた。
**26. Greydanus, Koul, Dodge, Fern（2018）「Visualizing and Understanding Atari Agents」**：arXiv v5。会議名は確かめていない。URL：https://arxiv.org/abs/1711.00138 。読んだ。
**27. Hilton, Cammarata, Carter, Goh, Olah（2020）「Understanding RL Vision」**：Distill 2020。URL：https://distill.pub/2020/understanding-rl-vision/ 。読んだ（付録 B）。
**28. Chen, Wang, Fan, Jin, Mardziel, Joe-Wong, Datta（2021）「Reconstructing Actions To Explain Deep Reinforcement Learning」**：arXiv v3。URL：https://arxiv.org/abs/2009.08507 。読んだ。
**29. Yang ほか（2020）「Q-value Path Decomposition for Deep Multiagent Reinforcement Learning」**：arXiv。会議名は確かめていない。URL：https://arxiv.org/abs/2002.03950 。読んだ。
**30. Hammersborg, Strümke（2023）「Information based explanation methods for deep learning agents – with applications on large open-source chess models」**：arXiv。URL：https://arxiv.org/abs/2309.09702 。読んだ（動機の節）。
**31. Spinnato（2025）「Towards Piece-by-Piece Explanations for Chess Positions with SHAP」**：CEUR-WS に掲載予定と書かれている。URL：https://arxiv.org/abs/2510.25775 。読んだ（方法の節）。
**32. Jenner ほか（2024）「Evidence of Learned Look-Ahead in a Chess-Playing Neural Network」**：arXiv v1。会議名は確かめていない。URL：https://arxiv.org/abs/2406.00877 。読んだ（activation patching の節）。
**33. Zhou ほか（2023）「Explaining How a Neural Network Play the Go Game and Let People Learn」**：arXiv。URL：https://arxiv.org/abs/2310.09838 。読んだ（マスクの節と飽和の節）。
**34. 廣瀬, 和賀, 末永（2023）「解釈が容易な特徴量を用いた Feature Attribution に基づく将棋 AI の指し手の解釈可能性向上手法」**：日本ソフトウェア科学会第 40 回大会。URL：https://jssst.or.jp/files/user/taikai/2023/papers/43-R-S.pdf 。読んだ（要旨、関連研究、参考文献）。
**35. 中屋敷, 金子（2018）「将棋用ニューラルネットワークへの顕著性抽出手法の適用」**：ゲームプログラミングワークショップ 2018。検索結果だけ（IPSJ のサーバーが 503 を返して開けなかった。内容は 34 の論文の関連研究の記述だけで知った）。

### 基準を選ぶ基準として文献に書かれていること（共通点と、意見が分かれる点）

#### 共通点
- **基準での出力が中立であること。** Sundararajan ら（2017）は、出力がゼロに近いことを求めている。IG の著者の howto.md は、対称な 2 クラスのモデルでは両方のクラスの中間を求めている。McCloskey ら（2019）は 0.5 の予測を求め、学習し直してまで 0.5 にした。Izzo ら（2021）と Morasso ら（2025）は、決定境界の上の点を求めている。Spinnato（2025）は、玉（キング）だけの局面の 0.5 を中立とした。
- **基準が信号の不在を表すこと。** Sundararajan ら、Sturmfels ら、Erion ら、Ren ら、Geiger らは、基準を「不在」の表し方として扱っている。Geiger らは、さらに、領域でありうる状態であることを求めている。
- **完全性を確かめること。** Sundararajan らと howto.md は、帰属の和が出力の差に近いことを確かめるよう勧めている。
- **基準と同じ値の特徴の帰属はゼロになること。** Sturmfels ら、Erion ら、XRAI、Blur IG、Mamalakis ら、IG2 は、IG の式から帰属がゼロになることを、一定の基準の欠点として挙げている。複数の基準（expected gradients、黒と白）が、欠点への対策として出されている。
- **基準を明記し、結果が基準で変わることを前提にすること。** Kindermans ら、Mamalakis ら、Haug ら、Higgs らが、明記を求めている。
- **基準がデータの分布の中にあること。** Haug ら、IG2、Morasso ら、Higgs らが、分布の中にあることを求めている。Sturmfels らと McGrath らは、IG の補間した入力は学習の分布の外にあると書いている。

#### 意見が分かれる点
- **固定の基準 1 つか、分布か。** Sturmfels ら、Erion ら、Weighted IG は、分布の基準に傾いている。Sundararajan と Najmi は、固定の基準は説明の文脈を選べる柔軟さだと書いており、決め手がないときに分布（RBShap）を使うとしている。XRAI は、ランダムな基準は結果が一定せず偽の帰属を生むとして、黒と白の 2 つの固定の基準を選んだ。Blur IG の著者は、平均をその場しのぎと呼んだ。
- **「中立」の定義。** Sundararajan らは出力がゼロに近いことを中立とし、howto.md はクラスの中間を中立とした。Hilton ら（2020）は、基準での出力が価値の平均と同じ程度であることを良い点として挙げている。Morasso らは、決定境界の上で入力に最も近い点を中立とした。Erion らの expected gradients では、完全性の比べる相手が基準での出力の平均になる。
- **一般に最良の基準があるか。** Sturmfels ら、Haug ら、Mamalakis らは、一般に最良の基準はないと書いている。Ren ら、Morasso ら、IG2 は、最適な基準の条件を提案している。
- **雑音の基準の評価。** Sturmfels らは画像で一様な雑音の基準をよい結果とし、Haug らは表形式のデータで一様な雑音の基準を悪い結果とした。Haug らは、データの種類による違いだと説明している。
- **ゼロの意味。** Sundararajan らは、テキストの全ゼロは有効な入力ではないが使えると書いている。Haug らは、名義尺度の特徴ではゼロが不在を表さないと書いている。Kindermans らは、ゼロと最小値の違いで帰属が変わることを示した。Ren らは、ゼロも平均も新しい信号を加えると書いている。
- **評価方法。** Sturmfels らは、ablation test の結果が分布のずれによるのか、特徴の重要さによるのかを区別できないと注意している。Haug らは ablation test で比べたが、クラスの偏りへの注意を書いている。

### ゲーム・強化学習での使われ方

- **AlphaZero 型のチェスのネットワーク（Czech ら 2024）。** Czech らは、IG で価値の出力への各チャネルの平均の帰属を計算し、検証データの入力の平均を基準にした。Czech らは、付録で個々の局面を説明したときには全ゼロの入力を基準にした。Czech らは、2 つの基準を使い分けた理由を書いていない。Czech らは、手番の色のチャネルと過去の局面のチャネルの重要度が小さいと報告している。Czech らは、キングの位置の重要度が小さく見えるのは、キングが常に盤上にあるので誤解を招くかもしれないと書いている。引用："It is crucial to establish an appropriate baseline for computing gradients. In Figure 5, we utilize the mean of all validation input features."／"Integrated gradient analysis employed all-zero inputs as the baseline."／"This may be misleading, as the king is always present"
- **AlphaZero（McGrath ら 2022）。** McGrath らは、IG を含む勾配の方法を引用した上で使わず、入力と活性の共分散を使った。McGrath らは、手数の面を除いて入力は 2 値で、ネットワークは 2 値の超立方体の外の入力を見たことがないと理由を書いている。引用："with the exception of a move-counter plane, z0 is binary and fθ(z0) has never seen examples that are not on the {0, 1}^{8×8×(14h+7)} hypercube"
- **Leela 系のチェスのモデル（Hammersborg, Strümke 2023）。** Hammersborg らは、チェスでは駒を 1 つ動かすだけで局面の性質が変わるので、摂動の方法は向かないと書いている。引用："the nature of any given position is more often than not significantly changed by even a small perturbation, such as moving a single piece on the board."
- **SARFA（Puri ら 2020）。** Puri らは、チェスで駒を 1 つ取り除く摂動を使った。Puri らは、駒を取り除くと合法手が変わるので、元の局面と摂動後の局面の両方で合法な手だけを比べた。引用："in chess, we can perturb the board position by removing the piece in the f th square."
- **チェスの SHAP（Spinnato 2025）。** Spinnato は、キングを取り除くと不正な局面になるので両方のキングを固定し、手番などのメタデータを元のまま残した。Spinnato は、キングだけの局面を基準とし、エンジンが引き分けと扱う 0.5 を中立の値とした。Spinnato は、キングの重要度を計算できないことを限界として挙げている。引用："removing either king would always result in an invalid position."／"Since engines universally treat king-only positions as trivially drawn, φ0 = 0.5, corresponding to a neutral evaluation."
- **Leela の activation patching（Jenner ら 2024）。** Jenner らは、1 マスか 1 つの駒だけが違う「壊した」局面を比べる相手にした。Jenner らは、元の局面と大きく違う局面では特定の仕組みが分からないと理由を書いている。引用："we want a corrupted state that is similar to the clean one but differs in some key detail that has an outsized effect on what move is best."
- **囲碁の価値ネットワーク（Zhou ら 2023）。** Zhou らは、石を取り除いた局面を不在の状態として使った。Zhou らは、学習データでは白石と黒石の数がほぼ等しいので、石の数の差が大きい局面では価値が飽和すると報告した。Zhou らは、石の数の差ごとの平均を出力から引いて補正した。引用："most training samples for the value network are usually biased to states with similar numbers of white stones and black stones"
- **Atari（Greydanus ら 2018）。** Greydanus らは、勾配ではなく、局所的なガウスぼかしの摂動を使った。Greydanus らは、ぼかしをその位置の空間的な不確かさを加えることと説明している。引用："We interpret this perturbation as adding spatial uncertainty to the region around (i, j)."
- **CoinRun の価値関数（Hilton ら 2020）。** Hilton らは、隠れ層の活性に IG を使い、ゼロの活性を基準にした。Hilton らは、ゼロでの出力が価値の平均と同じ程度であることを理由に挙げた。引用："0 tends to be a good baseline against which to compare other activations, with F(0) being on the same order as the average value function."
- **Atari の行動の説明（Chen ら 2021）。** Chen らは、全ゼロの行列を基準にした IG を使った（50 刻み）。Chen らは、全ゼロには意味がないと認めている。引用："we currently use zeros as the baseline input for IG, which is also not semantically meaningful"
- **マルチエージェントの強化学習（Yang ら 2020、QPD）。** Yang らは、直線の経路をやめて実際の軌跡を経路にし、Q が 0 の終端の状態を基準にした。引用："we can naturally use the termination state sT as baseline where Q(sT, ∅) = 0."
- **将棋（廣瀬ら 2023）。** 廣瀬らは、SARFA に基づき、駒の移動や除去で局面を摂動し、駒の有無や利きの数などの読み取りやすい特徴への貢献度を計算した。廣瀬らは、以前の DL-SARFA が dlshogi の特徴量の値を 1 つ反転させる摂動を使ったため、ほかの将棋 AI に使いにくかったと書いている。引用：「提案手法では入力局面に対して駒の移動や除去といった操作を行うことで摂動を加える」（2 段組みのテキストから復元した文）
- **将棋（中屋敷, 金子 2018、検索結果だけ）。** 廣瀬らの関連研究によると、中屋敷らは、将棋 AI の局面の評価値に勾配の方法（Simonyan らの saliency map と SmoothGrad）を使って比べた。IG を使ったという記述は見つからなかった。

### 9×9 の将棋の入力に当てはめたときに言えること

#### 文献の記述に基づくこと
1. IG の式の (xᵢ − x′ᵢ) の項から、基準と入力で値が同じ特徴の帰属は必ずゼロになる（Sundararajan ら、Sturmfels ら、Erion ら）。ゆえに、pieces-only-zero の基準では、繰り返しの面、手番の面、手数の面の帰属は必ずゼロになり、帰属は盤と持ち駒の面だけに割り振られる。全ゼロの基準では、手番の面と手数の面にも帰属が割り振られる。
2. Sundararajan と Najmi は、変えられない特徴を入力と同じ値にした基準で、変えられる特徴だけに帰属を割り振れると書いている。Sundararajan ら（2017）の翻訳のモデル（開始と終了の記号を残した）と化学のモデル（原子の特徴だけをゼロにした）は、中身の特徴だけをゼロにして構造の印を残した例である。pieces-only-zero は、2 つの例と同じ形の基準である。Sundararajan らはゲームを論じていないので、当てはまるかどうかは文献からは決められない。
3. Sundararajan らと howto.md の条件を価値の出力に当てはめると、勝ちと負けを対称に扱う出力 [-1,1] では、基準での価値が 0 に近いことが確かめる条件になる。McCloskey らと howto.md は、条件を満たさないときにモデルを学習し直した。
4. McGrath らによると、AlphaZero の入力は手数の面を除いて 2 値で、ネットワークは 2 値でない入力を見ていない。Sturmfels らも、IG の補間した入力は学習の分布の外にあると書いている。ゆえに、どの基準を選んでも、IG の経路の途中の入力は学習の分布の外にある。
5. Haug らによると、ぼかし、ガウス、一様の基準は特徴の連続性を仮定している。ゆえに、2 値の面では、3 つの基準は基準そのものが 2 値でない値になる。Haug らは、ぼかしの基準は特徴の間の近さの関係を必要とすると書いている。
6. 平均の基準には先例がある。DeepLIFT は one-hot の DNA に期待頻度の基準を使い、比べた IG にも同じ基準を使った。Czech らは、チェスのチャネルの平均の帰属に検証データの平均を使った。Czech らは、キングのように常にある駒は平均との差が小さく、重要度が小さく見えることがあると注意している。Ren らは、平均の基準が新しい信号を加えると書いている。Higgs らは、実際には現れない平均の状態が問題になりうると書いている。
7. Sturmfels らは、maximum distance の基準は不在を表さないと書いている。Haug らは、maximum distance の基準は外れ値になりやすく、表形式のデータで悪かったと書いている。
8. Erion らによると、expected gradients の帰属の和は、入力での価値と、引いた局面での価値の平均との差になる。
9. Mamalakis らによると、回帰では基準ごとに答える問いが違い、分類では情報のない基準 1 つで足りる。Jenner らと Spinnato は、チェスで、特定の問いに合わせた比べる相手の局面（1 マスだけ違う局面、キングだけの局面）を使った。
10. チェスでは、Spinnato がキングを取り除かなかった。Puri らは、駒を取り除くと合法手が変わることを扱った。Zhou らは、囲碁で、石の数の差が大きいマスクした局面では価値が飽和することを示した。

#### 推論（文献には書かれていない。こちらでは確かめていない）
1. 推論：pieces-only-zero の基準と全ゼロの基準は、両方とも盤上の玉をなくしている。Spinnato の理由をそのまま当てはめると、玉のない入力は学習で一度も見ていない入力になる。両方の玉だけを残し、持ち駒をゼロにし、ほかの面を入力のまま残す基準（玉だけの基準）は、候補の一覧にない。玉だけの基準の価値が 0 に近いかどうかは確かめていない。
2. 推論：Sturmfels らの maximum distance の定義を範囲 [0,1] の 2 値の面に当てはめると、maximum distance の基準は各ビットを反転した入力（1 − x）になる。1 − x の基準では、すべてのマスにすべての種類の駒がある盤になる。盤の面については、1 − x の基準は学習の分布から最も遠い入力の一つになる。
3. 推論：XRAI の黒と白の考え方を 2 値の面に当てはめると、全ゼロの基準と全 1 の基準の平均では、どの特徴でも |x − 0| + |x − 1| = 1 になり、駒のないマスにも帰属が割り振られうる。全 1 の基準は、推論 2 と同じく学習の分布から遠い。
4. 推論：IG の直線の経路では、すべての面が同じ α 倍で変わる。ゆえに、pieces-only-zero の基準からの経路では、途中の入力の駒の数の差も入力の α 倍になる。Zhou らの囲碁の飽和が経路の途中で起きるかどうかは確かめていない。
5. 推論：方策の出力では、駒のない基準での指し手の確率は、入力の局面では合法でも基準の局面では成り立たない手の確率になる。SARFA の合法手の扱いに対応する扱いを IG の方策の出力でどうするかは、文献で見つからなかった。
6. 推論：Kindermans らの結果を手数の面（2 値でない面）に当てはめると、全ゼロの基準での手数の面の帰属は、手数をどう符号化したか（どの値で割ったか）で変わりうる。
7. 推論：expected gradients で引いた局面での価値の平均が 0 に近ければ、Erion らの完全性は「価値が 0 に近い」という Sundararajan らの条件とほぼ同じ意味になる。データでの価値の平均は確かめていない。
8. 推論：McCloskey らのようにモデルを学習し直すと、調べたいモデルとは別のモデルになる。ゆえに、学習したモデルが何を考えているかを知るという目的とは合わないかもしれない。
- 確かめたこと：各候補の基準で 9×9 のネットワークが出す価値と方策の値は、こちらでは計算も確認もしていない。どの推論も、データやコードでは確かめていない。

### 見つからなかったこと・確かめていないこと
- 囲碁または将棋のネットワークに IG を使った論文は、英語と日本語の検索で見つからなかった。オセロ、Hex、Connect Four でも見つからなかった。
- ボードゲームのネットワークで複数の基準を比べた論文は、見つからなかった。過去の局面の面、繰り返しの面、手数の面、持ち駒の数の面の基準を論じた文献も見つからなかった。
- 盤を手番の側に向けて入力することが基準の選び方に与える影響を論じた文献は、見つからなかった。
- Atari で IG の基準を比べた研究は、見つからなかった。Atari の研究は、全ゼロ（Chen ら）か、ぼかしの摂動（Greydanus ら）を使っていた。
- 中屋敷, 金子（2018）の本文は、IPSJ のサーバーが 503 を返して開けなかった。IPSJ-GPWS2018002 の検索結果には囲碁の DNN の saliency map が書かれていたが、中屋敷らの将棋の論文と同じ論文かどうかは確かめられなかった。
- 会議名・誌名を確かめていないもの：Kindermans らの LNCS 11700 の章、DeepLIFT（ICML 2017）、Sundararajan と Najmi（ICML 2020）、Covert ら（JMLR）、Izzo ら、Guided IG（CVPR 2021）、McCloskey ら、McGrath ら（PNAS）、Greydanus ら、Yang ら（QPD）、Jenner ら。
- 要旨や一部だけを読んだもの：Izzo ら、Weighted IG、Geiger ら、Higgs ら。SARFA が囲碁でも使われたことは、検索結果だけで知った。
- Czech らが、個々の局面では全ゼロを使い、チャネルの平均では検証データの平均を使った理由は、論文に書かれていなかった。
- 依頼にあった「Pan et al. 2021」は、IJCAI 2021 の AGI の論文であることを確かめた。
