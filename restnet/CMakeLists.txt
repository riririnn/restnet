file(GLOB SRCS *.cpp)

add_executable(restnet ${SRCS})
target_link_libraries(
    restnet
    actor
    config
    console
    environment
    network
    utils
    zero
    ${TORCH_LIBRARIES}
)