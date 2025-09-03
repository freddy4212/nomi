# Camera Sensor Selection Guide

This document explains how to configure and use different camera sensors in your projects.

## Supported Camera Sensors

The `cis_sensor` component supports the following camera sensors:

| Sensor Type | Model | Max Resolution | Default Resolution | Notes |
|-------------|-------|----------------|-------------------|-------|
| OV5647 | OmniVision OV5647 | 2592x1944 | 640x480 | Default sensor |
| IMX219 | Sony IMX219 | 3280x2464 | 640x480 | High resolution |
| IMX477 | Sony IMX477 | 4056x3040 | 640x480 | Ultra high resolution |
| IMX708 | Sony IMX708 | 2304x1296 | 640x480 | Wide format |
| HM0360 | Himax HM0360 | 640x480 | 640x480 | Low power |

## How to Select a Camera Sensor

### Method 1: Set in Project CMakeLists.txt

Add the following line to your project's `CMakeLists.txt` file before including the project configuration:

```cmake
# Configure camera sensor type
set(CAMERA_SENSOR_TYPE "IMX219")  # Replace with your desired sensor

include(${ROOT_DIR}/cmake/project.cmake)
```

### Method 2: Pass as CMake argument

You can specify the camera sensor when configuring the build:

```bash
cmake -B build -DCAMERA_SENSOR_TYPE=IMX477
```

### Method 3: Environment variable

Set the `CAMERA_SENSOR_TYPE` environment variable:

```bash
export CAMERA_SENSOR_TYPE=IMX708
cmake -B build
```

## Example Usage

### Basic Configuration

```cmake
cmake_minimum_required(VERSION 3.5.0)

project(my_camera_project C CXX)

get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)
get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)

include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)

# Select IMX219 camera sensor
set(CAMERA_SENSOR_TYPE "IMX219")

include(${ROOT_DIR}/cmake/project.cmake)
```

### Using in C/C++ Code

Include the camera sensor configuration header:

```c
#include "cis_sensor_config.h"

void camera_init(void) {
    printf("Using camera sensor: %s\n", cis_get_sensor_name());
    
    #if IS_SENSOR_IMX219()
        printf("IMX219 specific initialization\n");
        // IMX219-specific code here
    #elif IS_SENSOR_OV5647()
        printf("OV5647 specific initialization\n");
        // OV5647-specific code here
    #endif
    
    printf("Default resolution: %dx%d\n", SENSOR_DEFAULT_WIDTH, SENSOR_DEFAULT_HEIGHT);
    printf("Maximum resolution: %dx%d\n", SENSOR_MAX_WIDTH, SENSOR_MAX_HEIGHT);
}
```

### Conditional Compilation

The build system automatically defines preprocessor macros based on your selection:

- `CIS_OV5647_ENABLED` and `CAMERA_SENSOR_OV5647` for OV5647
- `CIS_IMX219_ENABLED` and `CAMERA_SENSOR_IMX219` for IMX219
- `CIS_IMX477_ENABLED` and `CAMERA_SENSOR_IMX477` for IMX477
- `CIS_IMX708_ENABLED` and `CAMERA_SENSOR_IMX708` for IMX708
- `CIS_HM0360_ENABLED` and `CAMERA_SENSOR_HM0360` for HM0360

## Build Examples

### Build with default sensor (OV5647)
```bash
cmake -B build
make -C build
```

### Build with IMX219
```bash
cmake -B build -DCAMERA_SENSOR_TYPE=IMX219
make -C build
```

### Build with IMX477
```bash
cmake -B build -DCAMERA_SENSOR_TYPE=IMX477
make -C build
```

### Clean and rebuild with different sensor
```bash
rm -rf build
cmake -B build -DCAMERA_SENSOR_TYPE=HM0360
make -C build
```

## Project Structure

```
components/cis_sensor/
├── CMakeLists.txt          # Main component configuration
├── cis_sensor_config.h     # Unified sensor interface
├── cis_ov5647/            # OV5647 sensor driver
│   ├── cisdp_sensor.c
│   ├── cisdp_sensor.h
│   └── cisdp_cfg.h
├── cis_imx219/            # IMX219 sensor driver
│   ├── cisdp_sensor.c
│   ├── cisdp_sensor.h
│   └── cisdp_cfg.h
├── cis_imx477/            # IMX477 sensor driver
├── cis_imx708/            # IMX708 sensor driver
└── cis_hm0360/            # HM0360 sensor driver
```

## Troubleshooting

### Build Error: "No camera sensor type defined"

This error occurs when no sensor type is specified. Add one of these to your project:

```cmake
set(CAMERA_SENSOR_TYPE "OV5647")  # Or any supported sensor
```

### Build Error: "Unsupported CAMERA_SENSOR_TYPE"

Check that you're using one of the supported sensor types (case-sensitive):
- OV5647
- IMX219
- IMX477
- IMX708
- HM0360

### Linker Errors

Make sure the sensor-specific source files exist and are properly configured. Check that the sensor driver directory contains the required `cisdp_sensor.c` file.

## Best Practices

1. **Always specify sensor type**: Even if using the default, explicitly set `CAMERA_SENSOR_TYPE` for clarity
2. **Use the config header**: Include `cis_sensor_config.h` instead of sensor-specific headers directly
3. **Clean builds**: When switching sensors, always clean the build directory first
4. **Test configurations**: Verify your sensor selection works before committing code
5. **Document dependencies**: Note which sensor your application requires in documentation
