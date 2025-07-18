import torch
from .console_utils import *


class command_reg:
    def __init__(self, env, network, restnet):
        self.name = ""
        self.env = env
        self.network = network
        self.restnet = restnet
        self.boardsize = self.env.get_board_size()
        self.num_rt = self.restnet.get_nn_blocks_type().split('_').count('T')
        self.console_map = {
            "quit": self.quit_,
            "name": self.name_,
            "protocol_version": self.protocol_version_,
            "version": self.version_,
            "list_commands": self.list_commands_,
            "boardsize": self.boardsize_,
            "clear_board": self.clear_board_,
            "showboard": self.showboard_,
            "play": self.play_,
            "gogui-analyze_commands": self.gogui_registor_commands_,
            "p": self.policy_,
            "v": self.value_,
            "pv": self.pv_,
            "bv": self.bv_,
            "a": self.attn_,
            "aw": self.attn_w,
        }
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    def getfeature(self):
        return torch.FloatTensor(self.env.get_features()).view(1,
                                                               self.restnet.get_nn_num_input_channels(),
                                                               self.restnet.get_nn_input_channel_height(),
                                                               self.restnet.get_nn_input_channel_width())

    def execute_command(self, command_in):
        command_args = command_in.split()
        result_str = f"unknown command: \"{command_in}\""

        if not command_args or command_args[0] not in self.console_map:
            return result_str
        else:
            tmp_r = self.console_map[command_args[0]]() if len(command_args) == 1 else self.console_map[command_args[0]](command_args[1:])
            return tmp_r

    def run(self):
        while True:
            command = input().strip()
            result_str = self.execute_command(command)
            # print(f"= {result_str}", file=sys.stderr)
            print(f"= {result_str}", end="\n\n")

    def quit_(self):
        exit()

    def name_(self):
        return "gorestnet"

    def protocol_version_(self):
        return "2"

    def version_(self):
        return "1.0"

    def list_commands_(self):
        return "gogui-analyze_commands\n"

    def boardsize_(self, tmp):
        return ""

    def clear_board_(self):
        self.env.reset()
        return ""

    def showboard_(self):
        return "\n" + self.env.to_string()

    def play_(self, args):
        if (len(args) != 2):
            return "usage: play [color] [pos], (e.g., play B A1)\n"

        self.env.act(args)
        return ""

    def policy_(self):
        features = self.getfeature()
        policy = self.network(features.to(self.device))["policy"].cpu().detach().numpy()[0]
        result_str = gen_gptresult(policy, "gtx", self.boardsize)
        return result_str

    def value_(self):
        features = self.getfeature()
        value = self.network(features.to(self.device))["value"].cpu().detach().numpy()[0]
        result_str = value.item()
        return result_str

    def pv_(self):
        features = self.getfeature()
        out = self.network(features.to(self.device))
        policy = out["policy"].cpu().detach().numpy()[0]
        value = out["value"].cpu().detach().numpy()[0]
        result_str = gen_gptresult(policy, "gtx", self.boardsize)
        result_str += "\n" + str(value.item())
        return result_str

    def bv_(self):
        features = self.getfeature()
        out = self.network(features.to(self.device))
        if "bv" not in out:
            return "this model does not support bv command\n"

        bv = out["bv"].cpu().detach().numpy()[0]
        bv = bvnormalization(bv)
        result_str = gen_gptresult(bv, "dboard", self.boardsize)
        return result_str

    def attn_(self, args):
        if (len(args) != 3):
            return "usage: a [layer] [head] [pos]\n"
        layer = int(args[0])
        head = int(args[1])
        pos = trans2idx(args[2], self.boardsize)

        features = self.getfeature()
        attn_info = self.network.get_attn_table(features.to(self.device))["att_table"][layer]
        attn_result = attn_info.cpu().detach().numpy()[0][head][pos]
        attn_result = normalization_exp(attn_result)
        result_str = gen_gptresult(attn_result, "color", self.boardsize)
        return result_str

    def attn_w(self, args):
        if (len(args) != 3):
            return "usage: aw [layer] [head] [pos]\n"
        layer = int(args[0])
        head = int(args[1])
        pos = trans2idx(args[2], self.boardsize)

        features = self.getfeature()
        attn_info = self.network.get_attn_table(features.to(self.device))["att_table"][layer]
        attn_result = attn_info.cpu().detach().numpy()[0][head][pos]
        # attn_result = normalization_exp(attn_result)
        result_str = gen_gptresult(attn_result, "gtx", self.boardsize)
        return result_str

    def gogui_registor_commands_(self):
        result_str = "gfx/policy/p\n"
        result_str += "string/value/v\n"
        result_str += "gfx/pv/pv\n"
        result_str += "dboard/bv/bv\n"
        for i in range(self.num_rt):
            result_str += f"gfx/attn_l{i}_h0/a {i} 0 %p\n"
            result_str += f"gfx/attn_l{i}_h1/a {i} 1 %p\n"
            result_str += f"gfx/attn_l{i}_h2/a {i} 2 %p\n"
            result_str += f"gfx/attn_l{i}_h3/a {i} 3 %p\n"
        for i in range(self.num_rt):
            result_str += f"gfx/attn_l{i}_h0_w/aw {i} 0 %p\n"
            result_str += f"gfx/attn_l{i}_h1_w/aw {i} 1 %p\n"
            result_str += f"gfx/attn_l{i}_h2_w/aw {i} 2 %p\n"
            result_str += f"gfx/attn_l{i}_h3_w/aw {i} 3 %p\n"
        return result_str
