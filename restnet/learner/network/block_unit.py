import torch
import torch.nn as nn
import torch.nn.functional as F
from einops.layers.torch import Rearrange
from einops import rearrange


class ResidualBlock(nn.Module):
    def __init__(self, num_channels, input_channel_height):
        super(ResidualBlock, self).__init__()
        self.token_to_conv = Rearrange("b (h w) c -> b c h w", h=input_channel_height)
        self.conv1 = nn.Conv2d(num_channels, num_channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(num_channels)
        self.conv2 = nn.Conv2d(num_channels, num_channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(num_channels)

    def forward(self, x):
        if x.dim() == 3:
            x = self.token_to_conv(x)
        input = x
        x = self.conv1(x)
        x = self.bn1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = F.relu(input + x)
        return x


################## Transformer ##################
class TransformerBlock(nn.Module):
    def __init__(
        self,
        emb_size,
        MLP_hsize,
        n_head,
        input_channel_height,
        input_channel_width,
        drop=0.0,
        MLP_drop=0.0,
    ):
        super(TransformerBlock, self).__init__()

        self.input_channel_height = input_channel_height
        self.input_channel_width = input_channel_width
        self.conv_to_token = Rearrange("b c h w -> b (h w) c")
        self.MSA = self.MSA_type(emb_size, n_head, drop)
        self.MLP = MLP(emb_size, MLP_hsize, MLP_drop)
        self.ln1 = nn.LayerNorm(emb_size)
        self.ln2 = nn.LayerNorm(emb_size)

    def MSA_type(self, emb_size_, n_head, drop):
        return MSA_rel(
            emb_size_, n_head, drop, self.input_channel_height, self.input_channel_width
        )

    def attn(self, x):
        if x.dim() == 4:
            x = self.conv_to_token(x)
        input = x
        x = self.ln1(x)
        x, attn = self.MSA.attn(x)
        x += input
        y = self.ln2(x)
        y = self.MLP(y)

        return x + y, attn

    def forward(self, x):
        if x.dim() == 4:
            x = self.conv_to_token(x)
        input = x
        x = self.ln1(x)
        x = self.MSA(x)
        x += input
        y = self.ln2(x)
        y = self.MLP(y)

        return x + y


class MSA_rel(nn.Module):
    def __init__(
        self, emb_size, num_heads, dropout, input_channel_height, input_channel_width
    ):
        super(MSA_rel, self).__init__()
        self.emb_size = emb_size
        self.num_heads = num_heads
        self.input_channel_height = input_channel_height
        self.input_channel_width = input_channel_width
        self.token_len = input_channel_height * input_channel_width

        self.projq = nn.Sequential(
            nn.Linear(emb_size, emb_size),
            Rearrange("b n (h d) -> b h n d", h=num_heads),
        )
        self.projk = nn.Sequential(
            nn.Linear(emb_size, emb_size),
            Rearrange("b n (h d) -> b h n d", h=num_heads),
        )
        self.projv = nn.Sequential(
            nn.Linear(emb_size, emb_size),
            Rearrange("b n (h d) -> b h n d", h=num_heads),
        )
        self.rearrange_out = Rearrange("b h n d -> b n (h d)")
        self.rearrange_rel = Rearrange(
            "(h w) c -> 1 c h w", h=self.token_len, w=self.token_len
        )

        # relative bias table
        self.relative_bias_table = nn.Parameter(
            torch.zeros(
                (2 * input_channel_height - 1) * (2 * input_channel_width - 1),
                self.num_heads,
            )
        )

        # "ij" so the flattened order matches the token order the blocks use
        # (Rearrange "b (h w) c", i.e. token k is row k // w, column k % w).
        # "xy" laid the coordinates out column-major, which only stays consistent
        # when height == width -- on a 3x4 board it pairs tokens with the wrong
        # offsets and pushes the index past the end of the table.
        coords = torch.meshgrid(
            torch.arange(input_channel_height),
            torch.arange(input_channel_width),
            indexing="ij",
        )
        coords = torch.flatten(torch.stack(coords), 1)
        relative_coords = coords[:, :, None] - coords[:, None, :]

        relative_coords[0] += input_channel_height - 1
        relative_coords[1] += input_channel_width - 1
        relative_coords[0] *= 2 * input_channel_width - 1
        relative_coords = rearrange(relative_coords, "c h w -> h w c")
        relative_index = relative_coords.sum(-1).flatten().unsqueeze(1)
        self.register_buffer("relative_index", relative_index)

        self.scaling = (self.emb_size / self.num_heads) ** -0.5
        self.attend = nn.Softmax(dim=-1)
        self.out = nn.Sequential(nn.Linear(emb_size, emb_size), nn.Dropout(dropout))

    def attn(self, x):
        queries, keys, values = self.projq(x), self.projk(x), self.projv(x)
        dots = torch.einsum("b h q d, b h k d -> b h q k", queries, keys) * self.scaling
        relative_bias = self.relative_bias_table.gather(
            0, self.relative_index.repeat(1, self.num_heads)
        )
        relative_bias = self.rearrange_rel(relative_bias)
        dots = dots + relative_bias
        attn = self.attend(dots)
        x = torch.einsum("b h d i, b h i v -> b h d v", attn, values)
        x = self.out(self.rearrange_out(x))
        return x, attn

    def forward(self, x):
        # b: batch, n: boardsize, (h d qkv): emb_size*3 = head x emb/head x 3(q,k,v)
        # so after rearrage can get [0:2] b: batch, h: head, n: 361, d: emb_size/head_num
        # get the qkv from different kind of method (convolution projection or linear porjection)
        queries, keys, values = self.projq(x), self.projk(x), self.projv(x)

        # b: batch, h: head, q:queries, k:keys, d:dimension(emb_size/head_num)
        # (b, 8, 361, emb/8) dot (b, 8, 361, emb/8) => (b, 8, 361, 361) , scaling for nomalize
        dots = torch.einsum("b h q d, b h k d -> b h q k", queries, keys) * self.scaling

        # add relative position bias
        relative_bias = self.relative_bias_table.gather(
            0, self.relative_index.repeat(1, self.num_heads)
        )
        relative_bias = self.rearrange_rel(relative_bias)
        dots = dots + relative_bias

        attn = self.attend(dots)

        # get the final weight by attention value
        # do matrix multiplication (attention matrix dxi * value matrix i*v)
        x = torch.einsum("b h d i, b h i v -> b h d v", attn, values)
        # and rearrange to origin size (cat all of the head)
        x = self.out(self.rearrange_out(x))
        return x


class MLP(nn.Module):
    def __init__(self, dim, hidden_dim, dropout):
        super(MLP, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, dim),
        )

    def forward(self, x):
        x = self.net(x)
        return x
