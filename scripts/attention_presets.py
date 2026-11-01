"""Problem positions for the Attention Map presets of the two viewers.

  dobutsu  -> data/dobutsu_all_v2/attention_presets.npz, read by scripts/dobutsu_viewer.py
             lost : wins the network threw away (data/dobutsu_all_v2/lost_wins.csv),
                    orientations 0 and 2 only, 5 at random per model and orientation
             split: 6T and 6R disagree on a win (moves to the end >= 1) in 200,000
                    positions drawn at random (the same ones in both orientations;
                    the table's first positions all have empty hands): only one of
                    them plays a best move, 10 each way per orientation
             drop : a win (moves to the end >= 1) in the same positions whose best
                    moves include a drop, 10 per orientation; the query square is
                    the square of the first best drop, as for 9x9 hand pieces
             agree: 6T plays a best lion move RRTRRT misses and 6T's block 5 head 4 from
                    the lion peaks on its destination; threat: a piece other than the
                    lion attacks our lion and the head peaks on it (10 per orientation)
             defend: a loss in which 6T plays the best (longest) lion move and the head
                    peaks on its destination; gaze: block 4 head 1 from the opponent's lion
                    peaks on our lion (10 per orientation each)
             handkey: giving one hand piece to the opponent changes the true result
                    (data/hand_decides_dobutsu.tsv); the query square is our lion
             handattn: a best drop 6T plays, in SAMPLE positions drawn at random per
                    orientation (seed 21), where giving the dropped piece to the opponent moves some
                    6T head's weight from the drop square the most (10 per orientation)
             mate : a win in which the lion is taken next turn whatever the reply (as a
                    mate in one), where 6T misses the best move, 10 per orientation;
                    the query square is the square of 6T's move
             try  : the same, a win by a try
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

PART = 5_000_000  # records per file of RECORDS/full*/
SAMPLE = 200_000  # random positions searched for split and drop
TOTAL = 246_803_167
RECORDS = "data/dobutsu_all_v2"   # records of scripts/dobutsu_all.cc
MODELS = "models/dobutsu/v2"      # runs of the environment that turns the board to the side to move


def net_square(s, black):
    """Our absolute square s (row * 3 + col, row 0 = rank 4) as the network and the action ids see it:
    turned round for white."""
    return s if black else 11 - s


def dobutsu_move(a, black=True):
    """Our action id, in the mover's frame, as the console string (dobutsu.cpp getDobutsuActionString)."""
    def square(p):
        return "abc"[p % 3] + str(4 - p // 3)

    if a < 36:
        return "GEC"[a // 12] + "*" + square(net_square(a % 12, black))
    frm, d = divmod(a - 36, 8)
    frm, d = net_square(frm, black), (d if black else (d + 4) % 8)
    dr, dc = [-1, -1, 0, 1, 1, 1, 0, -1][d], [0, 1, 1, 1, 0, -1, -1, -1][d]
    return square(frm) + square((frm // 3 + dr) * 3 + frm % 3 + dc)


def record(dobutsu_all, index, orient):
    """One record of the complete analysis, in the data's orientation (0) or turned round (2)."""
    folder = {0: "full", 2: "full_o2"}[orient]
    path = "%s/%s/part_%03d.bin" % (RECORDS, folder, index // PART)
    r = np.fromfile(path, dtype=dobutsu_all.RECORD, count=1, offset=(index % PART) * dobutsu_all.RECORD.itemsize)
    assert r["index"][0] == index and r["orient"][0] == orient
    return r


# how a piece of each Tanaka code (1 chick, 2 elephant, 3 giraffe, 4 hen, 5 lion) steps, for sente (row 0 is rank 4)
STEPS = {1: [(-1, 0)], 2: [(-1, -1), (-1, 1), (1, -1), (1, 1)], 3: [(-1, 0), (1, 0), (0, -1), (0, 1)],
         4: [(-1, 0), (-1, -1), (-1, 1), (0, -1), (0, 1), (1, 0)],
         5: [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]}


def threats(board, target, side):
    """Squares of `side`'s pieces other than the lion (sign of the piece) that can step onto `target`."""
    out = []
    for s, p in enumerate(board):
        if p == 0 or np.sign(p) != side or abs(p) == 5:
            continue
        for dr, dc in STEPS[abs(p)]:
            r, c = s // 3 + (dr if side > 0 else -dr), s % 3 + dc
            if 0 <= r < 4 and 0 <= c < 3 and r * 3 + c == target:
                out.append(s)
    return out


def pick(mask, n=10, seed=2):
    """n of the positions in mask, at random (the table's order puts empty hands first)."""
    return np.sort(np.random.default_rng(seed).permutation(np.nonzero(mask)[0])[:n])


def sample(dobutsu_all, orient, seed=1):
    """SAMPLE records drawn at random from the whole table, in one orientation (0 or 2)."""
    folder = {0: "full", 2: "full_o2"}[orient]
    index = np.sort(np.random.default_rng(seed).choice(TOTAL, SAMPLE, replace=False))
    out = []
    for part in range(TOTAL // PART + 1):
        rows = index[(index >= part * PART) & (index < (part + 1) * PART)] - part * PART
        table = np.memmap("%s/%s/part_%03d.bin" % (RECORDS, folder, part), dtype=dobutsu_all.RECORD, mode="r")
        out.append(np.array(table[rows]))
    r = np.concatenate(out)
    assert (r["index"] == index).all()
    return r


def dobutsu(device):
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dobutsu_all_agreement as A

    side = {0: "先手番", 2: "後手番"}
    recs, labels, kinds, query, action = [], [], [], [], []

    def add(rec, label, kind, q=-1, a=-1):
        """q: the square to start the attention from (-1: chosen in the viewer); a: the move."""
        recs.append(rec)
        labels.append(label)
        kinds.append(kind)
        query.append(q)
        action.append(a)

    groups = {}
    with open(RECORDS + "/lost_wins.csv") as f:
        for name, index, orient, move in csv.reader(f):
            if name != "構成" and orient in ("0", "2"):
                groups.setdefault((name, orient), []).append((int(index), int(move)))
    for (name, orient), rows in groups.items():
        for k in pick(np.ones(len(rows), bool), 5):
            index, move = rows[k]
            add(record(A, index, int(orient)),
                "勝ちを失った %s %s 局面%d 選んだ手 %s" % (name, side[int(orient)], index, dobutsu_move(move, orient == "0")),
                "lost")

    nets = {n: A.load(Path("%s/%s/model/weight_iter_40000.pt" % (MODELS, n)), device) for n in ("6T", "6R", "RRTRRT")}
    import dobutsu_viewer as V
    net6, _, layers, _ = V.attention_net(MODELS + "/6T/model/weight_iter_40000.pt")
    head = (layers.index(4), 3)   # block 5, head 4: the head whose weights are least even

    def from_lion(r, rows, lions, hd=head):
        """One head of 6T (block 5 head 4 unless given) from the given squares, as ratios to the even 1/12.
        Squares in and out are absolute; the network sees white's positions turned round."""
        out = []
        for s in range(0, len(rows), 2048):
            sel = rows[s:s + 2048]
            black = r["turn"][sel] == 1
            with torch.no_grad():
                att = net6.get_attn_table(A.features(r[sel], "cpu"))["att_table"][hd[0]][:, hd[1]]
            w = att[torch.arange(len(sel)), torch.as_tensor(np.where(black, lions[sel], 11 - lions[sel]))].numpy() * 12
            w[~black] = w[~black][:, ::-1]
            out.append(w)
        return np.concatenate(out) if out else np.zeros((0, 12))
    for orient in (0, 2):
        r = sample(A, orient)
        blk = orient == 0
        best = A.bits(r["best"])
        idx = torch.arange(len(r))
        chosen = {n: A.choose(net, r, device) for n, net in nets.items()}
        hit = {n: best[idx, c].numpy() for n, c in chosen.items()}
        win = A.kind(r) == 0
        for good, bad in (("6T", "6R"), ("6R", "6T")):
            for i in pick(win & hit[good] & ~hit[bad]):
                add(r[i:i + 1], "%sだけ最善手 %s 局面%d %s %s／%s %s" % (
                    good, side[orient], r["index"][i], good, dobutsu_move(int(chosen[good][i]), blk),
                    bad, dobutsu_move(int(chosen[bad][i]), blk)), "split")
        drops = best[:, :36].numpy()
        for i in pick(win & drops.any(1)):
            a = int(np.argmax(drops[i]))
            add(r[i:i + 1], "最善手が駒打ち %s 局面%d 最善手 %s" % (side[orient], r["index"][i], dobutsu_move(a, blk)),
                "drop", net_square(a % 12, blk), a)
        # a win "count" moves from the end: 1 is a try, 2 a mate (the lion is taken next turn whatever the reply)
        for name, kind_, count in (("詰み（1手詰め相当）", "mate", 2), ("トライ", "try", 1)):
            for i in pick((r["value"] == 1) & (r["count"] == count) & ~hit["6T"]):
                a = int(chosen["6T"][i])
                add(r[i:i + 1], "%s 6Tが外した %s 局面%d 6T %s／6R %s／最善手 %s" % (
                    name, side[orient], r["index"][i], dobutsu_move(a, blk), dobutsu_move(int(chosen["6R"][i]), blk),
                    "・".join(dobutsu_move(int(b), blk) for b in np.nonzero(best[i].numpy())[0])),
                    kind_, net_square(a % 12 if a < 36 else (a - 36) // 8, blk), a)
        # agree: 6T plays a best lion move that RRTRRT misses, and block 5 head 4 from the lion peaks on
        # its destination (ratio 5 or more); threat: a piece other than the lion attacks our lion and
        # the head peaks on that piece. Positions where the opponent's lion can be taken are left out.
        me = np.where(r["turn"] == 1, 1, -1)
        lion_at = np.array([int(np.argmax(b == 5 * m)) if (b == 5 * m).any() else -1 for b, m in zip(r["board"], me)])
        lion_net = np.where(lion_at >= 0, net_square(lion_at, blk), -1)   # as the action ids see it
        c6 = chosen["6T"].numpy()
        to = np.array([V.SQUARES.index(dobutsu_move(int(a), blk)[-2:]) for a in c6])
        agree = win & hit["6T"] & ~hit["RRTRRT"] & (c6 >= 36) & ((c6 - 36) // 8 == lion_net) & (lion_at >= 0)
        rows = np.nonzero(agree)[0]
        w = from_lion(r, rows, lion_at)
        ok = np.zeros(len(r), bool)
        ok[rows] = (w.argmax(1) == to[rows]) & (w.max(1) >= 5)
        for i in pick(ok):
            k = list(rows).index(i)
            add(r[i:i + 1], "最善手と一致 %s 局面%d 起点 %s 第5ブロックH4 → %s %.2f／6T %s（最善）／RRTRRT %s／最善手 %s" % (
                side[orient], r["index"][i], V.SQUARES[lion_at[i]], V.SQUARES[int(w[k].argmax())], w[k].max(),
                dobutsu_move(int(c6[i]), blk), dobutsu_move(int(chosen["RRTRRT"][i]), blk),
                "・".join(dobutsu_move(int(b), blk) for b in np.nonzero(best[i].numpy())[0])), "agree", int(lion_at[i]), int(c6[i]))
        att_by = {i: threats(r["board"][i], lion_at[i], -me[i]) for i in np.nonzero((lion_at >= 0) & (A.kind(r) != 1))[0]}
        rows = np.array([i for i, t in att_by.items() if t], dtype=int)
        w = from_lion(r, rows, lion_at)
        ok = np.zeros(len(r), bool)
        ok[rows] = [int(w[k].argmax()) in att_by[i] and w[k].max() >= 5 for k, i in enumerate(rows)]
        for i in pick(ok):
            k = list(rows).index(i)
            add(r[i:i + 1], "狙ってくる駒 %s 局面%d 起点 %s 第5ブロックH4 → %s %.2f／狙う駒 %s／6T %s／RRTRRT %s／最善手 %s" % (
                side[orient], r["index"][i], V.SQUARES[lion_at[i]], V.SQUARES[int(w[k].argmax())], w[k].max(),
                "・".join(V.SQUARES[t] for t in att_by[i]), dobutsu_move(int(c6[i]), blk), dobutsu_move(int(chosen["RRTRRT"][i]), blk),
                "・".join(dobutsu_move(int(b), blk) for b in np.nonzero(best[i].numpy())[0])), "threat", int(lion_at[i]), int(c6[i]))
        # defend: a loss in which 6T plays the best (longest) lion move and the head peaks on its destination
        defend = (A.kind(r) == 3) & hit["6T"] & (c6 >= 36) & ((c6 - 36) // 8 == lion_net) & (lion_at >= 0)
        rows = np.nonzero(defend)[0]
        w = from_lion(r, rows, lion_at)
        ok = np.zeros(len(r), bool)
        ok[rows] = (w.argmax(1) == to[rows]) & (w.max(1) >= 5)
        for i in pick(ok):
            k = list(rows).index(i)
            add(r[i:i + 1], "粘りの手 %s 局面%d 起点 %s 第5ブロックH4 → %s %.2f／6T %s（最善）／RRTRRT %s／最善手 %s" % (
                side[orient], r["index"][i], V.SQUARES[lion_at[i]], V.SQUARES[int(w[k].argmax())], w[k].max(),
                dobutsu_move(int(c6[i]), blk), dobutsu_move(int(chosen["RRTRRT"][i]), blk),
                "・".join(dobutsu_move(int(b), blk) for b in np.nonzero(best[i].numpy())[0])), "defend", int(lion_at[i]), int(c6[i]))
        # gaze: block 4 head 1 from the opponent's lion peaks on our lion
        opp_at = np.array([int(np.argmax(b == -5 * m)) if (b == -5 * m).any() else -1 for b, m in zip(r["board"], me)])
        rows = np.nonzero((opp_at >= 0) & (lion_at >= 0) & np.isin(A.kind(r), (0, 2, 3)))[0]
        w = from_lion(r, rows, opp_at, (layers.index(3), 0))
        ok = np.zeros(len(r), bool)
        ok[rows] = (w.argmax(1) == lion_at[rows]) & (w.max(1) >= 5)
        for i in pick(ok):
            k = list(rows).index(i)
            add(r[i:i + 1], "相手のライオンから %s 局面%d 起点 %s（相手のライオン） 第4ブロックH1 → %s %.2f／%s／6T %s／RRTRRT %s／最善手 %s" % (
                side[orient], r["index"][i], V.SQUARES[opp_at[i]], V.SQUARES[int(w[k].argmax())], w[k].max(),
                A.KINDS[A.kind(r[i:i + 1])[0]], dobutsu_move(int(c6[i]), blk), dobutsu_move(int(chosen["RRTRRT"][i]), blk),
                "・".join(dobutsu_move(int(b), blk) for b in np.nonzero(best[i].numpy())[0])), "gaze", int(opp_at[i]), int(c6[i]))
    # handkey: giving one hand piece to the opponent changes the result of the complete analysis
    # (data/hand_decides_dobutsu.tsv, looked up with the exporter's text mode); query: our lion
    names = ["キリン", "ゾウ", "ヒヨコ"]
    result = {1: "勝ち", 0: "引き分け", -1: "負け"}
    with open("data/hand_decides_dobutsu.tsv") as f:
        for row in list(csv.DictReader(f, delimiter="\t")):
            rec = record(A, int(row["index"]), int(row["orient"]))
            a = int(A.choose(nets["6T"], rec, device)[0])
            me = 1 if rec["turn"][0] == 1 else -1
            add(rec, "持ち駒が勝敗を決める %s 局面%s %sを相手に渡すと %s→%s／6T value %+.2f→%+.2f／6T %s" % (
                side[int(row["orient"])], row["index"], names[int(row["piece"])], result[int(row["true_before"])],
                result[int(row["true_after"])], float(row["value_before"]), float(row["value_after"]), dobutsu_move(a, int(row["orient"]) == 0)),
                "handkey", int(np.argmax(rec["board"][0] == 5 * me)), a)
    # handattn: the drops whose attention from the drop square changes the most when the
    # dropped piece is given away (the largest change of any 6T head, as a ratio to 1/12)
    net6, _, layers6, heads6 = V.attention_net(Path(MODELS) / "6T/model/weight_iter_40000.pt")
    for orient in (0, 2):
        r = sample(A, orient, seed=21)
        blk = orient == 0
        best = A.bits(r["best"]).numpy()
        r = r[best[:, :36].any(1) & (r["count"] > 0)]
        best = A.bits(r["best"]).numpy()
        found = []
        for s in range(0, len(r), 1024):
            rr = r[s:s + 1024]
            a = A.choose(nets["6T"], rr, device).cpu().numpy()
            ok = np.nonzero((a < 36) & best[s:s + 1024][np.arange(len(rr)), a].astype(bool))[0]
            if not len(ok):
                continue
            rr, a = rr[ok], a[ok]
            x = A.features(rr, "cpu")
            g = x.clone()
            i = torch.arange(len(rr))
            plane = torch.as_tensor(12 + a // 12)
            g[i, plane] -= 1
            g[i, plane + 3] += 1
            q = torch.as_tensor([net_square(V.SQUARES.index(dobutsu_move(int(m), blk)[-2:]), blk) for m in a])
            with torch.no_grad():
                t0, t1 = net6.get_attn_table(x)["att_table"], net6.get_attn_table(g)["att_table"]
            change = torch.stack([((t0[k][i, h, q] - t1[k][i, h, q]).abs().max(-1).values * 12)
                                  for k in range(len(layers6)) for h in range(heads6)], 1)
            top, kh = change.max(1)
            found += [(float(top[j]), s + int(ok[j]), int(a[j]), int(kh[j])) for j in range(len(rr))]
        for d, j, a, kh in sorted(found, reverse=True)[:10]:
            add(r[j:j + 1], "持ち駒で Attention が変わる %s 局面%d 打つ先 %s 第%dブロックH%d 変化 %.2f／6T %s" % (
                side[orient], r["index"][j], dobutsu_move(a, blk)[-2:], layers6[kh // heads6] + 1, kh % heads6 + 1, d,
                dobutsu_move(a, blk)), "handattn", V.SQUARES.index(dobutsu_move(a, blk)[-2:]), a)
    out = RECORDS + "/attention_presets.npz"
    np.savez(out, records=np.concatenate(recs), labels=np.array(labels), kinds=np.array(kinds),
             query=np.array(query), action=np.array(action))
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
