# Event Handler Module Selection

This document describes how to configure and use event handler modules in your project.

## Overview

The event handler component supports conditional compilation of different modules. You can enable one or multiple modules based on your project requirements.

## Available Modules

| Module | Description |
|--------|-------------|
| EVT_DATAPATH | Data path event handling |
| EVT_I2CCOMM | I2C communication event handling |
| EVT_UARTCOMM | UART communication event handling |
| EVT_CM55MMB | Cortex-M55 memory management block events |
| EVT_CM55MMB_NBAPP | Cortex-M55 MMB non-blocking application events |
| EVT_CM55MTIMER | Cortex-M55 main timer events |
| EVT_CM55STIMER | Cortex-M55 system timer events |

## Configuration

### Single Module Selection

To enable a single event handler module, set the `EVENT_HANDLER_MODULES` variable in your project's CMakeLists.txt:

```cmake
# Enable only data path event handling
set(EVENT_HANDLER_MODULES "EVT_DATAPATH")
```

### Multiple Module Selection

To enable multiple event handler modules, separate them with semicolons:

```cmake
# Enable multiple modules
set(EVENT_HANDLER_MODULES "EVT_DATAPATH;EVT_I2CCOMM;EVT_UARTCOMM")
```

### All Modules

To enable all available modules:

```cmake
set(EVENT_HANDLER_MODULES "EVT_DATAPATH;EVT_I2CCOMM;EVT_UARTCOMM;EVT_CM55MMB;EVT_CM55MMB_NBAPP;EVT_CM55MTIMER;EVT_CM55STIMER")
```

## Usage in Code

### Include Headers

Include the relevant event handler headers based on enabled modules:

```c
// Include specific headers based on enabled modules
#ifdef EVT_DATAPATH_ENABLED
#include "event_handler.h"
#endif
```

### Check Individual Modules

Each enabled module defines a corresponding macro:

```c
#ifdef EVT_DATAPATH_ENABLED
    // Data path module is available
    printf("Data path event handling enabled\\n");
#endif

#ifdef EVT_I2CCOMM_ENABLED
    // I2C communication module is available
    printf("I2C communication event handling enabled\\n");
#endif

#ifdef EVT_UARTCOMM_ENABLED
    // UART communication module is available
    printf("UART communication event handling enabled\\n");
#endif
```

## Example Projects

### Basic Example

See `solutions/allon_sensor_tflm` for an example that enables data path, I2C, and UART event handling:

```cmake
set(EVENT_HANDLER_MODULES "EVT_DATAPATH;EVT_I2CCOMM;EVT_UARTCOMM")
```

### Timer-focused Example

For projects that primarily need timer event handling:

```cmake
set(EVENT_HANDLER_MODULES "EVT_CM55MTIMER;EVT_CM55STIMER")
```

### Communication-focused Example

For projects that need various communication interfaces:

```cmake
set(EVENT_HANDLER_MODULES "EVT_I2CCOMM;EVT_UARTCOMM")
```

## Build System Integration

The event handler component automatically:

1. Includes only the source files for enabled modules
2. Defines appropriate preprocessor macros
3. Links the necessary libraries
4. Provides a unified configuration header

## Troubleshooting

### Module Not Found Error

If you get an error like "Unknown event handler module", check:

1. Module name spelling (case-sensitive)
2. Available modules list in this document
3. CMakeLists.txt syntax (use semicolons for multiple modules)

### Linker Errors

If you encounter linker errors:

1. Ensure all required dependencies are included
2. Check that the WE2 SDK path is correctly configured
3. Verify that your linker script has sufficient memory allocation

### Runtime Issues

If event handlers fail to initialize:

1. Check that the hardware supports the selected modules
2. Verify that conflicting modules are not enabled simultaneously
3. Ensure proper board initialization before calling event_handler_init()

## Best Practices

1. **Minimize footprint**: Only enable modules you actually use
2. **Test combinations**: Some module combinations may have dependencies
3. **Check memory usage**: Multiple modules increase memory requirements
4. **Document choices**: Comment your module selection in CMakeLists.txt
5. **Version compatibility**: Verify module compatibility with your WE2 SDK version
