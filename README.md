# SSCMA Example for WE2 (Grove Vision AI Module V2)

🚀 **A comprehensive development framework for the Seeed Grove Vision AI Module V2 based on the WE2 (WiseEye 2) platform**

![Grove Vision AI Module V2](https://media-cdn.seeedstudio.com/media/catalog/product/cache/bb49d3ec4ee05b6f018e93f896b8a25d/4/-/4-101021112-grove-vision-ai-module-v2-45back.jpg)

## 📖 Overview

This project provides a complete development environment for the **Seeed Grove Vision AI Module V2**, which is powered by the **WiseEye 2 (WE2)** AI vision processor. The framework includes:

- **ARM Cortex-M55 development** with TrustZone security features
- **AI/ML acceleration** with CMSIS-NN and TensorFlow Lite Micro support
- **Rich peripheral support** including camera interfaces, sensors, and communication protocols
- **Example applications** to get you started quickly

### Key Features

- 🎯 **Grove Vision AI Module V2** development framework
- 🏗️ **Modular architecture** with component-based development
- 📷 **Vision processing** capabilities
- 🔧 **Example applications** to get started quickly

## 🏗️ Architecture

### Hardware Platform
- **Target Board**: Grove Vision AI Module V2
- **Development Framework**: Component-based modular architecture

### Software Stack
```
┌─────────────────────────────────┐
│        Applications            │
├─────────────────────────────────┤
│         Libraries               │
│  • Common utilities            │
├─────────────────────────────────┤
│        Device Drivers          │
│  • Board support package       │
├─────────────────────────────────┤
│      Hardware Abstraction      │
│  • Peripheral interfaces       │
└─────────────────────────────────┘
```

## 🔧 Prerequisites

### Development Environment
- **CMake** 3.5.0 or later
- **ARM GNU Toolchain** (`arm-none-eabi-gcc`)
- **WE2 SDK** from [Himax WiseEye Plus](https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2)

### Environment Setup
1. **Install ARM GNU Toolchain**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install gcc-arm-none-eabi
   
   # Or download from ARM official website
   wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/...
   ```

2. **Get WE2 SDK**:
   ```bash
   git clone https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2.git
   ```

3. **Set WE2 SDK Path**:
   ```bash
   export WE2_SDK_PATH=/path/to/Seeed_Grove_Vision_AI_Module_V2/EPII_CM55M_APP_S
   ```

3. **Verify Installation**:
   ```bash
   arm-none-eabi-gcc --version
   cmake --version
   echo $WE2_SDK_PATH
   ```

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Seeed-Studio/sscma-example-we2.git
cd sscma-example-we2
```

### 2. Build the HelloWorld Example
```bash
cd solutions/helloworld
cmake -B build -DCMAKE_BUILD_TYPE=Release .
cmake --build build
```

### 3. Flash to Device

The build process generates the following files in the `build/` directory:
- `<project_name>.elf` - Executable ELF file for debugging
- `<project_name>.map` - Memory mapping file
- `<project_name>.bin` - Binary image file for flashing (generated from `.elf` using WE2 image generator)

#### Output File Locations
```
solutions/<example_name>/build/
├── <project_name>.elf     # Main executable
├── <project_name>.map     # Memory layout
└── <project_name>.bin     # Flashable binary image
```

#### Flashing Methods

**Method 1: Using python-sscma (Recommended)**
```bash
# Install python-sscma
pip install python-sscma

# Flash the binary file
sscma.cli.exe flasher -f ./build/<project_name>.bin -p COMXX
# Replace COMXX with your actual COM port (e.g., COM3, COM4)
```

**Method 2: Manual Flashing**
For alternative flashing methods and advanced usage, refer to:
- [python-sscma Documentation](https://github.com/Seeed-Studio/python-sscma)
- [Grove Vision AI Module V2 Wiki](https://wiki.seeedstudio.com/Grove-Vision-AI-Module-V2/)

#### Finding Your COM Port
- **Windows**: Check Device Manager → Ports (COM & LPT)
- **Linux**: Use `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
- **macOS**: Use `ls /dev/tty.usb*`

#### Troubleshooting Flash Issues
```bash
# If flash fails, try:
# 1. List available COM ports (don't specify -p parameter)
sscma.cli flasher -f ./build/<project_name>.bin
# This will show available COM ports for selection:
# Multiple COM ports detected. Please select one:
# 1. COM71
# 2. COM72
# Enter the number of the COM port:

# 2. Reset device and retry
# 3. Flash to specify address
sscma.cli flasher -f ./build/<project_name>.tflite -p COMXX --offset 0x4000000
```

For more detailed usage and advanced flashing options, visit the [python-sscma repository](https://github.com/Seeed-Studio/python-sscma).

## 📁 Project Structure

```
sscma-example-we2/
├── cmake/                          # Build system configuration
│   ├── build.cmake                 # Main build configuration
│   ├── project.cmake               # Project-specific settings
│   ├── toolchain-arm-none-eabi.cmake # ARM toolchain setup
│   ├── macro.cmake                 # Utility macros
│   ├── version.h.in               # Version header template
│   └── linker/
│       └── grove.ld               # Linker script for Grove Vision AI V2
├── solutions/                      # Example applications
│   └── helloworld/                # Simple "Hello World" example
│       ├── CMakeLists.txt         # Build configuration
│       ├── README.md              # Example-specific documentation
│       └── main/
│           ├── CMakeLists.txt     # Main component configuration
│           └── main.cpp           # Application entry point
└── build/                         # Generated build artifacts (created during build)
```

## 💡 Example Applications

### HelloWorld
A simple example that demonstrates:
- Basic board initialization
- UART output functionality
- Periodic message printing
- Foundation for more complex applications

**Location**: `solutions/helloworld/`

**Features**:
- Board initialization and configuration
- Clean project structure for extension

## 🔧 Development Guide

### Creating a New Application

1. **Create Solution Directory**:
   ```bash
   mkdir solutions/my_app
   cd solutions/my_app
   ```

2. **Create CMakeLists.txt**:
   ```cmake
   cmake_minimum_required(VERSION 3.5.0)
   
   project(my_app C CXX)
   
   get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)
   get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)
   
   include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)
   
   include(${ROOT_DIR}/cmake/project.cmake)
   ```

3. **Create Main Source**:
   ```bash
   mkdir main
   cd main
   ```

4. **Add Your Code**:
   ```cpp
   #include "WE2_device.h"
   #include "WE2_core.h"
   #include "board.h"
   #include "xprintf.h"
   
   int main(void) {
       board_init();
       
       // Your application code here
       
       return 0;
   }
   ```

### Component System

The framework uses a component-based architecture. Each component is registered using the `component_register()` macro:

```cmake
component_register(
    COMPONENT_NAME my_component
    SRCS src/component.c
    INCLUDE_DIRS include/
    COMPILE_OPTIONS -O2 -Wall
    COMPILE_DEFINITIONS MY_FEATURE_ENABLED
    PRIVATE_COMPILE_OPTIONS -Wextra
    PRIVATE_COMPILE_DEFINITIONS DEBUG_MODE=1
    REQUIRED
)
```

#### Component Parameters
- **COMPONENT_NAME**: Name of the component
- **SRCS**: Source files for the component  
- **INCLUDE_DIRS**: Public include directories
- **PRIVATE_INCLUDE_DIRS**: Private include directories
- **REQUIREDS**: Public dependencies
- **PRIVATE_REQUIREDS**: Private dependencies
- **COMPILE_OPTIONS**: Public compile options (inherited by dependents)
- **PRIVATE_COMPILE_OPTIONS**: Private compile options (component only)
- **COMPILE_DEFINITIONS**: Public compile definitions (inherited by dependents)
- **PRIVATE_COMPILE_DEFINITIONS**: Private compile definitions (component only)
- **LIBRARY_DIRS**: Additional library directories
- **SHARED**: Create shared library instead of static
- **REQUIRED**: Mark component as required for linking

#### Example Usage

```cmake
# High-performance math component with optimizations
component_register(
    COMPONENT_NAME fast_math
    SRCS src/fast_math.c src/simd_ops.c
    INCLUDE_DIRS include/
    COMPILE_OPTIONS -O3 -ffast-math -mfpu=neon
    COMPILE_DEFINITIONS FAST_MATH_ENABLED USE_SIMD
    REQUIRED
)

