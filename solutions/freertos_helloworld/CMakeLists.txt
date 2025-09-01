cmake_minimum_required(VERSION 3.5.0)

project(freertos_helloworld C CXX)

get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)

message(STATUS "PROJECT_DIR: ${PROJECT_DIR}")

get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)

include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)

message(STATUS "ROOT_DIR: ${ROOT_DIR}")

# Enable FreeRTOS for this project
set(ENABLE_FREERTOS ON CACHE BOOL "Enable FreeRTOS support" FORCE)

include(${ROOT_DIR}/cmake/project.cmake)




