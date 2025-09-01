set(SOPHGO_PLATFORM ON)

include(${ROOT_DIR}/cmake/macro.cmake)

# choose board
if(NOT DEFINED BOARD_NAME)
    set(BOARD_NAME "Grove Vision AI V2")
    set(LINKER_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/linker/grove.ld)
endif()


message(STATUS "Building for board: ${BOARD_NAME}")

if(NOT "${WE2_SDK_PATH}" STREQUAL "")
    message(STATUS "WE2_SDK_PATH: ${WE2_SDK_PATH}")

    add_compile_definitions(  
        DEBUG
        __GNU__
        __NEWLIB__
        ARMCM55
        CM55_BIG
        IC_VERSION=30
        COREV_0P9V
        EPII_EVB
        IC_PACKAGE_WLCSP65
        
        # TrustZone 
        TRUSTZONE
        TRUSTZONE_CFG
        TRUSTZONE_SEC
        TRUSTZONE_SEC_ONLY
        
        # lib
        LIB_COMMON
        LIB_CMSIS_NN
        LIB_EVENT
        LIB_PWRMGMT
        LIB_QSPI_EEPROM
        LIB_SPI_EEPROM
        LIB_SPI_PTL
        LIB_SENSORDP
        
        # CMSIS-NN  TensorFlow Lite
        ARM_MATH_DSP
        ARM_MATH_LOOPUNROLL
        ARM_MATH_MVEI
        CMSIS_NN
        ETHOSU55
        ETHOSU_ARCH=u55
        ETHOSU_LOG_SEVERITY=ETHOSU_LOG_WARN
        ETHOS_U
        TFLM2209_U55TAG2205
        TF_LITE_MCU_DEBUG_LOG
        TF_LITE_STATIC_MEMORY
        
        # IP 
        IP_2x2
        IP_5x5
        IP_adcc
        IP_adcc_hv
        IP_cdm
        IP_csirx
        IP_csitx
        IP_dma
        IP_dp
        IP_edm
        IP_gpio
        IP_hxautoi2c_mst
        IP_i2s
        IP_i3c_mst
        IP_i3c_slv
        IP_iic
        IP_inp
        IP_inp1bitparser
        IP_inpovparser
        IP_isp
        IP_jpeg
        IP_mb
        IP_mpc
        IP_pdm
        IP_pmu
        IP_ppc
        IP_pwm
        IP_rtc
        IP_scu
        IP_sensorctrl
        IP_spi
        IP_swreg_aon
        IP_swreg_lsc
        IP_timer
        IP_tpg
        IP_u55
        IP_uart
        IP_vad
        IP_watchdog
        IP_xdma
        
        # IP instance
        IP_INST_ADCC
        IP_INST_ADCC_HV
        IP_INST_AON_GPIO
        IP_INST_DMA0
        IP_INST_DMA1
        IP_INST_DMA2
        IP_INST_DMA3
        IP_INST_GPIO_G0
        IP_INST_GPIO_G1
        IP_INST_GPIO_G2
        IP_INST_GPIO_G3
        IP_INST_I2S_HOST
        IP_INST_I2S_SLAVE
        IP_INST_IIC_HOST
        IP_INST_IIC_HOST_MIPI
        IP_INST_IIC_HOST_SENSOR
        IP_INST_IIIC_SLAVE0
        IP_INST_IIIC_SLAVE1
        IP_INST_OSPI_HOST
        IP_INST_PWM0
        IP_INST_PWM1
        IP_INST_PWM2
        IP_INST_QSPI_HOST
        IP_INST_RTC0
        IP_INST_RTC1
        IP_INST_RTC2
        IP_INST_SB_GPIO
        IP_INST_SSPI_HOST
        IP_INST_SSPI_SLAVE
        IP_INST_TIMER0
        IP_INST_TIMER1
        IP_INST_TIMER2
        IP_INST_TIMER3
        IP_INST_TIMER4
        IP_INST_TIMER5
        IP_INST_TIMER6
        IP_INST_TIMER7
        IP_INST_TIMER8
        IP_INST_UART0
        IP_INST_UART1
        IP_INST_UART2
        IP_INST_WDT0
        IP_INST_WDT1
        
        # 
        HM_COMMON
        EVT_DATAPATH
        SPI_EEPROM_USE_WB_25Q128JW_INST_
    )

    # board
    component_register(
        COMPONENT_NAME board
        INCLUDE_DIRS ${WE2_SDK_PATH}/board ${WE2_SDK_PATH}/board/epii_evb ${WE2_SDK_PATH}/board/epii_evb/config ${WE2_SDK_PATH}/interface
        SRCS ${WE2_SDK_PATH}/board/epii_evb/board.c
             ${WE2_SDK_PATH}/board/epii_evb/pinmux_init.c
             ${WE2_SDK_PATH}/board/epii_evb/platform_driver_init.c
        REQUIRED
    ) 

    # device
    component_register(
        COMPONENT_NAME device
        INCLUDE_DIRS ${WE2_SDK_PATH}/device/inc  ${WE2_SDK_PATH}/device/clib  ${WE2_SDK_PATH}/device/clib/gnu
        SRCS ${WE2_SDK_PATH}/device/startup_WE2_ARMCM55.cc
             ${WE2_SDK_PATH}/device/system_WE2_ARMCM55.c
             ${WE2_SDK_PATH}/device/WE2_core.c
             ${WE2_SDK_PATH}/device/clib/console_io.c
             ${WE2_SDK_PATH}/device/clib/gnu/retarget_io.c
             ${WE2_SDK_PATH}/device/clib/retarget.c
             ${WE2_SDK_PATH}/device/clib/retarget.c
        REQUIRED
    ) 

    # drivers
    component_register(
        COMPONENT_NAME drivers
        INCLUDE_DIRS  ${WE2_SDK_PATH}/drivers ${WE2_SDK_PATH}/drivers/inc ${WE2_SDK_PATH}/drivers/seconly_inc
        REQUIREDS driver
    )

    # cmsis
    component_register(
        COMPONENT_NAME CMSIS
        INCLUDE_DIRS ${WE2_SDK_PATH}/CMSIS
    )

    # libraries

    # trustzone configuration for secure build
    component_register(
        COMPONENT_NAME trustzone_cfg
        INCLUDE_DIRS ${WE2_SDK_PATH}/trustzone/tz_cfg
        SRCS ${WE2_SDK_PATH}/trustzone/tz_cfg/trustzone_cfg.c
        REQUIRED
    )

    #interface libraries
    component_register(
        COMPONENT_NAME interface
        INCLUDE_DIRS ${WE2_SDK_PATH}/interface
        SRCS ${WE2_SDK_PATH}/interface/driver_interface.c ${WE2_SDK_PATH}/interface/timer_interface.c
        REQUIRED 
    )

    # common libraries
    component_register(
        COMPONENT_NAME common
        INCLUDE_DIRS ${WE2_SDK_PATH}/library/common
        SRCS ${WE2_SDK_PATH}/library/common/xprintf.c
        REQUIRED 
    )

    # freertos
    com

else()
    message(WARNING "WE2_SDK_PATH is not set")
endif()

file(GLOB COMPONENTS LIST_DIRECTORIES true ${ROOT_DIR}/components/*)
include(${PROJECT_DIR}/main/CMakeLists.txt)

set(SKIP_COMPONENTS "")

foreach(component IN LISTS COMPONENTS)
    get_filename_component(component_name ${component} NAME)
    message(STATUS "component: ${component_name}")

    if(EXISTS "${component}/CMakeLists.txt" AND component_name IN_LIST REQUIREDS)
        include("${component}/CMakeLists.txt")
    else()
        list(APPEND SKIP_COMPONENTS ${component})
    endif()

    foreach(component IN LISTS SKIP_COMPONENTS)
        get_filename_component(component_name ${component} NAME)

        if(EXISTS "${component}/CMakeLists.txt" AND component_name IN_LIST REQUIREDS)
            include("${component}/CMakeLists.txt")
        endif()
    endforeach()
endforeach()

include(${ROOT_DIR}/cmake/build.cmake)

