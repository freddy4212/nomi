
function(libmpix_add_include_directory target directory)
  target_include_directories(${target} PRIVATE ${directory})
endfunction()

set(LIBMPIX_DIR ${CMAKE_CURRENT_LIST_DIR}/libmpix)
include(${LIBMPIX_DIR}/ports/common.cmake)

set(LIBMPIX_STREAM_DIR ${CMAKE_CURRENT_LIST_DIR}/stream)

set(LIBMPIX_ARM_HELIUM_SRC
  ${LIBMPIX_DIR}/src/arch/arm/op_correction_helium.c
  ${LIBMPIX_DIR}/src/arch/arm/op_debayer_helium.c
  ${LIBMPIX_DIR}/src/arch/arm/op_kernel_helium.c
  ${LIBMPIX_DIR}/src/arch/arm/op_palettize_helium.c
  ${LIBMPIX_DIR}/src/arch/arm/JPEGENC_helium.c
  ${LIBMPIX_DIR}/src/arch/arm/op_jpeg_helium.c
)

set(LIBMPIX_STREAM_SRC
  ${LIBMPIX_STREAM_DIR}/src/sensor/ov5647.c
  ${LIBMPIX_STREAM_DIR}/src/sensor/imx219.c
  ${LIBMPIX_STREAM_DIR}/src/sensor/sccb.c
  ${LIBMPIX_STREAM_DIR}/src/sensor/mipi_csi.c
  ${LIBMPIX_STREAM_DIR}/src/sensor/datapath.c
  ${LIBMPIX_STREAM_DIR}/src/sensor.c
)

component_register(
  COMPONENT_NAME libmpix
  SRCS ${LIBMPIX_SRC} ${CMAKE_CURRENT_LIST_DIR}/port.c ${LIBMPIX_ARM_HELIUM_SRC} ${LIBMPIX_STREAM_SRC}
  INCLUDE_DIRS ${LIBMPIX_DIR}/include ${LIBMPIX_STREAM_DIR}/include
  PRIVATE_COMPILE_OPTIONS -O3 -Wall -Wextra
)

libmpix_init(libmpix)
