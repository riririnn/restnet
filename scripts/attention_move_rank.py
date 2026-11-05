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
  python3 scripts/attention_move_rank.py shogi GAMES.sgf OUT.csv MODEL.pt [MODEL.pt ...] [--sample F] [--seed S]
  --peaked instead: per head, how far the weights are from even (the largest weight from each square
  times the number of squares, averaged; 1 = even)
The dobutsu models may be the paper's (20 planes, squares as stored) or the rebuilt environment's
(19 planes, the board turned to the side to move); the layout is read from the model.
9x9 shogi has no complete analysis: the move played in the game record (floodgate, engines
rated 2250 or more) is the provisional answer, so only "played vs other" questions are asked.
Every game is replayed in the C++ environment; a fraction F of the positions is drawn at random.
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
        kind_moved = np.abs(np.take_along_axis(r["board"].astype(int), np.where(drop, 0, frm), 1))  # Tanaka's code: 1 chick, 2 elephant, 3 giraffe, 4 hen, 5 lion
        assert board.sum(1).max() <= MB and drops.sum(1).max() <= MD, (board.sum(1).max(), drops.sum(1).max())

        def pack(mask, width, *arrays):
            order = np.argsort(~mask, axis=1, kind="stable")[:, :width]  # the masked entries first
            keep = np.take_along_axis(mask, order, 1)
            return keep, [np.where(keep, np.take_along_axis(a, order, 1), fill) for a, fill in arrays]

        self.N = N
        self.b_keep, (self.b_q, self.b_k, self.b_key, self.b_cap, self.b_out, self.b_left, self.b_pol, self.b_kind) = pack(
            board, MB, (q, 0), (k, 0), (key, -10 ** 6), (r["captured"].astype(int), 0),
            (r["outcome"].astype(int), 0), (r["left"].astype(int), 0), (pol, 0), (kind_moved, 0))
        self.value = r["value"].astype(int)
        self.count = r["count"].astype(int)
        self.n_legal = valid.sum(1)
        self.d_keep, (self.d_k, self.d_key, self.d_pol) = pack(drops, MD, (k, 0), (key, -10 ** 6), (pol, 0))
        self.pol_all = np.where(valid, pol, 0)
        self.valid = valid
        self.key_all = key


def bias_attention(net):
    """Per T block, (heads, N, N): the weights a head would give from its learned relative
    position bias alone, with no board content (the softmax of the bias)."""
    out = []
    for m in net.modules():
        if hasattr(m, "relative_bias_table") and hasattr(m, "relative_index"):
            bias = m.relative_bias_table.gather(0, m.relative_index.repeat(1, m.num_heads))
            out.append(torch.softmax(m.rearrange_rel(bias)[0], dim=-1).detach())
    return out


def untrain(net):
    """The same network with fresh random weights, as it was before training."""
    torch.manual_seed(0)
    for m in net.modules():
        if hasattr(m, "reset_parameters"):
            m.reset_parameters()
    if hasattr(net, "_init_weights_trunc_normal"):
        net.apply(net._init_weights_trunc_normal)
    for m in net.modules():
        if hasattr(m, "relative_bias_table"):
            torch.nn.init.zeros_(m.relative_bias_table)  # as at construction


def peaked(model_path, batches, device="cpu"):
    """Per head: the largest weight from each square, averaged over the squares and the inputs,
    times the number of squares (1 = even weights; the number of squares = all on one square)."""
    ts = torch.jit.load(model_path, map_location=device)
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    if not blocks:
        return []
    net = load_python_model(model_path, device)
    net.eval()
    total, n = 0, 0
    for x in batches:
        with torch.no_grad():
            att = torch.stack(net.get_attn_table(x.to(device))["att_table"], 1)  # (n, T, heads, squares, squares)
        total = total + att.max(-1).values.mean(3).sum(0).cpu().numpy() * att.shape[-1]
        n += len(x)
    return [{"model": model_path, "block": blocks[t] + 1, "head": h + 1, "largest_weight_x_squares": total[t, h] / n}
            for t in range(total.shape[0]) for h in range(total.shape[1])]


