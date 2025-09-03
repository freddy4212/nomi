component_register(
    COMPONENT_NAME main
    SRCS ${CMAKE_CURRENT_LIST_DIR}/main.c
    ${CMAKE_CURRENT_LIST_DIR}/allon_sensor_tflm.c
    ${CMAKE_CURRENT_LIST_DIR}/cvapp.cpp
    ${CMAKE_CURRENT_LIST_DIR}/person_detect_model_data_vela.cc
    INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}
    COMPILE_DEFINITIONS ALLON_SENSOR_TFLM IP_xdma EVT_DATAPATH DBG_MORE
    REQUIREDS cis_sensor event_handler tflm
)
