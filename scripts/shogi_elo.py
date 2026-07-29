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
import random
import re
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


class Logger:
    """Print to the screen and, if a path is given, append to a log file with
    timestamps (so a long round robin leaves a Training.log-style record)."""

    def __init__(self, path=None):
        self.fh = open(path, "a") if path else None

    def log(self, msg, timestamp=True):
        print(msg, flush=True)
        if self.fh:
            import datetime
            prefix = datetime.datetime.now().strftime("[%Y/%m/%d %H:%M:%S] ") if timestamp else ""
            self.fh.write(prefix + msg + "\n")
            self.fh.flush()

    def close(self):
        if self.fh:
            self.fh.close()


def get_pair(data, a, b):
    """Return the wins/draws record for the sorted pair, creating it if new."""
    lo, hi = pair_key(a, b)
    key = f"{lo}::{hi}"
    rec = data["pairs"].setdefault(key, {"lo": lo, "hi": hi,
                                         "lo_wins": 0, "hi_wins": 0, "draws": 0})
    return rec


def run_round_robin(args, logger):
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
                logger.log(f"{a} vs {b}  g{g}: {tag}  moves={n_moves}")
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
    elif elo:
        # default: shift so the weakest model sits at 0 (all ratings >= 0)
        shift = -min(elo.values())
        elo = {p: r + shift for p, r in elo.items()}

    return elo, score, games, players, idx


def print_table(data, anchors, logger):
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
        anchor_note = "  (relative, weakest model = 0)"
    logger.log(f"\n=== Elo ratings{anchor_note} ===", timestamp=False)
    logger.log(f"{'Elo':>6} {'model':<28} {'W':>4} {'D':>4} {'L':>4} {'games':>6} {'score%':>7}",
               timestamp=False)
    for r, p, w, d, l, gp, pts in rows:
        pct = 100 * pts / gp if gp else 0.0
        logger.log(f"{r:>6.0f} {p:<28} {w:>4} {d:>4} {l:>4} {int(gp):>6} {pct:>6.1f}%",
                   timestamp=False)


def bootstrap_ci(data, anchors, n_boot=300, seed=0):
    """95% confidence interval per player, by resampling each pair's games.

    For every pair we redraw its games (win/draw/loss multinomial) with
    replacement, refit Elo, and repeat; the 2.5/97.5 percentiles of each
    player's refitted Elo give the interval. Needs only the stdlib.
    """
    rng = random.Random(seed)
    players = data["players"]
    pairs = list(data["pairs"].values())
    samples = {p: [] for p in players}

    for _ in range(n_boot):
        bpairs = {}
        for rec in pairs:
            n = rec["lo_wins"] + rec["hi_wins"] + rec["draws"]
            lw = dw = hw = 0
            if n > 0:
                p_lo = rec["lo_wins"] / n
                p_draw = rec["draws"] / n
                for _ in range(n):
                    x = rng.random()
                    if x < p_lo:
                        lw += 1
                    elif x < p_lo + p_draw:
                        dw += 1
                    else:
                        hw += 1
            bpairs[f'{rec["lo"]}::{rec["hi"]}'] = {
                "lo": rec["lo"], "hi": rec["hi"],
                "lo_wins": lw, "hi_wins": hw, "draws": dw}
        elo, *_ = compute_elo({"players": players, "pairs": bpairs}, anchors)
        for p in players:
            samples[p].append(elo[p])

    ci = {}
    for p in players:
        vals = sorted(samples[p])
        lo = vals[max(0, int(0.025 * len(vals)))]
        hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
        ci[p] = (lo, hi)
    return ci


def training_step(name):
    """Extract the training-step number from weight_iter_<N>.pt for the x-axis."""
    m = re.search(r"weight_iter_(\d+)", name)
    return int(m.group(1)) if m else None


