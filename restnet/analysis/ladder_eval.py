import os
import sys
import time
import torch
import random
import torch.nn as nn
import torch.optim as optim
import numpy as np
from tqdm import tqdm
from collections import defaultdict

_temps = __import__(f'build.go', globals(), locals(), ['restnet_py'], 0)
restnet_py = _temps.restnet_py
from torch.utils.data import Dataset
from torch.utils.data import DataLoader

seed = 0
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

from restnet.learner.network.create_network import create_network

def eprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)

class EvalDataset(Dataset):
    def __init__(self, conf_file_name, data_set_name):
        self.data_loader = restnet_py.DataLoader(conf_file_name)
        self.data_loader.initialize()
        self.data_loader.load_data_from_env_file(data_set_name)
        self.random_flag = False

    def __len__(self):
        return self.data_loader.get_loader_size()

    def __getitem__(self, idx):
        result_dict = self.data_loader.get_alphazero_ladder_training_data_seq(idx, self.random_flag)
        features = torch.FloatTensor(result_dict["features"]).view(restnet_py.get_nn_num_input_channels(),
                                                                    restnet_py.get_nn_input_channel_height(),
                                                                    restnet_py.get_nn_input_channel_width())
        ladder = torch.FloatTensor([result_dict["ladder"]])
        return features, ladder  # board_evaluation

def load_model(model_dir):
    network = create_network(restnet_py.get_game_name(),
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
                             ladder_flag=True)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    network.to(device)
    if model_dir:
        snapshot = torch.load(
            f"{model_dir}", map_location=torch.device('cpu'))
        network.load_state_dict(snapshot['network'], strict=False)
    return network, device

def calculate_loss(output_value, label_value):
    ce_loss_ladder = torch.nn.functional.cross_entropy(output_value, label_value)
    mse_loss_ladder = torch.nn.functional.mse_loss(output_value, label_value)
    return ce_loss_ladder, mse_loss_ladder  # , loss_bv

def add_results_info(results_info, key, value):
    if key not in results_info:
        results_info[key] = 0
    results_info[key] += value

def process_data(data, n):
    x = n*-1 # 0.1, -0.1)
    result = torch.zeros_like(data)
    result[data >= n] = 1
    result[data <= x] = -1
    result[(data > x) & (data < n)] = 0
    return result

def calculate_accuracy(output, label, internal):
    max_output = process_data(output.to('cpu').detach(), internal).numpy() #> 0.5
    max_label = label.to('cpu').detach().numpy()
    return (max_output == max_label).sum() / output.shape[0]

if __name__ == '__main__':
    if len(sys.argv) != 7:
        eprint("Usage: python ladder_eval.py <R3RRT_model_path> <R3RRT_conf_path> <10R_model_path> <10R_conf_path> <dataset_path> <threshold>")
        sys.exit(1)
    R3RRT_model_path = sys.argv[1]

    R3RRT_conf_path = sys.argv[2]
    _10R_model_path = sys.argv[3]
    _10R_conf_path = sys.argv[4]
    dataset_path = sys.argv[5]
    threshold = sys.argv[6]
    threshold = float(threshold)

    restnet_py.load_config_file(R3RRT_conf_path)
    R3RRT_network, device = load_model(R3RRT_model_path)
    R3RRT_network = nn.DataParallel(R3RRT_network)

    restnet_py.load_config_file(_10R_conf_path)
    _10R_network, device = load_model(_10R_model_path)
    _10R_network = nn.DataParallel(_10R_network)

    test_dataset = EvalDataset(R3RRT_conf_path, dataset_path)
    test_data_loader = DataLoader(test_dataset, batch_size=1024, num_workers=2, shuffle=False)
    test_data_loader_iterator = iter(test_data_loader)
    results_info = {}

    R3RRT_network.eval()
    _10R_network.eval()
    for features, label_ladder in tqdm(test_data_loader_iterator):

        with torch.no_grad():
            R3RRT_network_output = R3RRT_network(features.to(device))
            R3RRT_output_ladder = R3RRT_network_output["ladder"]

        add_results_info(results_info, f'R3RRT_acc', calculate_accuracy(R3RRT_output_ladder, label_ladder, threshold))

        with torch.no_grad():
            _10R_network_output = _10R_network(features.to(device))
            _10R_output_ladder = _10R_network_output["ladder"]

        add_results_info(results_info, f'10R_acc', calculate_accuracy(_10R_output_ladder, label_ladder, threshold))

    print()
    print("Ladder Evaluation Results:")
    print(f"Total Samples: {test_dataset.data_loader.get_loader_size()}")
    print(f"Threshold: < -{threshold} or > {threshold}")
    print("")
    print("Average Accuracy:")
    print(f"R3RRT: {results_info['R3RRT_acc'] / len(test_data_loader_iterator):.5f}")
    print(f"10R: {results_info['10R_acc'] / len(test_data_loader_iterator):.5f}")
