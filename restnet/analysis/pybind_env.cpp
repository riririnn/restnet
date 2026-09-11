#include "../t_config.h"
#include "configuration.h"
#include "environment.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using namespace minizero;

PYBIND11_MODULE(env_py, m)
{
    m.def("init", [](std::string file_name) {
        env::setUpEnv();
        config::ConfigureLoader cl;
        transformer::setConfiguration(cl);
        cl.loadFromFile(file_name);
    });

    py::enum_<env::Player>(m, "Player")
        .value("player_none", env::Player::kPlayerNone)
        .value("player_1", env::Player::kPlayer1)
        .value("player_2", env::Player::kPlayer2)
        .value("player_size", env::Player::kPlayerSize)
        .export_values();

    py::class_<Action>(m, "Action")
        .def(py::init<>())
        .def(py::init<int, env::Player>())
        .def("next_player", &Action::nextPlayer)
        .def("to_console_string", &Action::toConsoleString)
        .def("get_action_id", &Action::getActionID)
        .def("get_player", &Action::getPlayer);

    py::class_<Environment>(m, "Env")
        .def(py::init<>())
        .def("reset", &Environment::reset)
        .def("act", py::overload_cast<const Action&>(&Environment::act))
        .def("act", py::overload_cast<const std::vector<std::string>&>(&Environment::act))
        .def("get_legal_actions", &Environment::getLegalActions)
        .def("is_legal_action", &Environment::isLegalAction)
        .def("is_terminal", &Environment::isTerminal)
        .def("get_eval_score", &Environment::getEvalScore)
        .def("get_features", [](Environment& env) { return py::cast(env.getFeatures()); })
        .def("get_action_features", &Environment::getActionFeatures)
#if SHOGI
        // rules that only appear in rare positions cannot be reached by playing
        // from the start, so let a test set the position directly. Guarded: every
        // other game builds this same file and has no setFromSFEN.
        .def("set_from_sfen", &Environment::setFromSFEN)
#endif
        .def("to_string", &Environment::toString)
        .def("name", &Environment::name)
        .def("get_turn", &Environment::getTurn)
        .def("get_action_history", &Environment::getActionHistory)
        .def("get_board_size", &Environment::getBoardSize);

    py::class_<EnvironmentLoader>(m, "EnvLoader")
        .def(py::init<>())
        .def("reset", &EnvironmentLoader::reset)
        .def("load_from_file", &EnvironmentLoader::loadFromFile)
        .def("load_from_string", &EnvironmentLoader::loadFromString)
        .def("load_from_environment", &EnvironmentLoader::loadFromEnvironment)
        .def("add_tag", &EnvironmentLoader::addTag)
        .def("get_tag", &EnvironmentLoader::getTag)
        .def("get_action_pairs", [](const EnvironmentLoader& self) {
            return self.getActionPairs();
        })
        .def("to_string", &EnvironmentLoader::toString)
        .def("init_env_from_sgf", [](EnvironmentLoader& env_loader, const std::string& sgf_file_name) {
            env_loader.loadFromFile(sgf_file_name);
            Environment env;
            size_t move_n = std::stoi(env_loader.getTag("MV"));
            size_t i = 0;
            while (i < move_n && i < env_loader.getActionPairs().size()) {
                const auto& action_pair = env_loader.getActionPairs()[i];
                env.act(action_pair.first);
                i++;
            }
            return env;
        });
}