def write_report(data, anchors, prefix, logger, n_boot=300):
    """Write <prefix>.csv (always) and <prefix>.png/.pdf (if matplotlib is
    available): the Elo of every model with a bootstrap 95% CI, ready for a
    paper's learning-curve figure."""
    elo, _score, _games, players, _idx = compute_elo(data, anchors)
    logger.log(f"computing bootstrap confidence intervals ({n_boot} resamples)...")
    ci = bootstrap_ci(data, anchors, n_boot=n_boot)

    def wdl(p):
        w = d = l = 0
        for rec in data["pairs"].values():
            if p == rec["lo"]:
                w += rec["lo_wins"]; l += rec["hi_wins"]; d += rec["draws"]
            elif p == rec["hi"]:
                w += rec["hi_wins"]; l += rec["lo_wins"]; d += rec["draws"]
        return w, d, l

    rows = []
    for p in players:
        w, d, l = wdl(p)
        gp = w + d + l
        rows.append({
            "model": p, "training_step": training_step(p),
            "elo": elo[p], "elo_ci_low": ci[p][0], "elo_ci_high": ci[p][1],
            "wins": w, "draws": d, "losses": l, "games": gp,
            "score_pct": 100 * (w + 0.5 * d) / gp if gp else 0.0,
        })
    rows.sort(key=lambda r: (r["training_step"] is None, r["training_step"]))

    csv_path = prefix + ".csv"
    cols = ["model", "training_step", "elo", "elo_ci_low", "elo_ci_high",
            "wins", "draws", "losses", "games", "score_pct"]
    with open(csv_path, "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(f"{r[c]:.2f}" if isinstance(r[c], float) else str(r[c])
                             for c in cols) + "\n")
    logger.log(f"wrote {csv_path}")

    # plot (skip gracefully if matplotlib is missing)
    plot_rows = [r for r in rows if r["training_step"] is not None]
    if not plot_rows:
        logger.log("no weight_iter_<N> models -- skipping plot (CSV only)")
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.log("matplotlib not available -- wrote CSV only")
        return

    xs = [r["training_step"] for r in plot_rows]
    ys = [r["elo"] for r in plot_rows]
    lo = [r["elo"] - r["elo_ci_low"] for r in plot_rows]
    hi = [r["elo_ci_high"] - r["elo"] for r in plot_rows]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(xs, ys, yerr=[lo, hi], marker="o", capsize=3, linewidth=1.5)
    ax.set_xlabel("training steps")
    ax.set_ylabel("Elo" + ("" if anchors else " (relative, weakest = 0)"))
    ax.set_title("ResTNet shogi self-play Elo"
                 + (f"  (anchored: {', '.join(f'{k}={v:g}' for k,v in anchors.items())})"
                    if anchors else ""))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{prefix}.{ext}", dpi=150)
        logger.log(f"wrote {prefix}.{ext}")
    plt.close(fig)


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
    r.add_argument("--log", default="", help="append per-game log + Elo table here")
    r.add_argument("--report", default="",
                   help="write <prefix>.csv + <prefix>.png/.pdf (Elo curve with "
                        "bootstrap 95%% CI) for papers")
    r.add_argument("--n-boot", type=int, default=300,
                   help="bootstrap resamples for the confidence interval")

    t = sub.add_parser("rate", help="recompute Elo from saved results")
    t.add_argument("--results", required=True)
    t.add_argument("--anchor", action="append", help="NAME=ELO to fix the scale")
    t.add_argument("--log", default="", help="append the Elo table here")
    t.add_argument("--report", default="",
                   help="write <prefix>.csv + <prefix>.png/.pdf for papers")
    t.add_argument("--n-boot", type=int, default=300,
                   help="bootstrap resamples for the confidence interval")

    args = ap.parse_args()
    anchors = parse_anchors(args.anchor)
    logger = Logger(args.log or None)

    try:
        if args.cmd == "run":
            data = run_round_robin(args, logger)
        else:
            data = load_results(args.results)
            if not data["players"]:
                sys.exit(f"no players found in {args.results}")

        print_table(data, anchors, logger)
        if args.report:
            write_report(data, anchors, args.report, logger, n_boot=args.n_boot)
    finally:
        logger.close()


if __name__ == "__main__":
    main()
