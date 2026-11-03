"""Does a head's attention weight follow how good a move is?

For every legal move that moves a piece, take the attention weight from the moving piece's
square to the destination. For two moves of the same position, count how often the better
move (by the complete analysis: a win is better the sooner, a loss the later) gets the larger
weight; equal weights count half. 0.5 is chance. A drop has no origin square, so its score is
the mean weight the destination receives from every square, compared among drops only.

Positions: `dobutsu_all TABLEDIR moves N SEED OUT` (scripts/dobutsu_all.cc) writes N random
positions of the complete analysis in all 4 orientations with the outcome of every legal move.
Positions where the opponent's lion can be taken or the try is already made are left out.

Usage:
  python3 scripts/attention_move_rank.py dobutsu RECORDS OUT.csv MODEL.pt [MODEL.pt ...]
The models may be the paper's (20 planes, squares as stored) or the rebuilt environment's
(19 planes, the board turned to the side to move); the layout is read from the model.
"""
import csv
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dobutsu_all_agreement as A  # noqa: E402  the rebuilt environment's planes
from xai_analysis import load_python_model  # noqa: E402

MAX = 64
MOVE_RECORD = np.dtype([("index", "<u4"), ("orient", "i1"), ("turn", "i1"), ("value", "i1"),
                        ("count", "u1"), ("board", "i1", 12), ("hands", "u1", 6), ("n", "u1"),
                        ("action", "u1", MAX), ("outcome", "i1", MAX), ("left", "u1", MAX),
                        ("captured", "i1", MAX)])
DR = np.array([-1, -1, 0, 1, 1, 1, 0, -1])
DC = np.array([0, 1, 1, 1, 0, -1, -1, -1])
LION = 5
BATCH = 2048
MB, MD = 24, 40  # the most board moves and drops a position can have (checked when read)


def features_paper(r, device):
    """The 20 planes of the paper's models (the environment of 2026-10): squares as stored,
    own pieces 0-4, opponent's 5-9, own hand 10-12, opponent's 13-15, black 16, white 17,
    first occurrence 18."""
    n = len(r)
    board = torch.as_tensor(r["board"].astype(np.int64), device=device)
    turn = torch.as_tensor(r["turn"].astype(np.int64), device=device)[:, None]
    x = torch.zeros(n, 20, 12, device=device)
    rows, squares = (board != 0).nonzero(as_tuple=True)
    piece = board[rows, squares]
    plane = A.PLANE.to(device)[piece.abs()] + 5 * (torch.sign(piece) != turn[rows, 0])
    x[rows, plane, squares] = 1
    hands = torch.as_tensor(r["hands"].astype(np.float32), device=device)
    black = turn == 1
    x[:, 10:13] = torch.where(black, hands[:, :3], hands[:, 3:])[:, :, None]
    x[:, 13:16] = torch.where(black, hands[:, 3:], hands[:, :3])[:, :, None]
    x[:, 16] = black.float()
    x[:, 17] = (~black).float()
    x[:, 18] = 1
    return x.view(n, 20, 4, 3)


