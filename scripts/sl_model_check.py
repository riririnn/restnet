"""Is a supervised (SL) 9x9 shogi model good enough to start self-play from?

The checks follow what the AlphaGo papers report for their SL networks: accuracy on games
the model never saw, no overfitting, and (with scripts/usi_bridge.py) strength in play.

  python3 scripts/sl_model_check.py curves LOG [LOG ...]
      test losses averaged per 5,000 steps over the last 50,000 steps, and train - test
  python3 scripts/sl_model_check.py test GAMES.sgf MODEL.pt [MODEL.pt ...] [--sample F] [--seed S]
      on positions drawn from the test games: the model's top legal move is the move played,
      the move played is in its top 5, the sign of the value matches the winner, the value's
      squared error against the result, and the share of positions with |value| > 0.99
"""
import re
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from attention_move_rank import shogi_env  # noqa: E402

KEYS = ["loss_policy", "accuracy_policy", "loss_value", "test_loss_policy", "test_accuracy_policy", "test_loss_value"]
PLY_BINS = [(0, 30), (31, 60), (61, 100), (101, 10 ** 6)]


def read_log(path):
    rows, row = [], None
    for line in open(path):
        m = re.search(r"nn step (\d+), lr: (\d[\d.e-]*\d)", line)
        if m:
            row = {"step": int(m.group(1)), "lr": float(m.group(2))}
            rows.append(row)
            continue
        m = re.match(r"\s+(\w+): ([-\d.e]+)", line)
        if m and row is not None and m.group(1) in KEYS:
            row[m.group(1)] = float(m.group(2))
    rows = [r for r in rows if all(k in r for k in KEYS)]
    # "pretrain resume" appends to the same log and restarts from the last checkpoint, so the steps
    # after that checkpoint appear twice: keep only the run that went on
    kept = []
    for r in rows:
        while kept and kept[-1]["step"] >= r["step"]:
            kept.pop()
        kept.append(r)
    return kept


def curves(logs):
    for path in logs:
        rows = read_log(path)
        last = rows[-1]["step"]
        print("== %s  (steps logged %d, last %d, lr at the end %g)" % (path, len(rows), last, rows[-1]["lr"]))
        print("  steps            test_loss_policy  test_accuracy  test_loss_value  train-test policy  train-test value")
        for start in range(last - 50000, last, 5000):
            b = [r for r in rows if start < r["step"] <= start + 5000]
            mean = {k: np.mean([r[k] for r in b]) for k in KEYS}
            print("  %6d-%6d   %.4f            %.4f         %.4f           %+.4f            %+.4f" % (
                start + 1, start + 5000, mean["test_loss_policy"], mean["test_accuracy_policy"], mean["test_loss_value"],
                mean["loss_policy"] - mean["test_loss_policy"], mean["loss_value"] - mean["test_loss_value"]))


def test(sgf, models, sample, seed, device):
    env_py = shogi_env()
    nets = []
    for p in models:
        net = torch.jit.load(p, map_location=device)
        net.eval()
        nets.append(net)
    rng = np.random.default_rng(seed)
    stats = [{"n": 0, "top1": 0, "top5": 0, "sign_n": 0, "sign": 0, "sq": 0.0, "sat": 0, "sat_n": 0, "sat_sign": 0,
              "bins": {b: [0, 0, 0, 0] for b in PLY_BINS}} for _ in models]  # bins: n, top1, sign_n, sign
    buf = []

    def flush():
        x = torch.stack([b[0] for b in buf]).to(device)
        with torch.no_grad():
            outs = [net(x) for net in nets]
        for s, o in zip(stats, outs):
            policy = o["policy"].cpu().numpy()
            value = o["value"][:, 0].cpu().numpy()
            for i, (_, ids, played, target, ply) in enumerate(buf):
                p = policy[i, ids]
                order = np.argsort(-p)
                k = ids.index(played)
                top1 = order[0] == k
                s["n"] += 1
                s["top1"] += int(top1)
                s["top5"] += int(k in order[:5])
                s["sq"] += (value[i] - target) ** 2
                s["sat"] += int(abs(value[i]) > 0.99)
                b = next(b for b in PLY_BINS if b[0] <= ply <= b[1])
                s["bins"][b][0] += 1
                s["bins"][b][1] += int(top1)
                if target != 0:
                    agree = int(np.sign(value[i]) == np.sign(target))
                    s["sign_n"] += 1
                    s["sign"] += agree
                    s["bins"][b][2] += 1
                    s["bins"][b][3] += agree
                    if abs(value[i]) > 0.99:  # a value this sure makes the loser resign at -0.9
                        s["sat_n"] += 1
                        s["sat_sign"] += agree
        buf.clear()

    with open(sgf) as f:
        for line in f:
            moves = [int(a) for a in re.findall(r";[BW]\[(\d+)\]", line)]
            result = re.search(r"RE\[([-\d.]+)\]", line)
            if not moves or not result:
                continue
            result = float(result.group(1))  # for black (sente): 1 win, -1 loss, 0 draw
            env = env_py.Env()
            env.reset()
            for ply, played in enumerate(moves):
                legal = env.get_legal_actions()
                by_id = {a.get_action_id(): a for a in legal}
                if rng.random() < sample and len(legal) > 1:
                    x = torch.tensor(np.asarray(env.get_features(), dtype=np.float32).reshape(362, 9, 9))
                    target = result if ply % 2 == 0 else -result  # the value is for the side to move
                    buf.append((x, list(by_id), played, target, ply + 1))
                    if len(buf) == 256:
                        flush()
                env.act(by_id[played])
    if buf:
        flush()
    for p, s in zip(models, stats):
        print("== %s" % p)
        print("  positions %d | top move = move played %.3f | move played in top 5 %.3f" % (s["n"], s["top1"] / s["n"], s["top5"] / s["n"]))
        print("  value: sign matches the winner %.3f (draws left out) | squared error %.3f | |value| > 0.99 in %.3f, its sign right in %.3f" % (
            s["sign"] / s["sign_n"], s["sq"] / s["n"], s["sat"] / s["n"], s["sat_sign"] / max(s["sat_n"], 1)))
        print("  by move number:  " + "   ".join("%d-%s: top move %.3f, sign %.3f (n %d)" % (
            b[0], str(b[1]) if b[1] < 10 ** 6 else "", v[1] / max(v[0], 1), v[3] / max(v[2], 1), v[0])
            for b, v in s["bins"].items()))


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "curves":
        return curves(args)
    assert mode == "test"
    sample = float(args[args.index("--sample") + 1]) if "--sample" in args else 0.1
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 1
    models = [a for a in args[1:] if a.endswith(".pt")]
    test(args[0], models, sample, seed, "cuda" if torch.cuda.is_available() else "cpu")


if __name__ == "__main__":
    main()
