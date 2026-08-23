import os
import sys
import time
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

from torch.utils.data import DataLoader
from torch.utils.data import IterableDataset
from torch.utils.data import get_worker_info
from network.create_network import create_network

# import pybind library
_temps = __import__(f"build.{sys.argv[1]}", globals(), locals(), ["restnet_py"], 0)
restnet_py = _temps.restnet_py


def eprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)


class MinizeroDataset(IterableDataset):
    def __init__(self, conf_file_name, train_data_dir):

        self.data_loader = restnet_py.DataLoader(conf_file_name)
        self.data_loader.load_data_from_env_file(train_data_dir)

    def __iter__(self):
        self.data_loader.seed(get_worker_info().id)
        use_bv = restnet_py.get_nn_bv_flag()
        while True:
            result_dict = (
                self.data_loader.get_alphazero_bv_training_data()
                if use_bv
                else self.data_loader.get_alphazero_sl_training_data()
            )
            features = torch.FloatTensor(result_dict["features"]).view(
                restnet_py.get_nn_num_input_channels(),
                restnet_py.get_nn_input_channel_height(),
                restnet_py.get_nn_input_channel_width(),
            )
            policy = torch.FloatTensor(result_dict["policy"])
            value = torch.FloatTensor([result_dict["value"]])
            # placeholder keeps the tuple shape when there is no bv head
            board_evaluation = (
                torch.FloatTensor(result_dict["bv"]) if use_bv else torch.zeros(1)
            )
            yield features, policy, value, board_evaluation


