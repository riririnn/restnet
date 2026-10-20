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
                rows.append([name, "第%d層" % (i + 1), "ヘッド%d" % (h + 1),
                             round(sum(r) / len(r), 3), round(min(r), 3), round(max(r), 3)])
    rows.sort(key=lambda r: -r[3])
    text = ("最善手順の %d 局面（最善手がすべて駒打ちの %d 局面を除く）、判定した手 %d 個。"
            "値は「動かす駒のマス → 行き先のマス」の重み ÷ 均等値 1/12。1 なら向いていない。"
            "初回は全モデルの読み込みに数秒かかる") % (len(positions), dropped, len(pairs))
    return "\n".join([text] + notes), rows


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
                "6T だけ最善手": "6Tだけ", "6R だけ最善手": "6Rだけ", "最善手が駒打ち": "最善手が駒打ち"}


def preset_labels(kind):
    return [k for k in presets() if k != "(line)" and k.startswith(PRESET_KINDS[kind])]


def step_preset(kind, label, d):
    """The preset before (d=-1) or after (d=1) this one, in the chosen kind."""
    labels = preset_labels(kind)
    if not labels:
        return None
    i = labels.index(label) if label in labels else (-1 if d > 0 else 0)
    return labels[(i + d) % len(labels)]


def save_candidate(game, label, models, block, query, style, files):
    """Copy the figures shown to data/attention_candidates/ and note what they show
    in data/attention_selected.tsv, for the paper's figures later."""
    import datetime
    import shutil
    out = Path("data/attention_candidates")
    out.mkdir(parents=True, exist_ok=True)
    n = len(list(out.glob("%s_*.png" % game))) + 1
    saved = []
    for k, f in enumerate(x for x in files if x):
        dst = out / ("%s_%03d%s.png" % (game, n, "" if k == 0 else "_hand"))
        shutil.copy(f, dst)
        saved.append(str(dst))
    if not saved:
        return "保存する図がない"
    layer = "all" if block == ALL_BLOCKS else str(block + 1 if isinstance(block, int) else block)
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
    """How much the value, and the policy of `action`, drop when one kind of hand piece
    is taken out of the input (its plane set to 0), as xai_analysis.hand_piece_contribution
    does for 9x9. Shape (value/policy, own/opponent, giraffe/elephant/chick); the own
    pieces are planes 10-12, the opponent's 13-15. A piece not held stays 0."""
    import numpy as np
    import torch
    model = torch.jit.load(path, map_location="cpu")
    model.eval()
    out = np.zeros((2, 2, 3))
    with torch.no_grad():
        base = model(x)
        for side in range(2):
            for k in range(3):
                ch = 10 + 3 * side + k
                if float(x[0, ch, 0, 0]) <= 0:
                    continue
                masked = x.clone()
                masked[:, ch] = 0
                o = model(masked)
                out[0, side, k] = float(base["value"]) - float(o["value"])
                out[1, side, k] = float(base["policy"][0, action]) - float(o["policy"][0, action])
    return out


