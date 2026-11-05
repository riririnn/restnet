"""IG and other attributions on the paper's dobutsu models, compared over many positions.

  python3 scripts/ig_statistics.py check MODEL.pt
      figure 2 of the paper again (IG from the all-zero input) and the exact Shapley values of the
      same position, before anything new is trusted
  python3 scripts/ig_statistics.py run RECORDS OUT.npz MODEL.pt [--positions N] [--seed S] [--steps K]
      N positions of each set (the opponent's lion can be taken / every other unfinished position)
      from RECORDS (scripts/dobutsu_all.cc, moves mode: each position in 4 orientations); every
      attribution of every piece, for the value (seen from the side to move) and for the
      probability of the model's own move; then the comparison tables

A player is a piece on the board, the hand pieces of one kind and side, or (only where the
baseline differs there) the turn and repetition planes, and the rest (empty squares and hands). Methods, one number per player:
  ig_zero, ig_removed, ig_mean   IG from the all-zero input (the paper), from the input with the
                                 pieces removed (turn planes kept), from the average input (Czech et al.)
  shap_zero, shap_removed, shap_mean   exact Shapley values against the same three inputs
  occlusion                      output minus the output with only that player removed
  grad_input                     gradient times input at the position (no path)
"""
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from attention_move_rank import MOVE_RECORD, decode, features_paper  # noqa: E402
from xai_analysis import integrated_gradients_inputs, load_python_model  # noqa: E402

# the records the paper's figures came from (the environment of 2026-10)
OLD_RECORD = np.dtype([("index", "<u4"), ("orient", "i1"), ("turn", "i1"), ("value", "i1"),
                       ("count", "u1"), ("board", "i1", 12), ("hands", "u1", 6),
                       ("legal", "u1", 17), ("best", "u1", 17), ("win", "u1", 17)])
