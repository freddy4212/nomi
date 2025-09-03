# Event Handler component with conditional compilation support
# Configure which event handler modules to include by defining EVENT_HANDLER_MODULES
# Supported modules: EVT_DATAPATH, EVT_I2CCOMM, EVT_UARTCOMM, EVT_CM55MMB, 
#                    EVT_CM55MMB_NBAPP, EVT_CM55MTIMER, EVT_CM55STIMER
# Multiple modules can be enabled simultaneously
# Default: EVT_DATAPATH (for compatibility)

set(LIB_EVENT_HANDLER_DIR ${WE2_SDK_PATH}/app/scenario_app/event_handler)

# Core event handler sources (always included)
file(GLOB CORE_SRCS ${LIB_EVENT_HANDLER_DIR}/*.c)

# Initialize module-specific variables
set(MODULE_SRCS "")
set(MODULE_INCS "")
set(MODULE_DEFINITIONS "")

# Default modules if not specified
if(NOT DEFINED EVENT_HANDLER_MODULES)
    set(EVENT_HANDLER_MODULES "EVT_DATAPATH")
    message(STATUS "EVENT_HANDLER_MODULES not defined, using default: ${EVENT_HANDLER_MODULES}")
endif()

# Convert to list if it's a string
if(EVENT_HANDLER_MODULES)
    string(REPLACE ";" " " EVENT_HANDLER_MODULES_STR "${EVENT_HANDLER_MODULES}")
    message(STATUS "Building with Event Handler modules: ${EVENT_HANDLER_MODULES_STR}")
endif()

# Define module descriptions for user-friendly messages
set(MODULE_DESCRIPTIONS
    "EVT_DATAPATH:Data path event handling"
    "EVT_I2CCOMM:I2C communication event handling" 
    "EVT_UARTCOMM:UART communication event handling"
    "EVT_CM55MMB:CM55M mailbox event handling"
    "EVT_CM55MMB_NBAPP:CM55M mailbox non-blocking app event handling"
    "EVT_CM55MTIMER:CM55M timer event handling"
    "EVT_CM55STIMER:CM55S timer event handling"
)

# Convert module descriptions to a map for lookup
foreach(DESC ${MODULE_DESCRIPTIONS})
    string(REGEX REPLACE "^([^:]+):(.+)$" "\\1" MODULE_NAME ${DESC})
    string(REGEX REPLACE "^([^:]+):(.+)$" "\\2" MODULE_DESC ${DESC})
    set(MODULE_DESC_${MODULE_NAME} ${MODULE_DESC})
endforeach()

# Process each enabled module
foreach(MODULE ${EVENT_HANDLER_MODULES})
    # Convert module name to lowercase directory name
    string(TOLOWER ${MODULE} MODULE_DIR)
    
    # Check if the module directory exists
    if(EXISTS ${LIB_EVENT_HANDLER_DIR}/${MODULE_DIR})
        # Add source files
        file(GLOB MODULE_SRCS_TMP ${LIB_EVENT_HANDLER_DIR}/${MODULE_DIR}/*.c)
        list(APPEND MODULE_SRCS ${MODULE_SRCS_TMP})
        
        # Add include directory
        list(APPEND MODULE_INCS ${LIB_EVENT_HANDLER_DIR}/${MODULE_DIR})
        
        # Add compile definition
        list(APPEND MODULE_DEFINITIONS ${MODULE}_ENABLED)
        
        # Print status message with description
        if(DEFINED MODULE_DESC_${MODULE})
            message(STATUS "  - ${MODULE}: ${MODULE_DESC_${MODULE}}")
        else()
            message(STATUS "  - ${MODULE}: Event handling module")
        endif()
    else()
        message(WARNING "Unknown event handler module: ${MODULE}")
        message(STATUS "Available modules: EVT_DATAPATH, EVT_I2CCOMM, EVT_UARTCOMM, EVT_CM55MMB, EVT_CM55MMB_NBAPP, EVT_CM55MTIMER, EVT_CM55STIMER")
    endif()
endforeach()

# Get all include directories
file(GLOB children RELATIVE ${LIB_EVENT_HANDLER_DIR} ${LIB_EVENT_HANDLER_DIR}/*)
set(ALL_INCS "")
foreach(child ${children})
    if(IS_DIRECTORY ${LIB_EVENT_HANDLER_DIR}/${child})
        list(APPEND ALL_INCS ${LIB_EVENT_HANDLER_DIR}/${child})
    endif()
endforeach()

component_register(
    COMPONENT_NAME event_handler
    SRCS ${CORE_SRCS} ${MODULE_SRCS}
    INCLUDE_DIRS ${WE2_SDK_PATH}/app ${LIB_EVENT_HANDLER_DIR} ${MODULE_INCS}
    COMPILE_DEFINITIONS ${MODULE_DEFINITIONS}
)
