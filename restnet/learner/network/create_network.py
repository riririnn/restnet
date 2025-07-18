from .alphazero_network import AlphaZeroNetwork
from .alphazero_bvnetwork import AlphaZeroBVNetwork


def create_network(
    game_name,
    num_input_channels,
    input_channel_height,
    input_channel_width,
    num_hidden_channels,
    hidden_channel_height,
    hidden_channel_width,
    num_action_feature_channels,
    num_blocks,
    action_size,
    num_value_hidden_channels,
    discrete_value_size,
    network_type_name,
    embed_kernel_size,
    blocks_type,
    policy_type,
    value_type,
    bv_flag,
    ladder_flag=False,
):

    network = None
    if network_type_name == "alphazero":
        if bv_flag:
            network = AlphaZeroBVNetwork(
                game_name,
                num_input_channels,
                input_channel_height,
                input_channel_width,
                num_hidden_channels,
                hidden_channel_height,
                hidden_channel_width,
                num_blocks,
                action_size,
                num_value_hidden_channels,
                discrete_value_size,
                embed_kernel_size,
                blocks_type,
                policy_type,
                value_type,
                ladder_flag,
            )
        else:
            network = AlphaZeroNetwork(
                game_name,
                num_input_channels,
                input_channel_height,
                input_channel_width,
                num_hidden_channels,
                hidden_channel_height,
                hidden_channel_width,
                num_blocks,
                action_size,
                num_value_hidden_channels,
                discrete_value_size,
                embed_kernel_size,
                blocks_type,
                policy_type,
                value_type,
            )
    else:
        assert False
    return network
