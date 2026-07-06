#!/usr/bin/env python3
"""
Shogi model-vs-model evaluation referee.

gogui-twogtp cannot referee shogi games because ShogiAction::toConsoleString()
returns an empty string (genmove replies are empty). This script drives two
restnet_shogi console processes directly and reads each move back via the
game_string command instead, so no C++ rebuild is required.

Usage (inside the container):
    python3 scripts/shogi_eval.py \
        --model1 shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_1000.pt \
        --model2 shogi_9x9_gaz_2R1T2R1T_P_TV_n50/model/weight_iter_13000.pt \
        --conf configs/9x9_shogi/RRTRRT.cfg \
        --games 10 --out eval_result

Colors alternate every game. Result is printed per game and summarised at
the end with win/draw/loss counts and an Elo difference estimate.
"""

import argparse
import math
import os
import re
import subprocess
import sys
import time


class Engine:
    def __init__(self, executable: str, conf: str, model: str, conf_str: str = ""):
        cs = f"nn_file_name={model}"
        if conf_str:
            cs = f"{conf_str}:{cs}"
        self.model = model
        self.proc = subprocess.Popen(
            [executable, "-conf_file", conf, "-conf_str", cs],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        # Console prints the full config on startup before entering GTP mode;
        # the first command's framed reply ("= ...") is still parsed correctly
        # because we scan for the "=" / "?" prefix.

    def send(self, cmd: str) -> str:
        """Send one GTP command, return the reply text (without '=' prefix)."""
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        lines = []
        status = None
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                raise RuntimeError(f"engine died on command: {cmd}")
            line = line.rstrip("\n")
            if status is None:
                if line.startswith("="):
                    status = "ok"
                    lines.append(line[1:].strip())
                elif line.startswith("?"):
                    status = "fail"
                    lines.append(line[1:].strip())
                # else: startup banner / config dump — skip
            else:
                if line == "":
                    break
                lines.append(line)
        reply = "\n".join(lines).strip()
        if status == "fail":
            raise RuntimeError(f"engine replied error to {cmd!r}: {reply}")
        return reply

    def last_action_id(self) -> int | None:
        """Parse the most recent move's action ID from game_string."""
        record = self.send("game_string")
        ids = re.findall(r";[BW]\[(\d+)\]", record)
        return int(ids[-1]) if ids else None

    def close(self):
        try:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        self.proc.terminate()


def play_game(black: Engine, white: Engine, max_moves: int = 600) -> tuple[str, int]:
    """Play one game. Returns (result, num_moves).

    result: 'B' black won, 'W' white won, 'D' draw.
    """
    for e in (black, white):
        e.send("clear_board")

    mover, waiter = black, white
    color, other = "b", "w"
    n_moves = 0

    while n_moves < max_moves:
        reply = mover.send(f"genmove {color}")
        if reply.lower() == "resign":
            return ("W" if color == "b" else "B"), n_moves
        if reply.upper() == "PASS":
            # environment is terminal — adjudicate by final_score
            break
        # genmove reply is empty (toConsoleString stub) — read the move back
        action_id = mover.last_action_id()
        if action_id is None:
            raise RuntimeError("no move found in game_string after genmove")
        waiter.send(f"play {color} {action_id}")
        n_moves += 1
        mover, waiter = waiter, mover
        color, other = other, color

    score = float(black.send("final_score") or 0.0)
    if score > 0:
        return "B", n_moves
    if score < 0:
        return "W", n_moves
    return "D", n_moves


def elo_diff(wins: float, total: float) -> float:
    """Elo difference from a score rate (draws counted as half)."""
    if total == 0:
        return 0.0
    p = min(max(wins / total, 1e-3), 1 - 1e-3)
    return 400.0 * math.log10(p / (1.0 - p))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--model1", required=True, help="model 1 (.pt)")
    ap.add_argument("--model2", required=True, help="model 2 (.pt)")
    ap.add_argument("--conf", required=True, help="config .cfg")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--executable", default="build/shogi/restnet_shogi")
    ap.add_argument("--conf_str", default="",
                    help="extra conf_str for both engines, e.g. "
                         "'actor_use_dirichlet_noise=false'")
    ap.add_argument("--out", default="", help="write result summary to this file")
    args = ap.parse_args()

    e1 = Engine(args.executable, args.conf, args.model1, args.conf_str)
    e2 = Engine(args.executable, args.conf, args.model2, args.conf_str)
    name1 = os.path.basename(args.model1)
    name2 = os.path.basename(args.model2)

    # score from model1's perspective; draws = 0.5
    m1_score = 0.0
    results = []
    t0 = time.time()

    try:
        for g in range(args.games):
            m1_is_black = (g % 2 == 0)
            black, white = (e1, e2) if m1_is_black else (e2, e1)
            t1 = time.time()
            result, n_moves = play_game(black, white)
            dt = time.time() - t1

            if result == "D":
                m1_score += 0.5
                outcome = "draw"
            elif (result == "B") == m1_is_black:
                m1_score += 1.0
                outcome = f"{name1} win"
            else:
                outcome = f"{name2} win"

            line = (f"game {g}: {result} ({outcome})  moves={n_moves}  "
                    f"{dt:.0f}s  [black={'m1' if m1_is_black else 'm2'}]")
            print(line, flush=True)
            results.append(line)
    finally:
        e1.close()
        e2.close()

    total = len(results)
    diff = elo_diff(m1_score, total)
    summary = (
        f"\n=== {name1} vs {name2} ===\n"
        f"games={total}  {name1} score={m1_score}/{total}"
        f"  (win rate {100 * m1_score / max(total, 1):.1f}%)\n"
        f"Elo({name1}) - Elo({name2}) = {diff:+.0f}\n"
        f"total time: {(time.time() - t0) / 60:.1f} min\n"
    )
    print(summary, flush=True)

    if args.out:
        with open(args.out, "w") as f:
            f.write("\n".join(results) + "\n" + summary)


if __name__ == "__main__":
    main()
