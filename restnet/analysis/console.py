import torch
import sys


def get_network(model_file, conf_file_name, game_type):
    from restnet.learner.network.create_network import create_network
    _temps = __import__(f'build.{game_type}', globals(), locals(), ['restnet_py'], 0)
    restnet_py = _temps.restnet_py
    restnet_py.load_config_file(conf_file_name)
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
                             restnet_py.get_nn_bv_flag())
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    network.to(device)
    snapshot = torch.load(f"{model_file}", map_location=torch.device('cpu'))
    network.load_state_dict(snapshot['network'])
    network.eval()
    return network, restnet_py


def get_env(conf_file_name, game_type, sgf_file_name=None):
    _temps = __import__(f'build.{game_type}', globals(), locals(), ['env_py'], 0)
    env_py = _temps.env_py
    env_py.init(conf_file_name)
    if sgf_file_name is not None:
        env_loader = env_py.EnvLoader()
        env = env_loader.init_env_from_sgf(sgf_file_name)
    else:
        env = env_py.Env()
    return env


if __name__ == '__main__':
    if len(sys.argv) == 4 or len(sys.argv) == 5:
        game_type = sys.argv[1]
        model_file = sys.argv[2]
        conf_file_name = sys.argv[3]
        sgf_file_name = None
        if len(sys.argv) == 5:
            sgf_file_name = sys.argv[4]
    else:
        print("Usage: python console.py [game_type] [model_file] [conf_file_name]")
        exit(0)

    env = get_env(conf_file_name, game_type, sgf_file_name)
    network, restnetpy = get_network(model_file, conf_file_name, game_type)
    from restnet.analysis.console_register import command_reg
    env_command = command_reg(env, network, restnetpy)
    env_command.run()
