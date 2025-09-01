configure_file(
    "${CMAKE_CURRENT_LIST_DIR}/version.h.in"
    "${CMAKE_CURRENT_BINARY_DIR}/version.h"
    @ONLY
)


include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_BINARY_DIR})

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/dummy.c "")

list(REMOVE_DUPLICATES REQUIREDS)

add_executable(${PROJECT_NAME}.elf ${CMAKE_CURRENT_BINARY_DIR}/dummy.c)


target_link_options(${PROJECT_NAME}.elf PRIVATE
    -mthumb -mcpu=cortex-m55 -mfloat-abi=hard -mcmse
    -Wl,--gc-sections
    -Wl,--sort-section=alignment
    -Wl,--cref
    -T ${LINKER_SCRIPT}
    -Wl,-Map=${PROJECT_NAME}.map
    -specs=nano.specs
    -Wl,--no-warn-rwx-segments
    -Wl,--cmse-implib
    -Wl,--start-group
    -L${WE2_SDK_PATH}/prebuilt_libs/gnu
  )
  
target_link_libraries(${PROJECT_NAME}.elf PRIVATE 
    main ${REQUIREDS}
    -lm -lc_nano -lgcc -lstdc++_nano
    -Wl,--end-group
    -Wl,--print-memory-usage
)

