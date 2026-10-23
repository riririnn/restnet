"""Browse Tanaka's complete analysis of dobutsu shogi in a browser.

The analysis (2009, data/dobutsu_tablebase) comes with checkState, which takes a
position file and prints the position's value, every legal move with its value and
distance to the end, and then the whole optimal line. The upper half of the page
shows that output as it is; it adds nothing and leaves nothing out.

The lower half is ours, not theirs: over the moves of saved self-play games it
counts how often the move played is one the analysis calls best. Their package has
no program for that. Every counted position keeps its source, so any number can be
opened on the board above.

Usage (inside the container, from /workspace):
    PYTHONPATH=build/dobutsu python3 scripts/dobutsu_viewer.py
"""
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import env_py

TABLEBASE = Path("data/dobutsu_tablebase/dobutsu")
AGREEMENT = Path("data/dobutsu_agreement.csv")
CHANNELS = 20
COLUMNS = ["構成", "sgf", "局", "手数", "手番", "棋譜の手", "値", "一致", "最善手"]
PIECE = {"G": "KI", "E": "ZO", "C": "HI", "H": "NI", "L": "LI"}
JP = {"KI": "きりん", "ZO": "ぞう", "HI": "ひよこ", "NI": "にわとり", "LI": "ライオン"}


def to_position_file(env):
    """our env -> their position file (4 board rows, 6 stand counts, turn)."""
    text = env.to_string().splitlines()
    rows = ["".join(" . " if c == "." else ("+" if c.isupper() else "-") + PIECE[c.upper()]
                    for c in line.split()[1:]) for line in text[2:6]]
    hands = {line[0]: line.split(":")[1].strip().replace("-", "")
             for line in text if line[1:6] == " hand"}
    stands = "".join(str(hands[side].count(c)) for side in "BW" for c in "CEG")
    return "\n".join(rows) + "\n" + stands + "\n" + ("+" if text[-1].endswith("B") else "-") + "\n"


def to_their_move(env, move, player):
    """ours 'b2b3' or 'C*b2' -> theirs '+B3B2HI'.

    Their square is written from the top (row 1), ours from the bottom (row 4), and
    their piece code is the type after the move, so a promoting chick is a hen.
    """
    def square(s):
        return s[0].upper() + str(5 - int(s[1]))

    sign = "+" if player == "B" else "-"
    if move[1] == "*":
        return sign + "00" + square(move[2:4]) + PIECE[move[0]]
    board = env.to_string().splitlines()
    piece = board[6 - int(move[1])].split()[1:][ord(move[0]) - ord("a")].upper()
    if piece == "C" and move[3] == ("4" if player == "B" else "1"):
        piece = "H"
    return sign + square(move[0:2]) + square(move[2:4]) + PIECE[piece]


def check_state(env):
    """Run checkState on this position; return its output and the first block."""
    # the file goes outside their directory; the cwd stays there for allstates.dat
    with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
        f.write(to_position_file(env))
        f.flush()
        done = subprocess.run(["./checkState", f.name], cwd=str(TABLEBASE),
                              capture_output=True, text=True)
    out = done.stdout + done.stderr

    position, moves, chosen = None, [], None
    for line in out.splitlines():
        if line.startswith("Move : "):
            chosen = line.split()[2]
            break
        m = re.match(r"^(\d+) : ([+-]\w{6}) (-?\d+)\((\d+)\)", line)
        if m:
            # kept in their order, with their number
            moves.append((int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))))
        elif re.match(r"^-?\d+\(\d+\)$", line):
            position = tuple(int(x) for x in re.findall(r"-?\d+", line))

    # A position their table has no entry for, such as one where a lion already
    # stands on the far rank, is looked up at a broken index and prints a value
    # outside -1, 0, 1. Nothing from such a lookup means anything.
    if position is None or position[0] not in (-1, 0, 1):
        return out, None, [], None
    return out, position, moves, chosen


def describe(value, distance):
    """A move's value is the position after it, so it is the opponent's.

    +1 there means the opponent wins, that is we lose (winLoseTable.cc:112, and
    makeWinLose.cc gives isWin() the value +1 for the side to move).
    """
    if value < 0:
        return f"{distance + 1}手で勝ち"
    if value > 0:
        return "即負け" if distance == 0 else f"{distance + 1}手粘れる"
    return "引き分け"


def order(value, distance):
    """Sorted first is best for the mover: win sooner, lose later."""
    return (value, distance if value < 0 else -distance)


def sgf_runs():
    """The runs that have self-play games saved, wherever they sit under models."""
    return sorted(str(p.parent) for p in Path("models").rglob("sgf") if p.is_dir())


def sgf_files(run):
    return [p.name for p in sorted(Path(run, "sgf").glob("*.sgf"), key=lambda p: int(p.stem))]


def load_game(run, name, index):
    """The index-th game of that file as our move strings, with where it came from."""
    path = Path(run, "sgf", name)
    text = None
    with open(path) as f:
        for i, row in enumerate(f, 1):
            if i == index:
                text = row
                break
    if text is None:
        return [], f"{path} に第{index}局はない"

    env = env_py.Env()
    env.reset()
    moves = []
    for action_id in [int(x) for x in re.findall(r";[BW]\[(\d+)\]", text)]:
        action = next((a for a in env.get_legal_actions()
                       if a.get_action_id() == action_id), None)
        if action is None:
            break
        moves.append(action.to_console_string())
        env.act(action)

    result = re.search(r"RE\[(-?[\d.]+)\]", text)
    outcome = {"1": "先手勝ち", "-": "後手勝ち"}.get(result.group(1)[0] if result else "", "引き分け")
    return moves, f"{path}  第{index}局  全{len(moves)}手  結果 {outcome}"


def analyse(line, played=None):
    """Replay the moves, then report the position as checkState sees it.

    played is the move the game record makes here, so it can be marked.
    """
    env = env_py.Env()
    env.reset()
    for move in line:
        env.act(next(a for a in env.get_legal_actions() if a.to_console_string() == move))

    board = env.to_string().rstrip()
    if env.is_terminal():
        return env, board + "\n\n終局", [], ""

    out, position, values, chosen = check_state(env)
    player = "B" if len(line) % 2 == 0 else "W"
    ours = {to_their_move(env, a.to_console_string(), player): a.to_console_string()
            for a in env.get_legal_actions()}

    if position is None:
        note = ("\n\nこの局面は完全解析の表にない。ライオンが相手陣の最奥にいる局面など、"
                "彼らの解析が決着済みとして持たない局面。\n「1手戻る」で戻れる。")
        return env, board + note, [], out

    # the position's own value is printed from sente's side (winLoseTable.cc:91)
    header = f"この局面の値 {position[0]}({position[1]})  …… 先手の" \
        f"{'負け' if position[0] < 0 else '勝ち' if position[0] > 0 else '引き分け'}" \
        f"（あと{position[1] + 1}手）"
    rows, choices = [board, "", header, ""], []

    if not values:
        # with the lion there for the taking, checkState prints no move list
        # (winLoseTable.cc:93-103). The moves below are ours, without values.
        rows += ["手番が相手のライオンを取れるため、checkState は手の一覧を出さない。",
                 "以下は値のないこちらの合法手。", ""]
        choices = [(f"{m} {JP.get(m[5:7], '')}", o) for m, o in sorted(ours.items())]
        return env, "\n".join(rows + [c[0] for c in choices]), choices, out

    # their number, their order, their value; the rest of the line is interpretation
    best = min(order(value, distance) for _, _, value, distance in values)
    record = next((m for m, o in ours.items() if o == played), None)
    if record:
        agreed = order(*next((v, d) for _, m, v, d in values if m == record)) == best
        rows[2] += f"\n棋譜の手 {record} は {'◯ 最善と一致' if agreed else '× 最善ではない'}"

    rows.append("番号・手・値（checkStateのまま）".ljust(34) + "意味（手番から見て）")
    for number, move, value, distance in values:
        mark = " ★最善" if order(value, distance) == best else ""
        mark += " ←checkState が選んだ手" if move == chosen else ""
        mark += " ←棋譜の手" if move == record else ""
        their = str(number) + " : " + f"{move} {value}({distance})"
        rows.append(their.ljust(28) + JP.get(move[5:7], "").ljust(6)
                    + describe(value, distance) + mark)
        if move in ours:
            choices.append((f"{their} {JP.get(move[5:7], '')}{mark}", ours[move]))
    return env, "\n".join(rows), choices, out


def optimal_line():
    """Every position along the analysis's own optimal line, with its values.

    checkState names the move it takes at each position, so following that move
    walks the line the solved game calls best. Each entry carries the features a
    network needs, the legal moves in their notation, and the values.
    """
    env = env_py.Env()
    env.reset()
    positions = []
    while not env.is_terminal():
        _, position, values, chosen = check_state(env)
        if position is None or not values or chosen is None:
            break
        player = "B" if len(positions) % 2 == 0 else "W"
        legal = [(a, a.get_action_id(), to_their_move(env, a.to_console_string(), player))
                 for a in env.get_legal_actions()]
        positions.append((list(env.get_features()),
                          [(i, m) for _, i, m in legal], values))
        env.act(next(a for a, _, m in legal if m == chosen))
    return positions


def branched_line(depth=12, limit=6000):
    """Positions one move off the best line, then the best line again.

    The line itself is 77 positions, too few to separate eleven architectures.
    Stepping aside once and then following the analysis again keeps every
    position on an optimal continuation while giving thousands of them.
    """
    main = []
    env = env_py.Env()
    env.reset()
    while not env.is_terminal():
        _, position, values, chosen = check_state(env)
        if position is None or not values or chosen is None:
            break
        action = next(a for a in env.get_legal_actions()
                      if to_their_move(env, a.to_console_string(),
                                       "B" if len(main) % 2 == 0 else "W") == chosen)
        main.append(action.to_console_string())
        env.act(action)

    positions, seen = [], set()

    def walk(prefix, alternative, steps):
        """Replay prefix, take the alternative, then follow the best line."""
        env = env_py.Env()
        env.reset()
        for move in prefix:
            env.act(next(a for a in env.get_legal_actions()
                         if a.to_console_string() == move))
        env.act(next(a for a in env.get_legal_actions()
                     if a.to_console_string() == alternative))
        ply = len(prefix) + 1
        for _ in range(steps):
            if env.is_terminal() or len(positions) >= limit:
                return
            key = to_position_file(env)
            _, position, values, chosen = check_state(env)
            if position is None or not values or chosen is None:
                return
            player = "B" if ply % 2 == 0 else "W"
            if key not in seen:
                seen.add(key)
                positions.append((list(env.get_features()),
                                  [(a.get_action_id(),
                                    to_their_move(env, a.to_console_string(), player))
                                   for a in env.get_legal_actions()], values))
            env.act(next(a for a in env.get_legal_actions()
                         if to_their_move(env, a.to_console_string(), player) == chosen))
            ply += 1

    for i in range(len(main)):
        env = env_py.Env()
        env.reset()
        for move in main[:i]:
            env.act(next(a for a in env.get_legal_actions()
                         if a.to_console_string() == move))
        for action in env.get_legal_actions():
            move = action.to_console_string()
            if move == main[i] or len(positions) >= limit:
                continue
            walk(main[:i], move, depth)
    return positions


