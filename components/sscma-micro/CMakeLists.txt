set(SSCMA_ROOT_DIR ${CMAKE_CURRENT_LIST_DIR}/sscma-micro)
set(SSCMA_PORTING_DIR ${CMAKE_CURRENT_LIST_DIR}/porting)

include(${SSCMA_ROOT_DIR}/3rdparty/json/CMakeLists.txt)

include(${SSCMA_ROOT_DIR}/3rdparty/littlefs/CMakeLists.txt)

file(GLOB_RECURSE CORE_SOURCES ${SSCMA_ROOT_DIR}/sscma/core/*.c ${SSCMA_ROOT_DIR}/sscma/core/*.cpp)

file(GLOB_RECURSE SREVER_SOURCES ${SSCMA_ROOT_DIR}/sscma/server/*.c ${SSCMA_ROOT_DIR}/sscma/server/*.cpp)

file(GLOB_RECURSE CLIENT_SOURCES ${SSCMA_ROOT_DIR}/sscma/client/*.c ${SSCMA_ROOT_DIR}/sscma/client/*.cpp)

file(GLOB_RECURSE PORT_SOURCES ${SSCMA_ROOT_DIR}/sscma/porting/osal/ma_osal_freertos.cpp)

file(GLOB_RECURSE PORTING_SOURCES ${SSCMA_PORTING_DIR}/*.c ${SSCMA_PORTING_DIR}/*.cpp)

list(APPEND EXTENSION_SSCMA_SOURCES ${BYTETRACK_SSCMA_SOURCES} ${COUNTER_SSCMA_SOURCES})

set(SOURCES ${CORE_SOURCES} ${SREVER_SOURCES} ${CLIENT_SOURCES} ${PORT_SOURCES} ${PORTING_SOURCES} ${SRCS_LITTLEFS} ${SRCS_CJSON} ${EXTENSION_SSCMA_SOURCES})

set(INCS
    ${INCS_LITTLEFS}
    ${INCS_CJSON}
    ${SSCMA_ROOT_DIR}/sscma
    ${SSCMA_ROOT_DIR}/sscma/porting
    ${SSCMA_ROOT_DIR}/sscma/porting/drivers
    ${SSCMA_ROOT_DIR}/sscma/server
    ${SSCMA_ROOT_DIR}/sscma/server/at
    ${SSCMA_ROOT_DIR}/sscma/server/at/codec
    ${SSCMA_ROOT_DIR}/sscma/server/at/callback
    ${SSCMA_PORTING_DIR}/we2
    ${SSCMA_PORTING_DIR}/we2/board
    ${SSCMA_PORTING_DIR}/we2/drivers
)

add_compile_definitions(CONFIG_MA_ENGINE_TFLITE=1 MA_BOARD_GROVE_VISION_AI_V2)

component_register(
    COMPONENT_NAME sscma-micro
    SRCS ${SOURCES}
    INCLUDE_DIRS ${INCS}
    PRIVATE_REQUIREDS freertos tflm
)