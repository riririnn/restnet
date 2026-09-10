#pragma once

#include "configure_loader.h"
#include <string>

namespace transformer {

extern std::string learner_lr_decay_steps;
extern float learner_lr_decay_gamma;
extern int nn_embed_kernel_size;
extern std::string nn_blocks_type;
extern std::string nn_policy_type;
extern std::string nn_value_type;
extern bool bv_flag;

void setConfiguration(minizero::config::ConfigureLoader& cl);
void updateConfig();

} // namespace transformer