def decode(action, black):
    """A mover's-frame action id -> (is_drop, kind, from_abs, to_abs, dir_abs) as stored."""
    drop = action < 36
    kind = np.where(drop, action // 12, 0)
    to_rel = np.where(drop, action % 12, 0)
    frm_rel, d_rel = np.divmod(np.where(drop, 0, action - 36), 8)
    frm = np.where(black, frm_rel, 11 - frm_rel)
    d = np.where(black, d_rel, (d_rel + 4) % 8)
    to_move = frm + DR[d] * 3 + DC[d]
    to = np.where(drop, np.where(black, to_rel, 11 - to_rel), to_move)
    return drop, kind, frm, to, d


def quality(outcome, left):
    """Larger is better for the mover: a win sooner, then a draw, then a loss later."""
    return outcome * 1000 + np.where(outcome == 1, -left.astype(int), np.where(outcome == -1, left.astype(int), 0))


def load_records(path):
    r = np.fromfile(path, dtype=MOVE_RECORD)
    finished = (r["count"] == 0) & (r["value"] != 0)
    lion = (r["captured"] == LION).any(1)  # the opponent's lion can be taken
    print("finished %d, lion can be taken %d, both %d" % (finished.sum(), lion.sum(), (finished & lion).sum()))
    r = r[~finished & ~lion]
    n = r["n"].astype(int)
    assert (n <= MAX).all()
    return r


class Prepared:
    """Per input: the board moves and the drops with their squares, quality and policy ids."""

    def __init__(self, r, layout):
        N = len(r)
        black = r["turn"] == 1
        idx = np.arange(MAX)[None, :]
        valid = idx < r["n"][:, None]
        drop, kind, frm, to, d = decode(r["action"].astype(int), black[:, None])
        key = quality(r["outcome"].astype(int), r["left"])
        key = np.where(valid, key, -10 ** 6)
        self.best_key = key.max(1)
        assert (r["outcome"][valid] != 2).all(), "an unknown outcome in an unfinished position"
        # squares in the network's frame
        if layout == "paper":
            q, k = frm, to
            pol = np.where(drop, 96 + kind * 12 + to, frm * 8 + d)
        else:
            q = np.where(black[:, None], frm, 11 - frm)
            k = np.where(black[:, None], to, 11 - to)
            pol = r["action"].astype(int)
        board = valid & ~drop
        drops = valid & drop
        assert board.sum(1).max() <= MB and drops.sum(1).max() <= MD, (board.sum(1).max(), drops.sum(1).max())

        def pack(mask, width, *arrays):
            order = np.argsort(~mask, axis=1, kind="stable")[:, :width]  # the masked entries first
            keep = np.take_along_axis(mask, order, 1)
            return keep, [np.where(keep, np.take_along_axis(a, order, 1), fill) for a, fill in arrays]

        self.N = N
        self.b_keep, (self.b_q, self.b_k, self.b_key, self.b_cap, self.b_out, self.b_left, self.b_pol) = pack(
            board, MB, (q, 0), (k, 0), (key, -10 ** 6), (r["captured"].astype(int), 0),
            (r["outcome"].astype(int), 0), (r["left"].astype(int), 0), (pol, 0))
        self.d_keep, (self.d_k, self.d_key, self.d_pol) = pack(drops, MD, (k, 0), (key, -10 ** 6), (pol, 0))
        self.pol_all = np.where(valid, pol, 0)
        self.valid = valid
        self.key_all = key


def pair_stats(w, key, keep, questions):
    """w: (n, H, M) scores, key: (n, M), keep: (n, M). For each question (a (n, M, M) mask of
    ordered pairs where i should beat j) return [sum over pairs of [w_i > w_j] + 0.5 [w_i == w_j],
    number of pairs] per head."""
    both = keep[:, :, None] & keep[:, None, :]
    diff = w[:, :, :, None] - w[:, :, None, :]  # (n, H, M, M)
    hit = (diff > 0).astype(np.float32) + 0.5 * (diff == 0)
    out = {}
    for name, mask in questions(key, both).items():
        pairs = mask.sum()
        out[name] = (np.einsum("nhij,nij->h", hit, mask.astype(np.float32)), float(pairs))
    return out


def board_questions(p, chunk, pol_move):
    """The ordered pair masks for board moves of inputs `chunk`."""
    key = p.b_key[chunk]
    out = p.b_out[chunk]
    left = p.b_left[chunk]
    cap = p.b_cap[chunk] != 0
    best = key == p.best_key[chunk][:, None]
    nocap = ~cap

    def q(key, both):
        better = (key[:, :, None] > key[:, None, :]) & both
        m = {}
        m["best_vs_other"] = best[:, :, None] & ~best[:, None, :] & both
        m["best_vs_other_no_capture"] = m["best_vs_other"] & nocap[:, :, None] & nocap[:, None, :]
        m["all_pairs"] = better
        m["win_vs_draw"] = (out[:, :, None] == 1) & (out[:, None, :] == 0) & both
        m["draw_vs_loss"] = (out[:, :, None] == 0) & (out[:, None, :] == -1) & both
        m["faster_win_vs_slower_win"] = (out[:, :, None] == 1) & (out[:, None, :] == 1) & (left[:, :, None] < left[:, None, :]) & both
        m["capture_vs_no_capture"] = cap[:, :, None] & nocap[:, None, :] & both
        # where the policy's move is not a best move: the policy's move against the others
        chosen = pol_move[:, :, None] & both
        wrong = ~(pol_move & best).any(1)[:, None, None]
        m["policy_move_vs_other_where_policy_wrong"] = chosen & ~pol_move[:, None, :] & wrong
        m["best_vs_other_where_policy_wrong"] = m["best_vs_other"] & wrong
        return m
    return q


def drop_questions(p, chunk):
    key = p.d_key[chunk]
    best = key == p.best_key[chunk][:, None]

    def q(key, both):
        return {"best_drop_vs_other_drop": best[:, :, None] & ~best[:, None, :] & both}
    return q


def run(model_path, r, p, layout, device="cpu"):
    net = load_python_model(model_path, device)
    ts = torch.jit.load(model_path, map_location=device)
    ts.eval()
    net.eval()
    feats = features_paper if layout == "paper" else A.features
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    sums, pairs = {}, {}
    max_best = None
    chance_best = 0.0
    chance_all = 0.0  # a move drawn among all legal moves, drops included
    policy_sums, policy_pairs = {}, {}
    H = None
    for start in range(0, p.N, BATCH):
        chunk = slice(start, min(start + BATCH, p.N))
        x = feats(r[chunk], device)
        with torch.no_grad():
            out = net.get_attn_table(x)
            if start == 0:
                ref = ts(x[:8])
                assert (ref["policy"] - out["policy"][:8]).abs().max() < 1e-4, "the Python model differs from the saved one"
            att = out["att_table"]  # per T block: (n, heads, 12, 12), softmax over the last axis
            policy = out["policy"].cpu().numpy()
        if not att:
            return None
        att = torch.stack(att, 1).cpu().numpy()  # (n, T, heads, 12, 12)
        n, T, heads = att.shape[:3]
        H = T * heads
        att = att.reshape(n, H, 12, 12)
        rows = np.arange(n)[:, None]
        # board moves: weight from the moving piece's square to the destination
        w = att[rows[:, :, None], np.arange(H)[None, None, :], p.b_q[chunk][:, :, None], p.b_k[chunk][:, :, None]]
        w = np.transpose(w, (0, 2, 1))  # (n, H, MB)
        w = np.where(p.b_keep[chunk][:, None, :], w, np.nan)
        # the policy's move among all legal moves
        pol_legal = np.where(p.valid[chunk], policy[rows, p.pol_all[chunk]], -1)
        pol_id = np.take_along_axis(p.pol_all[chunk], pol_legal.argmax(1)[:, None], 1)  # the action id
        pol_move = (p.b_pol[chunk] == pol_id) & p.b_keep[chunk]
        qs = board_questions(p, chunk, pol_move)
        for name, (s, c) in pair_stats(w, p.b_key[chunk], p.b_keep[chunk], qs).items():
            sums[name] = sums.get(name, 0) + s
            pairs[name] = pairs.get(name, 0) + c
        # the policy's probability on the same scale
        wp = policy[rows, p.b_pol[chunk]][:, None, :].astype(np.float32)
        wp = np.where(p.b_keep[chunk][:, None, :], wp, np.nan)
        for name, (s, c) in pair_stats(wp, p.b_key[chunk], p.b_keep[chunk], qs).items():
            policy_sums[name] = policy_sums.get(name, 0) + s
            policy_pairs[name] = policy_pairs.get(name, 0) + c
        # the move with the largest weight is a best move
        best = (p.b_key[chunk] == p.best_key[chunk][:, None]) & p.b_keep[chunk]
        has_board = p.b_keep[chunk].any(1)
        top = np.nanargmax(np.where(np.isnan(w), -1, w), axis=2)  # (n, H)
        hit = np.take_along_axis(best[:, None, :].repeat(H, 1), top[:, :, None], 2)[:, :, 0] & has_board[:, None]
        max_best = hit.sum(0) if max_best is None else max_best + hit.sum(0)
        chance_best += (best.sum(1)[has_board] / p.b_keep[chunk].sum(1)[has_board]).sum()
        best_all = (p.key_all[chunk] == p.best_key[chunk][:, None]) & p.valid[chunk]
        chance_all += (best_all.sum(1)[has_board] / p.valid[chunk].sum(1)[has_board]).sum()
        # drops: the mean weight the destination receives from every square
        wd = att.mean(2)[rows[:, :, None], np.arange(H)[None, None, :], p.d_k[chunk][:, :, None]]
        wd = np.transpose(wd, (0, 2, 1))
        wd = np.where(p.d_keep[chunk][:, None, :], wd, np.nan)
        for name, (s, c) in pair_stats(wd, p.d_key[chunk], p.d_keep[chunk], drop_questions(p, chunk)).items():
            sums[name] = sums.get(name, 0) + s
            pairs[name] = pairs.get(name, 0) + c
        wpd = policy[rows, p.d_pol[chunk]][:, None, :].astype(np.float32)
        wpd = np.where(p.d_keep[chunk][:, None, :], wpd, np.nan)
        for name, (s, c) in pair_stats(wpd, p.d_key[chunk], p.d_keep[chunk], drop_questions(p, chunk)).items():
            policy_sums[name] = policy_sums.get(name, 0) + s
            policy_pairs[name] = policy_pairs.get(name, 0) + c
    n_board = int(p.b_keep.any(1).sum())
    heads = H // len(blocks)
    rows_out = []
    for h in range(H):
        row = {"model": model_path, "block": blocks[h // heads] + 1, "head": h % heads + 1}
        for name in sums:
            row[name] = sums[name][h] / pairs[name] if pairs[name] else float("nan")
        row["max_is_best"] = max_best[h] / n_board
        rows_out.append(row)
    policy_row = {"model": model_path, "block": 0, "head": 0}
    for name in policy_sums:
        policy_row[name] = policy_sums[name][0] / policy_pairs[name] if policy_pairs[name] else float("nan")
    policy_row["max_is_best"] = float("nan")
    chance = {"model": model_path, "block": -1, "head": -1, "max_is_best": chance_best / n_board,
              "max_is_best_among_all_legal": chance_all / n_board}
    for name in sums:
        chance[name] = 0.5
    return rows_out, policy_row, chance, {k: int(v) for k, v in pairs.items()}


def main():
    game, records, out = sys.argv[1], sys.argv[2], sys.argv[3]
    assert game == "dobutsu"
    r = load_records(records)
    print("inputs after leaving out finished positions: %d of %d" % (len(r), len(np.fromfile(records, dtype=MOVE_RECORD))))
    prepared = {}
    rows = []
    for model_path in sys.argv[4:]:
        ts = torch.jit.load(model_path, map_location="cpu")
        layout = "paper" if ts.get_num_input_channels() == 20 else "rebuilt"
        if layout not in prepared:
            prepared[layout] = Prepared(r, layout)
        res = run(model_path, r, prepared[layout], layout)
        if res is None:
            print(model_path, "has no T block")
            continue
        head_rows, policy_row, chance, pairs = res
        rows += head_rows + [policy_row, chance]
        print("== %s (%s layout) pairs %s" % (model_path, layout, pairs))
        for row in head_rows:
            print("  block %d head %d  best %.3f  no-capture %.3f  all %.3f  max-is-best %.1f%%  win/draw %.2f draw/loss %.2f fast/slow %.2f  drops %.2f" % (
                row["block"], row["head"], row["best_vs_other"], row["best_vs_other_no_capture"], row["all_pairs"],
                100 * row["max_is_best"], row["win_vs_draw"], row["draw_vs_loss"], row["faster_win_vs_slower_win"],
                row["best_drop_vs_other_drop"]))
        print("  policy itself: best %.3f  all %.3f  drops %.2f  policy-wrong: policy's move %.3f best %.3f" % (
            policy_row["best_vs_other"], policy_row["all_pairs"], policy_row["best_drop_vs_other_drop"],
            policy_row["policy_move_vs_other_where_policy_wrong"], policy_row["best_vs_other_where_policy_wrong"]))
        print("  chance max-is-best: among board moves %.1f%%, among all legal moves %.1f%%" % (
            100 * chance["max_is_best"], 100 * chance["max_is_best_among_all_legal"]))
    if rows:
        keys = ["model", "block", "head"] + sorted({k for row in rows for k in row} - {"model", "block", "head"})
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in rows:
                w.writerow(row)
        print("wrote", out)


if __name__ == "__main__":
    main()
