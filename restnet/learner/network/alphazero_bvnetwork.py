import torch
import torch.nn as nn
import numpy as np
from timm.models.layers import trunc_normal_
from .embed_unit import EmbedNet
from .block_unit import ResidualBlock, TransformerBlock
from .policy_unit import TPolicyNetwork, PolicyNetwork
from .value_unit import (
    TValueNetwork,
    ValueNetwork,
    BoardEvaluationNetwork,
    LadderNetwork,
)


class AlphaZeroBVNetwork(nn.Module):
    def __init__(
        self,
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
        ladder_flag=False,
    ):
        super(AlphaZeroBVNetwork, self).__init__()
        self.game_name = game_name
        self.num_input_channels = num_input_channels
        self.input_channel_height = input_channel_height
        self.input_channel_width = input_channel_width
        self.num_hidden_channels = num_hidden_channels
        self.hidden_channel_height = hidden_channel_height
        self.hidden_channel_width = hidden_channel_width
        self.num_blocks = num_blocks
        self.action_size = action_size
        self.num_value_hidden_channels = num_value_hidden_channels
        self.discrete_value_size = discrete_value_size

        self.num_head = 4
        self.mlp_ratio = 2
        self.embed_kernel_size = embed_kernel_size
        self.blocks_type = blocks_type
        self.policy_type = policy_type
        self.value_type = value_type
        self.ladder_flag = ladder_flag

        self.embed = self.get_embed_net(embed_kernel_size)
        self.blocks = nn.ModuleList(
            [self.get_backbone(blocktype) for blocktype in blocks_type.split("_")]
        )

        self.policy = self.get_policy_net(policy_type)
        self.value = self.get_value_net(value_type)
        self.bv = BoardEvaluationNetwork(
            self.num_hidden_channels,
            self.input_channel_height,
            self.input_channel_width,
            self.num_value_hidden_channels,
        )
        if ladder_flag:
            self.ladder = LadderNetwork(
                self.num_hidden_channels,
                self.input_channel_height,
                self.input_channel_width,
                self.num_value_hidden_channels,
            )
        else:
            self.ladder = None
        # self.ladder = LadderNetwork(self.num_hidden_channels, self.input_channel_height, self.input_channel_width, self.num_value_hidden_channels)
        self.apply(self._init_weights_trunc_normal)

    def get_embed_net(self, embed_kernel_size):
        return EmbedNet(
            self.num_input_channels, self.num_hidden_channels, self.embed_kernel_size
        )

    def get_backbone(self, blocktype):
        if blocktype == "R":
            return ResidualBlock(self.num_hidden_channels, self.input_channel_height)
        elif blocktype == "T":
            return TransformerBlock(
                self.num_hidden_channels,
                self.num_hidden_channels * self.mlp_ratio,
                self.num_head,
                self.input_channel_height,
                self.input_channel_width,
            )
        else:
            assert "backbone type is not supported"

    def get_policy_net(self, policytype):
        if policytype == "TP":
            return TPolicyNetwork(
                self.num_hidden_channels,
                self.input_channel_height,
                self.input_channel_width,
                self.action_size,
            )
        elif policytype == "P":
            return PolicyNetwork(
                self.num_hidden_channels,
                self.input_channel_height,
                self.input_channel_width,
                self.action_size,
            )
        else:
            assert "policy type is not supported"

    def get_value_net(self, valuetype):
        if valuetype == "TV":
            return TValueNetwork(self.num_hidden_channels, self.input_channel_height)
        elif valuetype == "V":
            return ValueNetwork(
                self.num_hidden_channels,
                self.input_channel_height,
                self.input_channel_width,
                self.num_value_hidden_channels,
            )
        else:
            assert "value type is not supported"

    def _init_weights_trunc_normal(self, m):
        if isinstance(m, nn.Linear):
            trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, (nn.LayerNorm, nn.BatchNorm2d)):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    @torch.jit.export
    def get_type_name(self):
        return "alphazero"

    @torch.jit.export
    def get_game_name(self):
        return self.game_name

    @torch.jit.export
    def get_num_input_channels(self):
        return self.num_input_channels

    @torch.jit.export
    def get_input_channel_height(self):
        return self.input_channel_height

    @torch.jit.export
    def get_input_channel_width(self):
        return self.input_channel_width

    @torch.jit.export
    def get_num_hidden_channels(self):
        return self.num_hidden_channels

    @torch.jit.export
    def get_hidden_channel_height(self):
        return self.hidden_channel_height

    @torch.jit.export
    def get_hidden_channel_width(self):
        return self.hidden_channel_width

    @torch.jit.export
    def get_num_blocks(self):
        return self.num_blocks

    @torch.jit.export
    def get_action_size(self):
        return self.action_size

    @torch.jit.export
    def get_num_value_hidden_channels(self):
        return self.num_value_hidden_channels

    @torch.jit.export
    def get_discrete_value_size(self):
        return self.discrete_value_size

    def get_attn_table(self, state):
        attns = []
        block_table = self.blocks_type.split("_")
        x = self.embed(state)
        for i, block in enumerate(self.blocks):
            if block_table[i] != "T":
                x = block(x)
            else:
                x, att_table = block.attn(x)
                attns.append(att_table)

        policy_logit = self.policy(x)
        policy = torch.softmax(policy_logit, dim=1)
        value = self.value(x)
        bv = self.bv(x)

        return {
            "policy_logit": policy_logit,
            "policy": policy,
            "value": value,
            "bv": bv,
            "att_table": attns,
        }

    def forward(self, state):
        x = self.embed(state)
        for block in self.blocks:
            x = block(x)

        policy_logit = self.policy(x)
        policy = torch.softmax(policy_logit, dim=1)
        value = self.value(x)
        bv = self.bv(x)
        if self.ladder_flag:
            ladder = self.ladder(x)
            return {
                "policy_logit": policy_logit,
                "policy": policy,
                "value": value,
                "bv": bv,
                "ladder": ladder,
            }
        else:
            return {
                "policy_logit": policy_logit,
                "policy": policy,
                "value": value,
                "bv": bv,
            }
