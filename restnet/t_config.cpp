#include "t_config.h"
#include "configuration.h"
#include <string>

namespace transformer {

std::string learner_lr_decay_steps = ""; // empty keeps the rate flat
float learner_lr_decay_gamma = 0.5f;     // ResTNet paper halves it
int nn_embed_kernel_size = 3;            // int nn_embed_kernel_size
std::string nn_blocks_type = "R_R_T_R_R_T";
std::string nn_policy_type = "P";
std::string nn_value_type = "TV";
bool bv_flag = false; // bool bv_flag

void setConfiguration(minizero::config::ConfigureLoader& cl)
{
    minizero::config::setConfiguration(cl);
    // program parameters
    cl.addParameter("learner_lr_decay_steps", learner_lr_decay_steps, "training steps at which to drop the learning rate, comma separated; empty keeps it flat", "Learner");
    cl.addParameter("learner_lr_decay_gamma", learner_lr_decay_gamma, "the factor the learning rate is multiplied by at each of learner_lr_decay_steps", "Learner");
    cl.addParameter("nn_embed_kernel_size", nn_embed_kernel_size, "1 or 3, setting kernel window size used in the embedding convolution. 1 is positional embedding", "Network");
    cl.addParameter("nn_blocks_type", nn_blocks_type, "each block in restnet is split by '_', block type: R, T, e.g.: R_T is 1R1T; T_R is 1T1R", "Network");
    cl.addParameter("nn_policy_type", nn_policy_type, "P (AlphaZero Policy) / TP (Transformer Policy)", "Network");
    cl.addParameter("nn_value_type", nn_value_type, "V (AlphaZero Value) / TV (Transformer Value)", "Network");
    cl.addParameter("nn_bv_flag", bv_flag, "false, use board evaluation head or not", "Network");
}

void updateConfig()
{
    // Update the configuration based on the loaded parameters
    minizero::config::learner_training_step = 200;
    minizero::config::zero_end_iteration = 500;
    minizero::config::actor_use_gumbel = true;
    minizero::config::actor_use_gumbel_noise = true;
    minizero::config::actor_num_simulation = 64;
    // Add any additional updates needed for the configuration here
}

} // namespace transformer
