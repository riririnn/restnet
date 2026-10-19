"""Problem positions for the Attention Map presets of the two viewers.

  dobutsu  -> data/attention_presets_dobutsu.npz, read by scripts/dobutsu_viewer.py
             lost : wins the network threw away (data/dobutsu_lost_wins.csv),
                    orientations 0 and 2 only, the first 5 per model and orientation
             split: 6T and 6R disagree on a win (moves to the end >= 1) in the first
                    1M positions: only one of them plays a best move, 10 each way
                    per orientation
  shogi    -> data/9x9_attention_premate.npz, read by xai_app.py: the position before
             our last move in every game Suisho5 mated us (usi_matches_server/...),
             with the move the network played

Run inside the container:
  python3 scripts/attention_presets.py dobutsu --device cuda
  PYTHONPATH=build/shogi python3 scripts/attention_presets.py shogi
"""
import argparse
import csv
import glob
import re
import sys
from pathlib import Path

import numpy as np

PART = 5_000_000  # records per file of data/dobutsu_all/full*/


def dobutsu_move(a):
    """Our action id as the console string (dobutsu.cpp getDobutsuActionString)."""
    def square(p):
        return "abc"[p % 3] + str(4 - p // 3)

    if a >= 96:
        return "GEC"[(a - 96) // 12] + "*" + square((a - 96) % 12)
    frm, d = divmod(a, 8)
    dr, dc = [-1, -1, 0, 1, 1, 1, 0, -1][d], [0, 1, 1, 1, 0, -1, -1, -1][d]
    return square(frm) + square((frm // 3 + dr) * 3 + frm % 3 + dc)


def record(dobutsu_all, index, orient):
    """One record of the complete analysis, in the data's orientation (0) or turned round (2)."""
    folder = {0: "full", 2: "full_o2"}[orient]
    path = "data/dobutsu_all/%s/part_%03d.bin" % (folder, index // PART)
    r = np.fromfile(path, dtype=dobutsu_all.RECORD, count=1, offset=(index % PART) * dobutsu_all.RECORD.itemsize)
    assert r["index"][0] == index and r["orient"][0] == orient
    return r


def dobutsu(device):
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dobutsu_all_agreement as A

    side = {0: "先手番", 2: "後手番"}
    recs, labels, kinds = [], [], []
    taken = {}
    with open("data/dobutsu_lost_wins.csv") as f:
        for name, index, orient, move in csv.reader(f):
            if name == "構成" or orient not in ("0", "2"):
                continue
            key = (name, orient)
            if taken.get(key, 0) == 5:
                continue
            taken[key] = taken.get(key, 0) + 1
            recs.append(record(A, int(index), int(orient)))
            labels.append("勝ちを失った %s %s 局面%s 選んだ手 %s" % (name, side[int(orient)], index, dobutsu_move(int(move))))
            kinds.append("lost")

    nets = {n: A.load(Path("models/dobutsu/new/%s/model/weight_iter_40000.pt" % n), device) for n in ("6T", "6R")}
    for orient, folder in ((0, "test"), (2, "test_o2")):
        r = np.fromfile("data/dobutsu_all/%s/part_000.bin" % folder, dtype=A.RECORD)
        best = A.bits(r["best"])
        idx = torch.arange(len(r))
        chosen = {n: A.choose(net, r, device) for n, net in nets.items()}
        hit = {n: best[idx, c].numpy() for n, c in chosen.items()}
        win = A.kind(r) == 0
        for good, bad in (("6T", "6R"), ("6R", "6T")):
            for i in np.nonzero(win & hit[good] & ~hit[bad])[0][:10]:
                recs.append(r[i:i + 1])
                labels.append("%sだけ最善手 %s 局面%d %s %s／%s %s" % (
                    good, side[orient], r["index"][i], good, dobutsu_move(int(chosen[good][i])),
                    bad, dobutsu_move(int(chosen[bad][i]))))
                kinds.append("split")
    out = "data/attention_presets_dobutsu.npz"
    np.savez(out, records=np.concatenate(recs), labels=np.array(labels), kinds=np.array(kinds))
    print(out, len(labels), "局面:", {k: kinds.count(k) for k in set(kinds)})


def shogi():
    import env_py
    env_py.init("configs/9x9_shogi/RRTRRT-bigserver.cfg")
    feats, rec, ply, black, move = [], [], [], [], []
    files = sorted(glob.glob("usi_matches_server/n100_s16_10R/*_loss.usi"),
                   key=lambda p: int(re.search(r"game(\d+)", p).group(1)))
    for path in files:
        head, body = open(path).read().splitlines()[:2]
        moves = body.split()[2:]
        if (len(moves) % 2 == 0) != ("restnet=black" in head):
            continue  # the game did not end on our turn
        env = env_py.Env()
        env.reset()
        for k, m in enumerate(moves):
            if k == len(moves) - 2:
                position = (list(env.get_features()), len(moves) % 2 == 0)
            env.act({a.to_console_string(): a for a in env.get_legal_actions()}[m])
        # mated: the game is over with us to move, so our move was the one before last
        if not env.is_terminal() or env.get_legal_actions():
            continue
        feats.append(position[0])
        black.append(position[1])
        rec.append(path)
        ply.append(len(moves) - 2)
        move.append(moves[-2])
    out = "data/9x9_attention_premate.npz"
    np.savez(out, features=np.array(feats, dtype=np.float16).reshape(len(feats), 362, 9, 9),
             record=np.array(rec), ply=np.array(ply), black=np.array(black), bestmove=np.array(move),
             score=np.array(["mated next"] * len(move)))
    print(out, len(move), "局面（詰まされた対局", len(files), "局のうち）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("game", choices=["dobutsu", "shogi"])
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    dobutsu(args.device) if args.game == "dobutsu" else shogi()
