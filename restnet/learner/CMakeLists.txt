file(GLOB SRCS *.cpp)

set(PYBIND11_FINDPYTHON ON)
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(restnet_py t_data_loader.cpp pybind.cpp ../t_config.cpp ${SRCS})
target_link_libraries(
    restnet_py
    PUBLIC
    config
    environment
    learner
    actor
    network
    utils
)
