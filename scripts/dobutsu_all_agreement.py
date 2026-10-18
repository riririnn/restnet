"""Agreement with the complete analysis over every dobutsu position.

Reads the records of scripts/dobutsu_all.cc and judges each one by the network's own
move, with no search: the legal move with the highest policy.

  check FILE   records of `dobutsu_all sample`: how often the four orientations of a
               position get a different verdict, per model
  full DIR     every record file in DIR: mistakes as Haque, Wei and Mueller (ACG 2021)
               count them, and the agreement per kind of position, per model
"""
import argparse
import csv
import glob
import sys
from pathlib import Path

import numpy as np
import torch

RECORD = np.dtype([("index", "<u4"), ("orient", "i1"), ("turn", "i1"), ("value", "i1"),
                   ("count", "u1"), ("board", "i1", 12), ("hands", "u1", 6),
                   ("legal", "u1", 17), ("best", "u1", 17), ("win", "u1", 17)])
# Tanaka's piece code (1 chick, 2 elephant, 3 giraffe, 4 hen, 5 lion) -> our plane
# (giraffe, elephant, chick, hen, lion), as in dobutsu.cpp getFeatures()
PLANE = torch.tensor([0, 2, 1, 0, 3, 4])
KINDS = ["勝ち", "勝ち（手数0：ライオンを取れる）", "引き分け", "負け", "負け（手数0：トライ済み）"]


def models():
    return sorted(Path("models/dobutsu/new").glob("*/model/weight_iter_40000.pt"))


def kind(r):
    finished = (r["count"] == 0) & (r["value"] != 0)
    return np.select([(r["value"] == 1) & ~finished, (r["value"] == 1) & finished, r["value"] == 0,
                      (r["value"] == -1) & ~finished], [0, 1, 2, 3], 4)


def features(r, device):
    """The 20 input planes of our environment; a position seen for the first time."""
    n = len(r)
    board = torch.as_tensor(r["board"].astype(np.int64), device=device)
    turn = torch.as_tensor(r["turn"].astype(np.int64), device=device)[:, None]
    x = torch.zeros(n, 20, 12, device=device)
    rows, squares = (board != 0).nonzero(as_tuple=True)
    piece = board[rows, squares]
    plane = PLANE.to(device)[piece.abs()] + 5 * (torch.sign(piece) != turn[rows, 0])
    x[rows, plane, squares] = 1
    hands = torch.as_tensor(r["hands"].astype(np.float32), device=device)
    black = turn == 1
    x[:, 10:13] = torch.where(black, hands[:, :3], hands[:, 3:])[:, :, None]
    x[:, 13:16] = torch.where(black, hands[:, 3:], hands[:, :3])[:, :, None]
    x[:, 16] = black.float()
    x[:, 17] = (~black).float()
    x[:, 18] = 1
    return x.view(n, 20, 4, 3)


def bits(field):
    return torch.as_tensor(np.unpackbits(field, axis=1, bitorder="little")[:, :132].astype(bool))


def choose(model, r, device, batch=8192):
    """The network's move for every record, as an action id."""
    out = []
    legal = bits(r["legal"])
    for s in range(0, len(r), batch):
        with torch.no_grad():
            policy = model(features(r[s:s + batch], device))["policy"].float().cpu()
        out.append(policy.masked_fill(~legal[s:s + batch], -float("inf")).argmax(1))
    return torch.cat(out)


def load(path, device):
    model = torch.jit.load(str(path), map_location=device)
    model.eval()
    return model


