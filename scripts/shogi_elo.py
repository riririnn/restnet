#!/usr/bin/env python3
"""
Round-robin Elo rating for shogi models (AlphaZero-style self-iteration Elo).

Plays every pair of the given restnet models against each other, then fits
maximum-likelihood Elo ratings (Bradley-Terry model) to the full win/draw/loss
matrix -- so the whole set of models sits on one consistent Elo axis instead of
isolated pairwise win rates.

The axis is relative by default (mean Elo = 0). Pass --anchor NAME=ELO to shift
it so a chosen player equals a known rating, giving absolute Elo. The anchor is
usually an external engine of known strength added to the model list (that
requires a USI-vs-restnet game driver, not yet implemented -- see note below),
but you can also anchor a self-model whose absolute Elo you measured separately.

Two subcommands:
  run   play the round robin (reuses scripts/shogi_eval.py), save results, rate
  rate  recompute Elo from a saved results file (add/adjust anchors, no replay)

Usage (inside the container, from /workspace):
  # play 20 games per pair among five checkpoints, save, and rate
  python3 scripts/shogi_elo.py run \
      --conf configs/9x9_shogi/RRTRRT-bigserver.cfg --games 20 \
      --results elo.json \
      --model shogi_9x9_restnet64_v2/model/weight_iter_10.pt \
      --model shogi_9x9_restnet64_v2/model/weight_iter_30.pt \
      --model shogi_9x9_restnet64_v2/model/weight_iter_50.pt

  # later: re-rate with an anchor, no games replayed
  python3 scripts/shogi_elo.py rate --results elo.json \
      --anchor weight_iter_10.pt=1500
"""

import argparse
import itertools
import json
import math
import os
import sys

# reuse the engine + game driver from the pairwise evaluator
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shogi_eval  # noqa: E402

# default conf_str for rating games: greedy play, no exploration noise, so the
# measured strength reflects the model rather than sampling luck
DEFAULT_EVAL_CONF_STR = (
    "actor_select_action_by_count=true:"
    "actor_select_action_by_softmax_count=false:"
    "actor_use_dirichlet_noise=false"
)


def pair_key(a, b):
    """Order-independent key; also returns whether (a, b) is already sorted."""
    return (a, b) if a <= b else (b, a)


def load_results(path):
    if path and os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {"players": [], "pairs": {}}


