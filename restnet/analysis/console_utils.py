import numpy as np
import math
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


def gen_gptresult(p, tp, boardsize):
    result = ""
    bs = boardsize
    if tp == "dboard":
        for i in range(bs):
            for j in range(bs):
                result += str(p[(bs - i - 1) * bs + j]) + " "
            result += "\n"
    elif tp == "gtx":
        result += "LABEL "
        for i in range(bs):
            for j in range(bs):
                result += str(chr(ord('A') + j)) if ord('A') + j < ord('I') else str(chr(ord('A') + j + 1))
                result += str(bs - i) + " "
                result += str(round(p[(bs - i - 1) * bs + j], 3)) + " "
    elif tp == "color":
        cmap = plt.cm.coolwarm
        norm = mcolors.Normalize(vmin=-1, vmax=1)  # Normalize Your Data

        def get_color(val):
            return mcolors.to_hex(cmap(norm(val))[:3])  # Return RGBA Color from Normed Val

        for i in range(bs):
            for j in range(bs):
                result += "COLOR " + str(get_color(p[(bs - i - 1) * bs + j])) + " "
                result += str(chr(ord('A') + j)) if ord('A') + j < ord('I') else str(chr(ord('A') + j + 1))
                result += str(bs - i) + "\n"
    else:
        result += "LABEL "
        for i in range(bs):
            for j in range(bs):
                if p[(bs - i - 1) * bs + j] != 0:
                    result += str(chr(ord('A') + j)) if ord('A') + j < ord('I') else str(chr(ord('A') + j + 1))
                    result += str(bs - i) + " "
                    result += str(int(p[(bs - i - 1) * bs + j])) + " "
    return result


def trans2idx(pos, boardsize):
    b2idx = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "J": 8, "K": 9, "L": 10, "M": 11, "N": 12, "O": 13, "P": 14, "Q": 15, "R": 16, "S": 17, "T": 18, }
    return b2idx[pos[0]] + (int(pos[1:]) - 1) * boardsize


def idx2w(pos, boardsize):
    bsf = int(pos / boardsize)
    r = str(chr(ord('A') + bsf)) if ord('A') + bsf < ord('I') else str(chr(ord('A') + bsf + 1))
    return r + str(pos % boardsize + 1)


def normalization(data):
    min_val = min(data)
    max_val = max(data)
    range = max_val - min_val
    nl = [(i - min_val) / range for i in data]
    return np.array(nl)


def normalization_exp(data):
    min_val = min(data)
    max_val = max(data)
    range = max_val - min_val
    nl = [(i - min_val) / range for i in data]
    nll = [(((math.exp(4 * (sub_nl - 0.5)) - math.exp(-4 * (sub_nl - 0.5))) / (math.exp(4 * (sub_nl - 0.5)) + math.exp(-4 * (sub_nl - 0.5)))) + 1.0) / 2.0 for sub_nl in nl]
    return np.array(nll)


def bvnormalization(data):
    nl = [2 * i - 1 for i in data]
    return np.array(nl)