def check(path, device):
    r = np.fromfile(path, dtype=RECORD)
    assert len(r) % 4 == 0 and (r["orient"].reshape(-1, 4) == [0, 1, 2, 3]).all()
    best, win = bits(r["best"]), bits(r["win"])
    # the four are the same position, so they have as many legal and best moves
    for moves in (bits(r["legal"]), best):
        count = moves.sum(1).reshape(-1, 4)
        assert (count == count[:, :1]).all()
    k = kind(r).reshape(-1, 4)[:, 0]
    print("局面 %d（4つの向き）。種類：%s" % (len(r) // 4, ", ".join(
        "%s %d" % (KINDS[i], (k == i).sum()) for i in range(5))))
    print("構成  向きで判定が食い違う局面の割合  向きごとの最善手の割合（1 2 3 4）")
    lost = []
    for path in models():
        chosen = choose(load(path, device), r, device)
        hit = best[torch.arange(len(r)), chosen].numpy().reshape(-1, 4)
        differ = (hit != hit[:, :1]).any(1)
        print("%-7s %.4f   %s" % (path.parts[-3], differ.mean(),
                                  " ".join("%.4f" % hit[:, o].mean() for o in range(4))))
        kept = win[torch.arange(len(r)), chosen].numpy()
        for i in np.nonzero((r["value"] == 1) & ~kept)[0]:
            lost.append((path.parts[-3], int(r["index"][i]), int(r["orient"][i]), int(chosen[i])))
    with open("data/dobutsu_lost_wins.csv", "w", newline="") as f:
        csv.writer(f).writerows([("構成", "局面番号", "向き", "選んだ手")] + lost)
    print("勝ちの局面で勝ちの手を選ばなかった", len(lost), "件を data/dobutsu_lost_wins.csv に書いた")


def full(directory, device):
    """Mistakes as Haque, Wei and Mueller (ACG 2021) count them: a move that changes the
    outcome (a win to not a win, a draw to a loss), over the winning and drawing
    positions where some move would change it. Any move that keeps the outcome is right."""
    files = sorted(glob.glob(str(Path(directory) / "*.bin")))
    rows, depth_rows = [], []
    for path in models():
        model = load(path, device)
        n, best_hits, win_hits, can_err, mistakes = (np.zeros(5, dtype=np.int64) for _ in range(5))
        depth_can_err, depth_mistakes = np.zeros(256, dtype=np.int64), np.zeros(256, dtype=np.int64)
        for name in files:
            r = np.fromfile(name, dtype=RECORD)
            k = kind(r)
            chosen = choose(model, r, device)
            idx = torch.arange(len(r))
            legal, best, win = bits(r["legal"]), bits(r["best"]), bits(r["win"])
            hit, kept = best[idx, chosen].numpy(), win[idx, chosen].numpy()
            # a draw has no winning move, so its best moves are the ones that keep the draw
            keeps = np.where(r["value"] == 1, kept, hit)
            open_ = np.where(r["value"] == 1, (win.sum(1) < legal.sum(1)).numpy(),
                             (r["value"] == 0) & (best.sum(1) < legal.sum(1)).numpy())
            wrong = open_ & ~keeps
            for total, add in ((n, 1), (best_hits, hit), (win_hits, kept), (can_err, open_), (mistakes, wrong)):
                np.add.at(total, k, add)
            won = r["value"] == 1  # decision depth of a win: the moves to its end
            np.add.at(depth_can_err, r["count"][won], open_[won])
            np.add.at(depth_mistakes, r["count"][won], wrong[won])
        for i in range(5):
            if n[i]:
                rows.append((path.parts[-3], KINDS[i], n[i], best_hits[i], win_hits[i], can_err[i], mistakes[i]))
        depth_rows += [(path.parts[-3], d, depth_can_err[d], depth_mistakes[d])
                       for d in range(256) if depth_can_err[d]]
        print("%-7s 誤り：勝ち %.4f、引き分け %.4f、合計 %.4f" % (
            path.parts[-3], mistakes[:2].sum() / max(can_err[:2].sum(), 1),
            mistakes[2] / max(can_err[2], 1), mistakes.sum() / max(can_err.sum(), 1)), file=sys.stderr)
    with open("data/dobutsu_all_agreement.csv", "w", newline="") as f:
        csv.writer(f).writerows([("構成", "局面の種類", "局面数", "最善手を選んだ数", "勝ちの手を選んだ数",
                                  "誤りがありうる局面数", "誤りの数")] + rows)
    with open("data/dobutsu_all_mistakes_by_depth.csv", "w", newline="") as f:
        csv.writer(f).writerows([("構成", "勝ちまでの手数", "誤りがありうる勝ちの局面数", "誤りの数")] + depth_rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["check", "full"])
    ap.add_argument("path")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    (check if args.mode == "check" else full)(args.path, args.device)
