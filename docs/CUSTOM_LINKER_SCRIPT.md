# Custom Linker Script Support

This project supports customizing the linker script file. The default linker script is located at `cmake/linker/grove.ld`, but projects can override it by setting the `LINKER_SCRIPT` variable before including the project configuration.

## How to Use Custom Linker Script

### Method 1: Set LINKER_SCRIPT in CMakeLists.txt

In your project's `CMakeLists.txt`, set the `LINKER_SCRIPT` variable before including the project configuration:

```cmake
cmake_minimum_required(VERSION 3.5.0)

project(your_project C CXX)

get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)
get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)

include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)

# Override the default linker script with project-specific one
set(LINKER_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/custom_grove.ld)

include(${ROOT_DIR}/cmake/project.cmake)
```

### Method 2: Pass as CMake argument

You can also specify the linker script when configuring the build:

```bash
cmake -B build -DLINKER_SCRIPT=/path/to/your/custom.ld
```

### Method 3: Environment variable

Set the `LINKER_SCRIPT` environment variable:

```bash
export LINKER_SCRIPT=/path/to/your/custom.ld
cmake -B build
```

## Example Custom Linker Script

The `allon_sensor_tflm` project includes an example custom linker script (`custom_grove.ld`) that demonstrates:

1. **Custom memory layout**: Optimized heap and stack sizes for this specific application
2. **Model data placement**: Dedicated section for ML model data in SRAM
3. **Memory optimization**: Reduced heap and stack sizes to fit within memory constraints

### Key differences from default grove.ld:

- `__HEAP_SIZE = 0x8000` (32KB instead of 64KB)
- `__STACK_SIZE = 0x8000` (32KB instead of 64KB)  
- Custom `.model` section for efficient model data placement
- Enhanced memory checking and overflow protection

## Memory Layout

The custom linker script defines three main memory regions:

- **CM55M_S_APP_ROM** (0x10000000, 256KB): Code and read-only data
- **CM55M_S_APP_DATA** (0x30000000, 256KB): Data, BSS, heap, and stack
- **CM55M_S_SRAM** (0x34020000, ~2MB): SRAM for model data and large buffers

## Best Practices

1. **Always test memory usage**: Use `-Wl,--print-memory-usage` to verify your memory layout
2. **Backup original**: Keep a copy of the working linker script before modifications
3. **Document changes**: Comment your custom sections and memory adjustments
4. **Test thoroughly**: Verify that your custom linker script works with all build configurations

## Debugging Memory Issues

If you encounter memory-related build errors:

1. Check the build output for memory usage statistics
2. Review the generated `.map` file for section placement
3. Adjust heap and stack sizes as needed
4. Ensure model data fits in the allocated SRAM region

## Switching Back to Default

To use the default linker script again, simply comment out or remove the `set(LINKER_SCRIPT ...)` line in your CMakeLists.txt:

```cmake
# set(LINKER_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/custom_grove.ld)
```

The build system will automatically fall back to the default `cmake/linker/grove.ld`.
