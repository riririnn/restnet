#!/usr/bin/env python3
"""Replay a CSA game record and emit the SFEN at chosen plies.

Handles the initial position from P1..P9 lines (or PI = even game), then applies
each CSA move (captures -> hand, promotions), so any midgame position can be
exported as a SFEN for the SFEN console / attention visualization.

Usage:
    python3 scripts/csa_to_sfen.py GAME.csa                 # SFEN every 10 plies
    python3 scripts/csa_to_sfen.py GAME.csa --ply 40        # SFEN after 40 plies
    python3 scripts/csa_to_sfen.py GAME.csa --every 5       # SFEN every 5 plies
    python3 scripts/csa_to_sfen.py GAME.csa --model M.pt    # + policy confidence
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# CSA piece code -> (base kind 0..7, promoted?)
_CSA2KIND = {"FU": 0, "KY": 1, "KE": 2, "GI": 3, "KI": 4, "KA": 5, "HI": 6, "OU": 7,
             "TO": 0, "NY": 1, "NK": 2, "NG": 3, "UM": 5, "RY": 6}
_PROMOTED = {"TO", "NY", "NK", "NG", "UM", "RY"}
_KIND2SFEN = {0: "P", 1: "L", 2: "N", 3: "S", 4: "G", 5: "B", 6: "R", 7: "K"}
_DROPPABLE = ["R", "B", "G", "S", "N", "L", "P"]           # SFEN hand order
_SFEN_ORDER_KIND = [6, 5, 4, 3, 2, 1, 0]                    # R,B,G,S,N,L,P
_MOVE_RE = re.compile(r"^([+-])(\d{2})(\d{2})([A-Z]{2})$")


class State:
    def __init__(self):
        self.cells = {}                        # (file,rank) -> (owner,kind,promoted)
        self.hands = {"b": {k: 0 for k in range(7)}, "w": {k: 0 for k in range(7)}}
        self.ply = 0                            # number of moves applied

    def start_even(self):
        back = [1, 2, 3, 4, 7, 4, 3, 2, 1]     # L N S G K G S N L (file9..1)
        for i, kind in enumerate(back):
            f = 9 - i
            self.cells[(f, 1)] = ("w", kind, False)
            self.cells[(f, 9)] = ("b", kind, False)
            self.cells[(f, 3)] = ("w", 0, False)
            self.cells[(f, 7)] = ("b", 0, False)
        self.cells[(8, 2)] = ("w", 6, False)   # 後手飛
        self.cells[(2, 2)] = ("w", 5, False)   # 後手角
        self.cells[(2, 8)] = ("b", 6, False)   # 先手飛
        self.cells[(8, 8)] = ("b", 5, False)   # 先手角

    def set_from_p_lines(self, plines):
        for line in plines:
            rank = int(line[1])
            body = line[2:]
            for c in range(9):
                grp = body[c * 3:c * 3 + 3]
                f = 9 - c
                if "*" in grp or grp.strip() == "":
                    continue
                owner = "b" if grp[0] == "+" else "w"
                code = grp[1:3]
                self.cells[(f, rank)] = (owner, _CSA2KIND[code], code in _PROMOTED)

    def apply(self, sign, frm, to, code):
        owner = "b" if sign == "+" else "w"
        tf, tr = int(to[0]), int(to[1])
        kind = _CSA2KIND[code]
        promo = code in _PROMOTED
        if frm == "00":                        # drop
            self.hands[owner][kind] -= 1
            self.cells[(tf, tr)] = (owner, kind, False)
        else:
            ff, fr = int(frm[0]), int(frm[1])
            self.cells.pop((ff, fr), None)
            tgt = self.cells.get((tf, tr))
            if tgt is not None:                # capture -> demote into hand
                self.hands[owner][tgt[1]] += 1
            self.cells[(tf, tr)] = (owner, kind, promo)
        self.ply += 1

    def to_sfen(self):
        rows = []
        for r in range(1, 10):
            s = ""
            run = 0
            for f in range(9, 0, -1):
                c = self.cells.get((f, r))
                if c is None:
                    run += 1
                    continue
                if run:
                    s += str(run)
                    run = 0
                owner, kind, promo = c
                let = _KIND2SFEN[kind]
                let = ("+" + let) if promo else let
                s += let if owner == "b" else let.lower()
            if run:
                s += str(run)
            rows.append(s)
        turn = "b" if self.ply % 2 == 0 else "w"
        hand = ""
        for owner, up in (("b", True), ("w", False)):
            for k in _SFEN_ORDER_KIND:
                n = self.hands[owner][k]
                if n:
                    let = _KIND2SFEN[k]
                    hand += (str(n) if n > 1 else "") + (let if up else let.lower())
        return f"{'/'.join(rows)} {turn} {hand or '-'} {self.ply + 1}"


def parse_csa(path):
    plines, moves = [], []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if re.match(r"^P[1-9]", line):
                plines.append(line)
            elif line == "PI":
                plines = ["PI"]
            else:
                m = _MOVE_RE.match(line)
                if m:
                    moves.append(m.groups())
    return plines, moves


def build_states(path):
    plines, moves = parse_csa(path)
    st = State()
    if plines and plines[0] != "PI":
        st.set_from_p_lines(plines)
    else:
        st.start_even()
    states = [st.to_sfen()]                     # ply 0
    for sign, frm, to, code in moves:
        st.apply(sign, frm, to, code)
        states.append(st.to_sfen())
    return states                               # index = ply


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csa", help="CSA game record")
    ap.add_argument("--ply", type=int, default=None, help="単一の手数のSFEN")
    ap.add_argument("--every", type=int, default=10, help="この手数ごとに出力（既定10）")
    ap.add_argument("--model", default=None, help="policy自信度も表示するモデル.pt")
    args = ap.parse_args()

    states = build_states(args.csa)
    total = len(states) - 1
    print(f"総手数: {total}")

    model = None
    if args.model:
        import torch
        model = torch.jit.load(args.model, map_location="cpu")
        model.eval()

    def report(ply):
        sfen = states[ply]
        line = f"[{ply:3d}手] {sfen}"
        if model is not None:
            import torch
            import torch.nn.functional as F
            from tsume_shogi import sfen_to_tensor
            from shogi_coords import action_id_to_usi
            is_black = sfen.split()[1] == "b"
            with torch.no_grad():
                out = model(sfen_to_tensor(sfen))
            prob = F.softmax(out["policy_logit"][0], 0)
            top = prob.topk(1)
            ent = float(-(prob * prob.clamp_min(1e-12).log()).sum())
            bm = action_id_to_usi(int(top.indices[0]), is_black)
            line += f"\n        value={out['value'].item():+.2f} entropy={ent:.2f} top={bm}({top.values[0]*100:.0f}%)"
        print(line)

    if args.ply is not None:
        report(max(0, min(args.ply, total)))
    else:
        for ply in range(0, total + 1, args.every):
            report(ply)


if __name__ == "__main__":
    main()