class Model:
    def __init__(self):
        self.training_step = 0
        self.network = None
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.optimizer = None
        self.scheduler = None

    def load_model(self, training_dir, model_file):
        self.training_step = 0
        self.network = create_network(
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
        self.network.to(self.device)
        self.optimizer = optim.SGD(
            self.network.parameters(),
            lr=restnet_py.get_learning_rate(),
            momentum=restnet_py.get_momentum(),
            weight_decay=restnet_py.get_weight_decay(),
        )
        self.scheduler = optim.lr_scheduler.StepLR(
            self.optimizer, step_size=1000000, gamma=0.1
        )

        if model_file:
            snapshot = torch.load(
                f"{training_dir}/model/{model_file}", map_location=torch.device("cpu")
            )
            self.training_step = snapshot["training_step"]
            self.network.load_state_dict(snapshot["network"])
            self.optimizer.load_state_dict(snapshot["optimizer"])
            self.optimizer.param_groups[0]["lr"] = restnet_py.get_learning_rate()
            self.scheduler.load_state_dict(snapshot["scheduler"])

        # for multi-gpu
        self.network = nn.DataParallel(self.network)

    def save_model(self, training_dir):
        snapshot = {
            "training_step": self.training_step,
            "network": self.network.module.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": self.scheduler.state_dict(),
        }
        torch.save(
            snapshot, f"{training_dir}/model/weight_iter_{self.training_step}.pkl"
        )
        torch.jit.script(self.network.module).save(
            f"{training_dir}/model/weight_iter_{self.training_step}.pt"
        )


def calculate_loss(
    output_policy, output_value, label_policy, label_value, output_bv=None, label_bv=None
):
    loss_policy = (
        -(label_policy * nn.functional.log_softmax(output_policy, dim=1)).sum()
        / output_policy.shape[0]
    )
    loss_value = torch.nn.functional.mse_loss(output_value, label_value)
    loss_bv = (
        torch.nn.functional.mse_loss(output_bv, label_bv)
        if output_bv is not None
        else None
    )
    return loss_policy, loss_value, loss_bv


def add_training_info(training_info, key, value):
    if key not in training_info:
        training_info[key] = 0
    training_info[key] += value


def calculate_accuracy(output, label, batch_size):
    max_output = np.argmax(output.to("cpu").detach().numpy(), axis=1)
    max_label = np.argmax(label.to("cpu").detach().numpy(), axis=1)
    return (max_output == max_label).sum() / batch_size


if __name__ == "__main__":
    if len(sys.argv) == 8:
        game_type = sys.argv[1]
        training_dir = sys.argv[2]
        model_file = sys.argv[3]
        conf_file_name = sys.argv[4]
        training_step_limit = int(sys.argv[5])
        train_data_dir = sys.argv[6]
        test_data_dir = sys.argv[7]
    else:
        eprint(
            "python supervised_learning_bv_train.py <game_type> <training_dir> <model_file>"
            " <conf_file> <training_step> <train_data_dir> <test_data_dir>"
        )
        exit(0)

    model = Model()

    if not restnet_py.load_config_file(conf_file_name):
        eprint(f"WARNING: failed to load {conf_file_name}; using default settings")
    use_bv = restnet_py.get_nn_bv_flag()

    if model.network is None:
        model.load_model(training_dir, model_file)
    dataset = MinizeroDataset(conf_file_name, train_data_dir)
    data_loader = DataLoader(
        dataset, batch_size=restnet_py.get_batch_size(), num_workers=4
    )
    data_loader_iterator = iter(data_loader)

    test_dataset = MinizeroDataset(conf_file_name, test_data_dir)
    test_data_loader = DataLoader(test_dataset, batch_size=128, num_workers=4)
    test_data_loader_iterator = iter(test_data_loader)

    training_info = {}
    for i in range(model.training_step, training_step_limit):

        model.network.train()
        model.optimizer.zero_grad()

        features, label_policy, label_value, label_bv = next(data_loader_iterator)
        network_output = model.network(features.to(model.device))
        output_policy = network_output["policy_logit"]
        output_value = network_output["value"]
        output_bv = network_output["bv"] if use_bv else None

        loss_policy, loss_value, loss_bv = calculate_loss(
            output_policy,
            output_value,
            label_policy.to(model.device),
            label_value.to(model.device),
            output_bv,
            label_bv.to(model.device) if use_bv else None,
        )

        loss = loss_policy + loss_value + (loss_bv if use_bv else 0)

        # record training info
        add_training_info(training_info, "loss_policy", loss_policy.item())
        add_training_info(
            training_info,
            "accuracy_policy",
            calculate_accuracy(
                output_policy, label_policy, restnet_py.get_batch_size()
            ),
        )
        add_training_info(training_info, "loss_value", loss_value.item())
        if use_bv:
            add_training_info(training_info, "loss_bv", loss_bv.item())

        loss.backward()
        model.optimizer.step()
        model.scheduler.step()

        model.network.eval()
        features, label_policy, label_value, label_bv = next(test_data_loader_iterator)

        network_output = model.network(features.to(model.device))
        output_policy = network_output["policy_logit"]
        output_value = network_output["value"]
        output_bv = network_output["bv"] if use_bv else None

        loss_policy, loss_value, loss_bv = calculate_loss(
            output_policy,
            output_value,
            label_policy.to(model.device),
            label_value.to(model.device),
            output_bv,
            label_bv.to(model.device) if use_bv else None,
        )

        add_training_info(training_info, "test_loss_policy", loss_policy.item())
        add_training_info(
            training_info,
            "test_accuracy_policy",
            calculate_accuracy(output_policy, label_policy, 128),
        )
        add_training_info(training_info, "test_loss_value", loss_value.item())
        if use_bv:
            add_training_info(training_info, "test_loss_bv", loss_bv.item())

        training_step += 1
        if (
            training_step != 0
            and training_step % restnet_py.get_training_display_step() == 0
        ):
            eprint(
                "[{}] nn step {}, lr: {}.".format(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    training_step,
                    round(model.optimizer.param_groups[0]["lr"], 6),
                )
            )
            for loss in training_info:
                eprint(
                    "\t{}: {}".format(
                        loss,
                        round(
                            training_info[loss]
                            / restnet_py.get_training_display_step(),
                            5,
                        ),
                    )
                )
            training_info = {}

        if training_step % 5000 == 0:
            model.save_model(training_dir)

    print("Optimization_Done", training_step)
    eprint("Optimization_Done", training_step)
