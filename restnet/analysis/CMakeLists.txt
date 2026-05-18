file(GLOB SRCS *.cpp)

set(PYBIND11_FINDPYTHON ON)
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(env_py pybind_env.cpp ../t_config.cpp)
target_link_libraries(
    env_py
    PUBLIC
    config
    environment
    learner
    utils
)