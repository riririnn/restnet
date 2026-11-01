"""Checks of the dobutsu environment after it was rebuilt to turn the board to the side to move
(minizero/environment/dobutsu/README.md). Run inside the container:

  PYTHONPATH=build/dobutsu python3 scripts/dobutsu_env_check.py [OLD_GAMES.json [RECORDS_DIR]]

  rules       the same legal moves, ends and winners as the environment before the change, on
              the random games OLD_GAMES.json recorded with it (made before rebuilding)
  rotation    a white-to-move position and the same position with the colours swapped, black
              to move, give the same input but for the turn plane, and the same action ids
  value       the loader's value target is from the side to move: +1 at the winner's moves
  repetition  the third occurrence of a position is a draw, and the second one shows in plane 11
  features    dobutsu_all_agreement.features() equals getFeatures() on the complete analysis'
              records in both orientations
  records     the legal moves written in RECORDS_DIR (scripts/dobutsu_all.cc) equal the
              environment's, in both orientations
  best line   Tanaka's checkState agrees with the environment along the complete analysis'
              best line (dobutsu_viewer.self_check and validity_moves)
"""
import env_py
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

LETTERS = "GECHL"
failures = []


def report(name, ok, detail=""):
    print("%-11s %s  %s" % (name, "ok" if ok else "FAIL", detail))
    if not ok:
        failures.append(name)


def moves_of(env):
    return sorted(a.to_console_string() for a in env.get_legal_actions())


def play(env, move):
    env.act(next(a for a in env.get_legal_actions() if a.to_console_string() == move))


def sfen_of(env, swap=False):
    """The position as SFEN; with swap, turned 180 degrees with the colours and the turn swapped."""
    text = env.to_string().splitlines()
    rows = [line.split()[1:] for line in text[2:6]]
    hands = {line[0]: line.split(":", 1)[1].strip() for line in text if " hand:" in line}
    turn = text[-1].split()[-1]
    if swap:
        rows = [[c.swapcase() for c in row[::-1]] for row in rows[::-1]]
        hands = {"B": hands["W"], "W": hands["B"]}
        turn = "W" if turn == "B" else "B"
    placement = "/".join("".join(c if c != "." else "1" for c in row).replace("111", "3").replace("11", "2") for row in rows)
    hand = "".join(c for c in hands["B"] if c != "-") + "".join(c.lower() for c in hands["W"] if c != "-")
    return "%s %s %s 1" % (placement, "b" if turn == "B" else "w", hand or "-")


def check_rules(path):
    games = json.load(open(path))
    plies = bad = 0
    for g in games:
        env = env_py.Env()
        env.reset()
        for ply in g:
            same = (moves_of(env) == ply["legal"] and env.is_terminal() == ply["terminal"]
                    and env.get_eval_score(False) == ply["score"] and env.to_string() == ply["text"])
            plies += 1
            bad += not same
            if "move" not in ply:
                break
            play(env, ply["move"])
    report("rules", bad == 0, "%d games, %d positions, %d differ" % (len(games), plies, bad))


def random_positions(n, seed=1):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        env = env_py.Env()
        env.reset()
        for _ in range(rng.randrange(1, 40)):
            if env.is_terminal():
                break
            play(env, rng.choice(moves_of(env)))
        if not env.is_terminal():
            out.append(env)
    return out


def check_rotation():
    bad = 0
    for env in random_positions(300):
        a, b = env_py.Env(), env_py.Env()
        assert a.set_from_sfen(sfen_of(env)) and b.set_from_sfen(sfen_of(env, swap=True))
        fa, fb = np.asarray(a.get_features()).reshape(19, 12), np.asarray(b.get_features()).reshape(19, 12)
        planes = (fa[:18] == fb[:18]).all() and (fa[18] != fb[18]).all()
        ids = {x.get_action_id() for x in a.get_legal_actions()} == {x.get_action_id() for x in b.get_legal_actions()}
        strings = {x.to_console_string() for x in a.get_legal_actions()} != {x.to_console_string() for x in b.get_legal_actions()} or not a.get_legal_actions()
        bad += not (planes and ids and strings)
    report("rotation", bad == 0, "300 positions, %d differ" % bad)


def check_value():
    bad = 0
    for env in random_positions(50, seed=2):
        rng = random.Random(3)
        while not env.is_terminal():
            play(env, rng.choice(moves_of(env)))
        score = env.get_eval_score(False)
        loader = env_py.EnvLoader()
        loader.load_from_environment(env, [])
        loader.add_tag("RE", str(score))
        for pos, action in enumerate(env.get_action_history()):
            mover = action.get_player()
            want = score if mover == env_py.Player.player_1 else -score
            if loader.get_value(pos)[0] != want:
                bad += 1
    report("value", bad == 0, "50 games, %d positions with the wrong sign" % bad)


