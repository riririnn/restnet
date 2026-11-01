"""Checks of the 9x9 shogi environment against python-shogi (an independent implementation of the
rules) and against real floodgate games. Run inside the container, with python-shogi installed:

  pip install python-shogi
  PYTHONPATH=build/shogi python3 scripts/shogi_env_check.py [FLOODGATE_CSA_DIR|LIST.txt [GAMES [DATASET.sgf]...]]

  resign      getEvalScore(true), the RE of a resigned self-play game, is the loss of the side to move
  rules       random games: our legal moves equal python-shogi's, less the non-promotions our
              generator leaves out on purpose (pawn, bishop and rook that could promote; a lance
              to the last two ranks); mate, stalemate and the fourfold repetition end the game alike
  rotation    a white-to-move position and the same position with the colours swapped give the
              same planes of the current step but the turn plane, and the same action ids
  value       the loader's value target is from the side to move
  roundtrip   a record written by the loader reads back and replays to the same position
  features    tsume_shogi.sfen_to_tensor equals getFeatures() for a position given as SFEN
  floodgate   real games (CSA): every move is legal here (the omitted non-promotions are counted),
              and the recorded end (toryo, sennichite, oute_sennichite, kachi) is what we see
  records     a dataset file of scripts/bootstrap replays legally with a numeric RE
"""
import shogi.CSA
import shogi
import env_py
import random
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

B, W = env_py.Player.player_1, env_py.Player.player_2
failures = []
STARTPOS = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


def report(name, ok, detail=""):
    print("%-10s %s  %s" % (name, "ok" if ok else "FAIL", detail), flush=True)
    if not ok:
        failures.append(name)


def ours(env):
    return {a.to_console_string() for a in env.get_legal_actions()}


def omitted(board, move):
    """True when our generator leaves this python-shogi move out on purpose (MoveGenerator.cpp,
    exceptNonEffectiveNonProm): a non-promotion of a pawn, bishop or rook that could promote, or
    a lance's non-promotion to the last two ranks."""
    u = move.usi()
    if "*" in u or u.endswith("+"):
        return False
    kind = board.piece_type_at(move.from_square)
    black = board.turn == shogi.BLACK
    zone = "abc" if black else "ghi"
    if kind in (shogi.PAWN, shogi.BISHOP, shogi.ROOK):
        return u[1] in zone or u[3] in zone
    if kind == shogi.LANCE:
        return u[3] in ("ab" if black else "hi")
    return False


def theirs(board):
    return {m.usi() for m in board.legal_moves if not omitted(board, m)}


def play(env, usi):
    env.act(["B" if env.get_turn() == B else "W", usi])


def swap_sfen(sfen):
    """The position turned 180 degrees with the colours, hands and the turn swapped."""
    board, turn, hand, *rest = sfen.split()
    rows = []
    for row in board.split("/"):
        cells = re.findall(r"\+?[a-zA-Z]|\d", row)
        rows.append("".join(c.swapcase() if c.isalpha() or c.startswith("+") else c for c in cells[::-1]))
    return " ".join(["/".join(rows[::-1]), "w" if turn == "b" else "b", hand.swapcase() if hand != "-" else "-"] + rest)


def features(env):
    return np.asarray(env.get_features(), dtype=np.float32).reshape(362, 81)


def check_resign():
    env = env_py.Env()
    env.reset()
    play(env, "7g7f")
    scores = [env.get_eval_score(True)]       # White to move resigns: Black wins, +1
    play(env, "3c3d")
    scores.append(env.get_eval_score(True))   # Black to move resigns: White wins, -1
    report("resign", scores == [1.0, -1.0], "RE of a resigned game: White to move %+.0f, Black to move %+.0f (expected +1, -1)" % tuple(scores))


def check_rules(games, seed=1):
    rng = random.Random(seed)
    plies = bad = ends = 0
    examples = []
    for g in range(games):
        env = env_py.Env()
        env.reset()
        board = shogi.Board()
        for ply in range(512):
            mine, other = ours(env), theirs(board)
            plies += 1
            if mine != other:
                bad += 1
                if len(examples) < 5:
                    examples.append((board.sfen(), sorted(mine - other)[:5], sorted(other - mine)[:5]))
            over = board.is_checkmate() or board.is_stalemate() or board.is_fourfold_repetition()
            if env.is_terminal() != over:
                bad += 1
                if len(examples) < 5:
                    examples.append((board.sfen(), "terminal ours %s theirs %s score %s" % (env.is_terminal(), over, env.get_eval_score(False)), ""))
            if env.is_terminal() or over or not mine:
                ends += 1
                break
            usi = rng.choice(sorted(mine))
            play(env, usi)
            board.push_usi(usi)
    for e in examples:
        print("    ", e)
    report("rules", bad == 0, "%d games, %d positions, %d differ, %d ended" % (games, plies, bad, ends))