# Debug-enabled sensor component  
component_register(
    COMPONENT_NAME sensor_driver
    SRCS src/sensor.c
    INCLUDE_DIRS include/
    PRIVATE_COMPILE_OPTIONS -DDEBUG_SENSOR
    PRIVATE_COMPILE_DEFINITIONS SENSOR_LOG_LEVEL=3
    REQUIREDS fast_math
)
```

### Available Components

- **board**: Hardware abstraction layer
- **device**: Core device support and startup code
- **interface**: Driver interfaces and abstractions
- **common**: Utility functions and common libraries

## 🛠️ Build Configuration

### Build Types
- **Debug**: Development builds with debugging symbols
- **Release**: Optimized production builds

## 🐛 Debugging and Troubleshooting

### Common Issues

1. **WE2_SDK_PATH not set**:
   ```bash
   # Clone the SDK first
   git clone https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2.git
   export WE2_SDK_PATH=/path/to/Seeed_Grove_Vision_AI_Module_V2/EPII_CM55M_APP_S
   ```

2. **Toolchain not found**:
   ```bash
   sudo apt-get install gcc-arm-none-eabi
   # or add to PATH
   export PATH=$PATH:/path/to/arm/toolchain/bin
   ```

3. **Build failures**:
   ```bash
   # Clean build
   rm -rf build/
   cmake -B build -DCMAKE_BUILD_TYPE=Release .
   cmake --build build
   ```

## 📚 Documentation

### Additional Resources
- **WE2 SDK Repository**: [Himax WiseEye Plus SDK](https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2)
- **Grove Vision AI Module V2 Wiki**: [Seeed Studio Wiki](https://wiki.seeedstudio.com/grove_vision_ai_v2)

### API Reference
Detailed API documentation is available in the WE2 SDK documentation package.

## 🤝 Contributing

We welcome contributions! Please:

1. **Fork** the repository
2. **Create** a feature branch
3. **Commit** your changes
4. **Push** to the branch
5. **Create** a Pull Request

### Development Guidelines
- Follow the existing code style
- Add appropriate documentation
- Test your changes thoroughly
- Update README if necessary

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🆘 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/Seeed-Studio/sscma-example-we2/issues)
- **Seeed Forum**: [Community support](https://forum.seeedstudio.com/)
- **Technical Support**: [Contact Seeed Studio](https://www.seeedstudio.com/contacts)

---

**Happy coding with Grove Vision AI Module V2! 🎯**