_MODELS = {}


SQUARES = ["%s%d" % (c, r) for r in (4, 3, 2, 1) for c in "abc"]   # 特徴量の並び。行0が4段目
_ATTN = {}


def attention_models():
    """The newest checkpoint of each current run."""
    found = []
    for d in sorted(Path("models/dobutsu/new").glob("*/model")):
        newest = max(d.glob("weight_iter_*.pt"), key=lambda q: int(re.findall(r"\d+", q.name)[0]), default=None)
        if newest is not None:
            found.append(str(newest))
    return found


def attention_net(path):
    """The model rebuilt in Python, checked against the saved one before use.

    A saved model loads in training mode. It is put in eval mode before it runs:
    otherwise BatchNorm uses the one position's own statistics and overwrites the
    stored ones, and every output after that is off.
    """
    if path not in _ATTN:
        import torch
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from xai_analysis import load_python_model

        ts = torch.jit.load(path, map_location="cpu")
        ts.eval()
        net = load_python_model(path, "cpu")
        env = env_py.Env()
        env.reset()
        x = torch.tensor(env.get_features()).view(1, CHANNELS, 4, 3)
        with torch.no_grad():
            a, b = ts(x), net(x)
            att = net.get_attn_table(x)["att_table"]
        heads = att[0].shape[1] if att else 0
        diff = max((a["policy"] - b["policy"]).abs().max().item(),
                   (a["value"] - b["value"]).abs().max().item())
        layers = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
        _ATTN[path] = (net, diff, layers, heads)
    return _ATTN[path]


def replay(line):
    env = env_py.Env()
    env.reset()
    for move in line:
        env.act(next(a for a in env.get_legal_actions() if a.to_console_string() == move))
    return env


_VALIDITY = {}


def validity_moves():
    """The best line's positions, each with the best moves that move a piece on the board.

    A drop has no square it moves from, so a position whose best moves are all
    drops is left out and counted. Returns (positions, dropped, line), each position
    (ply, features, [(from, to, move), ...]) and line the whole best line's moves.
    """
    if "moves" not in _VALIDITY:
        env = env_py.Env()
        env.reset()
        positions, dropped, ply, line = [], 0, 0, []
        while not env.is_terminal():
            _, position, values, chosen = check_state(env)
            if position is None or not values or chosen is None:
                break
            player = "B" if ply % 2 == 0 else "W"
            actions = env.get_legal_actions()
            mine = {to_their_move(env, a.to_console_string(), player): a for a in actions}
            best = min(order(v, d) for _, _, v, d in values)
            moves = [mine[m].to_console_string() for _, m, v, d in values if order(v, d) == best]
            board = [(SQUARES.index(m[:2]), SQUARES.index(m[2:4]), m) for m in moves if "*" not in m]
            if board:
                positions.append((ply, list(env.get_features()), board))
            else:
                dropped += 1
            line.append(mine[chosen].to_console_string())
            env.act(mine[chosen])
            ply += 1
        _VALIDITY["moves"] = (positions, dropped, line)
    return _VALIDITY["moves"]


def attention_validity():
    """For every model, block and head: the weight from the moving piece's square to
    the square it moves to, divided by the even 1/12, averaged over the best moves.

    1 means the head looks there no more than at any other square. In dobutsu a
    capture lands on the square moved to, so this one square covers captures too.
    """
    import torch
    positions, dropped, _ = validity_moves()
    x = torch.tensor([f for _, f, _ in positions]).view(len(positions), CHANNELS, 4, 3)
    pairs = [(i, a, b) for i, (_, _, moves) in enumerate(positions) for a, b, _ in moves]
    rows, notes = [], []
    for path in attention_models():
        net, diff, layers, heads = attention_net(path)
        name = Path(path).parts[-3]
        if not layers:
            continue
        if diff > 1e-6:
            notes.append("%s：組み立て直しが一致しない（差 %.1e）ので測らない" % (name, diff))
            continue
        with torch.no_grad():
            att = net.get_attn_table(x)["att_table"]
        for k, i in enumerate(layers):
            for h in range(heads):
                r = [float(att[k][n, h, a, b]) * 12 for n, a, b in pairs]
                rows.append([name, "第%dTブロック（第%dブロック）" % (k + 1, i + 1), "第%dヘッド" % (h + 1),
                             round(sum(r) / len(r), 3), round(min(r), 3), round(max(r), 3)])
    rows.sort(key=lambda r: -r[3])
    text = ("最善手順の %d 局面（最善手がすべて駒打ちの %d 局面を除く）、判定した手 %d 個。"
            "値は「動かす駒のマス → 行き先のマス」の重み × 12。1 なら向いていない。"
            "初回は全モデルの読み込みに数秒かかる") % (len(positions), dropped, len(pairs))
    return "\n".join([text] + notes), rows


