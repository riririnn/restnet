# 効き方が見た目と違う cfg パラメータ

cfg には「書いてあるのに読まれない」「別の場所で効く」パラメータがある。
どうぶつしょうぎの cfg を論文設定に合わせる際に調べた結果をここに残す。

調査日: 2026-09-09 / 対象コミット: `7107047`

---

## 1. `program_seed`

```
program_seed=0
program_auto_seed=true
```

**`program_auto_seed=true` の間、`program_seed` は一度も読まれない。**
参照箇所は4つあり、いずれも同じ三項演算子になっている。

| 場所 | 何のシードか |
|---|---|
| [mode_handler.cpp:60](../minizero/minizero/console/mode_handler.cpp#L60) | コンソール実行 |
| [zero_server.cpp:176](../minizero/minizero/zero/zero_server.cpp#L176) | zero サーバー本体 |
| [actor_group.cpp:68](../minizero/minizero/actor/actor_group.cpp#L68) | 自己対局のアクター |
| [data_loader.cpp:104](../minizero/minizero/learner/data_loader.cpp#L104) | 学習データの読み出し |

```cpp
int seed = config::program_auto_seed ? std::random_device()() : config::program_seed + id_;
```

さらに、**自己対局のワーカーには cfg の値がそもそも届かない。**
サーバーがジョブを配るときに毎回上書きしている。

```cpp
// zero_server.cpp:92
job_command += ":program_auto_seed=false:program_seed=" + std::to_string(utils::Random::randInt());
```

つまり `program_auto_seed=true` のとき、cfg の `program_seed` が影響するのは
サーバー自身の乱数だけ。学習を完全に再現したい場合は
`program_auto_seed=false` にしたうえで `program_seed` を指定する必要があるが、
それでもワーカー側は上の上書きが効くため、自己対局までは再現されない。

論文はシードについて何も述べていないので、再現の対象外。

---

## 2. `nn_num_blocks`

```
nn_num_blocks=1
nn_blocks_type=R_R_T_R_R_T
```

**ネットワークの構築には使われない。** ブロック列は `nn_blocks_type` を
`_` で分解した結果だけで決まる。

```python
# restnet/learner/network/alphazero_network.py:51
self.blocks = nn.ModuleList(
    [self.get_backbone(blocktype) for blocktype in blocks_type.split("_")]
)
```

`num_blocks` は属性として保持され `get_num_blocks()` で外に出るが、
C++ 側では [network.cpp:54](../minizero/minizero/network/network.cpp#L54) の
`toString()` で表示されるだけで、検証にも分岐にも使われない。

上流 MiniZero では学習ディレクトリ名にも入るが、
**restnet のバイナリはそこも使っていない。** 名前生成が上書きされていて、
`nn_blocks_type` から `6R` / `RRTRRT` を組み立てる。

```cpp
// restnet/t_mode_handler.cpp:34 （restnet_* が使うのはこちら）
<< "_" << getBlockRepresentation()

// minizero/console/mode_handler.cpp:159 （minizero_* が使う旧実装）
<< "_" << config::nn_num_blocks << "b"
```

実測した名前。`6b` ではなく `6R` が出ている。

```
$ restnet_dobutsu -conf_file configs/dobutsu/6R.cfg -mode zero_training_name
dobutsu_gaz_6R_P_TV_n64-6fbc4d
```

したがって `restnet_*` を使う限り `nn_num_blocks` は**完全に不活性**で、
[network.cpp:54](../minizero/minizero/network/network.cpp#L54) の `toString()` に
表示されるだけ。ただし `build/*/minizero_*` のほうを実行すると名前に効くので、
**混乱を避けるため `nn_blocks_type` のブロック数と揃えて 6 にしておく**。

なお本家 MiniZero の [alphazero_network.py:35](../minizero/minizero/network/py/alphazero_network.py#L35)
は `num_blocks` で残差ブロックを並べている。ResTNet 側が
`nn_blocks_type` に置き換えたため、このパラメータだけが取り残された形になっている。

---

## 3. まとめ

| パラメータ | ネットワーク/学習への影響 | それ以外の影響 |
|---|---|---|
| `program_seed` | `auto_seed=true` なら無し | `auto_seed=false` にすればサーバーの乱数を固定 |
| `nn_num_blocks` | 無し（`nn_blocks_type` が決める） | `restnet_*` では無し。`minizero_*` の名前には `Nb` として出る |

どちらも「消してよい」ものではなく、**意図を持って値を選ぶべき**もの。
`nn_num_blocks` は構成に合わせて 6 にする。

## 関連

- [known_bugs.md](known_bugs.md) — 共通ファイルに特定ゲームの都合を書いた事例
