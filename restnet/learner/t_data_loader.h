#pragma once

#include "alphazero_network.h"
#include "base_actor.h"
#include <iostream>
// #include "create_actor.h"
// #include "create_network.h"
#include "data_loader.h"
#include "environment.h"
#include "network.h"
#include "random.h"
#include "utils.h"
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace transformer {

using namespace minizero::actor;
using namespace minizero::network;

class AlphaZeroLadderData {
public:
    std::vector<float> features_;
    float ladder_;
};

class AlphaZeroBVData {
public:
    std::vector<float> features_;
    std::vector<float> policy_;
    float value_;
    std::vector<float> board_evaluation_;
};

// same as AlphaZeroBVData without the board evaluation head, which only Go defines
class AlphaZeroSLData {
public:
    std::vector<float> features_;
    std::vector<float> policy_;
    float value_;
};

class DataLoader : public minizero::learner::DataLoader {
public:
    DataLoader(std::string conf_file_name);
    void loadDataFromEnvFile(const std::string& file_name);

    std::shared_ptr<actor::BaseActor> actor_;
    std::shared_ptr<minizero::network::Network> network_;
    std::vector<std::pair<EnvironmentLoader, int>> env_loaders_;
    int loaderSize() { return env_loaders_.size(); }

    inline int getDataSize() const { return env_loaders_.back().second; }
    std::pair<int, int> getEnvIDAndPosition(int index) const;
    AlphaZeroSLData getAlphaZeroSLData();

#if GO
    AlphaZeroLadderData getAlphaZeroLadderData_Seq(int idx, bool random_flag);

    void loadDataFromBVFile(const std::string& file_name);
    AlphaZeroBVData getAlphaZeroBVData();
#endif
};

} // namespace transformer
