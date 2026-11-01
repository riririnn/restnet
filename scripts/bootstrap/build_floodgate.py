"""floodgate (wdoor) CSA games -> minizero records for supervised pretraining.

  python3 scripts/bootstrap/build_floodgate.py RAW_DIR OUT_DIR [--min-rating 2500] [--years 2019 2020]
                                               [--test-games 3000] [--min-moves 20] [--jobs 8] [--limit N]

RAW_DIR holds one folder per year of CSA files (data/floodgate/raw). A game is kept when both
players have a rating ('black_rate' / 'white_rate' lines) at or above --min-rating, it starts
from the even initial position and it ended by toryo, sennichite, oute_sennichite or kachi
(the result comes from the 'summary' line: +1 Black, -1 White, 0 draw). Time-ups, abnormal
ends, illegal moves and the old 256-move cap are dropped.

Every game is replayed in the environment and cut at the first move it does not generate
(a non-promotion of a pawn, bishop or rook that could promote; the lance's to the last two
ranks) and where it is over by the rules (a declaration the players did not make yet), so
every id in the records is a legal action of the position it is played in.

Writes OUT_DIR/train.sgf and OUT_DIR/test.sgf (the first --test-games after a shuffle), one
record per line: (;GM[shogi]SZ[9]RE[r]EV[floodgate]BR[rating]WR[rating];B[id];W[id]...)

Needs python-shogi (pip install python-shogi) and build/shogi (env_py).
"""
import argparse
import os
import random
import re
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../build/shogi"))   # env_py
from shogi_coords import usi_to_action_id  # noqa: E402

STARTPOS = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"
KEPT_ENDS = ("toryo", "sennichite", "oute_sennichite", "kachi")
MIN_RATING = 0
MIN_MOVES = 20


def header(text):
    """(black rating, white rating, end kind, result) from the CSA comment lines."""
    rates = {}
    for side, value in re.findall(r"^'(black|white)_rate:[^\n]*:([0-9.]+)$", text, re.M):
        rates[side] = float(value)
    m = re.search(r"^'summary:([a-z_ ]+):([^:\n]*):([^\n]*)$", text, re.M)
    if not m:
        return rates, "?", 0
    result = 1 if m.group(2).endswith(" win") else -1 if m.group(3).endswith(" win") else 0
    return rates, m.group(1), result


def convert(path):
    """(record, reason) for one CSA file; record is None when the game is dropped."""
    import env_py
    import shogi.CSA
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    rates, kind, result = header(text)
    if "black" not in rates or "white" not in rates:
        return None, "no rating"
    if min(rates.values()) < MIN_RATING:
        return None, "below rating"
    if kind not in KEPT_ENDS:
        return None, "end: " + kind
    try:
        game = shogi.CSA.Parser.parse_str(text)[0]
    except Exception:  # noqa: BLE001  a malformed file
        return None, "unparsed"
    if game["sfen"] != STARTPOS:
        return None, "not the even start"
    if len(game["moves"]) < MIN_MOVES:
        return None, "too short"
    env = env_py.Env()
    env.reset()
    black, white = env_py.Player.player_1, env_py.Player.player_2
    actions = []
    cut = ""
    for usi in game["moves"]:
        if env.is_terminal():
            cut = "cut: over by the rules"
            break
        is_black = env.get_turn() == black
        try:
            action = env_py.Action(usi_to_action_id(usi, is_black), black if is_black else white)
        except ValueError:
            return None, "unconvertible move"
        if not env.is_legal_action(action):
            cut = "cut: a move the environment does not generate"
            break
        env.act(action)
        actions.append("%s[%d]" % ("B" if is_black else "W", action.get_action_id()))
    if len(actions) < MIN_MOVES:
        return None, "too short after the cut"
    record = "(;GM[shogi]SZ[9]RE[%d]EV[floodgate]BR[%d]WR[%d];%s)" % (result, rates["black"], rates["white"], ";".join(actions))
    return record, cut or "kept"


def main():
    global MIN_RATING, MIN_MOVES
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--min-rating", type=int, default=2500, help="both players at or above this floodgate rating")
    ap.add_argument("--years", nargs="*", help="year folders to read (default: all)")
    ap.add_argument("--test-games", type=int, default=3000, help="games held out in test.sgf")
    ap.add_argument("--min-moves", type=int, default=20, help="drop games shorter than this, before and after the cut")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--limit", type=int, default=0, help="read at most this many files (a trial)")
    args = ap.parse_args()
    MIN_RATING, MIN_MOVES = args.min_rating, args.min_moves

    years = args.years or sorted(d.name for d in Path(args.raw_dir).iterdir() if d.is_dir())
    files = [str(p) for y in years for p in sorted(Path(args.raw_dir, y).glob("*.csa"))]
    if args.limit:
        files = files[:args.limit]
    print("files", len(files), "years", " ".join(years), flush=True)

    records, reasons = [], {}
    with Pool(args.jobs) as pool:
        for i, (record, reason) in enumerate(pool.imap_unordered(convert, files, chunksize=64), 1):
            reasons[reason] = reasons.get(reason, 0) + 1
            if record:
                records.append(record)
            if i % 20000 == 0:
                print("  %d/%d scanned, %d kept" % (i, len(files), len(records)), flush=True)

    random.Random(0).shuffle(records)
    os.makedirs(args.out_dir, exist_ok=True)
    for name, part in (("test", records[:args.test_games]), ("train", records[args.test_games:])):
        path = os.path.join(args.out_dir, name + ".sgf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(part) + "\n")
        print("wrote %d games to %s" % (len(part), path))
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print("  %7d  %s" % (n, reason))


if __name__ == "__main__":
    main()
