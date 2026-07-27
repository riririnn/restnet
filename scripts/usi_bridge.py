#!/usr/bin/env python3
"""
Play a restnet shogi model against an external USI engine (YaneuraOu, Elmo, ...).

The two programs speak different protocols -- restnet uses MiniZero's GTP-like
console (moves are integer action ids), the external engine uses USI (moves are
strings like '7g7f') -- so this module keeps the game in USI move notation and
converts at the restnet boundary via scripts/shogi_coords.py.

Time control follows the AlphaZero paper's rating setup: both sides get the same
thinking time per move (the paper used 1 second per move for the training-time
Elo tournament, 1 minute per move for the headline matches).

Usage (inside the container, from /workspace):
    python3 scripts/usi_bridge.py \
        --conf configs/9x9_shogi/RRTRRT-bigserver.cfg \
        --model shogi_9x9_restnet64_v2/model/weight_iter_9000.pt \
        --usi-engine /path/to/YaneuraOu \
        --usi-option Threads=1 --usi-option USI_Hash=1024 \
        --games 10 --time-per-move 1.0
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shogi_coords import action_id_to_usi, usi_to_action_id  # noqa: E402
import shogi_eval  # noqa: E402


class UsiEngine:
    """Minimal USI driver: handshake, position/go, bestmove."""

    def __init__(self, executable, options=None, cwd=None, name=None, verbose=False):
        self.name = name or os.path.basename(executable)
        self.verbose = verbose
        self.recent = []  # last lines seen, for diagnosing an abnormal exit
        self.proc = subprocess.Popen(
            [executable],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=cwd or os.path.dirname(os.path.abspath(executable)) or None,
        )
        self._send("usi")
        self._wait_for("usiok")
        for opt in options or []:
            key, _, value = opt.partition("=")
            self._send(f"setoption name {key} value {value}")
        self._send("isready")
        self._wait_for("readyok")
        self._send("usinewgame")

    def _send(self, line):
        if self.verbose:
            print(f"  >{self.name}: {line}", flush=True)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _readline(self):
        line = self.proc.stdout.readline()
        if line == "":
            tail = "\n    ".join(self.recent[-8:])
            raise RuntimeError(
                f"USI engine {self.name} died. last output:\n    {tail}")
        line = line.strip()
        self.recent.append(line)
        if self.verbose:
            print(f"  <{self.name}: {line}", flush=True)
        return line

    def _wait_for(self, token, timeout=60.0):
        deadline = time.time() + timeout
        while True:
            line = self._readline()
            if line.split(" ")[0] == token:
                return line
            if time.time() > deadline:
                raise RuntimeError(f"timeout waiting for {token!r} from {self.name}")

    def new_game(self):
        self._send("usinewgame")

    def bestmove(self, moves, byoyomi_ms):
        """Ask for a move given the USI move list so far. Returns a USI move,
        or 'resign' / 'win' (declaration) as the engine reported it."""
        pos = "position startpos" + (" moves " + " ".join(moves) if moves else "")
        self._send(pos)
        self._send(f"go byoyomi {int(byoyomi_ms)}")
        line = self._wait_for("bestmove", timeout=byoyomi_ms / 1000.0 + 60.0)
        return line.split(" ")[1]

    def close(self):
        try:
            self._send("quit")
            self.proc.stdin.flush()
        except Exception:
            pass
        self.proc.terminate()


class RestnetPlayer:
    """restnet console wrapped to speak USI move strings."""

    def __init__(self, executable, conf, model, conf_str="", name=None):
        self.name = name or os.path.basename(model)
        self.engine = shogi_eval.Engine(executable, conf, model, conf_str)

    def new_game(self):
        self.engine.send("clear_board")

    def bestmove(self, moves, is_black):
        """Generate a move for the side to move. `moves` is unused because the
        engine keeps its own board (fed by apply_move). Returns a USI move, or
        'resign' / 'terminal' (minizero reports a terminal position -- mate,
        stalemate, sennichite, cap -- as a 'PASS' reply to genmove)."""
        reply = self.engine.send(f"genmove {'b' if is_black else 'w'}")
        if reply.lower() == "resign":
            return "resign"
        if reply.upper() == "PASS":
            return "terminal"
        action_id = self.engine.last_action_id()
        if action_id is None:
            raise RuntimeError("no move found in game_string after genmove")
        return action_id_to_usi(action_id, is_black)

    def apply_move(self, usi_move, is_black):
        """Play the opponent's move on this engine's board."""
        action_id = usi_to_action_id(usi_move, is_black)
        self.engine.send(f"play {'b' if is_black else 'w'} {action_id}")

    def final_score(self):
        return float(self.engine.send("final_score") or 0.0)

    def close(self):
        self.engine.close()


def _adjudicate(restnet, restnet_is_black, n_moves):
    """Decide the result from restnet's board using minizero's own rules
    (final_score: >0 black won, <0 white won, 0 draw)."""
    score = restnet.final_score()
    if score == 0:
        return "D", n_moves
    black_won = score > 0
    return ("R" if black_won == restnet_is_black else "U"), n_moves


def play_game(restnet, usi, restnet_is_black, time_per_move, max_moves=512):
    """Play one game. Returns (result, n_moves) with result in {'R','U','D'}
    for restnet win / usi win / draw."""
    restnet.new_game()
    usi.new_game()

    moves = []
    is_black = True
    byoyomi_ms = time_per_move * 1000

    while len(moves) < max_moves:
        restnet_to_move = (is_black == restnet_is_black)

        if restnet_to_move:
            mv = restnet.bestmove(moves, is_black)
            if mv == "resign":
                return "U", len(moves)
            if mv == "terminal":  # restnet's board is already decided (mate/draw)
                return _adjudicate(restnet, restnet_is_black, len(moves))
            usi_side_move = mv
        else:
            mv = usi.bestmove(moves, byoyomi_ms)
            if mv in ("resign",):
                return "R", len(moves)
            if mv == "win":       # entering-king declaration by the USI engine
                return "U", len(moves)
            usi_side_move = mv
            restnet.apply_move(mv, is_black)

        moves.append(usi_side_move)
        is_black = not is_black

    # hit the move cap: capped games are drawn under the training rules
    return _adjudicate(restnet, restnet_is_black, len(moves))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--conf", required=True, help="restnet config .cfg")
    ap.add_argument("--model", required=True, help="restnet model .pt")
    ap.add_argument("--executable", default="build/shogi/restnet_shogi")
    ap.add_argument("--conf_str", default="actor_use_dirichlet_noise=false",
                    help="extra conf_str for restnet (noise off for rating games)")
    ap.add_argument("--usi-engine", required=True, help="path to the USI engine")
    ap.add_argument("--usi-option", action="append", default=[],
                    help="USI setoption, e.g. --usi-option Threads=1 (repeatable)")
    ap.add_argument("--usi-cwd", default="", help="working directory for the USI engine")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--time-per-move", type=float, default=1.0,
                    help="seconds per move for both sides (AZ paper: 1s for the "
                         "training Elo tournament)")
    ap.add_argument("--restnet-sim-cap", type=int, default=8000,
                    help="max MCTS simulations restnet may run inside the per-move "
                         "time limit. Needed because think_time_limit only STOPS the "
                         "search early -- the search still ends at actor_num_simulation "
                         "first (64 by default, ~0.1s), so it must be raised to let the "
                         "time limit govern. Raise if restnet finishes before the time; "
                         "bounded by tree-pool RAM = (cap+1) x tree_max_children nodes.")
    ap.add_argument("--out", default="", help="write the result summary here")
    ap.add_argument("--verbose", action="store_true",
                    help="print every USI line sent/received (for debugging)")
    args = ap.parse_args()

    if not os.path.isfile(args.model):
        sys.exit(f"model not found: {args.model}")

    # match restnet's thinking time to the USI engine's. Raise num_simulation to
    # the cap so the time limit (not the 64-sim default) ends the search.
    conf_str = args.conf_str
    if args.time_per_move > 0:
        extra = (f"actor_mcts_think_time_limit={args.time_per_move}:"
                 f"actor_num_simulation={args.restnet_sim_cap}")
        conf_str = (conf_str + ":" if conf_str else "") + extra

    restnet = RestnetPlayer(args.executable, args.conf, args.model, conf_str)
    usi = UsiEngine(args.usi_engine, args.usi_option, args.usi_cwd or None,
                    verbose=args.verbose)

    wins = draws = losses = 0
    lines = []
    t0 = time.time()
    try:
        for g in range(args.games):
            restnet_is_black = (g % 2 == 0)
            t1 = time.time()
            result, n_moves = play_game(restnet, usi, restnet_is_black,
                                        args.time_per_move)
            if result == "R":
                wins += 1
            elif result == "U":
                losses += 1
            else:
                draws += 1
            line = (f"game {g}: {'win ' if result=='R' else 'loss' if result=='U' else 'draw'}"
                    f"  moves={n_moves}  {time.time()-t1:.0f}s"
                    f"  [restnet={'black' if restnet_is_black else 'white'}]")
            print(line, flush=True)
            lines.append(line)
    finally:
        restnet.close()
        usi.close()

    total = wins + draws + losses
    score = wins + 0.5 * draws
    summary = (
        f"\n=== {restnet.name} vs {usi.name} ({args.time_per_move}s/move) ===\n"
        f"games={total}  W-D-L = {wins}-{draws}-{losses}"
        f"  score={score}/{total} ({100*score/max(total,1):.1f}%)\n"
        f"Elo diff = {shogi_eval.elo_diff(score, total):+.0f}\n"
        f"total time: {(time.time()-t0)/60:.1f} min\n"
    )
    print(summary, flush=True)
    if args.out:
        with open(args.out, "w") as f:
            f.write("\n".join(lines) + "\n" + summary)


if __name__ == "__main__":
    main()
