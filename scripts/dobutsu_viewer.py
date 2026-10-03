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
import tempfile
from pathlib import Path

import env_py

TABLEBASE = Path("data/dobutsu_tablebase/dobutsu")
AGREEMENT = Path("data/dobutsu_agreement.csv")
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
    """The runs that have self-play games saved."""
    return sorted(str(p) for p in Path("models").glob("*") if (p / "sgf").is_dir())


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

    def render(st):
        line = st["moves"][: st["ply"]]
        played = st["moves"][st["ply"]] if st["ply"] < len(st["moves"]) else None
        _, text, choices, out = analyse(line, played)
        head = f"{st['label']}\n{st['ply']}手目  {'先手番' if st['ply'] % 2 == 0 else '後手番'}\n\n"
        return (st, head + text,
                gr.update(choices=choices, value=choices[0][1] if choices else None), out,
                gr.update(maximum=max(len(st["moves"]), 1), value=st["ply"]))

    def files_of(run):
        """The newest iteration first in the list, since that is the trained one."""
        names = sgf_files(run) if run else []
        return gr.update(choices=names, value=names[-1] if names else None)

    def load(run, name, index):
        if not run or not name:
            return render({"moves": [], "ply": 0,
                           "label": "構成と sgf ファイルを選んでください"})
        moves, label = load_game(run, name, int(index))
        return render({"moves": moves, "ply": 0, "label": label})

    def play(st, move):
        if not move:
            return render(st)
        label = st["label"] if "手で変更" in st["label"] else st["label"] + "（以降は手で変更）"
        return render({"moves": st["moves"][: st["ply"]] + [move],
                       "ply": st["ply"] + 1, "label": label})

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
                               label="sgfファイル（反復）")
            index = gr.Number(value=1, precision=0, label="何局目")
            read = gr.Button("棋譜を読み込む", variant="primary")
        ply = gr.Slider(0, 1, value=0, step=1, label="何手目")
        with gr.Row():
            move = gr.Dropdown([], label="手を選んで進める", scale=3)
            go = gr.Button("指す")
            reset = gr.Button("初期局面")
        position = gr.Textbox(label="出典・局面・全合法手", lines=24)
        with gr.Accordion("最善手で終局までの全手順（checkState の全出力）", open=False):
            raw = gr.Textbox(label="", lines=30)

        gr.Markdown("---\n## 一致率（ここから下は私たちの計算。彼らのツールにこの機能はない）")
        ok, checked = self_check()
        gr.Markdown(f"起動時の自己確認：{checked}")
        with gr.Row():
            runs_m = gr.Dropdown(runs, value=runs[:1], multiselect=True, label="構成")
            name_m = gr.Dropdown(start, value=start[-1] if start else None,
                                 label="sgfファイル（反復）")
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

        def pick(data, evt: gr.SelectData):
            row = data.values[evt.index[0]] if hasattr(data, "values") else data[evt.index[0]]
            moves, label = load_game(row[0], row[1], int(row[2]))
            return render({"moves": moves, "ply": int(row[3]), "label": label})

        out = [st, position, move, raw, ply]
        tally.click(count, [runs_m, name_m, first, last], [result, table])
        table.select(pick, table, out)
        app.load(render, st, out)
        run.change(files_of, run, name)
        runs_m.change(lambda r: files_of(r[0] if r else None), runs_m, name_m)
        read.click(load, [run, name, index], out)
        ply.release(lambda s, p: render({**s, "ply": int(p)}), [st, ply], out)
        go.click(play, [st, move], out)
        reset.click(lambda: render({"moves": [], "ply": 0, "label": "初期局面から手で進める"}),
                    None, out)

    app.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
