#!/usr/bin/env python

import sys
import time
import re
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from network.create_network import create_network


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs, flush=True)


def load_model(game_type, old_pkl, new_save_path):
    # training_step, network, device, optimizer, scheduler
    training_step = 0
    print("get_ganem_name:", restnet_py.get_game_name())
    print("get_nn_num_input_channels:", restnet_py.get_nn_num_input_channels())
    print("get_nn_input_channel_height:", restnet_py.get_nn_input_channel_height())
    print("get_nn_input_channel_width:", restnet_py.get_nn_input_channel_width())
    print("get_nn_num_hidden_channels:", restnet_py.get_nn_num_hidden_channels())
    print("get_nn_hidden_channel_height:", restnet_py.get_nn_hidden_channel_height())
    print("get_nn_hidden_channel_width:", restnet_py.get_nn_hidden_channel_width())
    print(
        "get_nn_num_action_feature_channels:",
        restnet_py.get_nn_num_action_feature_channels(),
    )
    print("get_nn_num_blocks:", restnet_py.get_nn_num_blocks())
    print("get_nn_action_size:", restnet_py.get_nn_action_size())
    print(
        "get_nn_num_value_hidden_channels:",
        restnet_py.get_nn_num_value_hidden_channels(),
    )
    print("get_nn_discrete_value_size:", restnet_py.get_nn_discrete_value_size())
    print("get_nn_type_name:", restnet_py.get_nn_type_name())
    print("get_nn_embed_kernel_size:", restnet_py.get_nn_embed_kernel_size())
    print("get_nn_blocks_type:", restnet_py.get_nn_blocks_type())
    print("get_nn_policy_type:", restnet_py.get_nn_policy_type())
    print("get_nn_value_type:", restnet_py.get_nn_value_type())

    network = create_network(
        restnet_py.get_game_name(),
        restnet_py.get_nn_num_input_channels(),
        restnet_py.get_nn_input_channel_height(),
        restnet_py.get_nn_input_channel_width(),
        restnet_py.get_nn_num_hidden_channels(),
        restnet_py.get_nn_hidden_channel_height(),
        restnet_py.get_nn_hidden_channel_width(),
        restnet_py.get_nn_num_action_feature_channels(),
        restnet_py.get_nn_num_blocks(),
        restnet_py.get_nn_action_size(),
        restnet_py.get_nn_num_value_hidden_channels(),
        restnet_py.get_nn_discrete_value_size(),
        restnet_py.get_nn_type_name(),
        restnet_py.get_nn_embed_kernel_size(),
        restnet_py.get_nn_blocks_type(),
        restnet_py.get_nn_policy_type(),
        restnet_py.get_nn_value_type(),
        restnet_py.get_nn_bv_flag(),
    )
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    network.to(device)
    optimizer = optim.SGD(
        network.parameters(),
        lr=restnet_py.get_learning_rate(),
        momentum=restnet_py.get_momentum(),
        weight_decay=restnet_py.get_weight_decay(),
    )
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=1000000, gamma=0.1)

    if old_pkl:
        snapshot = torch.load(f"{old_pkl}", map_location=torch.device("cpu"))
        training_step = snapshot["training_step"]

        new_snapshot = {}
        i = -1
        for key, value in snapshot["network"].items():
            match_conv = re.search(r"blocks\.(\d+)\.conv1\.weight", key)
            match_trans = re.search(r"blocks\.(\d+)\.MSA\.relative_bias_table", key)
            if match_conv or match_trans:
                i += 1

            key = re.sub(r"blocks\.(\d+)\.", f"blocks.{i}.", key)
            new_snapshot[key] = value

        snapshot["network"] = new_snapshot

        network.load_state_dict(snapshot["network"])
        optimizer.load_state_dict(snapshot["optimizer"])
        optimizer.param_groups[0]["lr"] = restnet_py.get_learning_rate()
        scheduler.load_state_dict(snapshot["scheduler"])

    return training_step, network, device, optimizer, scheduler


def save_model(training_step, network, optimizer, scheduler, training_dir):
    snapshot = {
        "training_step": training_step,
        "network": network.module.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
    }
    from pathlib import Path

    Path(f"{new_save_path}/model").mkdir(parents=True, exist_ok=True)
    torch.save(snapshot, f"{new_save_path}/model/weight_iter_{training_step}.pkl")
    torch.jit.script(network.module).save(
        f"{training_dir}/model/weight_iter_{training_step}.pt"
    )


def train(game_type, old_pkl, new_save_path, data_loader, start_iter, end_iter):
    training_step, network, device, optimizer, scheduler = load_model(
        game_type, old_pkl, new_save_path
    )
    network = nn.DataParallel(network)

    save_model(training_step, network, optimizer, scheduler, new_save_path)


if __name__ == "__main__":
    if len(sys.argv) == 5:
        game_type = sys.argv[1]
        old_pkl = sys.argv[2]
        new_save_path = sys.argv[3]
        conf_file_name = sys.argv[4]

        # add parent dir to path
        import os

        sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
        # import pybind library
        _temps = __import__(
            f"build.{game_type}", globals(), locals(), ["restnet_py"], 0
        )
        restnet_py = _temps.restnet_py
    else:
        eprint("python train.py game_type old_pkl new_save_path conf_file")
        exit(0)

    restnet_py.load_config_file(conf_file_name)

    train(game_type, old_pkl, new_save_path, None, 0, 0)
