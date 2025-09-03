# ALLON Sensor TensorFlow Lite Micro Example

This example demonstrates computer vision inference using TensorFlow Lite Micro on the Grove Vision AI Module V2 with various camera sensors.

## Features

- **Person Detection**: Uses a pre-trained person detection model
- **Multi-Sensor Support**: Supports OV5647, IMX219, IMX477, IMX708, and HM0360 camera sensors
- **TensorFlow Lite Micro**: Optimized inference on Cortex-M55 with Ethos-U55 NPU
- **Real-time Processing**: 96x96 input image processing with datapath events

## Model Information

- **Model**: Person detection model optimized with Vela compiler
- **Input Size**: 96x96 RGB
- **Output**: Person detection probability
- **Optimization**: Ethos-U55 NPU acceleration

## Supported Camera Sensors

- **OV5647** (default): Raspberry Pi Camera Module V1
- **IMX219**: Raspberry Pi Camera Module V2
- **IMX477**: Raspberry Pi HQ Camera
- **IMX708**: Raspberry Pi Camera Module V3
- **HM0360**: Himax camera sensor

## Build Instructions

```bash
cd solutions/allon_sensor_tflm
cmake -B build -DCMAKE_BUILD_TYPE=Release .
cmake --build build
```

## Configuration

The camera sensor type is configured in the CMake build system. To change the sensor:

1. Edit `cis_sensor/CMakeLists.txt`
2. Modify the `COMPILE_DEFINITIONS` to match your sensor
3. Rebuild the project

## Hardware Requirements

- Grove Vision AI Module V2
- Compatible camera sensor (OV5647, IMX219, IMX477, IMX708, or HM0360)
- Proper camera connection

## Usage

1. Build and flash the firmware to your Grove Vision AI Module V2
2. Connect the camera sensor
3. Power on the device
4. The system will continuously process camera frames and detect persons
5. Detection results are output via UART

## Code Structure

- `main.cpp`: Main application logic and inference pipeline
- `cvapp.h`: Application header with function declarations
- `common_config.h`: Common configuration definitions
- `person_detect_model_data_vela.cc/.h`: Pre-compiled model data
- `cis_sensor/`: Camera sensor drivers and configurations

## Performance

- **Inference Time**: Optimized for real-time performance with Ethos-U55
- **Memory Usage**: Efficient memory management with TensorFlow Lite Micro
- **Power Consumption**: Low power design suitable for edge applications