def check_rotation(sfens):
    bad = 0
    for sfen in sfens:
        a, b = env_py.Env(), env_py.Env()
        assert a.set_from_sfen(sfen) and b.set_from_sfen(swap_sfen(sfen)), sfen
        fa, fb = features(a), features(b)
        planes = (fa[:45] == fb[:45]).all() and (fa[45:360] == 0).all() and (fb[45:360] == 0).all() and (fa[360] != fb[360]).all() and (fa[361] == fb[361]).all()
        ids = {x.get_action_id() for x in a.get_legal_actions()} == {x.get_action_id() for x in b.get_legal_actions()}
        bad += not (planes and ids)
    report("rotation", bad == 0, "%d positions, %d differ" % (len(sfens), bad))


def check_value(games):
    bad = n = 0
    for env, win in games:
        loader = env_py.EnvLoader()
        loader.load_from_environment(env, [])
        loader.add_tag("RE", str(win))
        for pos, a in enumerate(env.get_action_history()):
            n += 1
            want = win if a.get_player() == B else -win
            bad += loader.get_value(pos)[0] != want
    report("value", bad == 0, "%d games, %d positions, %d with the wrong sign" % (len(games), n, bad))


def check_roundtrip(games):
    bad = 0
    for env, win in games:
        loader = env_py.EnvLoader()
        loader.load_from_environment(env, [])
        loader.add_tag("RE", str(win))
        text = loader.to_string()
        back = env_py.EnvLoader()
        ok = back.load_from_string(text) and back.to_string() == text
        replay = env_py.Env()
        replay.reset()
        for c, i in re.findall(r";([BW])\[(\d+)\]", text):
            act = env_py.Action(int(i), B if c == "B" else W)
            ok = ok and replay.is_legal_action(act) and replay.act(act)
        bad += not (ok and replay.to_string() == env.to_string())
    report("roundtrip", bad == 0, "%d games, %d differ" % (len(games), bad))


def check_features(sfens):
    import torch
    import tsume_shogi
    bad = n = 0
    differ = set()
    for sfen in sfens:
        env = env_py.Env()
        assert env.set_from_sfen(sfen)
        ours_ = torch.tensor(features(env)).view(362, 9, 9)
        py = tsume_shogi.sfen_to_tensor(sfen).view(362, 9, 9)
        n += 1
        same = (ours_ == py).all(-1).all(-1)
        if not same.all():
            bad += 1
            differ |= set(torch.nonzero(~same).flatten().tolist())
    report("features", bad == 0, "%d positions, %d differ; planes that differ: %s" % (n, bad, sorted(differ)[:12]))


def floodgate_games(root, n, seed=3):
    """n random CSA files under root, or the files listed in root when it is a text file."""
    files = [Path(l.strip()) for l in open(root) if l.strip()] if str(root).endswith(".txt") else sorted(Path(root).rglob("*.csa"))
    rng = random.Random(seed)
    return [files[i] for i in sorted(rng.sample(range(len(files)), min(n, len(files))))]


