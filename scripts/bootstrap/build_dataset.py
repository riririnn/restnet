#!/usr/bin/env python3
"""Build a bootstrap (supervised pretraining) dataset from lishogi game records.

Downloads games of highly-rated lishogi players and converts them into the
record format minizero's learner already reads (TRAIN_DIR/sgf/N.sgf, one game
per line), so the policy/value network can be pretrained on human games before
self-play starts.

No MCTS visit counts exist for human moves, so no P[] tag is written; the
loader then falls back to a one-hot policy target on the played move
(minizero/minizero/environment/base/base_env.h). The value target comes from
the RE tag, using the same +1/-1/0 (black's perspective) convention as
ShogiEnv::getEvalScore.

Usage:
    # look at the rating distribution first, without writing a dataset
    scripts/bootstrap/build_dataset.py --max-users 30 --games-per-user 20 --stats

    # then build it with a chosen threshold
    scripts/bootstrap/build_dataset.py --min-rating 2200 --games-per-user 300
"""
import argparse
import heapq
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shogi_coords import usi_to_action_id  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(REPO, "data/bootstrap/raw")
SGF_DIR = os.path.join(REPO, "data/bootstrap/sgf")
UA = "restnet-research/1.0 (shogi bootstrap dataset; contact via github.com/riririnn/restnet)"
PERF = "realTime"                                   # lishogi's main standard-shogi rating pool
BAD_STATUS = {"noStart", "cheat", "illegalMove", "unknownFinish"}   # not real games
TEST_GAMES = 3000                                   # held out so overfitting is visible


def get(url, accept="application/json", pause=1.0, retries=4):
    """GET with a polite pause, backing off on 429/5xx. Returns text, or None."""
    for attempt in range(retries):
        time.sleep(pause * (2 ** attempt) if attempt else pause)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code != 429 and e.code < 500:
                print(f"  ! HTTP {e.code} {url}", file=sys.stderr)
                return None
        except OSError as e:
            print(f"  ! {e} {url}", file=sys.stderr)
    return None


def strong_players(min_rating, pause):
    """The rating leaderboard, strongest first. Ratings come from the table itself,
    so no extra API call per player is needed."""
    html = get(f"https://lishogi.org/player/top/200/{PERF}", accept="text/html", pause=pause) or ""
    rows = re.findall(r'href="/@/([^"/]+)".*?</a></td><td>(\d+)</td>', html, re.S)
    players = [(n, int(r)) for n, r in rows if int(r) >= min_rating]
    print(f"leaderboard: {len(rows)} players, {len(players)} rated >= {min_rating}")
    return players


def download(players, target_games, games_per_user, min_rating, pause):
    """Collect games until target_games distinct *usable* ones (both sides
    >= min_rating) are held.

    Strong players mostly face weaker opponents, so only a fraction of what is
    fetched survives the filter. The leaderboard alone runs dry well short of a
    large target, so once it is exhausted we keep going through opponents who
    were themselves rated >= min_rating -- they are strong players too, just
    outside the top 200."""
    os.makedirs(RAW_DIR, exist_ok=True)
    # strongest first: lishogi's dan badge is just a rating tier, so ordering by
    # rating is the same as ordering by dan
    queue = [(-r, n) for n, r in players]
    heapq.heapify(queue)
    queued = {n.lower() for n, _ in players}
    seen, usable = set(), set()
    done = 0

    while queue:
        neg_rating, name = heapq.heappop(queue)
        done += 1
        path = os.path.join(RAW_DIR, f"{name}.ndjson")
        if not os.path.exists(path):
            url = (f"https://lishogi.org/api/games/user/{name}"
                   f"?max={games_per_user}&rated=true&perfType={PERF}")
            body = get(url, accept="application/x-ndjson", pause=pause)
            if not body:
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)

        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                g = json.loads(line)
                seen.add(g["id"])
                br, wr = ratings_of(g)
                if not br or not wr or min(br, wr) < min_rating:
                    continue
                usable.add(g["id"])
                # both sides cleared the bar, so both are worth crawling
                for side, rating in (("sente", br), ("gote", wr)):
                    who = g["players"][side].get("user", {}).get("name")
                    if who and who.lower() not in queued:
                        queued.add(who.lower())
                        heapq.heappush(queue, (-rating, who))

        print(f"  [{done}] {name} ({-neg_rating}): {len(usable)} usable / {len(seen)} fetched"
              f" ({len(queue)} players queued)")
        if len(usable) >= target_games:
            break


