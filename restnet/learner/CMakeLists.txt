file(GLOB SRCS *.cpp)

find_package(pybind11 REQUIRED)
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
