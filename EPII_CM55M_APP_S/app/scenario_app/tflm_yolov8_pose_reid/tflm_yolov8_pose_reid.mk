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

# Uncomment the following line to enable SD card input for testing
ENABLE_SD_TEST := 1

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
