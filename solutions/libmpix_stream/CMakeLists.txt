cmake_minimum_required(VERSION 3.5.0)

project(libmpix_stream C CXX)

get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)

message(STATUS "PROJECT_DIR: ${PROJECT_DIR}")

get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)

include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)

message(STATUS "ROOT_DIR: ${ROOT_DIR}")

# Enable protocol debugging
add_compile_definitions(DEBUG_PROTOCOL=1)

include(${ROOT_DIR}/cmake/project.cmake)




