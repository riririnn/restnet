file(GLOB SRCS *.cpp)

find_package(pybind11 REQUIRED)
pybind11_add_module(env_py pybind_env.cpp ../t_config.cpp)
target_link_libraries(
    env_py
    PUBLIC
    config
    environment
    learner
    utils
)