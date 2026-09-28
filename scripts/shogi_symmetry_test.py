"""Check that a shogi environment's network interface is colour-symmetric.

The features and the move encoding are built from the side to move: for gote the
board is turned 180 degrees and the colours swap. So a position and its mirror
image (board turned 180 degrees, colours swapped, the other side to move) must
look the same to the network, apart from the one plane saying whose turn it is.

This checks exactly that, and it runs on 9x9 shogi and 5x5 minishogi alike, so
passing on both means the two games share one rotation convention. The 5x5
comparison only tells us something about 9x9 if they do. The value-perspective
bug came from this rotation, which is why it is worth a test of its own.

How: start two games, one from a position and one from its mirror, then play the
same action id in both. Because moves are encoded from the mover's side, the
same id is the mirrored move. At every ply:

  features   identical except the turn plane, 1 where sente is to move and 0 in
             the mirror
  legal ids  identical sets
  game end   both end together, with results opposite in sign, except where the
             rules themselves are not colour-symmetric: minishogi's 千日手 goes
             against sente in both games, so both may end -1

Usage (inside the container, from /workspace):
    PYTHONPATH=build/shogi     python3 scripts/shogi_symmetry_test.py shogi     [GAMES] [SEED]
    PYTHONPATH=build/minishogi python3 scripts/shogi_symmetry_test.py minishogi [GAMES] [SEED]
"""
import random
import sys

import env_py

STARTS = {
    "shogi": [
        "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
        # lopsided, so the mirror is a different board
        "4k4/7R1/9/9/9/9/9/9/4K4 b - 1",
        "ln1g1k1nl/1r3s1b1/p1pppp1pp/6p2/1p7/2P6/PP1PPPPPP/1BG4R1/LNS1KGSNL b Pp 1",
    ],
    "minishogi": [
        "rbsgk/4p/5/P4/KGSBR b - 1",
        "2k2/5/5/1R3/K4 b - 1",
        "r1sgk/4p/2b2/P4/KGS1R b B 1",
    ],
}
MAX_PLIES = 120
# board_size alone cannot give the area: dobutsu is 3 wide and 4 tall
AREA = {"shogi": 81, "minishogi": 25}  # dobutsu does not rotate, so it has no mirror to check


def mirror_sfen(sfen):
    """Turn the board 180 degrees and swap the colours and the side to move."""
    placement, side, hands, *rest = sfen.split()
    rows = []
    for rank in placement.split("/"):
        cells, promoted = [], ""
        for ch in rank:
            if ch.isdigit():
                cells += [""] * int(ch)
            elif ch == "+":
                promoted = "+"
            else:
                cells.append(promoted + ch.swapcase())
                promoted = ""
        rows.append(cells[::-1])
    out = []
    for cells in rows[::-1]:
        text, empty = "", 0
        for cell in cells:
            if cell == "":
                empty += 1
                continue
            text += (str(empty) if empty else "") + cell
            empty = 0
        out.append(text + (str(empty) if empty else ""))
    swapped_hands = hands if hands == "-" else hands.swapcase()
    return " ".join(["/".join(out), "w" if side == "b" else "b", swapped_hands] + rest)


def new_env(sfen):
    env = env_py.Env()
    if not env.set_from_sfen(sfen):
        raise SystemExit(f"set_from_sfen refused: {sfen}")
    return env


def compare(first, mirror, turn_plane, area):
    fa, fb = first.get_features(), mirror.get_features()
    if len(fa) != len(fb):
        return "feature vectors differ in length"
    sente_first = 1.0 if first.get_turn() == env_py.Player.player_1 else 0.0
    for channel in range(len(fa) // area):
        xa = fa[channel * area:(channel + 1) * area]
        xb = fb[channel * area:(channel + 1) * area]
        if channel == turn_plane:
            if set(xa) != {sente_first} or set(xb) != {1.0 - sente_first}:
                return f"turn plane {channel}: {set(xa)} against {set(xb)}"
        elif xa != xb:
            squares = [i for i in range(area) if xa[i] != xb[i]]
            return f"channel {channel} differs at squares {squares[:6]}"
    la = sorted(a.get_action_id() for a in first.get_legal_actions())
    lb = sorted(a.get_action_id() for a in mirror.get_legal_actions())
    if la != lb:
        return f"legal ids differ: only first {sorted(set(la) - set(lb))[:6]}, only mirror {sorted(set(lb) - set(la))[:6]}"
    return None


def main():
    game = sys.argv[1]
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    env_py.init("")
    rng = random.Random(seed)

    probe = env_py.Env()
    area = AREA[game]
    channels = len(probe.get_features()) // area
    turn_plane = channels - 2
    print(f"{game}: {channels} channels on {area} squares, turn plane {turn_plane}")

    plies = failures = ends = asymmetric_ends = 0
    played = 0
    for played in range(games):
        start = STARTS[game][played % len(STARTS[game])]
        first, mirror = new_env(start), new_env(mirror_sfen(start))
        for ply in range(MAX_PLIES):
            problem = compare(first, mirror, turn_plane, area)
            if problem is None and first.is_terminal() != mirror.is_terminal():
                problem = "one game ended and the other did not"
            if problem is None and first.is_terminal():
                ra, rb = first.get_eval_score(False), mirror.get_eval_score(False)
                ends += 1
                if ra == rb == -1.0:
                    # 千日手 goes against sente whichever side caused it
                    asymmetric_ends += 1
                elif ra != -rb:
                    problem = f"results {ra} and {rb} are not opposite"
            if problem:
                failures += 1
                print(f"FAIL game {played} ply {ply} from '{start}': {problem}")
                break
            if first.is_terminal():
                break
            legal = sorted(first.get_legal_actions(), key=lambda a: a.get_action_id())
            action_id = rng.choice(legal).get_action_id()
            move_first = next(a for a in first.get_legal_actions() if a.get_action_id() == action_id)
            move_mirror = next(a for a in mirror.get_legal_actions() if a.get_action_id() == action_id)
            if not (first.act(move_first) and mirror.act(move_mirror)):
                raise SystemExit(f"act refused a legal action: {action_id}")
            plies += 1
        if failures >= 5:
            break

    print(f"games {played + 1}  plies compared {plies}  games ended {ends}  failures {failures}")
    if asymmetric_ends:
        print(f"  {asymmetric_ends} ends went against sente in both games (千日手)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
