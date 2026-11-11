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

from attention_presets import MODELS, RECORDS

RECORD = np.dtype([("index", "<u4"), ("orient", "i1"), ("turn", "i1"), ("value", "i1"),
                   ("count", "u1"), ("board", "i1", 12), ("hands", "u1", 6),
                   ("legal", "u1", 17), ("best", "u1", 17), ("win", "u1", 17)])
# Tanaka's piece code (1 chick, 2 elephant, 3 giraffe, 4 hen, 5 lion) -> our plane
# (giraffe, elephant, chick, hen, lion), as in dobutsu.cpp getFeatures()
PLANE = torch.tensor([0, 2, 1, 0, 3, 4])
KINDS = ["勝ち", "勝ち（手数0：ライオンを取れる）", "引き分け", "負け", "負け（手数0：トライ済み）"]
SPOT = 128  # records per file looked at before the long run, to refuse the wrong records or model


def models():
    return sorted(Path(MODELS).glob("*/model/weight_iter_40000.pt"))


def kind(r):
    finished = (r["count"] == 0) & (r["value"] != 0)
    return np.select([(r["value"] == 1) & ~finished, (r["value"] == 1) & finished, r["value"] == 0,
                      (r["value"] == -1) & ~finished], [0, 1, 2, 3], 4)


def features(r, device):
    """The 19 input planes of our environment (dobutsu.cpp getFeatures) for a position seen for
    the first time at an unknown move number: the board turned to the side to move (square s is
    11 - s for white), own pieces 0-4, opponent's 5-9, first occurrence 10, own hand 12-14,
    opponent's 15-17, black to move 18."""
    n = len(r)
    board = torch.as_tensor(r["board"].astype(np.int64), device=device)
    turn = torch.as_tensor(r["turn"].astype(np.int64), device=device)[:, None]
    x = torch.zeros(n, 19, 12, device=device)
    rows, squares = (board != 0).nonzero(as_tuple=True)
    piece = board[rows, squares]
    plane = PLANE.to(device)[piece.abs()] + 5 * (torch.sign(piece) != turn[rows, 0])
    x[rows, plane, torch.where(turn[rows, 0] == 1, squares, 11 - squares)] = 1
    x[:, 10] = 1
    hands = torch.as_tensor(r["hands"].astype(np.float32), device=device)
    black = turn == 1
    x[:, 12:15] = torch.where(black, hands[:, :3], hands[:, 3:])[:, :, None]
    x[:, 15:18] = torch.where(black, hands[:, 3:], hands[:, :3])[:, :, None]
    x[:, 18] = black.float()
    return x.view(n, 19, 4, 3)


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


def require_v2_records(r, name):
    """Stop unless the legal moves are action ids in the mover's frame, drops first (dobutsu_all.cc
    since 5346c97): a drop lands on an empty square with the piece in hand, a move starts on the
    mover's own piece. Older records fit the same layout and give wrong numbers without an error."""
    rows, a = bits(r["legal"]).numpy().nonzero()
    black = r["turn"][rows] == 1
    drop = a < 36
    square = np.where(drop, a % 12, (a - 36) // 8)
    piece = r["board"][rows, np.where(black, square, 11 - square)]
    hand = r["hands"][rows, np.where(black, 0, 3) + np.minimum(a // 12, 2)]
    ok = np.where(drop, (piece == 0) & (hand > 0), np.sign(piece) == r["turn"][rows])
    if not ok.all():
        sys.exit("%s は v2 の行動番号の記録ではない（合法手 %d 個のうち %d 個が局面と合わない）" % (name, len(ok), (~ok).sum()))


def require_v2_model(model, r, path, device):
    """Stop unless the network has our 19 planes and 132 actions and its policy is on the legal
    moves: the v2 models put 0.97 or more there, and about 0.04 on records in another frame."""
    if (model.get_num_input_channels(), model.get_action_size()) != (19, 132):
        sys.exit("%s は v2 のモデルではない（入力 %d 平面、行動 %d 個）" % (
            path, model.get_num_input_channels(), model.get_action_size()))
    with torch.no_grad():
        policy = model(features(r, device))["policy"].float().cpu()
    on_legal = (policy * bits(r["legal"])).sum(1).mean()
    if on_legal < 0.5:
        sys.exit("%s は記録と行動番号が合わない（合法手の policy の和の平均 %.4f）" % (path, on_legal))


def check(path, device):
    r = np.fromfile(path, dtype=RECORD)
    assert len(r) % 4 == 0 and (r["orient"].reshape(-1, 4) == [0, 1, 2, 3]).all()
    require_v2_records(r, path)
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
        model = load(path, device)
        require_v2_model(model, r[:SPOT], path, device)
        chosen = choose(model, r, device)
        hit = best[torch.arange(len(r)), chosen].numpy().reshape(-1, 4)
        differ = (hit != hit[:, :1]).any(1)
        print("%-7s %.4f   %s" % (path.parts[-3], differ.mean(),
                                  " ".join("%.4f" % hit[:, o].mean() for o in range(4))))
        kept = win[torch.arange(len(r)), chosen].numpy()
        for i in np.nonzero((r["value"] == 1) & ~kept)[0]:
            lost.append((path.parts[-3], int(r["index"][i]), int(r["orient"][i]), int(chosen[i])))
    with open(RECORDS + "/lost_wins.csv", "w", newline="") as f:
        csv.writer(f).writerows([("構成", "局面番号", "向き", "選んだ手")] + lost)
    print("勝ちの局面で勝ちの手を選ばなかった", len(lost), "件を", RECORDS + "/lost_wins.csv に書いた")


def full(directory, device):
    """Mistakes as Haque, Wei and Mueller (ACG 2021) count them: a move that changes the
    outcome (a win to not a win, a draw to a loss), over the winning and drawing
    positions where some move would change it. Any move that keeps the outcome is right."""
    files = sorted(glob.glob(str(Path(directory) / "*.bin")))
    if not files:
        sys.exit("%s に記録（*.bin）がない" % directory)
    spot = np.concatenate([np.fromfile(name, dtype=RECORD, count=SPOT) for name in files])
    require_v2_records(spot, directory)
    rows, depth_rows = [], []
    for path in models():
        model = load(path, device)
        require_v2_model(model, spot, path, device)
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
        # the paper's share leaves out the lost positions already tried, where every move is best
        print("%-7s 最善手を選んだ割合 %.4f、誤り：勝ち %.4f、引き分け %.4f、合計 %.4f" % (
            path.parts[-3], best_hits[:4].sum() / max(n[:4].sum(), 1), mistakes[:2].sum() / max(can_err[:2].sum(), 1),
            mistakes[2] / max(can_err[2], 1), mistakes.sum() / max(can_err.sum(), 1)), file=sys.stderr)
    tag = Path(directory).name  # one result per orientation folder
    with open(Path(directory).parent / ("agreement_%s.csv" % tag), "w", newline="") as f:
        csv.writer(f).writerows([("構成", "局面の種類", "局面数", "最善手を選んだ数", "勝ちの手を選んだ数",
                                  "誤りがありうる局面数", "誤りの数")] + rows)
    with open(Path(directory).parent / ("mistakes_by_depth_%s.csv" % tag), "w", newline="") as f:
        csv.writer(f).writerows([("構成", "勝ちまでの手数", "誤りがありうる勝ちの局面数", "誤りの数")] + depth_rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["check", "full"])
    ap.add_argument("path")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    (check if args.mode == "check" else full)(args.path, args.device)
