# 自己対戦棋譜のCSA変換（sgf_to_csa.py）

minizeroの自己対戦棋譜（`TRAIN_DIR/sgf/*.sgf`）を、ShogiHomeなどのCSA対応
ビューアで開ける **CSA v2** 形式に変換するスタンドアロンツール。

スクリプト: [scripts/sgf_to_csa.py](../scripts/sgf_to_csa.py)

> **2026-11-11 注記：** 2026-11-02 より前の 9×9 の棋譜では、投了した対局も `RE` が 0 である（`known_bugs.md` の #9）。このツールは `RE` だけを見るので、それらを `%SENNICHITE` と書き出す。**その頃の棋譜の `%SENNICHITE` は千日手とは限らない。** 本当の終局の理由は棋譜の `RR` タグにある（`RR[resign]` など。2026-07-20 から）。
> 例：論文の R3(RRT) の iteration 500 の棋譜では、`RE` が 0 の 1,127 局のうち 1,126 局が `RR[resign]`、1 局が `RR[cap]` で、千日手は 0 局だった。`csa_out/`（2026-07-28 に作った iteration 300 の 2,000 局）には `%SENNICHITE` が 775 局あるが、もとの棋譜がこの PC になく、内訳は確かめていない。

## これは何をするか

- 入力の `.sgf` は minizero 独自形式で、**1ファイルに複数ゲームが連続**して
  格納されている（各ゲームは `(;...)` ブロック）。棋譜はAlphaZeroの
  action-id 列だけを持つ。
- このツールはC++将棋環境には一切触らず、`shogi.h` の action-id デコード
  （`convertSunfish` / `get_to_sq_from_direction`）をPythonに移植して再現し、
  さらに軽量な盤面（駒配置＋持ち駒）を自前で持って手を再生する。
  action-id だけでは「どの駒が動いた／取られたか」が分からないため、
  初期局面から順に指し直して解決している。
- ゲームの `RE` タグ（結果）から、CSAの終局マーカー
  （`%TORYO` / `%SENNICHITE` / `%HIKIWAKE`）を付与する。

## 使い方

```bash
# ファイル内の全ゲームを out_dir/ に1ゲーム1ファイルで書き出す
./scripts/sgf_to_csa.py TRAIN_DIR/sgf/5.sgf -o out_dir/

# out_dir を指定しない場合は全ゲームを標準出力へ（空行区切り）
./scripts/sgf_to_csa.py TRAIN_DIR/sgf/5.sgf

# 引き分けラベルを正しくするため手数上限を渡す（下記参照）
./scripts/sgf_to_csa.py TRAIN_DIR/sgf/5.sgf -o out_dir/ --cap 512
```

出力ファイル名は `<入力ベース名>_<ゲーム番号>.csa`
（例: `5.sgf` → `5_0.csa`, `5_1.csa`, ...）。

## 引数

| 引数 | 説明 |
|---|---|
| `sgf_file`（必須） | minizeroの棋譜ファイル（例: `TRAIN_DIR/sgf/5.sgf`） |
| `-o`, `--out_dir` | 1ゲーム1ファイルで書き出す先。省略すると標準出力 |
| `--cap` | このファイルを生成したときの `env_shogi_max_moves`（学習ディレクトリの `.cfg` から）。**引き分けの表記にのみ影響**。省略可 |

## `--cap` について

結果が引き分け（`RE` が 0）のとき、CSAでは終局理由を区別する必要がある:

- **手数上限に達する前**に終わった引き分け → `%SENNICHITE`（千日手）
- **手数上限に達して**打ち切られた引き分け → `%HIKIWAKE`

両者とも `RE[0]` で区別がつかないため、`--cap` に上限手数を渡すと
「手数 ≥ cap なら `%HIKIWAKE`、そうでなければ `%SENNICHITE`」と判定する。
省略した場合は一律 `%SENNICHITE` になる。
（投了が 0 と記録された古い棋譜では、この判定は正しくない。上の注記を見る。）

## 終局マーカーの扱い

minizeroのactorはほとんどの対局で盤上の詰みまで指さず投了・裁定で終わるため、
勝敗の付いた対局はCSA慣例に従い一律 `%TORYO`（投了）として記録する。
2026-11-02 より後の棋譜では、投了は勝敗の付いた対局になる。
`RE` タグが無いゲームには終局マーカーを付けない（ビューア上は
「対局中」扱いになる）。

## デコード不能な手

action-id がデコードできなかった場合、その手は指されず
`# undecodable action_id=<id>` というコメント行が挿入される。
正常な棋譜では通常発生しない。