def summary_of(path):
    """(kind, winner) from the CSA summary line: 'summary:toryo:NAME1 win:NAME2 lose, NAME1 being Black."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^'summary:([a-z_ ]+):([^:\n]*):([^\n]*)$", text, re.M)
    if not m:
        return "?", 0
    return m.group(1), 1 if m.group(2).endswith(" win") else -1 if m.group(3).endswith(" win") else 0


def declaration_ok(board):
    """The 27-point rule for the side that just moved (python-shogi board, so the other side is to move)."""
    mover = not board.turn
    black = mover == shogi.BLACK
    pieces = points = 0
    king_in = False
    for sq in shogi.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color != mover:
            continue
        rank = sq // 9  # 0 is rank a
        if not (rank <= 2 if black else rank >= 6):
            continue
        if p.piece_type == shogi.KING:
            king_in = True
            continue
        pieces += 1
        points += 5 if p.piece_type in (shogi.BISHOP, shogi.ROOK, shogi.PROM_BISHOP, shogi.PROM_ROOK) else 1
    for pt, cnt in board.pieces_in_hand[mover].items():
        points += cnt * (5 if pt in (shogi.BISHOP, shogi.ROOK) else 1)
    return king_in and pieces >= 10 and points >= (28 if black else 27)


def check_floodgate(root, n):
    kinds = {}
    legal_bad = trunc = replayed = 0
    examples = []
    finished = []   # (env, win) of games replayed to the end
    sfens = []
    for path in floodgate_games(root, n):
        try:
            game = shogi.CSA.Parser.parse_file(str(path))[0]
        except Exception as e:  # noqa: BLE001
            kinds["unparsed"] = kinds.get("unparsed", 0) + 1
            continue
        kind, win = summary_of(path)
        if game["sfen"] != STARTPOS or kind not in ("toryo", "sennichite", "oute_sennichite", "kachi"):
            kinds["skipped " + kind] = kinds.get("skipped " + kind, 0) + 1
            continue
        env = env_py.Env()
        env.reset()
        board = shogi.Board()
        moves = game["moves"]
        result = None
        for i, usi in enumerate(moves):
            if usi not in ours(env):
                if omitted(board, shogi.Move.from_usi(usi)):
                    trunc += 1
                    result = "truncated at an omitted non-promotion"
                else:
                    legal_bad += 1
                    if len(examples) < 5:
                        examples.append((path.name, i, usi, board.sfen()))
                    result = "move not legal here"
                break
            play(env, usi)
            board.push_usi(usi)
            if i % 40 == 20 and len(sfens) < 400:
                sfens.append(board.sfen())
            if env.is_terminal():
                score = env.get_eval_score(False)
                last = i == len(moves) - 1
                if kind == "toryo":
                    # a mated player resigns: our mate at the last move with the same winner is the same end;
                    # a player who could declare a win but played on is ended here by the declaration
                    if last and score == win and not ours(env):
                        result = "toryo: mate at the end"
                    elif ours(env) and not board.is_fourfold_repetition() and score != 0 and declaration_ok(board):
                        result = "toryo: ours ends earlier by declaration (the 27-point conditions held, the player did not declare)"
                    else:
                        result = "toryo: ended early (%s, score %+.0f, ply %d/%d)" % ("repetition" if board.is_fourfold_repetition()
                                                                                      else "no moves" if not ours(env) else "rule", score, i + 1, len(moves))
                elif kind == "sennichite":
                    result = "sennichite: same" if last and score == 0 and board.is_fourfold_repetition() else "sennichite: differs (ply %d/%d score %+.0f)" % (i + 1, len(moves), score)
                elif kind == "oute_sennichite":
                    result = "oute_sennichite: same" if last and score == win and board.is_fourfold_repetition() else "oute_sennichite: differs (ply %d/%d score %+.0f)" % (i + 1, len(moves), score)
                elif kind == "kachi":
                    if score == win and declaration_ok(board):
                        result = "kachi: same" if last else "kachi: ours ends earlier (the conditions already held)"
                    else:
                        result = "kachi: differs (ply %d/%d score %+.0f)" % (i + 1, len(moves), score)
                break
        else:
            if kind == "toryo":
                result = "toryo: not terminal here (as expected)"
                replayed += 1
                finished.append((env, win))
            else:
                result = kind + ": not terminal here but the record ended so"
        kinds[result] = kinds.get(result, 0) + 1
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print("     %6d  %s" % (v, k))
    for e in examples:
        print("    ", e)
    bad = legal_bad + sum(v for k, v in kinds.items() if "differs" in k or "ended early" in k or "not terminal here but" in k)
    report("floodgate", bad == 0, "%d games; %d replayed to the end, %d truncated at an omitted non-promotion, %d illegal here, %d ends differ" % (n, replayed, trunc, legal_bad, bad - legal_bad))
    return finished, sfens


def check_records(path, n=3000):
    """A dataset of scripts/bootstrap (SGF lines of action ids): every id is legal when replayed,
    no game is over before its last move, and RE is numeric."""
    bad = games = plies = 0
    with open(path) as f:
        for line in f:
            if games >= n:
                break
            games += 1
            env = env_py.Env()
            env.reset()
            ok = re.search(r"RE\[(-?1|0)(\.0+)?\]", line) is not None
            for c, i in re.findall(r";([BW])\[(\d+)\]", line):
                act = env_py.Action(int(i), B if c == "B" else W)
                if env.is_terminal() or not env.is_legal_action(act):
                    ok = False
                    break
                env.act(act)
                plies += 1
            bad += not ok
    report("records", bad == 0, "%s: %d games, %d plies, %d bad" % (path, games, plies, bad))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else None
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    check_resign()
    check_rules(games=min(games, 100))
    finished, sfens = check_floodgate(root, games) if root else ([], [])
    if sfens:
        check_rotation(sfens)
        check_features(sfens[:100])
    if finished:
        check_value(finished[:200])
        check_roundtrip(finished[:100])
    for dataset in sys.argv[3:]:
        check_records(dataset)
    print("all ok" if not failures else "FAILED: " + ", ".join(failures))
    sys.exit(1 if failures else 0)