def validity_figure():
    """The numbers of attention_validity as dots, one column per model in the order of the
    ResTNet paper, so the head picked for the paper can be seen against all the others. A PNG path."""
    import tempfile
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    text, rows = attention_validity()
    order = ["6T", "5R1T", "4R2T", "3R3T", "2R4T", "1R5T", "TRRRRT", "RTRRRT", "RRTRRT", "RRRTRT"]
    order = [m for m in order if any(r[0] == m for r in rows)]
    top = max(rows, key=lambda r: r[3])
    # drawn at the paper's column width (3.4 in), so it is printed at this size, not shrunk
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for x, m in enumerate(order):
        v = [r[3] for r in rows if r[0] == m]
        ax.scatter([x] * len(v), v, s=12, color="#2a78d6", alpha=0.6, linewidths=0)
    ax.scatter([order.index(top[0])], [top[3]], s=30, color="#d0402a", zorder=3)
    ax.annotate("%s %s%s\n%.2f" % (top[0], top[1].split("（")[0], top[2], top[3]),
                (order.index(top[0]), top[3]), xytext=(8, -4), textcoords="offset points", fontsize=7, va="top")
    ax.axhline(1, color="#888", lw=0.8, ls="--")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("行き先への重み × 12（平均）", fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "validity.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return str(out), text


def validity_detail(name, block, head):
    """One head's ratio for every judged best move, largest first."""
    import torch
    positions, _, _ = validity_moves()
    path = dict(attention_arch_choices())[name]
    net, _, layers, _ = attention_net(path)
    x = torch.tensor([f for _, f, _ in positions]).view(len(positions), CHANNELS, 4, 3)
    with torch.no_grad():
        att = net.get_attn_table(x)["att_table"][layers.index(block)]
    rows = [[ply, "先手" if ply % 2 == 0 else "後手", m, SQUARES[a], SQUARES[b],
             round(float(att[n, head, a, b]) * 12, 3)]
            for n, (ply, _, moves) in enumerate(positions) for a, b, m in moves]
    return sorted(rows, key=lambda r: -r[5])


PRESETS = "data/attention_presets_dobutsu.npz"   # scripts/attention_presets.py dobutsu
CODE = {1: "c", 2: "e", 3: "g", 4: "h", 5: "l"}   # Tanaka's piece codes, as in dobutsu_all_agreement


def position_input(line, rec=None):
    """(input, board rows, hands, black to move) from a move line, or from one record of
    scripts/dobutsu_all.cc, which has no move line (the input is built as
    dobutsu_all_agreement.features() builds it)."""
    import torch
    if rec is None:
        env = replay(line)
        x = torch.tensor(env.get_features()).view(1, CHANNELS, 4, 3)
        text = env.to_string().splitlines()
        board = [r.split()[1:] for r in text[2:6]]
        hands = {r[0]: "・".join(PIECES[k.lower()] for k in r.split(":", 1)[1].strip() if k.isalpha()) or "なし"
                 for r in text if " hand:" in r}
        return x, board, hands, len(line) % 2 == 0
    import dobutsu_all_agreement
    x = dobutsu_all_agreement.features(rec, "cpu")
    b = rec["board"][0]
    board = [[(CODE[abs(p)].upper() if p > 0 else CODE[abs(p)]) if p else "." for p in b[r * 3:r * 3 + 3]]
             for r in range(4)]
    h = rec["hands"][0]
    hands = {side: "・".join(name for name, n in zip(("キリン", "ゾウ", "ヒヨコ"), h[i:i + 3]) for _ in range(n)) or "なし"
             for side, i in (("B", 0), ("W", 3))}
    return x, board, hands, rec["turn"][0] == 1


_PRESETS = {}


def presets():
    """label -> ("line", ply) on the best line, or ("rec", n) in PRESETS. Built once."""
    if not _PRESETS:
        line = validity_moves()[2]
        positions = position_set(False)
        picks = {Path(p).parts[-3]: policy_picks(p, positions) for p in attention_models()}
        for ply, (_, _, values) in enumerate(positions):
            best = min(order(v, d) for _, _, v, d in values)
            moves = {m: order(v, d) for _, m, v, d in values}
            missed = [n for n, pk in picks.items() if moves[pk[ply]] != best]
            if missed:
                _PRESETS["最善手順 %d手目（%s）で最善手を外した：%s" % (
                    ply, "先手番" if ply % 2 == 0 else "後手番", "・".join(missed))] = ("line", ply)
        if Path(PRESETS).is_file():
            import numpy as np
            for n, label in enumerate(np.load(PRESETS)["labels"]):
                _PRESETS[str(label)] = ("rec", n)
        _PRESETS["(line)"] = line
    return _PRESETS


PRESET_KINDS = {"すべて": "", "最善手順で外した": "最善手順", "勝ちを失った": "勝ちを失った",
                "6T だけ最善手": "6Tだけ", "6R だけ最善手": "6Rだけ", "最善手が駒打ち": "最善手が駒打ち",
                "詰み（6T が外した）": "詰み", "トライ（6T が外した）": "トライ",
                "最善手と一致（6T 正解・RRTRRT 不正解）": "最善手と一致", "狙ってくる駒": "狙ってくる駒",
                "粘りの手（負けの局面）": "粘りの手", "相手のライオンから（第4ブロック H1）": "相手のライオンから",
                "持ち駒が勝敗を決める（完全解析で確認）": "持ち駒が勝敗を決める",
                "持ち駒で Attention が変わる（6T、打つ駒を渡す）": "持ち駒で Attention が変わる"}


def preset_labels(kind):
    return [k for k in presets() if k != "(line)" and k.startswith(PRESET_KINDS[kind])]


def step_preset(kind, label, d):
    """The preset before (d=-1) or after (d=1) this one, in the chosen kind."""
    labels = preset_labels(kind)
    if not labels:
        return None
    i = labels.index(label) if label in labels else (-1 if d > 0 else 0)
    return labels[(i + d) % len(labels)]


def save_candidate(game, label, models, block, query, style, files, head="全ヘッド"):
    """Copy the figures shown to data/attention_candidates/ and note what they show
    in data/attention_selected.tsv, for the paper's figures later."""
    import datetime
    import shutil
    out = Path("data/attention_candidates")
    out.mkdir(parents=True, exist_ok=True)
    n = len(list(out.glob("%s_*.png" % game))) + 1
    saved = []
    for k, f in enumerate(x for x in files if x):
        dst = out / ("%s_%03d%s.png" % (game, n, ["", "_hand", "_drop"][min(k, 2)]))
        shutil.copy(f, dst)
        saved.append(str(dst))
    if not saved:
        return "保存する図がない"
    layer = "all" if block == ALL_BLOCKS else str(block + 1 if isinstance(block, int) else block)
    layer += "" if head == "全ヘッド" else "-" + head
    row = [datetime.datetime.now().isoformat(timespec="seconds"), game, label, ",".join(models), layer,
           str(query), "paper" if style == PAPER else "ratio", ",".join(saved)]
    with open("data/attention_selected.tsv", "a") as f:
        f.write("\t".join(row) + "\n")
    return "保存した：" + "、".join(saved)


def preset_record(n):
    import numpy as np
    return np.load(PRESETS)["records"][n:n + 1]


def preset_move(n):
    """(square to start the attention from, move) kept for preset n; -1 when not kept."""
    import numpy as np
    d = np.load(PRESETS)
    if "query" not in d.files:
        return -1, -1
    return int(d["query"][n]), int(d["action"][n])


def hand_contribution(path, x, action):
    """How much the value, and the policy of `action`, drop when one piece of a kind in hand is
    given to the other side, as xai_analysis.hand_piece_contribution does for 9x9. Giving it
    away keeps the eight pieces, so the position can occur and the complete analysis has it.
    Shape (value/policy, own/opponent, giraffe/elephant/chick); the own pieces are planes 10-12,
    the opponent's 13-15. A piece not held stays 0. The value of dobutsu's network is sente's,
    so it is turned to the side to move's first."""
    import numpy as np
    import torch
    model = torch.jit.load(path, map_location="cpu")
    model.eval()
    mover = 1.0 if float(x[0, 16, 0, 0]) > 0 else -1.0   # plane 16: sente to move
    out = np.zeros((2, 2, 3))
    with torch.no_grad():
        base = model(x)
        for side in range(2):
            for k in range(3):
                ch, other = 10 + 3 * side + k, 10 + 3 * (1 - side) + k
                if float(x[0, ch, 0, 0]) <= 0:
                    continue
                given = x.clone()
                given[:, ch] -= 1
                given[:, other] += 1
                o = model(given)
                out[0, side, k] = mover * (float(base["value"]) - float(o["value"]))
                out[1, side, k] = float(base["policy"][0, action]) - float(o["policy"][0, action])
    return out


def hand_figure(path, rec, action, label, bare=False):
    """Bar chart of hand_contribution for the move `action`, beside the Attention Map; a PNG path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    from attention_presets import dobutsu_move
    c = hand_contribution(path, position_input([], rec)[0], action)
    dropped = (action - 96) // 12 if action >= 96 else None
    if dropped is not None:
        # without the piece the move cannot be played, so its probability simply vanishes: the bar
        # would only repeat the move's own probability, and is left out
        c[1, 0, dropped] = np.nan
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
    x = np.arange(3)
    for ax, values, title in zip(axes, c, ("value への寄与", "policy への寄与（%s）" % dobutsu_move(action))):
        ax.bar(x - 0.19, values[0], 0.38, label="手番側の持ち駒", color="#D4A96A", edgecolor="#3a2000")
        ax.bar(x + 0.19, values[1], 0.38, label="相手の持ち駒", color="#4a6fa5", edgecolor="#1a2a45")
        ax.axhline(0, color="#666", linewidth=0.8)
        ax.set_ylim(*((-2, 2) if ax is axes[0] else (-1, 1)))   # value moves within ±2, a probability within ±1
        ax.set_xticks(x)
        ax.set_xticklabels(["キリン", "ゾウ", "ヒヨコ"])
        ax.tick_params(labelsize=13 if bare else 9)
        ax.set_title(title, fontsize=14 if bare else 10)
        ax.legend(fontsize=11 if bare else 7)
    if dropped is not None:
        axes[1].text(dropped, 0.12, "打つ駒は\n示さない", ha="center", va="bottom", fontsize=10 if bare else 7)
    axes[0].set_ylabel("相手に1枚渡したときの下がり方", fontsize=11 if bare else 7)
    if not bare:
        fig.suptitle("%s　%s" % (Path(path).parts[-3], label), fontsize=9)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "hand.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def block_statistics(per_orient=10000, seed=5, ig_positions=1000, ig_seed=1):
    """On the positions of head_statistics (the same draw), from the side to move's lion:
    (a) for each Transformer block of 6T and RRTRRT, the median and upper quartile over positions of
    the largest weight × 12 among the block's heads; (b) on `ig_positions` of them, how many of the
    3 squares with the largest |IG of the value| (pieces on the board, from the all-zero input) are
    among the 3 squares the head weighs most, averaged, for 6T's block 5 head 4 and block 4 head 1
    and the best head of each model, beside chance (3 × 3 / 12). The numbers as text."""
    import numpy as np
    import torch
    import dobutsu_all_agreement as A
    from attention_presets import PART, TOTAL
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from xai_analysis import integrated_gradients_inputs
    paths = dict(attention_arch_choices())
    rng = np.random.default_rng(seed)
    recs = []
    for orient, folder in ((0, "full"), (2, "full_o2")):
        index = np.sort(rng.choice(TOTAL, per_orient, replace=False))
        r = np.concatenate([np.array(np.memmap("data/dobutsu_all/%s/part_%03d.bin" % (folder, part), dtype=A.RECORD,
                                               mode="r")[index[(index // PART) == part] - part * PART])
                            for part in np.unique(index // PART)])
        recs.append(r[(r["count"] > 0) | (r["value"] != -1)])
    r = np.concatenate(recs)
    me = np.where(r["turn"] == 1, 1, -1)
    has = np.array([(r["board"][i] == 5 * me[i]).any() for i in range(len(r))])
    r, me = r[has], me[has]
    x = A.features(r, "cpu")
    lion = torch.as_tensor([int(np.argmax(r["board"][i] == 5 * me[i])) for i in range(len(r))])
    lines = ["局面：head_statistics と同じ（完全解析から先手番・後手番の向き各 %d 局面、seed %d）のうち、手番側のライオンが盤上にある %d 局面。起点は手番側のライオン"
             % (per_orient, seed, len(r))]
    weights = {}
    for name in ("6T", "RRTRRT"):
        net, _, layers, heads = attention_net(paths[name])
        with torch.no_grad():
            t = [net.get_attn_table(x[s:s + 2048])["att_table"] for s in range(0, len(r), 2048)]
        cells = []
        for k, b in enumerate(layers):
            w = torch.cat([tt[k] for tt in t])[torch.arange(len(r)), :, lion] * 12   # (positions, heads, 12)
            top = w.max(-1).values.max(-1).values.numpy()
            cells.append("第%dブロック %.2f（上位25%% %.2f）" % (b + 1, np.median(top), np.quantile(top, 0.75)))
            for h in range(heads):
                weights[(name, b + 1, h + 1)] = w[:, h].numpy()
        lines.append("(a) %s のブロックごとの 4 ヘッドの最大（重み×12）の中央値：%s" % (name, "　".join(cells)))
    sub = np.random.default_rng(ig_seed).choice(len(r), ig_positions, replace=False)
    for name in ("6T", "RRTRRT"):
        model = A.load(paths[name], "cpu")
        overlap = {k: [] for k in weights if k[0] == name}
        for j in sub:
            ig = integrated_gradients_inputs(model, x[j:j + 1], target="value", sign=float(me[j]))
            top_ig = set(np.argsort(-np.abs(ig[0:10].sum(0).reshape(12)))[:3].tolist())
            for key in overlap:
                overlap[key].append(len(top_ig & set(np.argsort(-weights[key][j])[:3].tolist())))
        best = max(overlap, key=lambda key: np.mean(overlap[key]))
        named = "".join("　第%dブロックH%d %.2f" % (k[1], k[2], np.mean(overlap[k])) for k in ((name, 5, 4), (name, 4, 1)) if k in overlap)
        lines.append("(b) %s：value の IG の |値| 上位 3 マスと重みの上位 3 マスの重なりの平均（%d 局面、seed %d）：最も重なるヘッド 第%dブロックH%d %.2f%s　偶然 %.2f"
                     % (name, ig_positions, ig_seed, best[1], best[2], np.mean(overlap[best]), named, 9 / 12))
    return "\n".join(lines)


def head_statistics(per_orient=10000, seed=5):
    """What 6T's block 5 head 4 looks at from the lion of the side to move, over positions
    drawn at random from the complete analysis (both orientations), next to the best of 6T's
    other 23 heads, the best of RRTRRT's 8 heads (each taken per question) and chance (a
    square other than the lion, at random). A bar chart as a PNG path, and the numbers."""
    import tempfile
    import numpy as np
    import torch
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import dobutsu_all_agreement as A
    from attention_presets import PART, TOTAL, dobutsu_move, threats
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    paths = dict(attention_arch_choices())
    net6, _, l6, _ = attention_net(paths["6T"])
    netR, _, lR, _ = attention_net(paths["RRTRRT"])
    key = (l6.index(4), 3)   # block 5, head 4
    groups = ["取れる相手のライオン\n（取れる局面）", "最善手の行き先\n（最善手がライオンの手）",
              "ライオンを狙う駒\n（ライオン以外）", "粘りの手の行き先\n（負け・最善手がライオンの手）"]
    hits = {"6T": {}, "RRTRRT": {}, "偶然": np.zeros(len(groups))}
    count = np.zeros(len(groups))
    rng = np.random.default_rng(seed)
    for orient, folder in ((0, "full"), (2, "full_o2")):
        index = np.sort(rng.choice(TOTAL, per_orient, replace=False))
        r = np.concatenate([np.array(np.memmap("data/dobutsu_all/%s/part_%03d.bin" % (folder, part), dtype=A.RECORD,
                                               mode="r")[index[(index // PART) == part] - part * PART])
                            for part in np.unique(index // PART)])
        r = r[(r["count"] > 0) | (r["value"] != -1)]
        x = A.features(r, "cpu")
        with torch.no_grad():
            t6 = [net6.get_attn_table(x[s:s + 2048])["att_table"] for s in range(0, len(r), 2048)]
            tR = [netR.get_attn_table(x[s:s + 2048])["att_table"] for s in range(0, len(r), 2048)]
        # (block, head) -> the square each head looks at most, from every square: (positions, 12)
        top6 = {(k, h): torch.cat([t[k][:, h] for t in t6]).argmax(-1).numpy() for k in range(len(l6)) for h in range(4)}
        topR = {(k, h): torch.cat([t[k][:, h] for t in tR]).argmax(-1).numpy() for k in range(len(lR)) for h in range(4)}
        kinds = A.kind(r)
        best = A.bits(r["best"]).numpy()
        for i in range(len(r)):
            b = r["board"][i]
            me = 1 if r["turn"][i] == 1 else -1
            if not (b == 5 * me).any():
                continue
            lion = int(np.argmax(b == 5 * me))
            opp = int(np.argmax(b == -5 * me)) if (b == -5 * me).any() else None
            moves = np.nonzero(best[i])[0]
            lion_best = {SQUARES.index(dobutsu_move(int(a))[-2:]) for a in moves if a < 96 and a // 8 == lion}
            targets = [({opp} if kinds[i] == 1 and opp is not None else set()),
                       (lion_best if kinds[i] != 3 else set()),
                       set(threats(b, lion, -me)) if kinds[i] != 1 else set(),
                       (lion_best if kinds[i] == 3 else set())]
            for g, t in enumerate(targets):
                if not t:
                    continue
                count[g] += 1
                for name, tops in (("6T", top6), ("RRTRRT", topR)):
                    for kh, top in tops.items():
                        hits[name].setdefault(kh, np.zeros(len(groups)))[g] += int(top[i, lion]) in t
                hits["偶然"][g] += len(t - {lion}) / 11
    n = np.maximum(count, 1)
    others = {kh: v for kh, v in hits["6T"].items() if kh != key}
    best_other = [max(others, key=lambda kh: others[kh][g]) for g in range(len(groups))]
    best_r = [max(hits["RRTRRT"], key=lambda kh: hits["RRTRRT"][kh][g]) for g in range(len(groups))]
    share = {"6T": 100 * hits["6T"][key] / n,
             "他": np.array([100 * others[best_other[g]][g] / n[g] for g in range(len(groups))]),
             "RRTRRT": np.array([100 * hits["RRTRRT"][best_r[g]][g] / n[g] for g in range(len(groups))]),
             "偶然": 100 * hits["偶然"] / n}
    # drawn at the paper's column width (3.4 in), so it is printed at this size, not shrunk
    fig, ax = plt.subplots(figsize=(3.4, 3.1))
    xs = np.arange(len(groups))
    colors = {"6T": "#2a78d6", "他": "#1baf7a", "RRTRRT": "#eb6834", "偶然": "#a3a29c"}
    labels = {"6T": "6T 第5Tブロック第4ヘッド", "他": "6T のほかの23ヘッドの最高",
              "RRTRRT": "RRTRRT の8ヘッドの最高", "偶然": "偶然"}
    short = ["取れる\nライオン", "最善手の\n行き先", "狙ってくる\n駒", "粘る手の\n行き先"]
    for k, (name, v) in enumerate(share.items()):
        bars = ax.bar(xs + (k - 1.5) * 0.2, v, 0.19, color=colors[name], label=labels[name])
        if name in ("6T", "他"):
            ax.bar_label(bars, fmt="%.0f", fontsize=7, padding=1)
    ax.set_xticks(xs)
    ax.set_xticklabels(["%s\n%d 局面" % (g, n) for g, n in zip(short, count)], fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("最大の重みが正解のマスに向いた割合（%）", fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.45, 1.0),
              handlelength=1.2, columnspacing=0.8)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "head_statistics.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    note = "起点＝手番側のライオン。完全解析から無作為に先手番・後手番の向き各 %d 局面（seed %d）。" % (per_orient, seed)
    note += "　".join("%s：6T 第5Tブロック第4ヘッド %.1f%%、ほかの最高 %.1f%%（第%dTブロック第%dヘッド）、RRTRRT の最高 %.1f%%（第%dTブロック第%dヘッド）、偶然 %.1f%%（%d 局面）" % (
        g.replace("\n", ""), share["6T"][k], share["他"][k], best_other[k][0] + 1, best_other[k][1] + 1,
        share["RRTRRT"][k], best_r[k][0] + 1, best_r[k][1] + 1, share["偶然"][k], count[k]) for k, g in enumerate(groups))
    return str(out), note


def drop_figure(path, rec, label, bare=False):
    """For each kind of piece the side to move holds, the policy's probability of dropping
    it on each square, as a board (rings: the best drops of the complete analysis); a PNG path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    import dobutsu_all_agreement as A
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    x, board, hands, black = position_input([], rec)
    with __import__("torch").no_grad():
        policy = A.load(path, "cpu")(x)["policy"][0].numpy()
    best = set(np.nonzero(A.bits(rec["best"])[0].numpy())[0].tolist())
    held = [k for k in range(3) if float(x[0, 10 + k, 0, 0]) > 0]
    if not held:
        return None
    names = ["キリン", "ゾウ", "ヒヨコ"]
    blue = LinearSegmentedColormap.from_list("board_blue", ["#f3d9b1", "#2a78d6"])
    fig, axes = plt.subplots(1, len(held), figsize=(2.6 * len(held) + 1, 3.4), squeeze=False)
    for ax, k in zip(axes[0], held):
        p = policy[96 + 12 * k: 108 + 12 * k].reshape(4, 3)
        im = ax.imshow(p, cmap=blue, norm=Normalize(0, 1))
        for sq in range(12):
            r, c = divmod(sq, 3)
            piece = board[r][c]
            if piece != ".":
                ax.text(c, r, PIECES[piece.lower()][0] if bare else PIECES[piece.lower()], ha="center", va="center",
                        fontsize=18 if bare else 8, rotation=0 if piece.isupper() else 180)
            elif p[r, c] >= 0.01:
                ax.text(c, r, "%.2f" % p[r, c], ha="center", va="center", fontsize=14 if bare else 8)
            if 96 + 12 * k + sq in best:
                ax.add_patch(plt.Circle((c, r), 0.44, fill=False, lw=2.5, ec="#1f5fbf"))
        square_lines(ax)
        ax.set_xticks(range(3))
        ax.set_xticklabels(list("abc"))
        ax.set_yticks(range(4))
        ax.set_yticklabels(["4", "3", "2", "1"])
        ax.tick_params(labelsize=14 if bare else 10)
        ax.set_title("%sを打つ確率" % names[k], fontsize=14 if bare else 10)
    bar = fig.colorbar(im, ax=axes, shrink=0.8)
    bar.set_label("打つ確率（○ 最善の打つ先）", fontsize=12 if bare else 9)
    if not bare:
        fig.suptitle("%s　%s" % (Path(path).parts[-3], label), fontsize=9)
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "drop.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def agreement_figure():
    """The share of positions where each configuration's policy picks a best move, over every
    position of the complete analysis but the lost ones where the lion has already been
    tried, in both orientations (data/dobutsu_all_agreement_full*.csv); a PNG path and the numbers."""
    import csv as _csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    order = ["6R", "5R1T", "4R2T", "3R3T", "2R4T", "1R5T", "6T", "TRRRRT", "RTRRRT", "RRTRRT", "RRRTRT"]
    share = {}
    for orient, f in (("先手番の向き", "full"), ("後手番の向き", "full_o2")):
        t = {}
        for row in _csv.DictReader(open("data/dobutsu_all_agreement_%s.csv" % f)):
            if row["局面の種類"].startswith("負け（手数0"):
                continue
            c = t.setdefault(row["構成"], [0, 0])
            c[0] += int(row["最善手を選んだ数"])
            c[1] += int(row["局面数"])
        share[orient] = [t[n][0] / t[n][1] for n in order]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for (orient, v), color, mark, dx in zip(share.items(), ("#2a78d6", "#eb6834"), ("o", "s"), (-0.12, 0.12)):
        ax.plot([k + dx for k in range(len(order))], v, mark, color=color, ms=8, label=orient)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=40, fontsize=9)
    ax.set_ylabel("最善手を選んだ割合", fontsize=9)
    ax.set_ylim(0.80, 0.88)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "agreement.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    note = "　".join("%s %.3f／%.3f" % (n, share["先手番の向き"][k], share["後手番の向き"][k]) for k, n in enumerate(order))
    return str(out), "最善手を選んだ割合（先手番の向き／後手番の向き、239,784,182 局面）：" + note


