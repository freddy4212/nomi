override SCENARIO_APP_SUPPORT_LIST := $(APP_TYPE) \
                                      $(APP_TYPE)/core \
                                      $(APP_TYPE)/models \
                                      $(APP_TYPE)/utils \
                                      $(APP_TYPE)/drivers

APPL_DEFINES += -DTFLM_YOLOV8_POSE
APPL_DEFINES += -DTF_LITE_STATIC_MEMORY
APPL_DEFINES += -Daudvidpre_ret_pll400_timer1 -DIP_xdma
APPL_DEFINES += -DEVT_DATAPATH

APPL_DEFINES += -DUART_SEND_ALOGO_RESEULT
#APPL_DEFINES += -DEVT_CM55MTIMER -DEVT_CM55MMB
APPL_DEFINES += -DDBG_MORE

##
# UART Output Port Selection (only applies when OUTPUT_MODE uses UART)
# Options:
#   0 = USB UART only (UART0, via USB Type-C debug port)
#   1 = XIAO Connector UART only (UART1, PB6=RX, PB7=TX)
#   2 = Both UART0 and UART1 (for comparing ESP32 forwarding vs direct Serial)
##
UART_OUTPUT_PORT := 1

ifeq ($(UART_OUTPUT_PORT), 1)
APPL_DEFINES += -DUART_USE_XIAO_CONNECTOR
else ifeq ($(UART_OUTPUT_PORT), 2)
APPL_DEFINES += -DUART_USE_BOTH
endif

##
# Output Mode Selection
# Options:
#   0 = UART only (USB Type-C and XIAO Connector)
#   1 = I2C only (Grove connector, for ESP32/XIAO connection via Grove cable)
#   2 = Both UART and I2C (may have performance impact)
##
OUTPUT_MODE := 0

ifeq ($(OUTPUT_MODE), 1)
APPL_DEFINES += -DOUTPUT_VIA_I2C
# 啟用 I2C Slave 0 驅動 (注意: IIC 是兩個 I，不是 IIIC)
APPL_DEFINES += -DIP_INST_IIC_SLAVE0
else ifeq ($(OUTPUT_MODE), 2)
APPL_DEFINES += -DOUTPUT_VIA_I2C
APPL_DEFINES += -DOUTPUT_VIA_UART
APPL_DEFINES += -DIP_INST_IIC_SLAVE0
else
APPL_DEFINES += -DOUTPUT_VIA_UART
endif

# Uncomment the following line to enable SD card input for testing
# ENABLE_SD_TEST := 1

ifdef ENABLE_SD_TEST
APPL_DEFINES += -DUSE_SD_CARD_INPUT
override SCENARIO_APP_SUPPORT_LIST += $(APP_TYPE)/sd_test_module
# Ensure the directory is added to include paths
APPL_INC_DIR += $(SCENARIO_APP_ROOT)/$(APP_TYPE)/sd_test_module
endif

EVENTHANDLER_SUPPORT = event_handler
EVENTHANDLER_SUPPORT_LIST += evt_datapath

##
# library support feature
# Add new library here
# The source code should be loacted in ~\library\{lib_name}\
##
# LIB_SEL = pwrmgmt sensordp tflmtag2209_u55tag2205 spi_ptl spi_eeprom hxevent img_proc
LIB_SEL = pwrmgmt sensordp tflmtag2412_u55tag2411 spi_ptl spi_eeprom hxevent img_proc

##
# middleware support feature
# Add new middleware here
# The source code should be loacted in ~\middleware\{mid_name}\
##
MID_SEL = fatfs
FATFS_PORT_LIST = mmc_spi
CMSIS_DRIVERS_LIST = SPI

override OS_SEL:=
override TRUSTZONE := y
override TRUSTZONE_TYPE := security
override TRUSTZONE_FW_TYPE := 1
override CIS_SEL := HM_COMMON
override EPII_USECASE_SEL := drv_user_defined

CIS_SUPPORT_INAPP = cis_sensor
#CIS_SUPPORT_INAPP_MODEL = cis_hm0360
CIS_SUPPORT_INAPP_MODEL = cis_ov5647
#CIS_SUPPORT_INAPP_MODEL = cis_imx219

ifeq ($(CIS_SUPPORT_INAPP_MODEL), cis_imx219)
APPL_DEFINES += -DCIS_IMX
else ifeq ($(CIS_SUPPORT_INAPP_MODEL), cis_imx477)
APPL_DEFINES += -DCIS_IMX
else ifeq ($(CIS_SUPPORT_INAPP_MODEL), cis_imx708)
APPL_DEFINES += -DCIS_IMX
endif

ifeq ($(strip $(TOOLCHAIN)), arm)
override LINKER_SCRIPT_FILE := $(SCENARIO_APP_ROOT)/$(APP_TYPE)/TFLM_yolov8_pose_S_only.sct
else#TOOLChain
override LINKER_SCRIPT_FILE := $(SCENARIO_APP_ROOT)/$(APP_TYPE)/TFLM_yolov8_pose_S_only.ld
endif
##
# Add new external device here
# The source code should be located in ~\external\{device_name}\
##
#EXT_DEV_LIST += 