def hand_figure(path, rec, action, label):
    """Bar chart of hand_contribution beside the Attention Map; a PNG path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams["font.family"] = ["IPAMincho", "DejaVu Sans"]
    c = hand_contribution(path, position_input([], rec)[0], action)
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
    x = np.arange(3)
    for ax, values, title in zip(axes, c, ("value への寄与", "policy への寄与（%s）" % label.split()[-1])):
        ax.bar(x - 0.19, values[0], 0.38, label="手番側の持ち駒", color="#D4A96A", edgecolor="#3a2000")
        ax.bar(x + 0.19, values[1], 0.38, label="相手の持ち駒", color="#4a6fa5", edgecolor="#1a2a45")
        ax.axhline(0, color="#666", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(["キリン", "ゾウ", "ヒヨコ"])
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=7)
    axes[0].set_ylabel("その持ち駒の入力を 0 にしたときの下がり方", fontsize=7)
    fig.suptitle("%s　%s" % (Path(path).parts[-3], label), fontsize=9)
    fig.tight_layout()
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / "hand.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)


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
                rows.append([name, "T%d（第%d層）" % (k + 1, i + 1), "ヘッド%d" % (h + 1),
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
    return every + [("第%d層（選んだうち %d 構成が Transformer）" % (i + 1, n), i) for i, n in sorted(count.items())]


PAPER = "論文と同じ（各図を [0, 1] に正規化、赤いほど高い）"
RATIO = "均等値 1/12 を 1 とした比（白＝均等、赤＝多い、青＝少ない）"
PIECES = {"l": "ライオン", "g": "キリン", "e": "ゾウ", "c": "ヒヨコ", "h": "ニワトリ"}


def position_title(label, line):
    """Where this position comes from, in words."""
    last = "直前の手 %s" % line[-1] if line else "初期局面"
    return "%s　%d手目まで指した局面（%s）　%s番" % (label, len(line), last, "先手" if len(line) % 2 == 0 else "後手")


def attention_grid(paths, block, query, line, style=PAPER, label="", rec=None):
    """The chosen models whose block `block` is a Transformer, every head, from one square.

    One row per model, one column per head, saved as a PNG to download.
    PAPER draws it as the ResTNet paper does (Fig. 5): each map scaled to [0, 1],
    redder is higher, the query square marked in green. That scaling stretches
    even a nearly even head over the whole range, so each title also gives the
    largest weight as a ratio to the uniform 1/12. RATIO colours that ratio on
    one fixed scale.
    """
    import tempfile
    import torch
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
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
            lines.append("%s：第%d層は Transformer ではないので表示しない" % (name, block + 1))
            continue
        if diff > 1e-6:
            lines.append("%s：組み立て直しが一致しない（差 %.1e）ので表示しない" % (name, diff))
            continue
        with torch.no_grad():
            table = net.get_attn_table(x)["att_table"]
        for b in (layers if block == ALL_BLOCKS else [block]):
            att = table[layers.index(b)]
            panels.append((name, b, [att[0, h, q].numpy().reshape(4, 3) * 12 for h in range(heads)]))
    if not panels:
        return None, "\n".join(lines) or "モデルを選んでください"

    top = max(float(w.max()) for _, _, ws in panels for w in ws)
    norm = TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=max(4.5, top))
    wood_red = LinearSegmentedColormap.from_list("wood_red", ["#f3d9b1", "#c8402a"])   # 盤の色から赤へ
    cols = max(len(ws) for _, _, ws in panels)
    height = 2.8 * len(panels) + 1.0
    fig, axes = plt.subplots(len(panels), cols, figsize=(2.2 * cols + 1, height), squeeze=False)
    for row, (name, b, ws) in zip(axes, panels):
        for h, ax in enumerate(row):
            if h >= len(ws):
                ax.axis("off")
                continue
            if style == PAPER:
                w = ws[h]
                span = float(w.max() - w.min())
                im = ax.imshow((w - w.min()) / span if span > 0 else w * 0, cmap=wood_red, vmin=0, vmax=1)
                ax.plot(q % 3, q // 3 + 0.36, "o", color="#00b050", ms=8)
            else:
                im = ax.imshow(ws[h], cmap="RdBu_r", norm=norm)
                ax.add_patch(plt.Rectangle((q % 3 - .5, q // 3 - .5), 1, 1, fill=False, lw=2.5, ec="k"))
            for r in range(4):
                for c in range(3):
                    p = board[r][c]
                    if p != ".":
                        ax.text(c, r, PIECES[p.lower()], ha="center", va="center", fontsize=8,
                                rotation=0 if p.isupper() else 180)
            ax.set_xticks(range(3))
            ax.set_xticklabels(list("abc"))
            ax.set_yticks(range(4))
            ax.set_yticklabels(["4", "3", "2", "1"])
            ax.set_title("%s　第%d層　ヘッド%d\nmax %.2f" % (name, b + 1, h + 1, ws[h].max()), fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.85 / height))   # 上に3行の説明の場所を空ける
    if style != PAPER:
        fig.colorbar(im, ax=axes, shrink=0.8, label="重み ÷ 均等値 1/12")
    fig.suptitle("%s\n起点 %s（%s）。逆さの駒が後手。持ち駒　先手：%s　後手：%s%s" %
                 (position_title(label, line) if rec is None else "%s　%s番" % (label, "先手" if black else "後手"),
                  SQUARES[q], "緑の点" if style == PAPER else "黒枠",
                  hands.get("B", "-"), hands.get("W", "-"),
                  "\n各図を [0, 1] に正規化、赤いほど高い。max は重み÷均等値 1/12" if style == PAPER else ""),
                 fontsize=10)
    name = "block%s_%s_ply%d_%s.png" % ("all" if block == ALL_BLOCKS else block + 1, SQUARES[q], len(line),
                                        "paper" if style == PAPER else "ratio")
    out = Path(tempfile.gettempdir()) / "dobutsu_attention" / name
    out.parent.mkdir(exist_ok=True)
    out = str(out)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    lines.insert(0, "%s から。各図の max は重み÷均等値 1/12（1 なら均等、最大は 12：1マスだけに集中）。"
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
                    "上の盤面と同じ局面について、選んだモデル・層の全ヘッドを並べる。"
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
                                  label="層（Transformer ブロックの位置）")
            a_query = gr.Dropdown(["手番のライオン"] + SQUARES, value="手番のライオン", scale=1,
                                  label="起点のマス（緑の点）")
        a_style = gr.Radio([PAPER, RATIO], value=PAPER, label="色の付け方")
        a_plot = gr.Image(label="Attention Map（右上のボタンで PNG をダウンロード）", type="filepath")
        a_note = gr.Textbox(label="数値", lines=3)
        a_hand = gr.Image(label="持ち駒の寄与（駒打ちの局面のプリセットだけ。最初に選んだモデル）", type="filepath")
        with gr.Row():
            a_save = gr.Button("この図を候補に保存（data/attention_candidates/）", scale=1)
            a_saved = gr.Textbox(label="保存", lines=1, scale=3)
        a_table = gr.Dataframe(
            headers=["構成", "レイヤー", "ヘッド", "最大の比", "起点", "注目先"], interactive=False,
            label="参考：この局面での全モデル・全ヘッドの偏り（最大の比＝重み×12 の最大。1 なら均等、"
                  "12 なら1マスに集中。大きい順。行をクリックすると、そのモデル・層・起点を上の欄に入れる）")
        gr.Markdown("### 最善手の行き先への Attention（最善手順の全局面、全構成・全ブロック・全ヘッド）\n"
                    "起点＝最善手で動かす駒のマス、行き先＝その手で駒が移るマス（駒を取る手も同じマス）。"
                    "上で選んだ局面とは関係なく、最善手順の全局面で計算する。")
        v_run = gr.Button("計算する")
        v_note = gr.Textbox(label="対象", lines=2)
        v_table = gr.Dataframe(
            headers=["構成", "レイヤー", "ヘッド", "行き先への比（平均）", "最小", "最大"], interactive=False,
            label="行き先への比＝重み ÷ 均等値 1/12（1 なら向いていない）。平均の大きい順。"
                  "行をクリックすると、そのヘッドの局面ごとの値が下に出る")
        v_head = gr.State(None)
        v_detail = gr.Dataframe(
            headers=["何手目まで指した局面", "手番", "最善手", "起点", "行き先", "行き先への比"], interactive=False,
            label="選んだヘッドの、最善手ごとの値（大きい順）。行をクリックすると、その局面を上の盤面に出し、"
                  "Attention Map の欄にそのモデル・層・起点を入れる（図は上の Attention Map に出る）")
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
            block = int(re.findall(r"第(\d+)層", row[1])[0]) - 1
            return [path], gr.update(choices=attention_layer_choices([path]), value=block), row[4]

        def layers_for(paths, block):
            choices = attention_layer_choices(paths)
            keep = block if any(v == block for _, v in choices) else (choices[0][1] if choices else None)
            return gr.update(choices=choices, value=keep)

        def show_attention(st, paths, block, query, style):
            line = st["moves"][: st["ply"]]
            rec = preset_record(st["record"]) if "record" in st else None
            pos = "**表示中の局面：** " + (st["label"] if rec is not None else position_title(st["label"], line))
            if not paths:
                return None, "モデルを選んでください", pos, None
            if block is None:
                return None, "層を選んでください", pos, None
            # a drop uses a hand piece, which has no square: add its contribution, as for 9x9
            move = preset_move(st["record"])[1] if rec is not None else -1
            hand = hand_figure(paths[0], rec, move, st["label"]) if move >= 0 else None
            return (*attention_grid(paths, int(block), query, line, style, st["label"], rec), pos, hand)

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

        a_in = [st, a_models, a_layer, a_query, a_style]
        a_out = [a_plot, a_note, a_pos, a_hand]
        a_table.select(pick_layer, a_table, [a_models, a_layer, a_query])
        a_preset.change(pick_preset, [a_preset, one_model], out + [a_query]).then(show_attention, a_in, a_out).then(
            summary, st, a_table)
        a_kind.change(lambda k: gr.update(choices=preset_labels(k), value=None), a_kind, a_preset)
        a_prev.click(lambda k, label: step_preset(k, label, -1), [a_kind, a_preset], a_preset)
        a_next.click(lambda k, label: step_preset(k, label, 1), [a_kind, a_preset], a_preset)
        a_save.click(lambda st, paths, block, query, style, plot, hand: save_candidate(
            "dobutsu", st["label"], [Path(p).parts[-3] for p in paths or []], block, query, style, [plot, hand]),
            [st, a_models, a_layer, a_query, a_style, a_plot, a_hand], a_saved)
        v_run.click(attention_validity, None, [v_note, v_table])

        def pick_head(data, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            block = int(re.findall(r"第(\d+)層", row[1])[0]) - 1
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
        for c in (a_layer, a_query, a_style):
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
