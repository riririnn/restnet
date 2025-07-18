#include "t_data_loader.h"
#include "../t_config.h"
#include <string>

namespace transformer {

using namespace minizero;
using namespace minizero::network;
using namespace minizero::utils;

DataLoader::DataLoader(std::string conf_file_name)
    : minizero::learner::DataLoader("")
{
    minizero::config::ConfigureLoader cl;
    transformer::setConfiguration(cl);
    cl.loadFromFile(conf_file_name);
}

void DataLoader::loadDataFromEnvFile(const std::string& file_name)
{
    std::ifstream fin(file_name, std::ifstream::in);
    for (std::string content; std::getline(fin, content);) {
        EnvironmentLoader env_loader;
        env_loader.loadFromString(content);
        int total_length = env_loaders_.empty() ? 0 : env_loaders_.back().second;
        std::string reold = env_loader.getTag("RE");
        env_loader.addTag("RE", (reold[0] == 'B' ? "1" : "-1"));
        env_loaders_.push_back({env_loader, total_length + env_loader.getActionPairs().size()});
    }
}

#if GO

AlphaZeroLadderData DataLoader::getAlphaZeroLadderData_Seq(int idx, bool random_flag)
{
    const EnvironmentLoader& env_loader = env_loaders_[idx].first;
    Environment env;
    for (auto& [sub_acta, _] : env_loader.getActionPairs()) { env.act(sub_acta); }

    // calculate training data
    AlphaZeroLadderData data;
    Rotation rotation;
    if (random_flag)
        rotation = static_cast<Rotation>(Random::randInt() % static_cast<int>(Rotation::kRotateSize));
    else
        rotation = Rotation::kRotationNone;

    data.features_ = env.getFeatures(rotation);
    data.ladder_ = (env_loader.getTag("LA") == "T") ? 1. : -1.;

    return data;
}

std::pair<int, int> DataLoader::getEnvIDAndPosition(int index) const
{
    int left = 0, right = env_loaders_.size();
    index %= env_loaders_.back().second;

    while (left < right) {
        int mid = left + (right - left) / 2;
        if (index >= env_loaders_[mid].second) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }

    return {left, (left == 0 ? index : index - env_loaders_[left - 1].second)};
}

void DataLoader::loadDataFromBVFile(const std::string& file_name)
{
    Environment env;
    std::ifstream fin(file_name, std::ifstream::in);
    for (std::string content; std::getline(fin, content);) {
        minizero::utils::SGFLoader sgf_loader;
        sgf_loader.loadFromString(content);

        env.reset();
        for (auto& action_string : sgf_loader.getActions()) {
            Action action = Action(action_string.first, 19);
            env.act(action);
        }

        EnvironmentLoader env_loader;

        env_loader.loadFromEnvironment(env);
        int total_length = env_loaders_.empty() ? 0 : env_loaders_.back().second;
        std::string evstr = sgf_loader.getTags().at("RE");
        env_loader.addTag("RE", (evstr[0] == 'B' ? "1" : "-1"));
        env_loaders_.push_back({env_loader, total_length + env_loader.getActionPairs().size()});
    }
}

AlphaZeroBVData DataLoader::getAlphaZeroBVData()
{
    // random pickup one position
    std::pair<int, int> p = getEnvIDAndPosition(Random::randInt() % getDataSize());
    int env_id = p.first, pos = p.second; //pos = 0;

    // replay the game until to the selected position
    const EnvironmentLoader& env_loader = env_loaders_[env_id].first;
    Environment env;
    env.reset();
    for (int i = 0; i < pos; ++i) { env.act(env_loader.getActionPairs()[i].first); }

    // calculate training data
    AlphaZeroBVData data;
    Rotation rotation = static_cast<Rotation>(Random::randInt() % static_cast<int>(Rotation::kRotateSize));
    data.features_ = env.getFeatures(rotation);
    data.policy_ = env_loader.getPolicy(pos, rotation);
    data.value_ = env_loader.getReturn();

    int board_size = config::env_board_size;
    std::string o = "";
    for (size_t i = pos; i < env_loader.getActionPairs().size(); ++i) { env.act(env_loader.getActionPairs()[i].first); }
    data.board_evaluation_.resize(board_size * board_size, 0.5f);
    for (int pos = 0; pos < board_size * board_size; ++pos) {
        int rotate_pos = env_loader.getRotatePosition(pos, rotation);

        if (env.getBensonBitboard().get(env::Player::kPlayer1).test(pos)) {
            data.board_evaluation_[rotate_pos] = 1.0f;
        } else if (env.getBensonBitboard().get(env::Player::kPlayer2).test(pos)) {
            data.board_evaluation_[rotate_pos] = 0.0f;
        } else {
            const env::go::GoGrid& grid = env.getGrid(pos);
            if (grid.getPlayer() == env::Player::kPlayer1) {
                data.board_evaluation_[rotate_pos] = 1.0f;
            } else if (grid.getPlayer() == env::Player::kPlayer2) {
                data.board_evaluation_[rotate_pos] = 0.0f;
            } else {
                if (grid.getArea(env::Player::kPlayer1)->getNumGrid() == 1) {
                    data.board_evaluation_[rotate_pos] = 1.0f;
                } else if (grid.getArea(env::Player::kPlayer2)->getNumGrid() == 1) {
                    data.board_evaluation_[rotate_pos] = 0.0f;
                }
            }
        }
    }

    return data;
}

#endif

} // namespace transformer
