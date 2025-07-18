import torch
import torch.nn as nn
import torch.nn.functional as F


class EmbedNet(nn.Module):
    def __init__(self, num_input_channels, num_hidden_channels, kernel_size):
        super(EmbedNet, self).__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv2d(
            num_input_channels,
            num_hidden_channels,
            kernel_size=kernel_size,
            stride=1,
            padding=padding,
            bias=False,
        )
        self.bn = nn.BatchNorm2d(num_hidden_channels)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        return x
