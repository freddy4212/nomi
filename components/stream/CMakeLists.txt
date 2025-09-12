component_register(
    COMPONENT_NAME stream
    SRCS  ${CMAKE_CURRENT_LIST_DIR}/sensor/ov5647.c
          ${CMAKE_CURRENT_LIST_DIR}/sensor/imx219.c
          ${CMAKE_CURRENT_LIST_DIR}/sensor/sccb.c
          ${CMAKE_CURRENT_LIST_DIR}/sensor/mipi_csi.c
          ${CMAKE_CURRENT_LIST_DIR}/sensor/datapath.c
          ${CMAKE_CURRENT_LIST_DIR}/sensor.c
    INCLUDE_DIRS  ${CMAKE_CURRENT_LIST_DIR}
    PRIVATE_COMPILE_OPTIONS -O3 -Wall -Wextra
    REQUIREDS libmpix
)