def save_results(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_pair(data, a, b):
    """Return the wins/draws record for the sorted pair, creating it if new."""
    lo, hi = pair_key(a, b)
    key = f"{lo}::{hi}"
    rec = data["pairs"].setdefault(key, {"lo": lo, "hi": hi,
                                         "lo_wins": 0, "hi_wins": 0, "draws": 0})
    return rec


def run_round_robin(args):
    data = load_results(args.results) if args.resume else {"players": [], "pairs": {}}

    # fail fast on missing models: a nonexistent .pt makes the engine die at
    # startup, which otherwise only surfaces as a cryptic "engine died" later
    missing = [p for p in args.model if not os.path.isfile(p)]
    if missing:
        sys.exit("model file(s) not found (models are saved every N iters, "
                 "e.g. weight_iter_200/400/...):\n  " + "\n  ".join(missing))

    # build one persistent engine per model (avoids reloading per pairing)
    names, engines = [], {}
    for path in args.model:
        name = os.path.basename(path)
        if name in engines:
            print(f"warning: duplicate model name {name}, skipping", file=sys.stderr)
            continue
        names.append(name)
        engines[name] = (path, shogi_eval.Engine(args.executable, args.conf, path, args.conf_str))
    for n in names:
        if n not in data["players"]:
            data["players"].append(n)

    try:
        for a, b in itertools.combinations(names, 2):
            _, ea = engines[a]
            _, eb = engines[b]
            rec = get_pair(data, a, b)
            for g in range(args.games):
                # alternate colors; 'a' is black on even games
                a_is_black = (g % 2 == 0)
                black, white = (ea, eb) if a_is_black else (eb, ea)
                result, n_moves = shogi_eval.play_game(black, white)
                if result == "D":
                    rec["draws"] += 1
                    tag = "draw"
                else:
                    a_won = (result == "B") == a_is_black
                    winner = a if a_won else b
                    rec[("lo_wins" if winner == rec["lo"] else "hi_wins")] += 1
                    tag = f"{winner} win"
                print(f"{a} vs {b}  g{g}: {tag}  moves={n_moves}", flush=True)
            if args.results:
                save_results(args.results, data)  # checkpoint after each pair
    finally:
        for _, e in engines.values():
            e.close()

    return data


def compute_elo(data, anchors=None, prior=2.0, iters=10000, tol=1e-11):
    """Bradley-Terry MLE Elo from the pairwise matrix, solved by MM iteration.

    prior adds, per player, `prior` virtual games (half won) against a mean-
    strength phantom opponent. This regularizes toward the field mean and keeps
    undefeated/winless players (common early in training) from diverging to
    +/-infinity.
    """
    players = list(data["players"])
    n = len(players)
    idx = {p: i for i, p in enumerate(players)}
    if n == 0:
        return {}

    score = [[0.0] * n for _ in range(n)]   # points i scored vs j
    games = [[0.0] * n for _ in range(n)]
    for rec in data["pairs"].values():
        if rec["lo"] not in idx or rec["hi"] not in idx:
            continue
        i, j = idx[rec["lo"]], idx[rec["hi"]]
        lw, hw, d = rec["lo_wins"], rec["hi_wins"], rec["draws"]
        score[i][j] += lw + 0.5 * d
        score[j][i] += hw + 0.5 * d
        games[i][j] += lw + hw + d
        games[j][i] += lw + hw + d

    gamma = [1.0] * n
    total_pts = [sum(score[i]) for i in range(n)]
    for _ in range(iters):
        new = [0.0] * n
        maxdiff = 0.0
        for i in range(n):
            denom = prior / (gamma[i] + 1.0)  # phantom opponent at gamma=1
            for j in range(n):
                if i != j and games[i][j] > 0:
                    denom += games[i][j] / (gamma[i] + gamma[j])
            num = total_pts[i] + 0.5 * prior
            new[i] = num / denom if denom > 0 else gamma[i]
        # normalize geometric mean to 1 (mean Elo 0) for numerical stability
        logmean = sum(math.log(g) for g in new) / n
        new = [g / math.exp(logmean) for g in new]
        maxdiff = max(abs(a - b) for a, b in zip(new, gamma))
        gamma = new
        if maxdiff < tol:
            break

    elo = {players[i]: 400.0 * math.log10(gamma[i]) for i in range(n)}

    # anchor: shift the whole scale so anchored players match their targets
    if anchors:
        offsets = [target - elo[name] for name, target in anchors.items() if name in elo]
        if offsets:
            shift = sum(offsets) / len(offsets)
            elo = {p: r + shift for p, r in elo.items()}

    return elo, score, games, players, idx


def print_table(data, anchors):
    elo, score, games, players, idx = compute_elo(data, anchors)
    rows = []
    for p in players:
        i = idx[p]
        pts = sum(score[i])
        gp = sum(games[i])
        # reconstruct W/D/L for display
        wins = draws = losses = 0
        for rec in data["pairs"].values():
            if p == rec["lo"]:
                wins += rec["lo_wins"]; losses += rec["hi_wins"]; draws += rec["draws"]
            elif p == rec["hi"]:
                wins += rec["hi_wins"]; losses += rec["lo_wins"]; draws += rec["draws"]
        rows.append((elo[p], p, wins, draws, losses, gp, pts))
    rows.sort(reverse=True)

    anchor_note = ""
    if anchors:
        anchor_note = "  (anchored: " + ", ".join(f"{k}={v}" for k, v in anchors.items()) + ")"
    else:
        anchor_note = "  (relative, mean Elo = 0)"
    print(f"\n=== Elo ratings{anchor_note} ===")
    print(f"{'Elo':>6} {'model':<28} {'W':>4} {'D':>4} {'L':>4} {'games':>6} {'score%':>7}")
    for r, p, w, d, l, gp, pts in rows:
        pct = 100 * pts / gp if gp else 0.0
        print(f"{r:>6.0f} {p:<28} {w:>4} {d:>4} {l:>4} {int(gp):>6} {pct:>6.1f}%")


def parse_anchors(anchor_args):
    anchors = {}
    for a in anchor_args or []:
        if "=" not in a:
            sys.exit(f"bad --anchor '{a}', expected NAME=ELO")
        name, val = a.rsplit("=", 1)
        anchors[name] = float(val)
    return anchors


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="play the round robin, save results, rate")
    r.add_argument("--conf", required=True)
    r.add_argument("--model", action="append", required=True,
                   help="model .pt (repeat for each participant)")
    r.add_argument("--games", type=int, default=20, help="games per pair")
    r.add_argument("--executable", default="build/shogi/restnet_shogi")
    r.add_argument("--conf_str", default=DEFAULT_EVAL_CONF_STR)
    r.add_argument("--results", default="elo.json", help="results JSON to write")
    r.add_argument("--resume", action="store_true",
                   help="add to an existing results file instead of overwriting")
    r.add_argument("--anchor", action="append", help="NAME=ELO to fix the scale")

    t = sub.add_parser("rate", help="recompute Elo from saved results")
    t.add_argument("--results", required=True)
    t.add_argument("--anchor", action="append", help="NAME=ELO to fix the scale")

    args = ap.parse_args()
    anchors = parse_anchors(args.anchor)

    if args.cmd == "run":
        data = run_round_robin(args)
    else:
        data = load_results(args.results)
        if not data["players"]:
            sys.exit(f"no players found in {args.results}")

    print_table(data, anchors)


if __name__ == "__main__":
    main()
