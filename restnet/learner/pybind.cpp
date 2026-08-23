#include "../t_config.h"
#include "configuration.h"
#include "environment.h"
#include "t_data_loader.h"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>

namespace py = pybind11;
using namespace minizero;

std::shared_ptr<Environment> kEnvInstance;

Environment& getEnvInstance()
{
    if (!kEnvInstance) { kEnvInstance = std::make_shared<Environment>(); }
    return *kEnvInstance;
}

PYBIND11_MODULE(restnet_py, m)
{
    m.def("load_config_file", [](std::string file_name) {
        minizero::env::setUpEnv();
        minizero::config::ConfigureLoader cl;
        transformer::setConfiguration(cl);
        bool success = cl.loadFromFile(file_name);
        if (success) { kEnvInstance = std::make_shared<Environment>(); }
        return success;
    });
    m.def("load_config_string", [](std::string conf_str) {
        minizero::config::ConfigureLoader cl;
        transformer::setConfiguration(cl);
        bool success = cl.loadFromString(conf_str);
        if (success) { kEnvInstance = std::make_shared<Environment>(); }
        return success;
    });
    m.def("use_gumbel", []() { return config::actor_use_gumbel; });
    m.def("get_zero_replay_buffer", []() { return config::zero_replay_buffer; });
    m.def("use_per", []() { return config::learner_use_per; });
    m.def("get_training_step", []() { return config::learner_training_step; });
    m.def("get_training_display_step", []() { return config::learner_training_display_step; });
    m.def("get_batch_size", []() { return config::learner_batch_size; });
    m.def("get_muzero_unrolling_step", []() { return config::learner_muzero_unrolling_step; });
    m.def("get_n_step_return", []() { return config::learner_n_step_return; });
    m.def("get_learning_rate", []() { return config::learner_learning_rate; });
    m.def("get_momentum", []() { return config::learner_momentum; });
    m.def("get_weight_decay", []() { return config::learner_weight_decay; });
    m.def("get_value_loss_scale", []() { return config::learner_value_loss_scale; });
    m.def("get_game_name", []() { return getEnvInstance().name(); });
    m.def("get_nn_num_input_channels", []() { return getEnvInstance().getNumInputChannels(); });
    m.def("get_nn_input_channel_height", []() { return getEnvInstance().getInputChannelHeight(); });
    m.def("get_nn_input_channel_width", []() { return getEnvInstance().getInputChannelWidth(); });
    m.def("get_nn_num_hidden_channels", []() { return config::nn_num_hidden_channels; });
    m.def("get_nn_hidden_channel_height", []() { return getEnvInstance().getHiddenChannelHeight(); });
    m.def("get_nn_hidden_channel_width", []() { return getEnvInstance().getHiddenChannelWidth(); });
    m.def("get_nn_num_action_feature_channels", []() { return getEnvInstance().getNumActionFeatureChannels(); });
    m.def("get_nn_num_blocks", []() { return config::nn_num_blocks; });
    m.def("get_nn_action_size", []() { return getEnvInstance().getPolicySize(); });
    m.def("get_nn_num_value_hidden_channels", []() { return config::nn_num_value_hidden_channels; });
    m.def("get_nn_discrete_value_size", []() { return kEnvInstance->getDiscreteValueSize(); });
    m.def("get_nn_type_name", []() { return config::nn_type_name; });
    m.def("get_nn_embed_kernel_size", []() { return transformer::nn_embed_kernel_size; });
    m.def("get_nn_blocks_type", []() { return transformer::nn_blocks_type; });
    m.def("get_nn_policy_type", []() { return transformer::nn_policy_type; });
    m.def("get_nn_value_type", []() { return transformer::nn_value_type; });
    m.def("get_nn_bv_flag", []() { return transformer::bv_flag; });

    py::class_<transformer::DataLoader>(m, "DataLoader")
        .def(py::init<std::string>())
        .def("initialize", &transformer::DataLoader::initialize)
        .def("load_data_from_file", &transformer::DataLoader::loadDataFromFile, py::call_guard<py::gil_scoped_release>())
        .def(
            "update_priority", [](transformer::DataLoader& data_loader, py::array_t<int>& sampled_index, py::array_t<float>& batch_values) {
                data_loader.updatePriority(static_cast<int*>(sampled_index.request().ptr), static_cast<float*>(batch_values.request().ptr));
            },
            py::call_guard<py::gil_scoped_release>())
        .def(
            "sample_data", [](transformer::DataLoader& data_loader, py::array_t<float>& features, py::array_t<float>& action_features, py::array_t<float>& policy, py::array_t<float>& value, py::array_t<float>& reward, py::array_t<float>& loss_scale, py::array_t<int>& sampled_index) {
                data_loader.getSharedData()->getDataPtr()->features_ = static_cast<float*>(features.request().ptr);
                data_loader.getSharedData()->getDataPtr()->action_features_ = static_cast<float*>(action_features.request().ptr);
                data_loader.getSharedData()->getDataPtr()->policy_ = static_cast<float*>(policy.request().ptr);
                data_loader.getSharedData()->getDataPtr()->value_ = static_cast<float*>(value.request().ptr);
                data_loader.getSharedData()->getDataPtr()->reward_ = static_cast<float*>(reward.request().ptr);
                data_loader.getSharedData()->getDataPtr()->loss_scale_ = static_cast<float*>(loss_scale.request().ptr);
                data_loader.getSharedData()->getDataPtr()->sampled_index_ = static_cast<int*>(sampled_index.request().ptr);
                data_loader.sampleData();
            },
            py::call_guard<py::gil_scoped_release>())
        .def("load_data_from_env_file", &transformer::DataLoader::loadDataFromEnvFile)
        .def("get_alphazero_sl_training_data", [](transformer::DataLoader& data_loader) {
            transformer::AlphaZeroSLData data = data_loader.getAlphaZeroSLData();
            py::dict res;
            res["features"] = py::cast(data.features_);
            res["policy"] = py::cast(data.policy_);
            res["value"] = data.value_;
            return res;
        })
#if GO
        .def("get_alphazero_ladder_training_data_seq", [](transformer::DataLoader& data_loader, int idx, bool random_flag) {
            transformer::AlphaZeroLadderData data = data_loader.getAlphaZeroLadderData_Seq(idx, random_flag);
            py::dict res;
            res["features"] = py::cast(data.features_);
            res["ladder"] = data.ladder_;
            return res;
        })
        .def("load_data_from_bv_file", &transformer::DataLoader::loadDataFromBVFile)
        .def("get_alphazero_bv_training_data", [](transformer::DataLoader& data_loader) {
            transformer::AlphaZeroBVData data = data_loader.getAlphaZeroBVData();
            py::dict res;
            res["features"] = py::cast(data.features_);
            res["policy"] = py::cast(data.policy_);
            res["value"] = data.value_;
            res["bv"] = py::cast(data.board_evaluation_);
            return res;
        })
#endif
        .def("get_loader_size", [](transformer::DataLoader& data_loader) {
            return data_loader.loaderSize();
        });
}
