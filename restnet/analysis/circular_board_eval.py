import torch
import sys
import os
from console import get_network
import re
import numpy as np

game_type = "go"
_temps = __import__(f"build.{game_type}", globals(), locals(), ["restnet_py"], 0)
restnet_py = _temps.restnet_py

_temps = __import__(f"build.{game_type}", globals(), locals(), ["env_py"], 0)
env_py = _temps.env_py

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def get_env(sgf_file_name):

    if sgf_file_name is not None:
        env_loader = env_py.EnvLoader()
        env = env_loader.init_env_from_sgf(sgf_file_name)
    else:
        env = env_py.Env()
    return env


def getfeature(env):
    return torch.FloatTensor(env.get_features()).view(
        1,
        restnet_py.get_nn_num_input_channels(),
        restnet_py.get_nn_input_channel_height(),
        restnet_py.get_nn_input_channel_width(),
    )


def extract_pos_to_array(sgf_string, color, board_size=19):
    """
    Extract indices from POS[] field in an SGF string and convert them into a 1D numpy array.
    The positions mentioned in POS[] will be marked as 1.
    Output array will have shape (board_size * board_size,)
    """

    target_value = 1 if color == "B" else -1
    # Initialize a flat array of zeros
    board = np.zeros(board_size * board_size, dtype=np.int32)

    # Use regex to extract the content inside POS[...]
    match = re.search(r"POS\[([0-9,]+)\]", sgf_string)
    if not match:
        return board  # Return empty array if POS not found

    # Parse the indices and mark them as 1
    indices = [int(i) for i in match.group(1).split(",") if i.strip()]
    for idx in indices:
        if 0 <= idx < board_size * board_size:
            board[idx] = target_value
        else:
            print(f"Warning: index {idx} is out of board bounds")

    return board, indices


def mse(array1, array2, indices):
    """
    Compute the Mean Squared Error (MSE) between array1 and array2,
    but only over the positions specified in `indices`.

    Parameters:
        array1 (np.ndarray): First array (flattened or 1D).
        array2 (np.ndarray): Second array (same shape as array1).
        indices (Iterable[int]): List or array of indices to include in the MSE calculation.

    Returns:
        float: Mean Squared Error over the selected indices.
    """
    if array1.shape != array2.shape:
        raise ValueError(f"Shape mismatch: {array1.shape} vs {array2.shape}")

    if len(indices) == 0:
        return float("nan")  # Avoid divide by zero

    # Convert indices to numpy array in case it's a list
    indices = np.array(indices, dtype=int)

    # Index into both arrays
    array1_selected = array1[indices]
    array2_selected = array2[indices]

    # Compute MSE
    mse_value = np.mean((array1_selected - array2_selected) ** 2)
    return mse_value


def bv(network, env):
    features = getfeature(env)
    out = network(features.to(device))
    if "bv" not in out:
        return "this model does not support bv command\n"

    bv = out["bv"].cpu().detach().numpy()[0]
    bv = bv * 2 - 1  # Map [0, 1] to [-1, 1]
    return bv


if __name__ == "__main__":
    if len(sys.argv) == 6:
        R3RRT_model_file = sys.argv[1]
        R3RRT_conf_file_name = sys.argv[2]
        _10R_model_file = sys.argv[3]
        _10R_conf_file_name = sys.argv[4]
        opening_dir_path = sys.argv[5]
    else:
        print("Usage: python console.py [model_file] [conf_file_name] [sgf_file_name]")
        exit(0)

    restnet_py.load_config_file(R3RRT_conf_file_name)
    env_py.init(R3RRT_conf_file_name)
    network, restnetpy = get_network(R3RRT_model_file, R3RRT_conf_file_name, "go")
    R3RRT_results_table = {}

    # each sgf file in the sgf_file_name
    for sgf_file_name in sorted(os.listdir(opening_dir_path)):
        if not sgf_file_name.endswith(".sgf"):
            continue
        sgf_file_base = sgf_file_name
        sgf_file_name = os.path.join(opening_dir_path, sgf_file_name)

        with open(sgf_file_name, "r") as f:
            sgf_string = f.read()
            match = re.search(r"CO\[(B|W)\]", sgf_string)
            color = match.group(1)
        env = get_env(sgf_file_name)
        bv_ = bv(network, env)
        labels, indices = extract_pos_to_array(sgf_string, color, board_size=19)
        mse_ = mse(bv_, labels, indices)
        R3RRT_results_table[sgf_file_base] = mse_

    restnet_py.load_config_file(_10R_conf_file_name)
    env_py.init(_10R_conf_file_name)
    network, restnetpy = get_network(_10R_model_file, _10R_conf_file_name, "go")
    _10R_results_table = {}

    # each sgf file in the sgf_file_name
    for sgf_file_name in sorted(os.listdir(opening_dir_path)):
        if not sgf_file_name.endswith(".sgf"):
            continue
        sgf_file_base = sgf_file_name
        sgf_file_name = os.path.join(opening_dir_path, sgf_file_name)

        with open(sgf_file_name, "r") as f:
            sgf_string = f.read()
            match = re.search(r"CO\[(B|W)\]", sgf_string)
            color = match.group(1)
        env = get_env(sgf_file_name)
        bv_ = bv(network, env)
        labels, indices = extract_pos_to_array(sgf_string, color, board_size=19)
        mse_ = mse(bv_, labels, indices)
        _10R_results_table[sgf_file_base] = mse_

    # Sort the dict by numeric part of the filename
    sorted_items = sorted(
        _10R_results_table.items(), key=lambda x: int(x[0].split(".")[0])
    )
    # Header
    print(f"{'sgf name':<15} | {'10R':<10} | {'R3RRT':<10}")
    print("-" * 15 + "-+-" + "-" * 10 + "-+-" + "-" * 10)

    # Accumulators for computing average
    total_10R = 0.0
    total_r3rrt = 0.0
    count = 0

    # Rows
    for sgf_file_base, mse_value in sorted_items:
        r3rrt_value = R3RRT_results_table[sgf_file_base]
        print(
            f"{os.path.basename(sgf_file_base):<15} | {mse_value:<10.5f} | {r3rrt_value:<10.5f}"
        )
        total_10R += mse_value
        total_r3rrt += r3rrt_value
        count += 1

    # Compute and print averages
    avg_10R = total_10R / count if count > 0 else float("nan")
    avg_r3rrt = total_r3rrt / count if count > 0 else float("nan")

    print("-" * 15 + "-+-" + "-" * 10 + "-+-" + "-" * 10)
    print(f"{'average':<15} | {avg_10R:<10.5f} | {avg_r3rrt:<10.5f}")
    print()
    print("Table: The MSE of board evaluation in 24 games from cyclic-adversary.")
