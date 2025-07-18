#pragma once

#include "mode_handler.h"
#include "t_config.h"
#include <string>

namespace transformer {

class ModeHandler : public minizero::console::ModeHandler {
public:
    ModeHandler() {}

protected:
    std::string getBlockRepresentation();
    void runZeroTrainingName() override;
    void setDefaultConfiguration(minizero::config::ConfigureLoader& cl) override
    {
        transformer::setConfiguration(cl);
        transformer::updateConfig();
    }
};

} // namespace transformer