def load_games():
    """Yield every standard-variant game across the raw ndjson files, deduplicated."""
    seen = set()
    for fn in sorted(os.listdir(RAW_DIR)) if os.path.isdir(RAW_DIR) else []:
        if not fn.endswith(".ndjson"):
            continue
        with open(os.path.join(RAW_DIR, fn), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                g = json.loads(line)
                if g.get("variant") != "standard" or g["id"] in seen:
                    continue
                seen.add(g["id"])
                yield g


def is_bot(game):
    """lishogi marks engine accounts with a BOT title; they are not human games."""
    return any(game["players"][side].get("user", {}).get("title") == "BOT"
               for side in ("sente", "gote"))


def ratings_of(game):
    p = game.get("players", {})
    return p.get("sente", {}).get("rating"), p.get("gote", {}).get("rating")


def to_record(game):
    """minizero record line, or None if any move fails to encode."""
    actions = []
    for i, move in enumerate(game.get("moves", "").split()):
        is_black = (i % 2 == 0)
        try:
            actions.append((("B" if is_black else "W"), usi_to_action_id(move, is_black)))
        except ValueError:
            return None
    if not actions:
        return None
    winner = game.get("winner")
    result = 1 if winner == "sente" else -1 if winner == "gote" else 0
    br, wr = ratings_of(game)
    tags = f"(;GM[shogi]SZ[9]RE[{result}]EV[lishogi]BR[{br or 0}]WR[{wr or 0}]"
    return tags + "".join(f";{c}[{a}]" for c, a in actions) + ")"


def show_stats(games):
    """Rating distribution and how many games survive each candidate threshold."""
    pairs = [(min(br, wr), len(g.get("moves", "").split()))
             for g in games for br, wr in [ratings_of(g)] if br and wr]
    if not pairs:
        print("no games with ratings on both sides")
        return
    lower = sorted(r for r, _ in pairs)
    print(f"\ngames with both ratings: {len(lower)}")
    print(f"lower-of-two rating: min {lower[0]}  median {lower[len(lower) // 2]}  max {lower[-1]}")
    print(f"average game length: {sum(n for _, n in pairs) / len(pairs):.0f} moves")
    print("\n threshold | games kept")
    print(" ----------+-----------")
    for t in range(1400, 2601, 100):
        print(f"   {t:>4}    | {sum(1 for r in lower if r >= t):>6}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-rating", type=int, default=2000,
                    help="both players must be at least this strong (default 2000)")
    ap.add_argument("--target-games", type=int, default=10000,
                    help="stop downloading once this many distinct games are collected")
    ap.add_argument("--games-per-user", type=int, default=300, help="games to fetch per player")
    ap.add_argument("--min-moves", type=int, default=20, help="skip games shorter than this")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--stats", action="store_true", help="only report the rating distribution")
    ap.add_argument("--no-fetch", action="store_true", help="convert what is already downloaded")
    args = ap.parse_args()

    if not args.no_fetch:
        # the player cutoff is deliberately loose while surveying, so --stats sees a real spread
        cutoff = 1500 if args.stats else args.min_rating
        download(strong_players(cutoff, args.pause),
                 args.target_games, args.games_per_user, args.min_rating, args.pause)

    games = list(load_games())
    print(f"\ntotal games downloaded: {len(games)}")

    if args.stats:
        show_stats(games)
        return

    records = []
    short = weak = aborted = bot = failed = 0
    for g in games:
        br, wr = ratings_of(g)
        if not br or not wr or min(br, wr) < args.min_rating:
            weak += 1
        elif g.get("status") in BAD_STATUS:
            aborted += 1
        elif is_bot(g):
            bot += 1
        elif len(g.get("moves", "").split()) < args.min_moves:
            short += 1
        elif (record := to_record(g)) is None:
            failed += 1
        else:
            records.append(record)

    # held-out games, so training can be watched for overfitting
    random.Random(0).shuffle(records)
    os.makedirs(SGF_DIR, exist_ok=True)
    for name, part in (("test", records[:TEST_GAMES]),
                       ("train", records[TEST_GAMES:])):
        path = os.path.join(SGF_DIR, f"{name}.sgf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(part) + "\n")
        print(f"wrote {len(part)} games to {path}")
    print(f"skipped: {weak} below rating, {aborted} aborted/illegal, {bot} bot games, "
          f"{short} too short, {failed} unconvertible")


if __name__ == "__main__":
    main()