PART = 5_000_000
SQ = ["abc"[p % 3] + str(4 - p // 3) for p in range(12)]
METHODS = ["ig_zero", "ig_removed", "ig_mean", "shap_zero", "shap_removed", "shap_mean", "occlusion", "grad_input"]
HEADS = [(4, 3), (3, 0)]  # 6T: block 5 head 4 and block 4 head 1 (0-based), the paper's two heads


def mirror(s):
    return (s // 3) * 3 + 2 - s % 3


def to_orient0(s, orient):
    """A square of an input in `orient` -> the same square of the position as stored."""
    return [s, mirror(s), 11 - s, 11 - mirror(s)][orient]


def players_of(rec, x):
    """The players of one input: (name key, mask over the 20 planes, kind)."""
    turn = int(rec["turn"])
    out = []
    for s in range(12):
        c = int(rec["board"][s])
        if c:
            m = torch.zeros_like(x)
            m[:10, s // 3, s % 3] = 1
            own = (c > 0) == (turn == 1)
            out.append((("board", own, abs(c), to_orient0(s, int(rec["orient"]))), m, s))
    for plane in range(10, 16):
        if float(x[plane, 0, 0]) > 0:
            m = torch.zeros_like(x)
            m[plane] = 1
            out.append((("hand", plane < 13, (plane - 10) % 3), m, None))
    m = torch.zeros_like(x)
    m[16:] = 1
    out.append((("turn",), m, None))
    rest = 1 - torch.stack([mm for _, mm, _ in out]).sum(0).clamp(max=1)
    out.append((("rest",), rest, None))  # empty squares and empty hands; differs from the baseline only for "mean"
    return out


def model_move(net, x, rec):
    """The model's own move: its most probable legal move, as the paper's action id."""
    n = int(rec["n"])
    action = rec["action"][:n].astype(int)
    black = int(rec["turn"]) == 1
    drop, kind, frm, to, d = decode(action, black)
    pol = np.where(drop, 96 + kind * 12 + to, frm * 8 + d)
    with torch.no_grad():
        p = net(x[None])["policy"][0].cpu().numpy()
    i = int(np.argmax(p[pol]))
    o = int(rec["orient"])
    move0 = (bool(drop[i]), int(kind[i]) if drop[i] else -1, -1 if drop[i] else to_orient0(int(frm[i]), o), to_orient0(int(to[i]), o))
    return int(pol[i]), move0  # the move as the paper's action id, and in the stored position's squares


def outputs(net, batch, sign, action):
    with torch.no_grad():
        o = net(batch)
    return sign * o["value"][:, 0].cpu().numpy(), o["policy"][:, action].cpu().numpy()


def shapley(net, x, base, masks, sign, action):
    """Exact Shapley values of the players against `base`, for (value, move probability); also
    every coalition's output (for the deletion test). Coalition rows follow itertools.product,
    so the first player is the highest bit."""
    n = len(masks)
    pats = np.array(list(itertools.product((0, 1), repeat=n)), dtype=np.int64)
    union = (torch.tensor(pats, dtype=torch.float32, device=x.device) @ torch.stack(masks).view(n, -1)).clamp(max=1).view(-1, *x.shape)
    v, p = outputs(net, base[None] + (x - base)[None] * union, sign, action)
    w = np.array([math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n) for k in range(n)])
    size = pats.sum(1)
    phi = np.zeros((2, n))
    for j in range(n):
        lo = np.nonzero(pats[:, j] == 0)[0]
        hi = lo + (1 << (n - 1 - j))
        phi[0, j] = (w[size[lo]] * (v[hi] - v[lo])).sum()
        phi[1, j] = (w[size[lo]] * (p[hi] - p[lo])).sum()
    return phi, pats, v, p


def ig_players(ig, masks):
    return np.array([float((ig * m.cpu().numpy()).sum()) for m in masks])


def analyse(net, rec, x, mean_input, steps):
    """Every method for one input."""
    turn = int(rec["turn"])
    sign = 1.0 if turn == 1 else -1.0  # the paper's models give the value for sente
    action, move0 = model_move(net, x, rec)
    pl = players_of(rec, x)
    keys = [k for k, _, _ in pl]
    masks = [m for _, m, _ in pl]
    removed = x.clone()
    removed[:16] = 0  # the pieces removed, turn and repetition planes kept
    bases = {"zero": torch.zeros_like(x), "removed": removed, "mean": mean_input}
    res = {"keys": keys, "squares": [s for _, _, s in pl], "action": action, "move0": move0}
    full_v, full_p = outputs(net, x[None], sign, action)
    res["out"] = (float(full_v[0]), float(full_p[0]))
    for bname, base in bases.items():
        bv, bp = outputs(net, base[None], sign, action)
        res["base_" + bname] = (float(bv[0]), float(bp[0]))
        for t, target in enumerate(("value", "policy")):
            ig = integrated_gradients_inputs(net, x[None], target=target, action_idx=action, steps=steps, sign=sign, baseline=base[None])
            res.setdefault("ig_" + bname, np.zeros((2, len(pl))))[t] = ig_players(ig, masks)
            res.setdefault("ig_sum_" + bname, [0, 0])[t] = float(ig.sum())
        # Shapley: only players that differ from the baseline take part (the turn player against "removed" does not)
        live = [j for j in range(len(pl)) if float(((x - base) * masks[j]).abs().sum()) > 0]
        phi, pats, v, p = shapley(net, x, base, [masks[j] for j in live], sign, action)
        full = np.zeros((2, len(pl)))
        full[:, live] = phi
        res["shap_" + bname] = full
        if bname == "removed":
            res["coalitions"] = (live, pats, v, p)
    # occlusion: remove one player (back to the pieces-removed input on its planes)
    occ = np.zeros((2, len(pl)))
    for j, m in enumerate(masks):
        if keys[j][0] in ("turn", "rest"):
            continue
        v, p = outputs(net, (x - x * m)[None], sign, action)
        occ[:, j] = (res["out"][0] - v[0], res["out"][1] - p[0])
    res["occlusion"] = occ
    gi = np.zeros((2, len(pl)))
    for t, target in enumerate(("value", "policy")):
        xx = x[None].clone().requires_grad_(True)
        o = net(xx)
        (sign * o["value"][:, 0].sum() if target == "value" else o["policy"][:, action].sum()).backward()
        g = (xx.grad[0] * x).detach()
        gi[t] = [float((g * m).sum()) for m in masks]
    res["grad_input"] = gi
    # attention of the paper's two heads, from the side to move's lion
    lion = [s for s in range(12) if int(rec["board"][s]) == 5 * turn]
    if lion and hasattr(net, "get_attn_table"):
        with torch.no_grad():
            att = net.get_attn_table(x[None])["att_table"]
        if len(att) > max(b for b, _ in HEADS):
            res["attention"] = np.array([att[b][0, h, lion[0]].cpu().numpy() for b, h in HEADS])
            res["lion"] = lion[0]
    return res


def check(model_path):
    net = load_python_model(model_path, "cpu")
    net.eval()
    index, orient = 228767705, 2  # figure 2: white to move
    path = "data/dobutsu_all/full_o2/part_%03d.bin" % (index // PART)
    old = np.fromfile(path, dtype=OLD_RECORD, count=1, offset=(index % PART) * OLD_RECORD.itemsize)
    assert old["index"][0] == index
    rec = np.zeros(1, dtype=MOVE_RECORD)
    for f in ("index", "orient", "turn", "value", "count", "board", "hands"):
        rec[f] = old[f]
    rec["n"] = 1  # only the model's move is needed: a3 -> any legal move id works for the value
    rec["action"][0] = 36 + 7 * 8  # a placeholder; the value attributions do not use it
    x = features_paper(rec, "cpu")[0]
    res = analyse(net, rec[0], x, torch.zeros_like(x), 300)
    names = {1: "chick", 2: "elephant", 3: "giraffe", 4: "hen", 5: "lion"}
    print("figure 2: value %.3f (paper 0.99) | all-zero input %.3f" % (res["out"][0], res["base_zero"][0]))
    for j, k in enumerate(res["keys"]):
        what = ("%s %s %s" % (SQ[res["squares"][j]], "own" if k[1] else "opponent", names[k[2]])) if k[0] == "board" else \
            ("%s hand %s" % ("own" if k[1] else "opponent", ["giraffe", "elephant", "chick"][k[2]])) if k[0] == "hand" else "turn and repetition planes"
        print("  %-32s ig_zero %+.2f  shap_zero %+.2f  ig_removed %+.2f  shap_removed %+.2f  occlusion %+.2f" % (
            what, res["ig_zero"][0, j], res["shap_zero"][0, j], res["ig_removed"][0, j], res["shap_removed"][0, j], res["occlusion"][0, j]))
    print("sums: ig_zero %.3f, output - all-zero output %.3f" % (res["ig_sum_zero"][0], res["out"][0] - res["base_zero"][0]))


def run(records, out, model_path, positions, seed, steps, device):
    r = np.fromfile(records, dtype=MOVE_RECORD)
    r4 = r.reshape(-1, 4)
    assert (r4["orient"] == np.arange(4)).all() and (r4["index"] == r4["index"][:, :1]).all()
    finished = (r4["count"][:, 0] == 0) & (r4["value"][:, 0] != 0)
    takeable = (r4["captured"][:, 0] == 5).any(1)
    sets = {"takeable": np.nonzero(takeable)[0], "other": np.nonzero(~finished)[0]}
    net = load_python_model(model_path, device)
    net.eval()
    unf = r[~((r["count"] == 0) & (r["value"] != 0))]
    mean_input = sum(features_paper(unf[i:i + 8192], device).sum(0) for i in range(0, len(unf), 8192)) / len(unf)
    rng = np.random.default_rng(seed)
    results = []
    for sname, idxs in sets.items():
        for k, pi in enumerate(rng.choice(idxs, positions, replace=False)):
            for o in range(4):
                rec = r4[pi, o]
                x = features_paper(rec[None], device)[0]
                res = analyse(net, rec, x, mean_input, steps)
                n = int(rec["n"])
                drop, kind, frm, to, d = decode(rec["action"][:n].astype(int), int(rec["turn"]) == 1)
                res["takers"] = sorted(set(frm[(rec["captured"][:n] == 5) & ~drop].tolist()))
                res.update(set=sname, position=int(pi), orient=o, turn=int(rec["turn"]))
                results.append(res)
            if k % 100 == 99:
                print("  %s: %d / %d positions" % (sname, k + 1, positions), flush=True)
    np.save(out, np.array(results, dtype=object), allow_pickle=True)
    summarize(results)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def summarize(results):
    T = ("value", "policy")
    print("\n== inputs: %s" % {s: sum(1 for r in results if r["set"] == s) for s in ("takeable", "other")})
    print("\n== output at each baseline (value for the side to move), mean (sd)")
    for b in ("zero", "removed", "mean"):
        for turn, tname in ((1, "sente to move"), (-1, "gote to move")):
            v = [r["base_" + b][0] for r in results if r["turn"] == turn]
            print("  %-8s %-14s value %+.3f (%.3f)" % (b, tname, np.mean(v), np.std(v)))
    print("\n== sum check: |sum of IG over every input - (output - baseline output)|, mean and max")
    for b in ("zero", "removed", "mean"):
        for t in range(2):
            e = [abs(r["ig_sum_" + b][t] - (r["out"][t] - r["base_" + b][t])) for r in results]
            print("  ig_%-8s %-7s %.4f  %.4f" % (b, T[t], np.mean(e), np.max(e)))
    print("\n== the takeable opponent lion: share of inputs where its number is negative (value)")
    for m in METHODS:
        line = []
        for turn, tname in ((1, "sente to move"), (-1, "gote to move")):
            neg = [r[m][0, j] < 0 for r in results if r["set"] == "takeable" and r["turn"] == turn
                   for j, k in enumerate(r["keys"]) if k[0] == "board" and not k[1] and k[2] == 5]
            line.append("%s %.1f%% (n %d)" % (tname, 100 * np.mean(neg), len(neg)))
        print("  %-13s %s" % (m, "   ".join(line)))
    print("\n== the same position in two inputs: share of players (|number| > 0.02 in both) whose sign differs")
    byp = {}
    for r in results:
        byp.setdefault((r["set"], r["position"]), {})[r["orient"]] = r
    for t in range(2):
        for pair, pname in (((0, 2), "sides swapped"), ((0, 1), "mirrored")):
            line = []
            for m in METHODS:
                diff, n = 0, 0
                for g in byp.values():
                    if pair[0] in g and pair[1] in g:
                        a, b = g[pair[0]], g[pair[1]]
                        if t == 1 and a["move0"] != b["move0"]:
                            continue  # the move probability is comparable only for the same move
                        ka = {k: a[m][t, j] for j, k in enumerate(a["keys"])}
                        for j, k in enumerate(b["keys"]):
                            if k in ka and k[0] in ("board", "hand") and abs(ka[k]) > 0.02 and abs(b[m][t, j]) > 0.02:
                                n += 1
                                diff += int(np.sign(ka[k]) != np.sign(b[m][t, j]))
                line.append("%s %.1f%%" % (m, 100 * diff / max(n, 1)))
            print("  %-7s %-13s %s" % (T[t], pname, "  ".join(line)))
    print("\n== agreement with the exact Shapley values (players without the turn planes): rank correlation | same top player")
    for t in range(2):
        for ref in ("shap_zero", "shap_removed"):
            line = []
            for m in METHODS:
                if m == ref:
                    continue
                cs, tops = [], []
                for r in results:
                    sel = [j for j, k in enumerate(r["keys"]) if k[0] in ("board", "hand")]
                    if len(sel) >= 3:
                        cs.append(spearman(r[m][t, sel], r[ref][t, sel]))
                        tops.append(int(np.argmax(r[m][t, sel]) == np.argmax(r[ref][t, sel])))
                line.append("%s %.2f|%.2f" % (m, np.nanmean(cs), np.mean(tops)))
            print("  %-7s vs %-13s %s" % (T[t], ref, "  ".join(line)))
    print("\n== deletion test (pieces removed one by one, the method's largest number first): mean output over the")
    print("   curve minus that of a random order; more negative = the method found what the output rests on")
    for t in range(2):
        line = []
        for m in METHODS + ["attention_5_4", "attention_4_1"]:
            ds = []
            for r in results:
                live, pats, v, p = r["coalitions"]
                f = (v, p)[t]
                n = len(live)
                if n < 2:
                    continue
                if m.startswith("attention"):
                    if "attention" not in r or t == 1:
                        continue
                    w = r["attention"][0 if m.endswith("5_4") else 1]
                    score = [w[r["squares"][j]] if r["keys"][j][0] == "board" else -1.0 for j in live]
                else:
                    score = [r[m][t, j] for j in live]
                order = np.argsort(-np.array(score), kind="stable")
                row = np.ones(n, dtype=np.int64)
                curve = []
                for k in range(n):
                    row[order[k]] = 0
                    curve.append(f[int((row * (1 << np.arange(n - 1, -1, -1))).sum())])
                size = pats.sum(1)
                rand = [f[size == n - k - 1].mean() for k in range(n)]
                ds.append(np.mean(curve) - np.mean(rand))
            if ds:
                line.append("%s %+.3f" % (m, np.mean(ds)))
        print("  %-7s %s" % (T[t], "  ".join(line)))
    print("\n== the piece (or hand) with the largest number for the value, takeable positions")
    for m in METHODS:
        cat = {}
        for r in results:
            if r["set"] != "takeable":
                continue
            sel = [j for j, k in enumerate(r["keys"]) if k[0] in ("board", "hand")]
            j = sel[int(np.argmax(r[m][0, sel]))]
            k = r["keys"][j]
            if k[0] == "board":
                c = "piece that takes the lion" if (k[1] and r["squares"][j] in r["takers"]) else "opponent lion" if (not k[1] and k[2] == 5) else "own lion" if k[2] == 5 else "other piece"
            else:
                c = "hand" if k[0] == "hand" else "turn planes"
            cat[c] = cat.get(c, 0) + 1
        tot = sum(cat.values())
        print("  %-13s %s" % (m, "  ".join("%s %.1f%%" % (c, 100 * v / tot) for c, v in sorted(cat.items(), key=lambda z: -z[1]))))
    print("\n== share of the total |number| (value) taken by the turn planes / the rest")
    for m in METHODS:
        tot = [np.abs(r[m][0]).sum() for r in results]
        turn = [sum(abs(r[m][0, j]) for j, k in enumerate(r["keys"]) if k[0] == "turn") for r in results]
        rest = [sum(abs(r[m][0, j]) for j, k in enumerate(r["keys"]) if k[0] == "rest") for r in results]
        print("  %-13s turn %.1f%%  rest %.1f%%" % (m, 100 * np.sum(turn) / np.sum(tot), 100 * np.sum(rest) / np.sum(tot)))
    print("\n== overlap of the 3 board squares with the largest |number| (value) and the 3 squares the head weighs most from the")
    print("   side to move's lion; chance 0.75 (3 x 3 / 12), and chance if the head picked 3 occupied squares at random")
    for hi, hname in ((0, "block 5 head 4"), (1, "block 4 head 1")):
        line = []
        occ_chance = []
        for m in METHODS:
            ov = []
            for r in results:
                if "attention" not in r:
                    continue
                sel = [j for j, k in enumerate(r["keys"]) if k[0] == "board"]
                if len(sel) < 3:
                    continue
                top_m = {r["squares"][j] for j in sorted(sel, key=lambda j: -abs(r[m][0, j]))[:3]}
                top_a = set(np.argsort(-r["attention"][hi])[:3].tolist())
                ov.append(len(top_m & top_a))
                if m == METHODS[0]:
                    occ_chance.append(9.0 / len(sel))
            line.append("%s %.2f" % (m, np.mean(ov)))
        print("  %-15s %s  | chance among occupied squares %.2f" % (hname, "  ".join(line), np.mean(occ_chance)))


def main():
    mode = sys.argv[1]
    if mode == "check":
        return check(sys.argv[2])
    assert mode == "run"
    args = sys.argv[2:]
    positions = int(args[args.index("--positions") + 1]) if "--positions" in args else 1000
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 1
    steps = int(args[args.index("--steps") + 1]) if "--steps" in args else 300
    device = "cuda" if torch.cuda.is_available() else "cpu"
    run(args[0], args[1], args[2], positions, seed, steps, device)


if __name__ == "__main__":
    main()
