"""Exercise the shogi rules that only show up in rare positions.

Reading the code proves the functions exist. These set the positions up and check
what the environment actually decides.
"""
import sys

sys.path.insert(0, "scripts")
mod = __import__("build.shogi", globals(), locals(), ["env_py"], 0)
env_py = mod.env_py
env_py.init("configs/9x9_shogi/10R-bigserver.cfg")
from shogi_coords import usi_to_action_id, action_id_to_usi  # noqa: E402

B, W = env_py.Player.player_1, env_py.Player.player_2


def legal_usi(env, is_black):
    return sorted(action_id_to_usi(a.get_action_id(), is_black)
                  for a in env.get_legal_actions())


def try_move(env, usi, is_black):
    aid = usi_to_action_id(usi, is_black)
    return env.is_legal_action(env_py.Action(aid, B if is_black else W))


def play(env, moves, black_first=True):
    for i, m in enumerate(moves):
        is_black = (i % 2 == 0) == black_first
        aid = usi_to_action_id(m, is_black)
        act = env_py.Action(aid, B if is_black else W)
        if not env.is_legal_action(act):
            return False, i, m
        env.act(act)
    return True, len(moves), None


print("=== 1. 打ち歩詰め ===")
# white king on 5a with its own lances on 6a and 4a: lances move straight down
# for white, so neither can take on 5b. Black golds on 6c and 4c cover 6b and 4b
# and both defend 5b, so the king cannot take there either.
# P*5b is mate, so it must be illegal. G*5b is the same mate with a gold and
# must stay legal -- that is the difference the rule draws.
env = env_py.Env()
env.reset()
ok = env.set_from_sfen("3lkl3/9/3G1G3/9/9/9/9/9/8K b GP 1")
print(f"  position set: {ok}")
print(env.to_string())
print(f"  P*5b (pawn drop mate)  legal = {try_move(env, 'P*5b', True)} <- must be False")
print(f"  G*5b (gold drop mate)  legal = {try_move(env, 'G*5b', True)} <- must be True")

print("\n=== 2. 二歩 ===")
env = env_py.Env()
env.reset()
env.set_from_sfen("4k4/9/9/9/9/9/4P4/9/4K4 b P 1")
print(f"  black already has a pawn on file 5")
print(f"  P*5e (same file)       legal = {try_move(env, 'P*5e', True)} <- must be False")
print(f"  P*4e (another file)    legal = {try_move(env, 'P*4e', True)} <- must be True")

print("\n=== 3. 行き所のない駒 ===")
env = env_py.Env()
env.reset()
env.set_from_sfen("4k4/9/9/9/9/9/9/9/4K4 b NLP 1")
for m, want in [("P*5a", False), ("L*5a", False), ("N*5a", False), ("N*5b", False), ("N*5c", True)]:
    got = try_move(env, m, True)
    mark = "OK " if got == want else "!! "
    print(f"  {mark}{m: <6} legal = {got}   (expected {want})")

print("\n=== 4. 千日手 ===")
env = env_py.Env()
env.reset()
cycle = ["2h3h", "8b7b", "3h2h", "7b8b"]
for rep in range(1, 6):
    done, n, bad = play(env, cycle)
    if not done:
        print(f"  repetition {rep}: {bad} rejected")
        break
    score = env.get_eval_score(False)
    print(f"  same position seen {rep + 1} times: terminal={env.is_terminal()} score={score}")
    if env.is_terminal():
        break

print("\n=== 5. 連続王手の千日手 ===")
# black rook on 4i, outside the promotion zone so it can move without promoting.
# it checks the bare white king along a file, the king steps aside, the rook
# swings to the next file: perpetual check, repeating every four plies.
env = env_py.Env()
env.reset()
env.set_from_sfen("4k4/9/9/9/9/9/9/9/5RK2 b - 1")
seq = ["4i5i", "5a4a", "5i4i", "4a5a"] * 4
for i, mv in enumerate(seq):
    is_black = (i % 2 == 0)
    act = env_py.Action(usi_to_action_id(mv, is_black), B if is_black else W)
    if not env.is_legal_action(act):
        print(f"  ply {i}: {mv} rejected")
        break
    env.act(act)
    if env.is_terminal():
        print(f"  ply {i} ({mv}): terminal, score {env.get_eval_score(False)}")
        print("  score is from black's view: -1 means the perpetual checker lost")
        break
else:
    print(f"  {len(seq)} plies played without a verdict")
