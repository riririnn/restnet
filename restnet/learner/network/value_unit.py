import torch
import torch.nn as nn
import torch.nn.functional as F
from einops.layers.torch import Rearrange, Reduce


class TValueNetwork(nn.Module):
    def __init__(self, emb_size, input_channel_height):
        super().__init__()
        self.input_channel_height = input_channel_height
        self.avg_pool = nn.AdaptiveAvgPool2d(1)  # squeeze
        self.fc = nn.Sequential(
            nn.Linear(emb_size, emb_size * 2),
            nn.SiLU(),
            nn.Linear(emb_size * 2, 1),
        )
        self.rearrange_to_conv = Rearrange(
            "b (h w) c -> b c h w", h=input_channel_height
        )
        self.tanh = nn.Tanh()

    def forward(self, x):
        if x.dim() == 3:
            x = self.rearrange_to_conv(x)
        b, c, _, _ = x.size()
        x = self.avg_pool(x).view(b, c)
        x = self.fc(x)
        x = self.tanh(x)
        return x


class LadderNetwork(nn.Module):
    def __init__(
        self, num_channels, channel_height, channel_width, num_output_channels
    ):
        super(LadderNetwork, self).__init__()
        self.channel_height = channel_height
        self.channel_width = channel_width
        self.rearrange_to_2d = Rearrange(
            "b (h w) c -> b c h w", h=channel_height, w=channel_width
        )
        self.conv = nn.Conv2d(num_channels, 2, 1)
        self.bn = nn.BatchNorm2d(2)
        self.fc1 = nn.Linear(channel_height * channel_width * 2, num_output_channels)
        self.fc2 = nn.Linear(num_output_channels, 1)
        self.tanh = nn.Tanh()

    def forward(self, x):
        if x.dim() == 3:
            x = self.rearrange_to_2d(x)
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        x = x.contiguous().view(-1, self.channel_height * self.channel_width * 2)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.fc2(x)
        x = self.tanh(x)
        return x


class ValueNetwork(nn.Module):
    def __init__(
        self, num_channels, channel_height, channel_width, num_output_channels
    ):
        super(ValueNetwork, self).__init__()
        self.channel_height = channel_height
        self.channel_width = channel_width
        self.rearrange_to_conv = Rearrange(
            "b (h w) c -> b c h w", h=channel_height, w=channel_width
        )
        self.conv = nn.Conv2d(num_channels, 1, 1)
        self.bn = nn.BatchNorm2d(1)
        self.fc1 = nn.Linear(channel_height * channel_width, num_output_channels)
        self.fc2 = nn.Linear(num_output_channels, 1)
        self.tanh = nn.Tanh()

    def forward(self, x):
        if x.dim() == 3:
            x = self.rearrange_to_conv(x)
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        x = x.contiguous().view(-1, self.channel_height * self.channel_width)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.fc2(x)
        x = self.tanh(x)
        return x


class BoardEvaluationNetwork(nn.Module):
    def __init__(
        self, num_channels, channel_height, channel_width, num_output_channels
    ):
        super(BoardEvaluationNetwork, self).__init__()

        self.rearrange_to_2d = Rearrange(
            "b (h w) c -> b c h w", h=channel_height, w=channel_width
        )
        self.channel_height = channel_height
        self.channel_width = channel_width
        # Two layer convolution with 3x3 kernel
        self.conv1 = nn.Conv2d(num_channels, num_output_channels, 3, padding=1)
        self.bn = nn.BatchNorm2d(num_output_channels)
        self.conv2 = nn.Conv2d(num_output_channels, 1, 3, padding=1)
        # One layer convolution with 3x3 kernel
        # self.conv = nn.Conv2d(num_channels, 1, 3, padding=1)

    def forward(self, x):
        if x.dim() == 3:
            x = self.rearrange_to_2d(x)
        batch_size = x.shape[0]
        # Two layer convolution with 3x3 kernel
        x = self.conv1(x)
        x = self.bn(x)
        x = F.relu(x)
        x = self.conv2(x).view(batch_size, -1)

        # One layer convolution with 3x3 kernel
        # x = self.conv(x).view(batch_size, -1)
        x = torch.sigmoid(x)
        return x
