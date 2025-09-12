configure_file(
    "${CMAKE_CURRENT_LIST_DIR}/version.h.in"
    "${CMAKE_CURRENT_BINARY_DIR}/version.h"
    @ONLY
)


include_directories(${PROJECT_NAME}  ${CMAKE_CURRENT_BINARY_DIR} ${CMAKE_CURRENT_BINARY_DIR}/include)

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

  # Add post-build step to generate IMG file
if(EXISTS "${WE2_SDK_PATH}/../we2_image_gen_local")
    set(WE2_IMAGE_GEN_DIR "${WE2_SDK_PATH}/../we2_image_gen_local")
    set(TARGET_ELF_NAME "EPII_CM55M_gnu_epii_evb_WLCSP65_s.elf")
    
    add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E echo "Copying ELF to image generation directory..."
        COMMAND ${CMAKE_COMMAND} -E copy 
            $<TARGET_FILE:${PROJECT_NAME}.elf>
            ${WE2_IMAGE_GEN_DIR}/input_case1_secboot/${TARGET_ELF_NAME}
        
        COMMAND ${CMAKE_COMMAND} -E echo "Generating IMG file..."
        COMMAND ${CMAKE_COMMAND} -E chdir ${WE2_IMAGE_GEN_DIR}
            ./we2_local_image_gen project_case1_blp_wlcsp.json
        
        COMMAND ${CMAKE_COMMAND} -E echo "Copying generated images back to build directory..."
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${WE2_IMAGE_GEN_DIR}/output_case1_sec_wlcsp/output.img
            ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin
        COMMAND ${CMAKE_COMMAND} -E echo "IMG file generated at ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin"
        
        COMMENT "Converting ELF to IMG using WE2 image generator"
        VERBATIM
    )
    
    # Create a separate target for just image generation
    add_custom_target(${PROJECT_NAME}_img
        DEPENDS ${PROJECT_NAME}.elf
        COMMENT "Generate IMG file from ELF"
    )
    
    message(STATUS "Post-build IMG generation enabled")
else()
    message(WARNING "WE2 image generator not found at ${WE2_SDK_PATH}/../we2_image_gen_local")
endif()

target_link_libraries(${PROJECT_NAME}.elf PRIVATE 
    "-Wl,--whole-archive"  
    main ${REQUIREDS}       
    "-Wl,--no-whole-archive" 
    -lm -lc_nano -lgcc -lstdc++_nano
    -Wl,--end-group
    -Wl,--print-memory-usage
)
