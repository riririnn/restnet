import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from einops.layers.torch import Rearrange


class TPolicyNetwork(nn.Module):
    def __init__(self, num_channels, channel_height, channel_width, action_size):
        super(TPolicyNetwork, self).__init__()
        self.extra_action = action_size - channel_height * channel_width
        self.rearrange_to_token = Rearrange("b c h w -> b (h w) c")
        self.fc = nn.Sequential(
            nn.Linear(num_channels, num_channels),
            nn.Tanh(),
        )

        self.policynet = nn.Sequential(
            nn.Linear(num_channels, 1), Rearrange("b n e -> b (n e)")
        )

        self.zero = nn.Parameter(torch.zeros(1, 1))

    def forward(self, x):
        if x.dim() == 4:
            x = self.rearrange_to_token(x)
        x = self.fc(x)
        x = self.policynet(x)
        b, _ = x.shape
        zero_tokens = self.zero.expand(b, -1)
        for _ in range(self.extra_action):
            x = torch.cat([x, zero_tokens], dim=1)
        return x


class PolicyNetwork(nn.Module):
    def __init__(self, num_channels, channel_height, channel_width, action_size):
        super(PolicyNetwork, self).__init__()
        self.channel_height = channel_height
        self.channel_width = channel_width
        self.rearrange_to_conv = Rearrange(
            "b (h w) c -> b c h w", h=channel_height, w=channel_width
        )
        self.num_output_channels = math.ceil(
            action_size / (channel_height * channel_width)
        )
        self.conv = nn.Conv2d(num_channels, self.num_output_channels, 1)
        self.bn = nn.BatchNorm2d(self.num_output_channels)
        self.fc = nn.Linear(
            self.num_output_channels * channel_height * channel_width, action_size
        )

    def forward(self, x):
        if x.dim() == 3:
            x = self.rearrange_to_conv(x)
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        x = x.contiguous().view(
            -1, self.num_output_channels * self.channel_height * self.channel_width
        )
        x = self.fc(x)
        return x