def run(model_path, r, p, layout, device="cpu", control="", splits=False):
    """Every head of one model on the teacher's scale. Each comparison is the share of a
    position's pairs that the better move wins (equal weights half), averaged over the positions
    that have such a pair; the same numbers pooled over all pairs are kept with "_pooled".
    control: "" the trained model; "bias" the position bias alone; "untrained" fresh random
    weights; "reverse" the weight from the destination to the moving piece; "rollout" attention
    rollout over all T blocks, as one head. splits: also the table by kind of position and piece."""
    net = load_python_model(model_path, device)
    ts = torch.jit.load(model_path, map_location=device)
    ts.eval()
    if control == "untrained":
        untrain(net)
    net.eval()
    fixed = bias_attention(net) if control == "bias" else None
    feats = features_paper if layout == "paper" else A.features
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    acc = {}

    def add(name, value):
        acc[name] = acc.get(name, 0) + value

    def count(tag, scores, masks):
        """Accumulate hits per input for every question; tag "" for the heads, "policy" for the policy."""
        for name, m in masks.items():
            hits, npairs = pair_hits(scores, m)
            has = npairs > 0
            add(tag + name + "|pos_sum", (hits[has] / npairs[has, None]).sum(0))
            add(tag + name + "|pos_n", float(has.sum()))
            add(tag + name + "|pool_hits", hits.sum(0))
            add(tag + name + "|pool_pairs", float(npairs.sum()))

    H = None
    for start in range(0, p.N, BATCH):
        c = slice(start, min(start + BATCH, p.N))
        x = feats(r[c], device)
        with torch.no_grad():
            out = net.get_attn_table(x)
            if start == 0 and control != "untrained":
                ref = ts(x[:8])
                assert (ref["policy"] - out["policy"][:8]).abs().max() < 1e-4, "the Python model differs from the saved one"
            att = out["att_table"]  # per T block: (n, heads, 12, 12), softmax over the last axis
            if fixed is not None:
                att = [f[None].expand(len(x), -1, -1, -1) for f in fixed]
            if control == "rollout" and att:  # Abnar & Zuidema: the heads' mean, half kept for the residual, multiplied through the blocks
                eye = torch.eye(att[0].shape[-1])
                roll = None
                for a in att:
                    a = 0.5 * a.mean(1) + 0.5 * eye
                    a = a / a.sum(-1, keepdim=True)
                    roll = a if roll is None else torch.bmm(a, roll)
                att = [roll[:, None]]
            policy = out["policy"].cpu().numpy()
        if not att:
            return None
        att = torch.stack(att, 1).cpu().numpy()
        n, T, heads = att.shape[:3]
        H = T * heads
        att = att.reshape(n, H, 12, 12)
        rows = np.arange(n)[:, None]
        hidx = np.arange(H)[None, None, :]
        keep, key, cap = p.b_keep[c], p.b_key[c], p.b_cap[c] != 0
        nocap = keep & ~cap
        # board moves: the weight from the moving piece's square to the destination
        q, k = (p.b_k[c], p.b_q[c]) if control == "reverse" else (p.b_q[c], p.b_k[c])
        w = att[rows[:, :, None], hidx, q[:, :, None], k[:, :, None]]
        w = np.where(keep[:, None, :], np.transpose(w, (0, 2, 1)), np.nan)
        wp = np.where(keep, policy[rows, p.b_pol[c]], np.nan)[:, None, :].astype(np.float32)
        best = (key == p.best_key[c][:, None]) & keep  # a best move of the complete analysis
        out_, left = p.b_out[c], p.b_left[c]
        both = keep[:, :, None] & keep[:, None, :]
        pol_legal = np.where(p.valid[c], policy[rows, p.pol_all[c]], -1)
        pol_id = np.take_along_axis(p.pol_all[c], pol_legal.argmax(1)[:, None], 1)
        pol_move = (p.b_pol[c] == pol_id) & keep
        best_all = (p.key_all[c] == p.best_key[c][:, None]) & p.valid[c]
        pol_wrong = ~(best_all & (p.pol_all[c] == pol_id)).any(1)  # the policy's top legal move is not a best move
        bvo = best[:, :, None] & ~best[:, None, :] & both
        masks = {
            "best_vs_other": bvo,
            "best_vs_other_no_capture": bvo & nocap[:, :, None] & nocap[:, None, :],
            "all_pairs": (key[:, :, None] > key[:, None, :]) & both,
            "win_vs_draw": (out_[:, :, None] == 1) & (out_[:, None, :] == 0) & both,
            "draw_vs_loss": (out_[:, :, None] == 0) & (out_[:, None, :] == -1) & both,
            "faster_win_vs_slower_win": (out_[:, :, None] == 1) & (out_[:, None, :] == 1) & (left[:, :, None] < left[:, None, :]) & both,
            "capture_vs_no_capture": cap[:, :, None] & nocap[:, None, :] & both,
            "policy_move_vs_other_where_policy_wrong": pol_move[:, :, None] & ~pol_move[:, None, :] & both & pol_wrong[:, None, None],
            "best_vs_other_where_policy_wrong": bvo & pol_wrong[:, None, None],
        }
        count("", w, masks)
        count("policy|", wp, masks)
        if splits:
            # per position and head, the share of its pairs the better move wins, grouped by the position's kind
            groups = {"value": p.value[c], "moves_to_end": np.where(p.value[c] == 0, -1, np.digitize(p.count[c], [3, 6, 11, 21])),  # -1: draws
                      "legal_moves": np.digitize(p.n_legal[c], [6, 11, 16, 21])}
            for qname in ("best_vs_other", "all_pairs"):
                hits, npairs = pair_hits(w, masks[qname])
                has = npairs > 0
                frac = np.zeros_like(hits)
                frac[has] = hits[has] / npairs[has, None]
                for gname, g in groups.items():
                    for v in np.unique(g):
                        sel = has & (g == v)
                        add("split|%s|%s|%s" % (qname, gname, v), frac[sel].sum(0))
                        add("split_n|%s|%s|%s" % (qname, gname, v), float(sel.sum()))
                # moves of one kind of piece only
                for kind in range(1, 6):
                    same = (p.b_kind[c] == kind) & keep
                    mk = masks[qname] & same[:, :, None] & same[:, None, :]
                    hits, npairs = pair_hits(w, mk)
                    has = npairs > 0
                    add("split|%s|piece|%d" % (qname, kind), (hits[has] / npairs[has, None]).sum(0))
                    add("split_n|%s|piece|%d" % (qname, kind), float(has.sum()))
        # drops: the mean weight the destination square receives from every square
        dkeep, dkey = p.d_keep[c], p.d_key[c]
        wd = att.mean(2)[rows[:, :, None], hidx, p.d_k[c][:, :, None]]
        wd = np.where(dkeep[:, None, :], np.transpose(wd, (0, 2, 1)), np.nan)
        wpd = np.where(dkeep, policy[rows, p.d_pol[c]], np.nan)[:, None, :].astype(np.float32)
        dbest = (dkey == p.best_key[c][:, None]) & dkeep  # a drop that is a best move overall (the teacher's 13,864 inputs)
        dmasks = {"best_drop_vs_other_drop": dbest[:, :, None] & ~dbest[:, None, :] & dkeep[:, :, None] & dkeep[:, None, :]}
        count("", wd, dmasks)
        count("policy|", wpd, dmasks)
        # the largest weight is on a best move: among the board moves, in the positions whose board
        # moves are not all equally good; chance is a board move drawn at random
        kb = np.where(keep, key, -10 ** 6)
        best_board = (key == kb.max(1)[:, None]) & keep
        differ = keep.any(1) & (np.where(keep, key, 10 ** 6).min(1) != kb.max(1))
        top = np.argmax(np.where(np.isnan(w), -1, w), axis=2)
        hit = np.take_along_axis(best_board[:, None, :].repeat(H, 1), top[:, :, None], 2)[:, :, 0]
        add("max_is_best", hit[differ].sum(0))
        add("max_is_best|n", float(differ.sum()))
        wrong = differ & pol_wrong  # where the policy's top legal move is not a best move
        add("max_is_best_where_policy_wrong", hit[wrong].sum(0))
        add("max_is_best_where_policy_wrong|n", float(wrong.sum()))
        add("max_is_best|chance", (best_board.sum(1)[differ] / keep.sum(1)[differ]).sum())
        has_board = keep.any(1)  # the teacher's chance (18.9%): best board moves over all legal moves, every position
        add("max_is_best|chance_legal", (best.sum(1)[has_board] / p.valid[c].sum(1)[has_board]).sum())
        add("max_is_best|n_board", float(has_board.sum()))
        add("inputs|policy_wrong", float((pol_wrong & keep.any(1)).sum()))
    if control == "rollout":
        blocks = [98]  # one row, labelled block 99: attention rollout over all T blocks
    heads = H // len(blocks)

    def values(tag, h, names):
        row = {}
        for name in names:
            row[name] = acc[tag + name + "|pos_sum"][h] / acc[tag + name + "|pos_n"] if acc[tag + name + "|pos_n"] else float("nan")
            row[name + "_pooled"] = acc[tag + name + "|pool_hits"][h] / acc[tag + name + "|pool_pairs"] if acc[tag + name + "|pool_pairs"] else float("nan")
        return row

    names = list(masks) + list(dmasks)
    rows_out = []
    for h in range(H):
        row = {"model": model_path, "block": blocks[h // heads] + 1, "head": h % heads + 1}
        row.update(values("", h, names))
        row["max_is_best"] = acc["max_is_best"][h] / acc["max_is_best|n"]
        row["max_is_best_where_policy_wrong"] = acc["max_is_best_where_policy_wrong"][h] / acc["max_is_best_where_policy_wrong|n"]
        for name in acc:
            if name.startswith("split|"):
                n_ = acc["split_n|" + name[6:]]
                row[name] = acc[name][h] / n_ if n_ else float("nan")
                row["n|" + name[6:]] = n_
        rows_out.append(row)
    policy_row = {"model": model_path, "block": 0, "head": 0}
    policy_row.update(values("policy|", 0, names))
    chance = {"model": model_path, "block": -1, "head": -1, "max_is_best": acc["max_is_best|chance"] / acc["max_is_best|n"],
              "max_is_best_chance_legal": acc["max_is_best|chance_legal"] / acc["max_is_best|n_board"]}
    for name in names:
        chance[name] = 0.5
    inputs = {name: int(acc[name + "|pos_n"]) for name in names}
    inputs["max_is_best"] = int(acc["max_is_best|n"])
    inputs["policy_wrong"] = int(acc["inputs|policy_wrong"])
    return rows_out, policy_row, chance, inputs


def ablation(model_path, r, p, layout, device="cpu"):
    """Switch one head off at a time (its weights replaced by uniform weights, through a hook on
    the softmax; the model code is not changed) and measure what the model loses: the policy on
    the teacher's scale (best move vs other board moves, per position), how often the policy's
    top legal move is a best move, and how often the sign of the value matches the analysis.
    The first row (block 0) is the model with nothing switched off."""
    net = load_python_model(model_path, device)
    net.eval()
    feats = features_paper if layout == "paper" else A.features
    softmaxes = [m.attend for m in net.modules() if hasattr(m, "relative_bias_table")]
    heads = next(m for m in net.modules() if hasattr(m, "relative_bias_table")).num_heads
    ts = torch.jit.load(model_path, map_location=device)
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    black = r["turn"] == 1
    target = r["value"].astype(int)  # for the side to move: 1 win, 0 draw, -1 loss
    rows_out = []
    for off in [None] + [(b, h) for b in range(len(softmaxes)) for h in range(heads)]:
        handle = None
        if off is not None:
            def hook(module, inputs, output, h=off[1]):
                output = output.clone()
                output[:, h] = 1.0 / output.shape[-1]
                return output
            handle = softmaxes[off[0]].register_forward_hook(hook)
        acc = {"bvo": 0.0, "bvo_n": 0, "top": 0, "top_n": 0, "sign": 0, "sign_n": 0}
        for start in range(0, p.N, BATCH):
            c = slice(start, min(start + BATCH, p.N))
            with torch.no_grad():
                o = net(feats(r[c], device))
            policy = o["policy"].cpu().numpy()
            value = o["value"][:, 0].cpu().numpy()
            if layout == "paper":
                value = np.where(black[c], value, -value)  # the paper's models give the value for sente
            n = len(policy)
            rows = np.arange(n)[:, None]
            keep, key = p.b_keep[c], p.b_key[c]
            best = (key == p.best_key[c][:, None]) & keep
            wp = np.where(keep, policy[rows, p.b_pol[c]], np.nan)[:, None, :].astype(np.float32)
            hits, npairs = pair_hits(wp, best[:, :, None] & ~best[:, None, :] & keep[:, :, None] & keep[:, None, :])
            has = npairs > 0
            acc["bvo"] += (hits[has, 0] / npairs[has]).sum()
            acc["bvo_n"] += int(has.sum())
            pol_legal = np.where(p.valid[c], policy[rows, p.pol_all[c]], -1)
            chosen = pol_legal.argmax(1)
            best_all = (p.key_all[c] == p.best_key[c][:, None]) & p.valid[c]
            acc["top"] += int(best_all[np.arange(n), chosen].sum())
            acc["top_n"] += n
            decided = target[c] != 0
            acc["sign"] += int((np.sign(value[decided]) == target[c][decided]).sum())
            acc["sign_n"] += int(decided.sum())
        if handle is not None:
            handle.remove()
        rows_out.append({"model": model_path, "block": 0 if off is None else blocks[off[0]] + 1, "head": 0 if off is None else off[1] + 1,
                         "policy_best_vs_other": acc["bvo"] / acc["bvo_n"], "policy_top_is_best": acc["top"] / acc["top_n"],
                         "value_sign_right": acc["sign"] / acc["sign_n"]})
        print("  %s  policy best vs other %.4f  top move is best %.4f  value sign right %.4f" % (
            "nothing off  " if off is None else "block %d head %d" % (blocks[off[0]] + 1, off[1] + 1),
            rows_out[-1]["policy_best_vs_other"], rows_out[-1]["policy_top_is_best"], rows_out[-1]["value_sign_right"]), flush=True)
    return rows_out


def pair_hits(w, mask):
    """w: (n, H, M) scores, mask: (n, M, M) ordered pairs where i should beat j. Per input and
    head: [w_i > w_j] + 0.5 [w_i == w_j] summed over the pairs, and the number of pairs."""
    diff = w[:, :, :, None] - w[:, :, None, :]
    hit = np.nan_to_num((diff > 0).astype(np.float32) + 0.5 * (diff == 0))
    return np.einsum("nhij,nij->nh", hit, mask.astype(np.float32)), mask.sum((1, 2))


def variants(model_path, r, p, layout, device="cpu"):
    """The table's cells under the definitions one could mean, side by side, to find the one
    another implementation used: pairs pooled over all inputs or averaged per input; the best
    move among all legal moves or among board moves only; captures left out as pairs or as
    moves; the largest weight and chance over every input or only over inputs whose board moves
    are not all equally good."""
    net = load_python_model(model_path, device)
    net.eval()
    feats = features_paper if layout == "paper" else A.features
    acc = {}

    def add(name, value):
        acc[name] = acc.get(name, 0) + value

    for start in range(0, p.N, BATCH):
        c = slice(start, min(start + BATCH, p.N))
        with torch.no_grad():
            att = net.get_attn_table(feats(r[c], device))["att_table"]
        att = torch.stack(att, 1).cpu().numpy()
        n, T, heads = att.shape[:3]
        H = T * heads
        att = att.reshape(n, H, 12, 12)
        rows = np.arange(n)[:, None]
        keep, key, cap = p.b_keep[c], p.b_key[c], p.b_cap[c] != 0
        w = att[rows[:, :, None], np.arange(H)[None, None, :], p.b_q[c][:, :, None], p.b_k[c][:, :, None]]
        w = np.where(keep[:, None, :], np.transpose(w, (0, 2, 1)), np.nan)
        kb = np.where(keep, key, -10 ** 6)
        best_all = (key == p.best_key[c][:, None]) & keep  # best among all legal moves, drops included
        best_board = (key == kb.max(1)[:, None]) & keep  # best among the board moves
        nc = keep & ~cap
        knc = np.where(nc, key, -10 ** 6)
        best_nc = (key == knc.max(1)[:, None]) & nc  # best among the board moves that take nothing
        both = keep[:, :, None] & keep[:, None, :]
        both_nc = nc[:, :, None] & nc[:, None, :]
        masks = {
            "best_all": best_all[:, :, None] & ~best_all[:, None, :] & both,
            "best_board": best_board[:, :, None] & ~best_board[:, None, :] & both,
            "nocap_pairs": best_all[:, :, None] & ~best_all[:, None, :] & both_nc,
            "nocap_pairs_board": best_board[:, :, None] & ~best_board[:, None, :] & both_nc,
            "nocap_moves": best_nc[:, :, None] & ~best_nc[:, None, :] & both_nc,
            "rank": (key[:, :, None] > key[:, None, :]) & both,
        }
        for name, m in masks.items():
            hits, npairs = pair_hits(w, m)
            add(name + "|pooled_hits", hits.sum(0))
            add(name + "|pooled_pairs", float(npairs.sum()))
            has = npairs > 0
            add(name + "|pos_sum", (hits[has] / npairs[has, None]).sum(0))
            add(name + "|pos_n", float(has.sum()))
        has_board = keep.any(1)
        differ = has_board & (np.where(keep, key, 10 ** 6).min(1) != kb.max(1))
        top = np.argmax(np.where(np.isnan(w), -1, w), axis=2)
        nboard = keep.sum(1)
        nlegal = p.valid[c].sum(1)
        for bname, best in (("best_all", best_all), ("best_board", best_board)):
            hit = np.take_along_axis(best[:, None, :].repeat(H, 1), top[:, :, None], 2)[:, :, 0]
            for sname, sel in (("every_input", has_board), ("qualities_differ", differ)):
                add("max|%s|%s" % (bname, sname), hit[sel].sum(0))
                add("max_n|%s" % sname, 0)
                add("chance_board|%s|%s" % (bname, sname), (best.sum(1)[sel] / nboard[sel]).sum())
                add("chance_legal|%s|%s" % (bname, sname), (best.sum(1)[sel] / nlegal[sel]).sum())
        add("n|every_input", float(has_board.sum()))
        add("n|qualities_differ", float(differ.sum()))
    ts = torch.jit.load(model_path, map_location=device)
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    out = []
    for h in range(H):
        row = {"model": model_path, "block": blocks[h // heads] + 1, "head": h % heads + 1}
        for name in masks:
            row[name + "|pooled"] = acc[name + "|pooled_hits"][h] / acc[name + "|pooled_pairs"]
            row[name + "|per_input"] = acc[name + "|pos_sum"][h] / acc[name + "|pos_n"]
        for bname in ("best_all", "best_board"):
            for sname in ("every_input", "qualities_differ"):
                row["max|%s|%s" % (bname, sname)] = acc["max|%s|%s" % (bname, sname)][h] / acc["n|" + sname]
        out.append(row)
    chance = {"model": model_path, "block": -1, "head": -1}
    for bname in ("best_all", "best_board"):
        for sname in ("every_input", "qualities_differ"):
            chance["chance_board|%s|%s" % (bname, sname)] = acc["chance_board|%s|%s" % (bname, sname)] / acc["n|" + sname]
            chance["chance_legal|%s|%s" % (bname, sname)] = acc["chance_legal|%s|%s" % (bname, sname)] / acc["n|" + sname]
    print("inputs with a board move %d, of them with board moves not all equally good %d" % (acc["n|every_input"], acc["n|qualities_differ"]))
    return out, chance

# ── 9x9 shogi: the played move as the provisional answer ─────────────────────────────────────


def shogi_env(config="configs/9x9_shogi/10T-bootstrap.cfg"):
    from xai_analysis import _load_build_so
    root = Path(__file__).resolve().parent.parent
    env_py = _load_build_so(str(root / "build" / "shogi"), "env_py")
    env_py.init(str(root / config))
    return env_py


def usi_square(file_ch, rank_ch, black):
    """A USI square -> the flat index of the network's frame (1筋 at column 0; the board is
    turned round when white is to move), as tsume_shogi._usi_sq_to_py."""
    sq = (ord(rank_ch) - ord("a")) * 9 + int(file_ch) - 1
    return sq if black else 80 - sq


def shogi_batches(sgf, sample, seed, batch):
    """Replay every game; draw positions at random; yield batches of positions with their legal
    moves: the squares in the network's frame, whether a move captures, the action ids, and
    which move was played."""
    import re
    env_py = shogi_env()
    rng = np.random.default_rng(seed)
    buf = []

    def flush():
        n = len(buf)
        mb = max(len(b["board"]) for b in buf)
        md = max(max(len(b["drops"]) for b in buf), 1)
        ml = max(len(b["ids"]) for b in buf)
        out = {"x": torch.stack([b["x"] for b in buf]),
               "b_q": np.zeros((n, mb), int), "b_k": np.zeros((n, mb), int), "b_keep": np.zeros((n, mb), bool),
               "b_cap": np.zeros((n, mb), bool), "b_pol": np.zeros((n, mb), int), "b_played": np.zeros((n, mb), bool),
               "b_kind": np.zeros((n, mb), int), "b_dist": np.zeros((n, mb), int),
               "d_k": np.zeros((n, md), int), "d_keep": np.zeros((n, md), bool), "d_pol": np.zeros((n, md), int),
               "d_played": np.zeros((n, md), bool), "pol_all": np.zeros((n, ml), int), "valid": np.zeros((n, ml), bool)}
        for i, b in enumerate(buf):
            for j, (q, k, cap, a, played, kind, dist) in enumerate(b["board"]):
                out["b_q"][i, j], out["b_k"][i, j], out["b_cap"][i, j], out["b_pol"][i, j], out["b_played"][i, j] = q, k, cap, a, played
                out["b_kind"][i, j], out["b_dist"][i, j] = kind, dist
                out["b_keep"][i, j] = True
            for j, (k, a, played) in enumerate(b["drops"]):
                out["d_k"][i, j], out["d_pol"][i, j], out["d_played"][i, j] = k, a, played
                out["d_keep"][i, j] = True
            out["pol_all"][i, :len(b["ids"])] = b["ids"]
            out["valid"][i, :len(b["ids"])] = True
        buf.clear()
        return out

    with open(sgf) as f:
        for line in f:
            moves = [int(a) for a in re.findall(r";[BW]\[(\d+)\]", line)]
            if not moves:
                continue
            env = env_py.Env()
            env.reset()
            for ply, played in enumerate(moves):
                legal = env.get_legal_actions()
                by_id = {a.get_action_id(): a for a in legal}
                if rng.random() < sample and len(legal) > 1:
                    black = ply % 2 == 0
                    x = torch.tensor(np.asarray(env.get_features(), dtype=np.float32).reshape(362, 9, 9))
                    enemy = x[14:28].sum(0).reshape(81)  # the opponent's pieces, current position
                    board, drops = [], []
                    for a in legal:
                        m = a.to_console_string()
                        aid = a.get_action_id()
                        if m[1] == "*":
                            drops.append((usi_square(m[2], m[3], black), aid, aid == played))
                        else:
                            q, k = usi_square(m[0], m[1], black), usi_square(m[2], m[3], black)
                            kind = int(x[0:14, q // 9, q % 9].argmax())  # own piece planes 0-13 (shogi.cpp getFeatures)
                            dist = max(abs(q // 9 - k // 9), abs(q % 9 - k % 9))
                            board.append((q, k, bool(enemy[k] > 0), aid, aid == played, kind, dist))
                    buf.append({"x": x, "board": board, "drops": drops, "ids": [a.get_action_id() for a in legal]})
                    if len(buf) == batch:
                        yield flush()
                env.act(by_id[played])
    if buf:
        yield flush()


def played_stats(w, keep, played, among):
    """w: (n, H, M) scores, keep/played/among: (n, M). For inputs whose played move is in `among`
    with at least one other move there: the share of those other moves that the played move beats
    ([w_played > w_other] + 0.5 equal), per head. Returns the shares summed over inputs and the
    number of inputs (the teacher's per-position average), then hits and pairs pooled."""
    others = keep & among & ~played
    sel = (played & among & keep).any(1) & others.any(1)
    if not sel.any():
        return np.zeros(w.shape[1]), 0.0, np.zeros(w.shape[1]), 0.0
    w, played, others = w[sel], played[sel], others[sel]
    wp = np.nansum(np.where(played[:, None, :], w, 0), axis=2)[:, :, None]  # the played move's score
    hits = (np.nan_to_num((wp > w) + 0.5 * (wp == w)) * others[:, None, :]).sum(2)
    npairs = others.sum(1)
    return (hits / npairs[:, None]).sum(0), float(sel.sum()), hits.sum(0), float(npairs.sum())


def run_shogi(model_path, batches, device="cpu", control="", off=None):
    """Every head of one 9x9 model; control "bias": the position bias alone. off=(T block, head):
    that head switched off (uniform weights), to see what the policy loses."""
    net = load_python_model(model_path, device)
    ts = torch.jit.load(model_path, map_location=device)
    ts.eval()
    net.eval()
    blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
    if not blocks:
        return None
    fixed = [f.to(device) for f in bias_attention(net)] if control == "bias" else None
    handle = None
    if off is not None:
        softmaxes = [m.attend for m in net.modules() if hasattr(m, "relative_bias_table")]

        def hook(module, inputs, output, h=off[1]):
            output = output.clone()
            output[:, h] = 1.0 / output.shape[-1]
            return output
        handle = softmaxes[off[0]].register_forward_hook(hook)
    acc = {}
    H = None

    def add(name, value):
        acc[name] = acc.get(name, 0) + value

    def count(tag, name, res):
        pos_sum, pos_n, hits, npairs = res
        add(tag + name + "|pos_sum", pos_sum)
        add(tag + name + "|pos_n", pos_n)
        add(tag + name + "|pool_hits", hits)
        add(tag + name + "|pool_pairs", npairs)

    n_inputs = 0
    for b in batches:
        x = b["x"].to(device)
        with torch.no_grad():
            out = net.get_attn_table(x)
            if n_inputs == 0 and off is None:  # the same batch: on the GPU another batch size changes the rounding (TF32)
                assert (ts(x)["policy"] - out["policy"]).abs().max() < 1e-4, "the Python model differs from the saved one"
            att = out["att_table"]
            if fixed is not None:
                att = [f[None].expand(len(x), -1, -1, -1) for f in fixed]
            att = torch.stack(att, 1).cpu().numpy()  # (n, T, heads, 81, 81)
            policy = out["policy"].cpu().numpy()
        n, T, heads = att.shape[:3]
        H = T * heads
        att = att.reshape(n, H, 81, 81)
        rows = np.arange(n)[:, None]
        hidx = np.arange(H)[None, None, :]
        w = att[rows[:, :, None], hidx, b["b_q"][:, :, None], b["b_k"][:, :, None]]
        w = np.where(b["b_keep"][:, None, :], np.transpose(w, (0, 2, 1)), np.nan)
        wd = att.mean(2)[rows[:, :, None], hidx, b["d_k"][:, :, None]]
        wd = np.where(b["d_keep"][:, None, :], np.transpose(wd, (0, 2, 1)), np.nan)
        wp = np.where(b["b_keep"], policy[rows, b["b_pol"]], np.nan)[:, None, :]
        wpd = np.where(b["d_keep"], policy[rows, b["d_pol"]], np.nan)[:, None, :]
        keep_all, played, cap = b["b_keep"], b["b_played"], b["b_cap"]
        # a promotion and the same move without it share their squares, so every head gives them the same
        # weight: for the attention keep one of each (from, to) pair, the played one where it is in the pair
        code = b["b_q"] * 81 + b["b_k"]
        same = (code[:, :, None] == code[:, None, :]) & keep_all[:, :, None] & keep_all[:, None, :] & ~np.eye(code.shape[1], dtype=bool)[None]
        earlier = np.tril(np.ones((code.shape[1], code.shape[1]), dtype=bool), -1)[None]
        keep = keep_all & (played | (~(same & played[:, None, :]).any(2) & ~(same & earlier).any(2)))
        w = np.where(keep[:, None, :], w, np.nan)
        pol_legal = np.where(b["valid"], policy[rows, b["pol_all"]], -1)
        pol_id = np.take_along_axis(b["pol_all"], pol_legal.argmax(1)[:, None], 1)
        pol_wrong = ~((b["b_pol"] == pol_id) & played).any(1) & ~((b["d_pol"] == pol_id) & b["d_played"]).any(1)
        pol_move = (b["b_pol"] == pol_id) & keep_all
        pol_move_rep = keep & (pol_move | (same & pol_move[:, None, :]).any(2))  # its (from, to) pair, for the attention
        same_piece = keep & (b["b_q"] == np.where(played, b["b_q"], -1).max(1)[:, None])  # moves of the played piece
        questions = {
            "played_vs_other": (played, keep),
            "played_vs_other_no_capture": (played, keep & ~cap),
            "played_vs_other_same_piece": (played, same_piece),
            "played_vs_other_where_policy_wrong": (played, keep & pol_wrong[:, None]),
            "policy_move_vs_other_where_policy_wrong": (pol_move_rep, keep & pol_wrong[:, None]),
        }
        kind_played = np.where(played, b["b_kind"], -1).max(1)
        dist_played = np.where(played, b["b_dist"], -1).max(1)
        for kind in range(14):  # moves of the played piece's kind only, as in dobutsu
            questions["played_vs_other|piece|%d" % kind] = (played, keep & (b["b_kind"] == kind) & (kind_played == kind)[:, None])
        for d, sel in (("1", dist_played == 1), ("2", dist_played == 2), ("3+", dist_played >= 3)):
            questions["played_vs_other_same_piece|distance|%s" % d] = (played, same_piece & sel[:, None])
        for name, (p_, among) in questions.items():
            count("", name, played_stats(w, keep, p_, among))
            # the policy tells a promotion from the move without it, so it keeps both
            p_all = pol_move if name.startswith("policy_move") else p_
            among_all = keep_all & (among | (same & among[:, None, :]).any(2))
            count("policy|", name, played_stats(wp, keep_all, p_all, among_all))
        count("", "played_drop_vs_other_drop", played_stats(wd, b["d_keep"], b["d_played"], b["d_keep"]))
        count("policy|", "played_drop_vs_other_drop", played_stats(wpd, b["d_keep"], b["d_played"], b["d_keep"]))
        hits, npairs = pair_hits(w, cap[:, :, None] & ~cap[:, None, :] & keep[:, :, None] & keep[:, None, :])
        has = npairs > 0
        count("", "capture_vs_no_capture", ((hits[has] / npairs[has, None]).sum(0), float(has.sum()), hits.sum(0), float(npairs.sum())))
        has = (played & keep).any(1) & (keep.sum(1) > 1)
        top = np.argmax(np.where(np.isnan(w), -1, w), axis=2)
        hit = np.take_along_axis(played[:, None, :].repeat(H, 1), top[:, :, None], 2)[:, :, 0] & has[:, None]
        add("max_is_played", hit.sum(0))
        add("max_is_played|chance", (1.0 / keep.sum(1)[has]).sum())  # one (from, to) pair drawn at random
        add("max_is_played|n", float(has.sum()))
        played_id = np.where(played, b["b_pol"], -1).max(1)
        played_id = np.where(played_id >= 0, played_id, np.where(b["d_played"], b["d_pol"], -1).max(1))
        add("policy_top_is_played", float((pol_id[:, 0] == played_id).sum()))
        n_inputs += n
    if handle is not None:
        handle.remove()
    heads = H // len(blocks)
    names = sorted({k.split("|pos_sum")[0] for k in acc if k.endswith("|pos_sum") and not k.startswith("policy|")})

    def values(tag, h):
        row = {}
        for name in names:
            pn, pp = acc.get(tag + name + "|pos_n", 0), acc.get(tag + name + "|pool_pairs", 0)
            row[name] = acc[tag + name + "|pos_sum"][h] / pn if pn else float("nan")
            row[name + "_pooled"] = acc[tag + name + "|pool_hits"][h] / pp if pp else float("nan")
            row["n|" + name] = pn
        return row
    rows_out = []
    for h in range(H):
        row = {"model": model_path, "block": blocks[h // heads] + 1, "head": h % heads + 1}
        row.update(values("", h))
        row["max_is_played"] = acc["max_is_played"][h] / acc["max_is_played|n"]
        rows_out.append(row)
    policy_row = {"model": model_path, "block": 0, "head": 0, "policy_top_is_played": acc["policy_top_is_played"] / n_inputs}
    policy_row.update(values("policy|", 0))
    chance_row = {"model": model_path, "block": -1, "head": -1, "max_is_played": acc["max_is_played|chance"] / acc["max_is_played|n"]}
    for name in names:
        chance_row[name] = 0.5
    return rows_out, policy_row, chance_row, {"inputs": n_inputs}, n_inputs


def main_shogi(argv):
    sgf, out = argv[0], argv[1]
    models = [a for a in argv[2:] if a.endswith(".pt")]
    sample = float(argv[argv.index("--sample") + 1]) if "--sample" in argv else 0.1
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 1
    control = argv[argv.index("--control") + 1] if "--control" in argv else ""
    assert control in ("", "bias"), control
    rows = []
    if "--peaked" in argv:  # how far each head is from even weights, on the first 2,048 positions drawn
        batches = [b["x"] for _, b in zip(range(16), shogi_batches(sgf, sample, seed, 128))]
        for model_path in models:
            rows += peaked(model_path, batches, "cuda" if torch.cuda.is_available() else "cpu")
        return write_csv(rows, out)
    if "--ablate" in argv:  # every head switched off in turn; the positions are kept in memory once
        cached = list(shogi_batches(sgf, sample, seed, 128))
        for model_path in models:
            ts = torch.jit.load(model_path, map_location="cpu")
            t_blocks = [i for i, t in enumerate(ts.blocks_type.split("_")) if t == "T"]
            if not t_blocks:
                print(model_path, "has no T block")
                continue
            for off in [None] + [(b, h) for b in range(len(t_blocks)) for h in range(4)]:
                res = run_shogi(model_path, cached, "cuda" if torch.cuda.is_available() else "cpu", off=off)
                pol = res[1]
                rows.append({"model": model_path, "block": 0 if off is None else t_blocks[off[0]] + 1, "head": 0 if off is None else off[1] + 1,
                             "policy_top_is_played": pol["policy_top_is_played"], "policy_played_vs_other": pol["played_vs_other"]})
                print("  %s off %s: policy top move = played %.4f, played vs other %.4f" % (
                    model_path, "nothing" if off is None else "block %d head %d" % (rows[-1]["block"], rows[-1]["head"]),
                    rows[-1]["policy_top_is_played"], rows[-1]["policy_played_vs_other"]), flush=True)
            write_csv(rows, out)  # after each model, so a later failure keeps what is done
        return
    for model_path in models:
        res = run_shogi(model_path, shogi_batches(sgf, sample, seed, 128), "cuda" if torch.cuda.is_available() else "cpu", control=control)
        if res is None:
            print(model_path, "has no T block")
            continue
        head_rows, policy_row, chance, pairs, n = res
        rows += head_rows + [policy_row, chance]
        print("== %s  inputs %d" % (model_path, n))
        for row in head_rows:
            print("  block %2d head %d  played %.3f  no-capture %.3f  max-is-played %.1f%%  capture/no %.2f  drops %.2f  policy-wrong: played %.2f policy %.2f" % (
                row["block"], row["head"], row["played_vs_other"], row["played_vs_other_no_capture"], 100 * row["max_is_played"],
                row["capture_vs_no_capture"], row["played_drop_vs_other_drop"], row["played_vs_other_where_policy_wrong"],
                row["policy_move_vs_other_where_policy_wrong"]))
        print("  policy itself: played %.3f  no-capture %.3f  drops %.2f  top move = played %.3f | chance max-is-played %.1f%%" % (
            policy_row["played_vs_other"], policy_row["played_vs_other_no_capture"], policy_row["played_drop_vs_other_drop"],
            policy_row["policy_top_is_played"], 100 * chance["max_is_played"]))
    write_csv(rows, out)


def write_csv(rows, out):
    if rows:
        keys = ["model", "block", "head"] + sorted({k for row in rows for k in row} - {"model", "block", "head"})
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in rows:
                w.writerow(row)
        print("wrote", out)


def main():
    game, records, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if game == "shogi":
        return main_shogi(sys.argv[2:])
    assert game == "dobutsu"
    r = load_records(records)
    control = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else ""
    if "--orient" in sys.argv:  # one orientation only: 0 as stored, 1 mirrored, 2 sides swapped, 3 both
        r = r[r["orient"] == int(sys.argv[sys.argv.index("--orient") + 1])]
        print("orientation %s only: %d inputs" % (sys.argv[sys.argv.index("--orient") + 1], len(r)))
    print("inputs after leaving out finished positions: %d of %d" % (len(r), len(np.fromfile(records, dtype=MOVE_RECORD))))
    if "--peaked" in sys.argv:  # how far each head is from even weights, on 2,000 of the inputs drawn at random
        sub = r[np.random.default_rng(0).choice(len(r), 2000, replace=False)]
        rows = []
        for model_path in [a for a in sys.argv[4:] if a.endswith(".pt")]:
            feats = features_paper if torch.jit.load(model_path, map_location="cpu").get_num_input_channels() == 20 else A.features
            rows += peaked(model_path, [feats(sub, "cpu")])
        return write_csv(rows, out)
    prepared = {}
    rows = []
    assert control in ("", "bias", "untrained", "reverse", "rollout"), control
    for model_path in [a for a in sys.argv[4:] if a.endswith(".pt")]:
        if "T" not in torch.jit.load(model_path, map_location="cpu").blocks_type.split("_"):
            print(model_path, "has no T block")
            continue
        ts = torch.jit.load(model_path, map_location="cpu")
        layout = "paper" if ts.get_num_input_channels() == 20 else "rebuilt"
        if layout not in prepared:
            prepared[layout] = Prepared(r, layout)
        if "--ablate" in sys.argv:
            rows += ablation(model_path, r, prepared[layout], layout)
            continue
        if "--variants" in sys.argv:
            head_rows, chance = variants(model_path, r, prepared[layout], layout)
            rows += head_rows + [chance]
            continue
        res = run(model_path, r, prepared[layout], layout, control=control, splits="--splits" in sys.argv)
        if res is None:
            print(model_path, "has no T block")
            continue
        head_rows, policy_row, chance, inputs = res
        rows += head_rows + [policy_row, chance]
        print("== %s (%s layout) inputs per question %s" % (model_path, layout, inputs))
        for row in head_rows:
            print("  block %d head %d  best %.3f  no-capture %.3f  all %.3f  max-is-best %.1f%%  win/draw %.2f draw/loss %.2f fast/slow %.2f  drops %.2f" % (
                row["block"], row["head"], row["best_vs_other"], row["best_vs_other_no_capture"], row["all_pairs"],
                100 * row["max_is_best"], row["win_vs_draw"], row["draw_vs_loss"], row["faster_win_vs_slower_win"],
                row["best_drop_vs_other_drop"]))
        print("  policy itself: best %.3f  all %.3f  drops %.2f  policy-wrong: policy's move %.3f best %.3f" % (
            policy_row["best_vs_other"], policy_row["all_pairs"], policy_row["best_drop_vs_other_drop"],
            policy_row["policy_move_vs_other_where_policy_wrong"], policy_row["best_vs_other_where_policy_wrong"]))
        print("  chance max-is-best: %.1f%% (a board move at random; the teacher's chance, a legal move at random: %.1f%%)" % (
            100 * chance["max_is_best"], 100 * chance["max_is_best_chance_legal"]))
    write_csv(rows, out)


if __name__ == "__main__":
    main()
