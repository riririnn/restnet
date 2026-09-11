"""Compare the C++ feature tensor against the Python one, position by position.

getFeatures() in shogi.cpp and sfen_to_tensor() in tsume_shogi.py build the same
362-plane input independently. Pretraining data and the XAI tools go through the
Python one; self-play goes through the C++ one. If they disagree, the two learn
different worlds and nothing errors.

Python encodes only the current position, so only the t=0 block is comparable:
channels 0-27 (board), 31-44 (hands), 360 (turn), 361 (move count). Channels
28-30 (repetition) and the seven older history steps are left out of the
comparison because a single SFEN cannot carry them.
"""
import re
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from csa_to_sfen import build_states           # noqa: E402
from tsume_shogi import sfen_to_tensor         # noqa: E402
from shogi_coords import action_id_to_usi      # noqa: E402  (only for reporting)

mod = __import__("build.shogi", globals(), locals(), ["env_py"], 0)
env_py = mod.env_py
env_py.init("configs/9x9_shogi/10R-bigserver.cfg")

BOARD = list(range(0, 28))
HANDS = list(range(31, 45))
GLOBALS = [360, 361]

sgf_path = sys.argv[1]
num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 5


lines = [l for l in open(sgf_path, errors="ignore") if l.startswith("(")][:num_games]
total_positions = 0
mismatched_positions = 0
channel_hits = {}

for gi, line in enumerate(lines, 1):
    ids = [(c, int(a)) for c, a in re.findall(r";([BW])\[(\d+)\]", line)]
    if not ids:
        continue

    with tempfile.NamedTemporaryFile("w", suffix=".sgf", delete=False) as f:
        f.write(line)
        sgf_one = f.name
    csa = subprocess.run([sys.executable, "scripts/sgf_to_csa.py", sgf_one],
                         capture_output=True, text=True).stdout
    with tempfile.NamedTemporaryFile("w", suffix=".csa", delete=False) as f:
        f.write(csa)
        csa_path = f.name
    sfens = build_states(csa_path)

    env = env_py.Env()
    env.reset()
    for ply in range(len(ids) + 1):
        if ply >= len(sfens):
            break
        cpp = np.array(env.get_features(), dtype=np.float32).reshape(362, 81)
        py = sfen_to_tensor(sfens[ply]).numpy().reshape(362, 81)
        total_positions += 1
        bad = [c for c in BOARD + HANDS + GLOBALS if not np.allclose(cpp[c], py[c])]
        if bad:
            mismatched_positions += 1
            for c in bad:
                channel_hits[c] = channel_hits.get(c, 0) + 1
            if mismatched_positions <= 3:
                print(f"game {gi} ply {ply}: channels {bad[:8]}")
                for c in bad[:2]:
                    print(f"   ch {c}: c++ sum {cpp[c].sum(): .3f}  python sum {py[c].sum(): .3f}")
        if ply < len(ids):
            colour, aid = ids[ply]
            p = env_py.Player.player_1 if colour == "B" else env_py.Player.player_2
            act = env_py.Action(aid, p)
            if not env.is_legal_action(act):
                break
            env.act(act)

print(f"\npositions compared: {total_positions}")
print(f"positions differing: {mismatched_positions}")
if channel_hits:
    print("channels involved  :")
    for c, n in sorted(channel_hits.items()):
        what = ("board" if c < 28 else "hand" if c < 45 else
                "turn" if c == 360 else "move count")
        print(f"   ch {c: <3} ({what: <10}) in {n} positions")
else:
    print("=> the two implementations agree on every compared channel")