def check_repetition():
    env = env_py.Env()
    env.reset()
    seen = []
    for move in ["c1c2", "a4a3", "c2c1", "a3a4"] * 2:   # both giraffes out and back, twice
        if env.is_terminal():
            break
        seen.append((np.asarray(env.get_features()).reshape(19, 12)[10:12, 0].tolist(), env.is_terminal()))
        play(env, move)
    plane11 = [s[0] for s in seen]
    ok = env.is_terminal() and env.get_eval_score(False) == 0.0 and plane11[0] == [1.0, 0.0] and plane11[4] == [0.0, 1.0] and len(seen) == 8
    report("repetition", ok, "ended %s score %s planes %s" % (env.is_terminal(), env.get_eval_score(False), plane11))


def check_features():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import torch
    import dobutsu_all_agreement as A
    bad = n = 0
    rng = random.Random(4)
    for _ in range(300):
        env = env_py.Env()
        env.reset()
        for _ in range(rng.randrange(0, 40)):
            if env.is_terminal():
                break
            play(env, rng.choice(moves_of(env)))
            a = env_py.Env()
            assert a.set_from_sfen(sfen_of(env))   # a fresh position: first occurrence, move count 0
            r = record_of(env, A)
            n += 1
            bad += not torch.equal(A.features(r, "cpu"), torch.tensor(a.get_features()).view(1, 19, 4, 3))
    report("features", bad == 0, "%d positions, %d differ" % (n, bad))


def record_of(env, A):
    """One record of scripts/dobutsu_all.cc for this position (board, hands, turn only)."""
    code = {"c": 1, "e": 2, "g": 3, "h": 4, "l": 5}
    text = env.to_string().splitlines()
    r = np.zeros(1, dtype=A.RECORD)
    for i, line in enumerate(text[2:6]):
        for j, ch in enumerate(line.split()[1:]):
            if ch != ".":
                r["board"][0, i * 3 + j] = code[ch.lower()] * (1 if ch.isupper() else -1)
    for line in text:
        if " hand:" in line:
            side = 0 if line[0] == "B" else 3
            for k, letter in enumerate("gec"):
                r["hands"][0, side + k] = line.split(":", 1)[1].upper().count(letter.upper())
    r["turn"][0] = 1 if text[-1].strip().endswith("B") else -1
    return r


def sfen_of_record(r):
    """SFEN of one record of scripts/dobutsu_all.cc (Tanaka's codes 1 chick 2 elephant 3 giraffe 4 hen 5 lion)."""
    code = {1: "C", 2: "E", 3: "G", 4: "H", 5: "L"}
    rows = []
    for row in range(4):
        cells = [code[abs(int(p))] if p > 0 else code[abs(int(p))].lower() if p < 0 else "1" for p in r["board"][0][row * 3:row * 3 + 3]]
        rows.append("".join(cells).replace("111", "3").replace("11", "2"))
    hand = "".join(c * int(n) for c, n in zip("GEC", r["hands"][0][:3])) + "".join(c * int(n) for c, n in zip("gec", r["hands"][0][3:]))
    return "%s %s %s 1" % ("/".join(rows), "b" if r["turn"][0] == 1 else "w", hand or "-")


def check_records(root):
    """The records' legal moves (bits over action ids) equal the environment's on random records."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dobutsu_all_agreement as A
    from attention_presets import PART, TOTAL
    rng = np.random.default_rng(5)
    bad = n = 0
    for folder in ("full", "full_o2"):
        for index in np.sort(rng.choice(TOTAL, 50000, replace=False)):
            r = np.fromfile("%s/%s/part_%03d.bin" % (root, folder, index // PART), dtype=A.RECORD, count=1, offset=int(index % PART) * A.RECORD.itemsize)
            env = env_py.Env()
            assert env.set_from_sfen(sfen_of_record(r))
            ours = {a.get_action_id() for a in env.get_legal_actions()}
            theirs = set(np.nonzero(np.unpackbits(r["legal"], axis=1, bitorder="little")[0, :132])[0].tolist())
            n += 1
            bad += ours != theirs
    report("records", bad == 0, "%d records, %d differ" % (n, bad))


def check_best_line():
    import dobutsu_viewer as V
    ok, note = V.self_check()
    positions, dropped, line = V.validity_moves()
    report("best line", ok and len(line) == 77 and len(positions) == 61, "%s; best line %d moves, %d positions with a board move" % (note, len(line), len(positions)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_rules(sys.argv[1])
    check_rotation()
    check_value()
    check_repetition()
    check_features()
    if len(sys.argv) > 2:
        check_records(sys.argv[2])
    check_best_line()
    print("all ok" if not failures else "FAILED: " + ", ".join(failures))
    sys.exit(1 if failures else 0)
