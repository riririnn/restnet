"""Starting positions for matches, as in Demura and Kaneko (GPW 2023, ICGA Journal 2024):
human games of nine openings, each cut at a random ply from 20 to 40.

The games are the 2ch kifu collection (2chkifu_csa.zip from
https://web.archive.org/web/2019/http://www.geocities.jp/shogi_depot/), which holds
at least 2,000 games of each opening. Every move is checked against minizero's
legal moves, so a position that minizero cannot reach is never written.

Run inside the container (env_py is built for its python):
  PYTHONPATH=build/shogi python3 scripts/make_openings.py data/2chkifu/2chkifu_csa.zip \
      --conf configs/9x9_shogi/RRTRRT-bigserver.cfg --per-opening 2000 --out data/openings.tsv
"""
import argparse
import random
import zipfile

import env_py

OPENINGS = ["角換わり", "相掛かり", "横歩取り", "矢倉", "中飛車", "四間飛車", "三間飛車", "向飛車", "相振飛車"]
DROP = {"FU": "P", "KY": "L", "KE": "N", "GI": "S", "KI": "G", "KA": "B", "HI": "R"}
PROMOTED = {"TO", "NY", "NK", "NG", "UM", "RY"}


def usi_moves(csa, plies):
    """The first `plies` moves of a CSA move string as USI moves, or None if one is not legal."""
    env = env_py.Env()
    env.reset()
    out = []
    for i in range(plies):
        m = csa[6 * i:6 * i + 6]
        if len(m) < 6:
            return None
        to = m[2] + chr(ord("a") + int(m[3]) - 1)
        if m[:2] == "00":
            usi = DROP[m[4:]] + "*" + to
        else:
            usi = m[0] + chr(ord("a") + int(m[1]) - 1) + to
        legal = {a.to_console_string(): a for a in env.get_legal_actions()}
        # a promoted piece code means a promotion only if the piece was not promoted before
        if m[4:] in PROMOTED and usi + "+" in legal:
            usi += "+"
        if usi not in legal:
            return None
        env.act(legal[usi])
        out.append(usi)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kifu_zip")
    ap.add_argument("--conf", required=True)
    ap.add_argument("--per-opening", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    env_py.init(args.conf)
    rng = random.Random(args.seed)

    games = {name: [] for name in OPENINGS}
    z = zipfile.ZipFile(args.kifu_zip)
    for part in sorted(z.namelist()):
        lines = z.read(part).decode("shift_jis", errors="replace").splitlines()
        for head, moves in zip(lines[0::2], lines[1::2]):
            fields = head.split()
            if fields and fields[-1] in games:
                games[fields[-1]].append((fields[0], part, moves.strip()))

    with open(args.out, "w") as f:
        for name in OPENINGS:
            pool = games[name][:]
            rng.shuffle(pool)
            written = 0
            for game_id, part, csa in pool:
                if written == args.per_opening:
                    break
                plies = rng.randint(20, 40)
                moves = usi_moves(csa, plies)
                if moves is None:
                    continue
                f.write("%s\t%s:%s\t%d\t%s\n" % (name, part, game_id, plies, " ".join(moves)))
                written += 1
            print(name, "games", len(games[name]), "written", written)


if __name__ == "__main__":
    main()