def attention_summary(line, rec=None):
    """How far each head is from even, in this position: every model, layer and head.

    The ratio is the weight times 12, so 1 is the even 1/12 and 12 is all on one
    square. The row gives the largest ratio over every query and key square.
    """
    import torch
    x = position_input(line, rec)[0]
    rows = []
    for path in attention_models():
        net, diff, layers, _ = attention_net(path)
        name = Path(path).parts[-3]
        if diff > 1e-6:
            rows.append([name, "", "", "組み立て直しが一致しない（差 %.1e）" % diff, "", ""])
            continue
        with torch.no_grad():
            att = net.get_attn_table(x)["att_table"]
        for k, i in enumerate(layers):
            for h in range(att[k].shape[1]):
                w = att[k][0, h].numpy() * 12
                q, key = divmod(int(w.argmax()), 12)
                rows.append([name, "第%dTブロック（第%dブロック）" % (k + 1, i + 1), "第%dヘッド" % (h + 1),
                             round(float(w.max()), 2), SQUARES[q], SQUARES[key]])
    return sorted(rows, key=lambda r: -r[3] if isinstance(r[3], float) else 0)


def attention_arch_choices():
    """(name, path) of the newest checkpoint of every run that has a Transformer block."""
    return [(Path(p).parts[-3], p) for p in attention_models() if attention_net(p)[2]]


ALL_BLOCKS = -1   # draw every Transformer block of every chosen model


def attention_layer_choices(paths):
    """Block positions that are a Transformer in at least one of these models."""
    count = {}
    for path in paths or []:
        for i in attention_net(path)[2]:
            count[i] = count.get(i, 0) + 1
    every = [("すべての T ブロック（モデルごと・ブロックごとに縦に並べる）", ALL_BLOCKS)] if count else []
    return every + [("第%dブロック（選んだうち %d 構成が Transformer）" % (i + 1, n), i) for i, n in sorted(count.items())]


PAPER = "論文と同じ（各図を [0, 1] に正規化、赤いほど高い）"
RATIO = "均等値 1/12 を 1 とした比（盤の色＝均等以下、赤いほど多い、12＝1マスに集中）"
PIECES = {"l": "ライオン", "g": "キリン", "e": "ゾウ", "c": "ヒヨコ", "h": "ニワトリ"}


def position_title(label, line):
    """Where this position comes from, in words."""
    last = "直前の手 %s" % line[-1] if line else "初期局面"
    return "%s　%d手目まで指した局面（%s）　%s番" % (label, len(line), last, "先手" if len(line) % 2 == 0 else "後手")


