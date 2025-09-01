

file(GLOB_RECURSE SRCS ${CMAKE_CURRENT_LIST_DIR}/*.c ${CMAKE_CURRENT_LIST_DIR}/*.cpp)

component_register(
    COMPONENT_NAME main
    SRCS ${SRCS} 
    REQUIREDS freertos
)

