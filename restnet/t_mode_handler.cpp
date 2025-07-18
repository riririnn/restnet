#include "t_mode_handler.h"
#include "console.h"
#include "git_info.h"
#include <sstream>
#include <string>

namespace transformer {

std::string ModeHandler::getBlockRepresentation()
{
    std::stringstream ss(transformer::nn_blocks_type);
    std::string prev_block_type = "", cur_block_type, representation = "";
    int cnt = 0;
    while (getline(ss, cur_block_type, '_')) {
        if (prev_block_type != cur_block_type && prev_block_type != "") {
            representation += std::to_string(cnt) + prev_block_type;
            cnt = 0;
        }
        if (cur_block_type == "2R" || cur_block_type == "2T") {
            prev_block_type = "";
            continue;
        }
        ++cnt;
        prev_block_type = cur_block_type;
    }
    if (cnt > 0) { representation += std::to_string(cnt) + prev_block_type; }
    return representation;
}

void ModeHandler::runZeroTrainingName()
{
    std::cout << Environment().name()                                                                               // name for environment
              << "_" << (minizero::config::actor_use_gumbel ? "g" : "") << minizero::config::nn_type_name[0] << "z" // network & training algorithm
              << "_" << getBlockRepresentation()
              << "_" << transformer::nn_policy_type
              << "_" << transformer::nn_value_type
              << "_n" << minizero::config::actor_num_simulation // number of simulations
              << "-" << GIT_SHORT_HASH << std::endl;            // git hash info
}

} // namespace transformer