def draw_move(ax, move, color, dashed, black, bare=False):
    """A move as an arrow from the square it leaves (a drop: from the hand, off the board)."""
    t = SQUARES.index(move[-2:])
    if "*" in move:
        start = (t % 3, 4.15 if black else -1.15)   # the side to move's hand: below for sente, above for gote
        ax.text(*start, PIECES[{"G": "g", "E": "e", "C": "c"}[move[0]]][0] + "打", ha="center",
                va="top" if black else "bottom", fontsize=(18 if bare else 8) * 0.7, color=color, clip_on=False)
    else:
        f = SQUARES.index(move[:2])
        start = (f % 3, f // 3)
    ax.annotate("", xy=(t % 3, t // 3), xytext=start, annotation_clip=False,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=2.5 if bare else 1.8, alpha=0.85,
                                linestyle="--" if dashed else "-", shrinkA=6, shrinkB=6, mutation_scale=18))


def ig_figure(path, rec, action, label, bare=False, parts=False):
    """Integrated Gradients of the value (from the side to move) and of the probability of
    `action`, from the all-zero input: the pieces on the board as maps (red raises the output,
    blue lowers it, one scale per map), the hand pieces as bars; a PNG path. With `parts`, the
    three panels as three PNG paths instead (value, the move's probability, the bars), each one
    column of the paper wide."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.lines import Line2D
    import dobutsu_all_agreement as A
    from attention_presets import dobutsu_move
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from xai_analysis import integrated_gradients_inputs
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    model = A.load(path, "cpu")
    x, board, hands, black = position_input([], rec)
    mover = 1.0 if black else -1.0   # dobutsu's value is sente's
    best = [dobutsu_move(int(a)) for a in np.nonzero(A.bits(rec["best"])[0].numpy())[0]]
    own = dobutsu_move(int(action))
    cmap = LinearSegmentedColormap.from_list("ig", ["#2a78d6", "#ffffff", "#c8402a"])
    targets = (("value", "value（手番側から見た勝ちやすさ）"), ("policy", "policy（%s の確率）" % own))
    igs = [integrated_gradients_inputs(model, x, target=t, action_idx=int(action), sign=mover) for t, _ in targets]
    bars = [(ig[10:13].sum((1, 2)), ig[13:16].sum((1, 2)), float(ig[16:].sum())) for ig in igs]

    def draw_board(fig, ax, ig, title):
        m = ig[0:10].sum(0).reshape(4, 3)   # the pieces on each square
        top = float(max(np.abs(m).max(), 1e-9))
        im = ax.imshow(m, cmap=cmap, norm=TwoSlopeNorm(vmin=-top, vcenter=0, vmax=top))
        for r in range(4):
            for c in range(3):
                p = board[r][c]
                if p != ".":
                    ax.text(c, r, PIECES[p.lower()][0] if bare else PIECES[p.lower()], ha="center", va="center",
                            fontsize=18 if bare else 8, rotation=0 if p.isupper() else 180)
        for mv in best:
            draw_move(ax, mv, "#1f5fbf", False, black, bare)
        draw_move(ax, own, "k", True, black, bare)
        square_lines(ax)
        ax.set_xticks(range(3))
        ax.set_xticklabels(list("abc"))
        ax.set_yticks(range(4))
        ax.set_yticklabels(["4", "3", "2", "1"])
        ax.tick_params(labelsize=13 if bare else 9)
        ax.set_title("IG：" + title, fontsize=11 if bare else 9, pad=30 if not black and "*" in "".join(best + [own]) else 6)
        fig.colorbar(im, ax=ax, shrink=0.8)

    def draw_bars(bx):
        xs = np.arange(3)
        for k, (name, (o, e, _)) in enumerate(zip(("value", "policy"), bars)):
            bx.bar(xs + (k - 0.5) * 0.4 - 0.1, o, 0.2, label="%s：手番側の持ち駒" % name, color=("#D4A96A", "#f0d090")[k], edgecolor="#3a2000")
            bx.bar(xs + (k - 0.5) * 0.4 + 0.1, e, 0.2, label="%s：相手の持ち駒" % name, color=("#4a6fa5", "#9fb8dd")[k], edgecolor="#1a2a45")
        bx.axhline(0, color="#666", linewidth=0.8)
        bx.set_xticks(xs)
        bx.set_xticklabels(["キリン", "ゾウ", "ヒヨコ"])
        bx.set_title("持ち駒の IG（盤に場所がないので棒）", fontsize=11 if bare else 9)
        bx.legend(fontsize=7)
        bx.text(0.02, 0.02, "手番などの IG の合計 value %+.3f／policy %+.3f" % (bars[0][2], bars[1][2]),
                transform=bx.transAxes, fontsize=7, va="bottom")

    def legend(fig, x):
        fig.legend([Line2D([], [], color="#1f5fbf", lw=2.5), Line2D([], [], color="k", lw=2.5, linestyle="--")],
                   ["最善手", "%sの手" % Path(path).parts[-3]], loc="lower center", ncol=2, frameon=False,
                   fontsize=11 if bare else 8, bbox_to_anchor=(x, -0.13))

    def save(fig, name):
        fig.tight_layout()
        out = Path(tempfile.gettempdir()) / "dobutsu_attention" / name
        out.parent.mkdir(exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(out)

    if parts:
        outs = []
        for ig, (target, title) in zip(igs, targets):
            fig, ax = plt.subplots(figsize=(3.6, 3.9))
            draw_board(fig, ax, ig, title)
            legend(fig, 0.5)
            outs.append(save(fig, "ig_%s.png" % target))
        fig, bx = plt.subplots(figsize=(4.2, 3.9))
        draw_bars(bx)
        outs.append(save(fig, "ig_bars.png"))
        return outs
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.9), gridspec_kw={"width_ratios": [1, 1, 1.3]})
    for ax, ig, (_, title) in zip(axes, igs, targets):
        draw_board(fig, ax, ig, title)
    draw_bars(axes[2])
    legend(fig, 0.35)
    if not bare:
        fig.suptitle("%s　%s" % (Path(path).parts[-3], label), fontsize=9)
    return save(fig, "ig.png")


def square_lines(ax):
    """A line around every square, as on a shogi board, under the marks drawn on top."""
    for x in (-0.5, 0.5, 1.5, 2.5):
        ax.axvline(x, color="#5a3a1a", lw=0.8, zorder=0.5)
    for y in (-0.5, 0.5, 1.5, 2.5, 3.5):
        ax.axhline(y, color="#5a3a1a", lw=0.8, zorder=0.5)


def attention_grid(paths, block, query, line, style=PAPER, label="", rec=None, head=None, bare=False, marks=False,
                   minus=None):
    """The chosen models whose block `block` is a Transformer, every head, from one square.

    One row per model, one column per head, saved as a PNG to download.
    PAPER draws it as the ResTNet paper does (Fig. 5): each map scaled to [0, 1],
    redder is higher, the query square framed in black as in RATIO. That scaling stretches
    even a nearly even head over the whole range, so each title also gives the
    largest weight as a ratio to the uniform 1/12. RATIO colours that ratio on
    one fixed scale. `head` (0-3) draws that head only, "best" the head of each model
    whose largest weight is the largest; `bare` leaves out the title above the maps and
    writes each piece as one large character, for a figure of the paper; `marks`
    draws the best moves as blue arrows and the model's own move as a dashed black one
    (positions of the complete analysis only). `minus` (an input plane, 10-15) draws, instead of
    the weights, how they change when one piece of that kind is given to the other side: the
    weights × 12 minus those after giving it, blue less, white none, red more, on one scale.
    """
    import tempfile
    import torch
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]

    x, board, hands, black = position_input(line, rec)
    note = ""
    if query == "手番のライオン":
        lion = "L" if black else "l"
        spots = [r * 3 + c for r in range(4) for c in range(3) if board[r][c] == lion]
        q = spots[0] if spots else 0
        note = "" if spots else "（手番のライオンが盤上にないので a4 を表示）"
    else:
        q = SQUARES.index(query)

    panels, lines = [], []
    for path in paths:
        net, diff, layers, heads = attention_net(path)
        name = Path(path).parts[-3]
        if block != ALL_BLOCKS and block not in layers:
            lines.append("%s：第%dブロックは Transformer ブロックではないので表示しない" % (name, block + 1))
            continue
        if diff > 1e-6:
            lines.append("%s：組み立て直しが一致しない（差 %.1e）ので表示しない" % (name, diff))
            continue
        with torch.no_grad():
            table = net.get_attn_table(x)["att_table"]
            if minus is not None:   # one piece of that kind given to the other side (eight pieces kept)
                fewer = x.clone()
                fewer[:, minus] -= 1
                fewer[:, minus + 3 if minus < 13 else minus - 3] += 1
                less = net.get_attn_table(fewer)["att_table"]
                table = [t - u for t, u in zip(table, less)]
        maps = [(b, h, table[layers.index(b)][0, h, q].numpy().reshape(4, 3) * 12)
                for b in (layers if block == ALL_BLOCKS else [block]) for h in range(heads)]
        if head == "best":
            b, h, w = max(maps, key=lambda m: abs(m[2]).max())
            panels.append((name, b, [(h, w)], path))
            continue
        for b in (layers if block == ALL_BLOCKS else [block]):
            panels.append((name, b, [(h, w) for bb, h, w in maps if bb == b and head in (None, h)], path))
    if not panels:
        return None, "\n".join(lines) or "モデルを選んでください"

    top = max(float(abs(w).max()) for _, _, ws, _ in panels for _, w in ws)
    best_moves, own_move = [], {}
    if marks and rec is not None:
        import numpy as np
        import dobutsu_all_agreement as A
        from attention_presets import dobutsu_move
        best_moves = [dobutsu_move(int(a)) for a in np.nonzero(A.bits(rec["best"])[0].numpy())[0]]
        own_move = {p: dobutsu_move(int(A.choose(A.load(p, "cpu"), rec, "cpu")[0])) for p in {pp for _, _, _, pp in panels}}

    def arrow(ax, move, color, dashed):
        draw_move(ax, move, color, dashed, black, bare)
    big = 18 if bare else 8   # a figure of the paper is shrunk to about 25 mm a board, as in the ResTNet paper
    norm = Normalize(1, 12, clip=True)   # the same scale in every figure, as in the paper
    wood_red = LinearSegmentedColormap.from_list("wood_red", ["#f3d9b1", "#c8402a"])   # 盤の色から赤へ
    if minus is not None:   # a change has a sign: blue less, white none, red more, on one fixed scale
        from matplotlib.colors import TwoSlopeNorm
        from xai_analysis import HAND_DIFF_SCALE
        norm = TwoSlopeNorm(vmin=-HAND_DIFF_SCALE, vcenter=0, vmax=HAND_DIFF_SCALE)
        wood_red = LinearSegmentedColormap.from_list("change", ["#2a78d6", "#ffffff", "#c8402a"])
    cols = max(len(ws) for _, _, ws, _ in panels)
    height = 2.8 * len(panels) + 1.0
    fig, axes = plt.subplots(len(panels), cols, figsize=(2.5 * cols + 1, height), squeeze=False)   # room for "RRTRRT" in the titles
    for row, (name, b, ws, path) in zip(axes, panels):
        for col, ax in enumerate(row):
            if col >= len(ws):
                ax.axis("off")
                continue
            h, w = ws[col]
            if style == PAPER and minus is None:
                span = float(w.max() - w.min())
                im = ax.imshow((w - w.min()) / span if span > 0 else w * 0, cmap=wood_red, vmin=0, vmax=1)
            else:
                im = ax.imshow(w, cmap=wood_red, norm=norm)
            ax.add_patch(plt.Rectangle((q % 3 - .5, q // 3 - .5), 1, 1, fill=False, lw=2.5, ec="k"))
            for r in range(4):
                for c in range(3):
                    p = board[r][c]
                    if p != ".":
                        ax.text(c, r, PIECES[p.lower()][0] if bare else PIECES[p.lower()], ha="center", va="center",
                                fontsize=big, rotation=0 if p.isupper() else 180)
            for m in best_moves:
                arrow(ax, m, "#1f5fbf", False)
            if path in own_move:
                arrow(ax, own_move[path], "k", True)
            square_lines(ax)
            ax.set_xticks(range(3))
            ax.set_xticklabels(list("abc"))
            ax.set_yticks(range(4))
            ax.set_yticklabels(["4", "3", "2", "1"])
            ax.tick_params(labelsize=14 if bare else 10)
            gote_drop = not black and any("*" in m for m in best_moves + list(own_move.values()))
            t = attention_net(path)[2].index(b) + 1   # T blocks counted alone, as in the ResTNet paper
            ax.set_title(("%s　第%dTブロック\n第%dヘッド　増 %+.2f／減 %+.2f" % (name, t, h + 1, w.max(), w.min())) if minus is not None
                         else "%s　第%dTブロック\n第%dヘッド　max %.2f" % (name, t, h + 1, w.max()), fontsize=12 if bare else 9,
                         pad=30 if gote_drop else 6)   # a drop by gote comes from above the board
    fig.tight_layout(rect=(0, 0, 1, 1 if bare else 1 - 0.85 / height))   # 上に3行の説明の場所を空ける
    if style != PAPER or minus is not None:
        bar = fig.colorbar(im, ax=axes, shrink=0.8)
        bar.set_label("重み × 12 の差" if minus is not None else "重み × 12", fontsize=14 if bare else 10)
        bar.ax.tick_params(labelsize=14 if bare else 10)
    if best_moves or own_move:   # which arrow is which
        from matplotlib.lines import Line2D
        names = sorted({n for n, _, _, _ in panels})
        fig.legend([Line2D([], [], color="#1f5fbf", lw=2.5), Line2D([], [], color="k", lw=2.5, linestyle="--")],
                   ["最善手", "%sの手" % names[0] if len(names) == 1 else "各行のモデルの手"],
                   loc="lower center", ncol=2, frameon=False, fontsize=13 if bare else 9,
                   bbox_to_anchor=(0.5, -0.06 if bare else -0.02))
    if not bare:
        fig.suptitle("%s\n起点 %s（%s）。逆さの駒が後手。持ち駒　先手：%s　後手：%s%s" %
                     (position_title(label, line) if rec is None else "%s　%s番" % (label, "先手" if black else "後手"),
                      SQUARES[q], "黒枠",
                      hands.get("B", "-"), hands.get("W", "-"),
                      "\n各図を [0, 1] に正規化、赤いほど高い。max は重み × 12" if style == PAPER else ""),
                     fontsize=10)
    name = "block%s_h%s_%s_ply%d_%s%s.png" % ("all" if block == ALL_BLOCKS else block + 1,
                                              "all" if head is None else head if head == "best" else head + 1,
                                              SQUARES[q], len(line),
                                              "paper" if style == PAPER else "ratio",
                                              "" if minus is None else "_give%d" % minus)
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / name
    out.parent.mkdir(exist_ok=True)
    out = str(out)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    lines.insert(0, "%s から。各図の max は重み × 12（1 なら均等、最大は 12：1マスだけに集中）。"
                    "全図の max の最大 %.2f%s" % (SQUARES[q], top, note))
    return out, "\n".join(lines)


def model_policy(model_path, env, player):
    """What this model would play here: every legal move with its probability.

    No search, no noise: the policy head alone, which is what the architecture
    comparison is about. The model is kept after the first load.
    """
    import torch

    if model_path not in _MODELS:
        model = torch.jit.load(model_path, map_location="cpu")
        model.eval()
        _MODELS[model_path] = model
    features = torch.tensor(list(env.get_features())).view(1, CHANNELS, 4, 3)
    with torch.no_grad():
        policy = _MODELS[model_path](features)["policy"][0]
    return {to_their_move(env, a.to_console_string(), player): float(policy[a.get_action_id()])
            for a in env.get_legal_actions()}


def policy_picks(model_path, positions):
    """The legal move with the highest policy at each position, in their notation."""
    import torch

    model = torch.jit.load(model_path, map_location="cpu")
    model.eval()
    picks = []
    for start in range(0, len(positions), 256):
        chunk = positions[start:start + 256]
        batch = torch.tensor([f for f, _, _ in chunk]).view(len(chunk), CHANNELS, 4, 3)
        with torch.no_grad():
            out = model(batch)["policy"]
        picks += [max(legal, key=lambda im: float(out[i][im[0]]))[1]
                  for i, (_, legal, _) in enumerate(chunk)]
    return picks


def judge(model_path, positions):
    """The network's own move at each position, with no search and no noise.

    Returns the strict agreement, how often a won position stayed won, and how
    far down the line the network went before its first miss.
    """
    strict = kept = winning = 0
    first_miss = None
    picks = policy_picks(model_path, positions)
    for ply, ((features, legal, values), pick) in enumerate(zip(positions, picks)):
        value, distance = next((v, d) for _, m, v, d in values if m == pick)
        best = min(order(v, d) for _, _, v, d in values)
        if order(value, distance) == best:
            strict += 1
        elif first_miss is None:
            first_miss = ply
        # the mover is winning when the best move leaves the opponent lost
        if best[0] < 0:
            winning += 1
            kept += value < 0
    return {"strict": strict, "total": len(positions), "kept": kept,
            "winning": winning,
            "reproduced": len(positions) if first_miss is None else first_miss}


_POSITIONS = {}


def position_set(branched):
    """The test positions, built once and kept."""
    key = "branched" if branched else "line"
    if key not in _POSITIONS:
        _POSITIONS[key] = branched_line() if branched else optimal_line()
    return _POSITIONS[key]


def checkpoints():
    """The newest checkpoint of every run this build can read."""
    import torch

    found = []
    for d in sorted(Path("models").rglob("model")):
        newest = max(d.glob("weight_iter_*.pt"),
                     key=lambda q: int(re.findall(r"\d+", q.name)[0]), default=None)
        if newest is None:
            continue
        try:
            if torch.jit.load(str(newest), map_location="cpu").get_num_input_channels() == CHANNELS:
                found.append(str(newest))
        except Exception:
            pass
    return found


def self_check():
    """The known answer for the initial position, checked before counting anything.

    Tanaka's published sample gives -1(77) with three best moves. If this does not
    come back, something between our board and their table is broken and no number
    from here means anything.
    """
    env = env_py.Env()
    env.reset()
    _, position, values, _ = check_state(env)
    if not values:
        return False, "初期局面で checkState が手の一覧を出さない"
    best = min(order(value, distance) for _, _, value, distance in values)
    got = {move for _, move, value, distance in values if order(value, distance) == best}
    ok = position == (-1, 77) and got == {"+C4C3KI", "+B4C3LI", "+B4A3LI"}
    return ok, f"初期局面 {position[0]}({position[1]})  最善 {' '.join(sorted(got))}" \
        + ("" if ok else "  ← 既知の正解と違う")


def count_games(run, name, first, last):
    """Per position: was the move in the record one the analysis calls best?

    checkState is called on every position, so nothing is skipped. The counts of
    the positions that cannot be judged are returned with the rows.
    """
    rows, counts, agreed = [], {"判定した": 0, "一覧なし": 0, "表にない": 0}, 0
    for index in range(first, last + 1):
        moves, _ = load_game(run, name, index)
        env = env_py.Env()
        env.reset()
        for ply, move in enumerate(moves):
            _, position, values, _ = check_state(env)
            player = "B" if ply % 2 == 0 else "W"
            their = to_their_move(env, move, player)
            if position is None:
                counts["表にない"] += 1
            elif not values:
                counts["一覧なし"] += 1
            else:
                best = min(order(value, distance) for _, _, value, distance in values)
                value, distance = next((v, d) for _, m, v, d in values if m == their)
                ok = order(value, distance) == best
                counts["判定した"] += 1
                agreed += ok
                rows.append([run, name, index, ply, "先手" if player == "B" else "後手",
                             their, f"{value}({distance})", "◯" if ok else "×",
                             " ".join(m for _, m, v, d in values if order(v, d) == best)])
            env.act(next(a for a in env.get_legal_actions()
                         if a.to_console_string() == move))
    return rows, counts, agreed


def judge_by_checkcsa(run, name, first, last):
    """The same judgement through checkcsa, keyed by (game, ply), as a cross-check.

    It takes a whole game in one call but does not report every position, so its
    blocks are matched to the moves of the game by the move played, never counted.
    """
    judged = {}
    for index in range(first, last + 1):
        moves, _ = load_game(run, name, index)
        env = env_py.Env()
        env.reset()
        line = []
        for ply, move in enumerate(moves):
            line.append(to_their_move(env, move, "B" if ply % 2 == 0 else "W"))
            env.act(next(a for a in env.get_legal_actions()
                         if a.to_console_string() == move))
        with tempfile.NamedTemporaryFile("w", suffix=".csa") as f:
            f.write("\n".join(line[:-1]) + "\n")   # their engine throws on the last
            f.flush()
            out = subprocess.run(["./checkcsa", f.name], cwd=str(TABLEBASE),
                                 capture_output=True, text=True).stderr

        values, ply = {}, 0
        for row in out.splitlines():
            m = re.match(r"^\d+ : ([+-]\w{6}),wl=(-?\d+)\((\d+)\)", row)
            if m:
                values[m.group(1)] = (int(m.group(2)), int(m.group(3)))
            elif row.startswith("Move : ") and values:
                played = row[len("Move : "):].strip()
                while ply < len(line) and line[ply] != played:
                    ply += 1          # they skip a position now and then
                if ply < len(line) and all(-1 <= v <= 1 for v, _ in values.values()):
                    judged[(index, ply)] = \
                        order(*values[played]) == min(order(*v) for v in values.values())
                    ply += 1
                values = {}
    return judged


def main():
    env_py.init("")
    import gradio as gr

    runs = sgf_runs()

    def model_text(env, ply, path):
        """The model's own move here, beside the analysis's verdict."""
        if not path:
            return "モデルを選ぶと、この局面で選ぶ手が出ます"
        if env.is_terminal():
            return "終局"
        _, position, values, _ = check_state(env)
        if position is None or not values:
            return "この局面は完全解析の表にない、または手の一覧が出ない局面です"
        player = "B" if ply % 2 == 0 else "W"
        probs = model_policy(path, env, player)
        best = min(order(v, d) for _, _, v, d in values)
        best_moves = {m for _, m, v, d in values if order(v, d) == best}
        pick = max(probs, key=probs.get)
        rows = [f"{path}", ""]
        for move, prob in sorted(probs.items(), key=lambda kv: -kv[1]):
            mark = " ★最善" if move in best_moves else ""
            mark += " ←モデルの選択" if move == pick else ""
            rows.append("%s %-6s確率 %.3f%s" % (move, JP.get(move[5:7], ""), prob, mark))
        verdict = "一致" if pick in best_moves else "不一致"
        rows += ["", f"モデルの選択 {pick} は完全解析の最善手と{verdict}"]
        return "\n".join(rows)

    def render(st, path=None):
        st = {k: v for k, v in st.items() if k != "record"}   # a preset record is only shown below
        line = st["moves"][: st["ply"]]
        played = st["moves"][st["ply"]] if st["ply"] < len(st["moves"]) else None
        env, text, choices, out = analyse(line, played)
        head = f"{st['label']}\n{st['ply']}手目  {'先手番' if st['ply'] % 2 == 0 else '後手番'}\n\n"
        return (st, head + text,
                gr.update(choices=choices, value=choices[0][1] if choices else None), out,
                gr.update(maximum=max(len(st["moves"]), 1), value=st["ply"]),
                model_text(env, st["ply"], path))

    def files_of(run):
        """The newest iteration first in the list, since that is the trained one."""
        names = sgf_files(run) if run else []
        return gr.update(choices=names, value=names[-1] if names else None)

    def load(run, name, index, path):
        if not run or not name:
            return render({"moves": [], "ply": 0,
                           "label": "構成と sgf ファイルを選んでください"}, path)
        moves, label = load_game(run, name, int(index))
        return render({"moves": moves, "ply": 0, "label": label}, path)

    def play(st, move, path):
        if not move:
            return render(st, path)
        label = st["label"] if "手で変更" in st["label"] else st["label"] + "（以降は手で変更）"
        return render({"moves": st["moves"][: st["ply"]] + [move],
                       "ply": st["ply"] + 1, "label": label}, path)

    with gr.Blocks(title="どうぶつしょうぎ 完全解析") as app:
        gr.Markdown("# どうぶつしょうぎ：完全解析（田中哲朗先生, 2009）\n"
                    "`checkState` の出力をそのまま表示する。手の値 `1(76)` は"
                    "**指した側の負け、77手粘れる**の意味（表の値は手番視点で、"
                    "手の値は指した後の手番＝相手から見たもの）。")
        st = gr.State({"moves": [], "ply": 0, "label": "初期局面から手で進める"})
        with gr.Row():
            run = gr.Dropdown(runs, value=runs[0] if runs else None, label="構成")
            start = sgf_files(runs[0]) if runs else []
            name = gr.Dropdown(start, value=start[-1] if start else None,
                               label="sgfファイル（iteration）")
            index = gr.Number(value=1, precision=0, label="何局目")
            read = gr.Button("棋譜を読み込む", variant="primary")
        ply = gr.Slider(0, 1, value=0, step=1, label="何手目")
        with gr.Row():
            move = gr.Dropdown([], label="手を選んで進める", scale=3)
            go = gr.Button("指す")
            reset = gr.Button("初期局面")
        position = gr.Textbox(label="出典・局面・全合法手", lines=24)
        with gr.Row():
            one_model = gr.Dropdown(checkpoints(), value=None, label="モデルの手（選ぶと即座に計算）")
        model_move = gr.Textbox(label="この局面でモデルが選ぶ手", lines=10)

        gr.Markdown("### Attention Map\n"
                    "上の盤面と同じ局面について、選んだモデル・ブロックの全ヘッドを並べる。"
                    "1枚の図は、起点のマスから盤上の各マスに向けた Attention（ResTNet 論文 §4.3 と同じ）。"
                    "Attention は盤面だけから計算され、局面が変われば変わる。")
        with gr.Row():
            a_kind = gr.Radio(list(PRESET_KINDS), value="すべて", label="問題の局面の種類", scale=4)
            a_prev = gr.Button("← 前の局面", scale=1)
            a_next = gr.Button("次の局面 →", scale=1)
        a_preset = gr.Dropdown(preset_labels("すべて"), value=None, label="問題の局面（プリセット）")
        a_pos = gr.Markdown("")
        _archs = attention_arch_choices()
        _first = [p for n, p in _archs if n in ("RRTRRT", "6T", "5R1T")] or [p for _, p in _archs[:1]]
        with gr.Row():
            a_models = gr.Dropdown(_archs, value=_first, multiselect=True, scale=3,
                                   label="モデル（各構成の最新。複数選ぶと縦に並ぶ）")
            a_layer = gr.Dropdown(attention_layer_choices(_first), value=ALL_BLOCKS if _first else None, scale=2,
                                  label="ブロック（入力側から数えた位置）")
            a_query = gr.Dropdown(["手番のライオン"] + SQUARES, value="手番のライオン", scale=1,
                                  label="起点のマス（黒枠）")
        with gr.Row():
            a_style = gr.Radio([PAPER, RATIO], value=PAPER, label="色の付け方", scale=3)
            a_head = gr.Dropdown(["全ヘッド", "ヘッド1", "ヘッド2", "ヘッド3", "ヘッド4", "最も偏ったヘッド"], value="全ヘッド",
                                 scale=1, label="ヘッド（1つだけ選ぶとそのヘッドだけ描く。最も偏ったヘッド＝選んだブロックの中で最大の比が最も大きいヘッド、モデルごと）")
            a_marks = gr.Checkbox(value=False, scale=1, label="盤上の矢印（青：最善手、黒の点線：モデルの手。完全解析の局面のみ）")
            a_minus = gr.Dropdown(["使わない", "手番側のキリン", "手番側のゾウ", "手番側のヒヨコ", "相手のキリン", "相手のゾウ", "相手のヒヨコ"], value="使わない", scale=1,
                                  label="持ち駒の Attention の差（持っているときの重み×12 − 1枚相手に渡した後の重み×12。赤＝持っていると多い、青＝少ない）")
            a_bare = gr.Checkbox(value=False, scale=1, label="論文用（図の上の説明を付けない）")
            a_hand_move = gr.Radio(["モデルの手", "最善手"], value="モデルの手", scale=2,
                                   label="持ち駒の寄与を見る手（最善手が複数なら駒打ちを優先）")
        a_plot = gr.Image(label="Attention Map（右上のボタンで PNG をダウンロード）", type="filepath")
        a_note = gr.Textbox(label="数値", lines=3)
        a_hand = gr.Image(label="持ち駒の寄与（完全解析の局面のプリセット。最初に選んだモデル。右上のボタンで PNG をダウンロード）",
                          type="filepath")
        a_drop = gr.Image(label="持ち駒を打つ確率の盤（手番側の持ち駒の種類ごと。○ 最善の打つ先。最初に選んだモデル）",
                          type="filepath")
        a_ig = gr.Image(label="Integrated Gradients（赤＝出力を上げる駒、青＝下げる駒。持ち駒は棒。完全解析の局面。最初に選んだモデル、「持ち駒の寄与を見る手」と同じ手）",
                        type="filepath")
        with gr.Row():   # the same IG as three figures, each one column of the paper wide
            a_ig_v = gr.Image(label="IG：value の盤", type="filepath")
            a_ig_p = gr.Image(label="IG：手の確率の盤", type="filepath")
            a_ig_b = gr.Image(label="IG：持ち駒の棒", type="filepath")
        with gr.Row():
            a_save = gr.Button("この図を候補に保存（data/attention_candidates/）", scale=1)
            a_saved = gr.Textbox(label="保存", lines=1, scale=3)
        a_table = gr.Dataframe(
            headers=["構成", "ブロック", "ヘッド", "最大の比", "起点", "注目先"], interactive=False,
            label="参考：この局面での全モデル・全ヘッドの偏り（最大の比＝重み×12 の最大。1 なら均等、"
                  "12 なら1マスに集中。大きい順。行をクリックすると、そのモデル・ブロック・起点を上の欄に入れる）")
        gr.Markdown("### 6T の第5ブロック・ヘッド4が何を見ているか（無作為な局面の集計、CPU で約1分）")
        h_run = gr.Button("集計を描く")
        g_run = gr.Button("一致率の図を描く（完全解析の全局面、11 構成）")
        b_run = gr.Button("ブロックごとの重みの偏りと IG との重なりを計算する（CPU で数分）")
        b_note = gr.Textbox(label="ブロックごとの重みの偏りと IG との重なり", lines=6)
        h_plot = gr.Image(label="集計の図（右上のボタンで PNG をダウンロード）", type="filepath")
        h_note = gr.Textbox(label="数値", lines=3)
        g_plot = gr.Image(label="一致率の図（右上のボタンで PNG をダウンロード）", type="filepath")
        g_note = gr.Textbox(label="数値", lines=2)
        gr.Markdown("### 最善手の行き先への Attention（最善手順の全局面、全構成・全ブロック・全ヘッド）\n"
                    "起点＝最善手で動かす駒のマス、行き先＝その手で駒が移るマス（駒を取る手も同じマス）。"
                    "上で選んだ局面とは関係なく、最善手順の全局面で計算する。")
        v_run = gr.Button("計算する")
        v_note = gr.Textbox(label="対象", lines=2)
        v_table = gr.Dataframe(
            headers=["構成", "ブロック", "ヘッド", "行き先への比（平均）", "最小", "最大"], interactive=False,
            label="行き先への値＝重み × 12（1 なら向いていない）。平均の大きい順。"
                  "行をクリックすると、そのヘッドの局面ごとの値が下に出る")
        v_fig_run = gr.Button("全構成・全ヘッドの平均を点の図にする（論文のヘッドの選び方の図）")
        v_fig = gr.Image(label="構成ごとに全ヘッドの平均（点線は均等の 1）", type="filepath")
        v_head = gr.State(None)
        v_detail = gr.Dataframe(
            headers=["何手目まで指した局面", "手番", "最善手", "起点", "行き先", "行き先への比"], interactive=False,
            label="選んだヘッドの、最善手ごとの値（大きい順）。行をクリックすると、その局面を上の盤面に出し、"
                  "Attention Map の欄にそのモデル・ブロック・起点を入れる（図は上の Attention Map に出る）")
        with gr.Accordion("最善手で終局までの全手順（checkState の全出力）", open=False):
            raw = gr.Textbox(label="", lines=30)

        gr.Markdown("---\n## モデルの一致率（完全解析の最善手順の上で、方策の argmax を比べる）\n"
                    "探索なし・ノイズなし・抽選なし。同じモデルなら何度測っても同じ数字になる。")
        found = checkpoints()
        with gr.Row():
            picked = gr.Dropdown(found, value=found, multiselect=True, label="モデル（20チャンネルのみ）")
            branched = gr.Radio(["最善手順のみ（77局面）", "分岐込み（約4200局面）"],
                                value="最善手順のみ（77局面）", label="局面の集合")
            measure = gr.Button("測定する", variant="primary")
        model_result = gr.Textbox(label="結果", lines=4)
        model_table = gr.Dataframe(
            headers=["モデル", "最善手を選んだ割合", "勝ちの局面で勝ちの手を選んだ割合", "判定した局面"],
            column_count=(4, "fixed"), wrap=True,
            label="最善手を選んだ割合＝方策が最大の確率を与えた手が、勝敗と決着までの手数の両方で最善の手"
                  "（複数あればどれでも）だった局面の割合。勝ちの局面で勝ちの手を選んだ割合＝手番側が勝てる局面のうち、"
                  "選んだ手の後も勝てる（手数は問わない）局面の割合")

        def run_models(paths, which):
            if not paths:
                return "モデルを選んでください", []
            ok, checked = self_check()
            if not ok:
                return f"自己確認に失敗: {checked}", []
            positions = position_set(which.startswith("分岐"))
            rows = []
            for path in paths:
                r = judge(path, positions)
                rows.append([path, round(r["strict"] / r["total"], 3),
                             round(r["kept"] / r["winning"], 3) if r["winning"] else 0,
                             r["total"]])
            rows.sort(key=lambda row: -row[1])
            return (f"{checked}\n局面 {len(positions)}（勝ち {sum(1 for _, _, v in positions if min(order(a, b) for _, _, a, b in v)[0] < 0)}）"
                    f"\n最善手を選んだ割合の高い順に並べた"), rows

        measure.click(run_models, [picked, branched], [model_result, model_table])

        gr.Markdown("---\n## 棋譜の手の一致率（抽選とノイズ込みの手を測るので、強さの指標にはならない）")
        ok, checked = self_check()
        gr.Markdown(f"起動時の自己確認：{checked}")
        with gr.Row():
            runs_m = gr.Dropdown(runs, value=runs[:1], multiselect=True, label="構成")
            name_m = gr.Dropdown(start, value=start[-1] if start else None,
                                 label="sgfファイル（iteration）")
            first = gr.Number(value=1, precision=0, label="最初の局")
            last = gr.Number(value=50, precision=0, label="最後の局")
            tally = gr.Button("集計する", variant="primary", interactive=ok)
        result = gr.Textbox(label="一致率・分母の内訳・検算", lines=10)
        table = gr.Dataframe(headers=COLUMNS, label="1局面ごと（行をクリックすると上の盤面に出る）",
                             column_count=(len(COLUMNS), "fixed"), wrap=True)

        def count(chosen_runs, name_value, first_value, last_value):
            if not chosen_runs or not name_value:
                return "構成と sgf ファイルを選んでください", []
            first_value, last_value = int(first_value), int(last_value)
            rows, text = [], []
            for run_value in chosen_runs:
                part, counts, agreed = count_games(run_value, name_value, first_value, last_value)
                other = judge_by_checkcsa(run_value, name_value, first_value, last_value)
                rows += part
                judged = counts["判定した"]
                rate = format(agreed / judged, ".3f") if judged else "-"
                # the two programs must judge the positions they share the same way
                shared = [r for r in part if (r[2], r[3]) in other]
                differ = [r for r in shared if (r[7] == "◯") != other[(r[2], r[3])]]
                text.append(
                    f"{run_value}/sgf/{name_value}  第{first_value}〜{last_value}局\n"
                    f"  一致率 {rate}  ({agreed}/{judged})\n"
                    f"  分母の内訳  判定した {judged} / 一覧なし {counts['一覧なし']} "
                    f"/ 表にない {counts['表にない']}\n"
                    f"  検算（checkcsa と同じ局面で比較）  共通 {len(shared)}局面、"
                    f"判定が違った {len(differ)}局面")
            AGREEMENT.parent.mkdir(parents=True, exist_ok=True)
            with open(AGREEMENT, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(COLUMNS)
                writer.writerows(rows)
            return "\n".join(text) + f"\n\n{AGREEMENT} に保存した（{len(rows)}行）", rows

        def pick(data, path, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            moves, label = load_game(row[0], row[1], int(row[2]))
            return render({"moves": moves, "ply": int(row[3]), "label": label}, path)

        out = [st, position, move, raw, ply, model_move]

        def pick_layer(data, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            if not row[1]:
                return gr.update(), gr.update(), gr.update()
            path = dict(attention_arch_choices())[row[0]]
            block = int(re.findall(r"第(\d+)ブロック", row[1])[0]) - 1
            return [path], gr.update(choices=attention_layer_choices([path]), value=block), row[4]

        def layers_for(paths, block):
            choices = attention_layer_choices(paths)
            keep = block if any(v == block for _, v in choices) else (choices[0][1] if choices else None)
            return gr.update(choices=choices, value=keep)

        def show_attention(st, paths, block, query, style, head="全ヘッド", bare=False, hand_move="モデルの手", marks=False,
                           minus="使わない"):
            line = st["moves"][: st["ply"]]
            rec = preset_record(st["record"]) if "record" in st else None
            pos = "**表示中の局面：** " + (st["label"] if rec is not None else position_title(st["label"], line))
            if not paths:
                return None, "モデルを選んでください", pos, None, None, None, None, None, None
            if block is None:
                return None, "ブロックを選んでください", pos, None, None, None, None, None, None
            # a hand piece has no square: its contribution to the value and to one move's policy, as for 9x9
            hand = drop = ig = None
            ig_parts = [None] * 3   # value, the move's probability, the bars, each one column wide
            if rec is not None:
                import numpy as np
                import dobutsu_all_agreement as A
                best = np.nonzero(A.bits(rec["best"])[0].numpy())[0]
                move = (max(best, key=lambda a: a >= 96) if hand_move == "最善手" and len(best)
                        else int(A.choose(A.load(paths[0], "cpu"), rec, "cpu")[0]))
                hand = hand_figure(paths[0], rec, int(move), st["label"], bare)
                drop = drop_figure(paths[0], rec, st["label"], bare)
                ig = ig_figure(paths[0], rec, int(move), st["label"], bare)
                ig_parts = ig_figure(paths[0], rec, int(move), st["label"], bare, parts=True)
            h = None if head == "全ヘッド" else "best" if head == "最も偏ったヘッド" else int(head[-1]) - 1
            plane = None if minus == "使わない" else ["使わない", "手番側のキリン", "手番側のゾウ", "手番側のヒヨコ", "相手のキリン", "相手のゾウ", "相手のヒヨコ"].index(minus) + 9
            return (*attention_grid(paths, int(block), query, line, style, st["label"], rec, h, bare, marks, plane),
                    pos, hand, drop, ig, *ig_parts)

        def summary(st):
            return attention_summary(st["moves"][: st["ply"]],
                                     preset_record(st["record"]) if "record" in st else None)

        def pick_preset(label, path):
            kind, value = presets()[label]
            if kind == "line":
                return (*render({"moves": presets()["(line)"], "ply": value, "label": "完全解析の最善手順"}, path),
                        gr.update())
            _, board, hands, black = position_input([], preset_record(value))
            text = "\n".join([label, "先手番" if black else "後手番", "後手の持ち駒：" + hands["W"]]
                             + [" ".join(r) for r in board] + ["先手の持ち駒：" + hands["B"],
                                                               "（完全解析の局面。大文字が先手の駒）"])
            q = preset_move(value)[0]   # a drop: start from the square dropped on
            return ({"moves": [], "ply": 0, "label": label, "record": value}, text,
                    gr.update(choices=[], value=None), "", gr.update(), "",
                    gr.update(value=SQUARES[q]) if q >= 0 else gr.update())

        a_in = [st, a_models, a_layer, a_query, a_style, a_head, a_bare, a_hand_move, a_marks, a_minus]
        a_out = [a_plot, a_note, a_pos, a_hand, a_drop, a_ig, a_ig_v, a_ig_p, a_ig_b]
        a_table.select(pick_layer, a_table, [a_models, a_layer, a_query])
        a_preset.change(pick_preset, [a_preset, one_model], out + [a_query]).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        a_kind.change(lambda k: gr.update(choices=preset_labels(k), value=None), a_kind, a_preset)
        a_prev.click(lambda k, label: step_preset(k, label, -1), [a_kind, a_preset], a_preset)
        a_next.click(lambda k, label: step_preset(k, label, 1), [a_kind, a_preset], a_preset)
        a_save.click(lambda st, paths, block, query, style, head, plot, hand, drop: save_candidate(
            "dobutsu", st["label"], [Path(p).parts[-3] for p in paths or []], block, query, style, [plot, hand, drop], head),
            [st, a_models, a_layer, a_query, a_style, a_head, a_plot, a_hand, a_drop], a_saved)
        v_run.click(attention_validity, None, [v_note, v_table])
        v_fig_run.click(validity_figure, None, [v_fig, v_note])
        h_run.click(head_statistics, None, [h_plot, h_note])
        g_run.click(agreement_figure, None, [g_plot, g_note])
        b_run.click(block_statistics, None, b_note)

        def pick_head(data, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            block = int(re.findall(r"第(\d+)ブロック", row[1])[0]) - 1
            head = int(re.findall(r"\d+", row[2])[0]) - 1
            return (row[0], block, head), validity_detail(row[0], block, head)

        def pick_position(chosen, data, path, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            name, block, _ = chosen
            model = dict(attention_arch_choices())[name]
            line = validity_moves()[2]
            st = {"moves": line, "ply": int(row[0]), "label": "完全解析の最善手順"}
            return (*render(st, path), [model],
                    gr.update(choices=attention_layer_choices([model]), value=block), row[3])

        v_table.select(pick_head, v_table, [v_head, v_detail])
        v_detail.select(pick_position, [v_head, v_detail, one_model], out + [a_models, a_layer, a_query]).then(
            show_attention, a_in, a_out)
        a_models.change(layers_for, [a_models, a_layer], a_layer).then(show_attention, a_in, a_out)
        for c in (a_layer, a_query, a_style, a_head, a_bare, a_hand_move, a_marks, a_minus):
            c.change(show_attention, a_in, a_out)
        app.load(layers_for, [a_models, a_layer], a_layer).then(show_attention, a_in, a_out)
        tally.click(count, [runs_m, name_m, first, last], [result, table])
        table.select(pick, [table, one_model], out).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        app.load(render, [st, one_model], out).then(
            summary, st, a_table)
        run.change(files_of, run, name)
        runs_m.change(lambda r: files_of(r[0] if r else None), runs_m, name_m)
        read.click(load, [run, name, index, one_model], out).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        ply.release(lambda s, p, m: render({**s, "ply": int(p)}, m), [st, ply, one_model], out).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        go.click(play, [st, move, one_model], out).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        one_model.change(render, [st, one_model], out)
        reset.click(lambda m: render({"moves": [], "ply": 0,
                                      "label": "初期局面から手で進める"}, m), one_model, out).then(show_attention, a_in, a_out).then(
            summary, st, a_table)

    app.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
