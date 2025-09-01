# TensorFlow Lite Micro (TFLM) Component for Ethos-U55
# Based on tflmtag2412_u55tag2411.mk

set(TFLM_BASE_PATH ${WE2_SDK_PATH}/library/inference/tflmtag2412_u55tag2411)

# Check if TFLM library exists
if(NOT EXISTS ${TFLM_BASE_PATH})
    message(WARNING "TFLM library not found at ${TFLM_BASE_PATH}")
    return()
endif()

# Collect TensorFlow Lite Micro source files
set(TFLM_SRCS
    ${TFLM_BASE_PATH}/tensorflow/compiler/mlir/lite/core/api/error_reporter.cc
    ${TFLM_BASE_PATH}/tensorflow/compiler/mlir/lite/schema/schema_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/core/c/common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/portable_tensor_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/quantization_util.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/tensor_ctypes.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/tensor_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/runtime_shape.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/reference/comparisons.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal/reference/portable_tensor_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/kernel_util.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/core/api/tensor_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/core/api/flatbuffer_conversions.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/arena_allocator/non_persistent_arena_buffer_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/arena_allocator/persistent_arena_buffer_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/arena_allocator/recording_single_arena_buffer_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/arena_allocator/single_arena_buffer_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/cortex_m_corstone_300/micro_time.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/memory_planner/greedy_memory_planner.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/memory_planner/linear_memory_planner.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/memory_planner/non_persistent_buffer_planner_shim.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/tflite_bridge/flatbuffer_conversions_bridge.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/tflite_bridge/micro_error_reporter.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/debug_log.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/fake_micro_context.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/flatbuffer_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/memory_helpers.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_allocation_info.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_context.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_interpreter_context.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_interpreter_graph.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_interpreter.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_log.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_op_resolver.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_profiler.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_resource_variable.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_time.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/micro_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/mock_micro_graph.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/recording_micro_allocator.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/system_setup.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/test_helpers.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/test_helper_custom_ops.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/activations_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/activations.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/add_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/add_n.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/arg_min_max.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/assign_variable.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/batch_to_space_nd.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/broadcast_args.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/broadcast_to.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/call_once.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cast.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/ceil.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/circular_buffer.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/circular_buffer_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/comparisons.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/concatenation.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/conv_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cumsum.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/decompress_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/decompress.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/depth_to_space.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/depthwise_conv_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/dequantize.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/dequantize_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/detection_postprocess.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/div.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/elementwise.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/elu.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/embedding_lookup.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/exp.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/expand_dims.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/fill.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/floor.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/floor_div.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/floor_mod.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/fully_connected_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/gather.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/gather_nd.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/hard_swish.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/hard_swish_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/if.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/kernel_runner.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/kernel_util.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/l2_pool_2d.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/l2norm.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/leaky_relu.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/leaky_relu_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/log_softmax.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/logical.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/logical_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/logistic.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/logistic_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/lstm_eval_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/lstm_eval.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/maximum_minimum.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/micro_tensor_utils.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/mirror_pad.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/mul_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/neg.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/pack.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/pad.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/pooling_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/prelu.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/prelu_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/quantize.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/quantize_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/read_variable.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/reduce.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/reduce_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/reshape.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/reshape_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/resize_bilinear.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/resize_nearest_neighbor.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/round.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/select.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/shape.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/slice.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/softmax_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/space_to_batch_nd.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/space_to_depth.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/split.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/split_v.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/squared_difference.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/squeeze.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/strided_slice.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/strided_slice_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/sub.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/sub_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/svdf_common.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/tanh.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/transpose.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/unpack.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/var_handle.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/while.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/zeros_like.cc
)

# Collect CMSIS-NN optimized kernels
set(CMSIS_NN_SRCS
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/add.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/conv.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/depthwise_conv.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/fully_connected.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/mul.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/pooling.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/softmax.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/svdf.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/unidirectional_sequence_lstm.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/transpose_conv.cc
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn/batch_matmul.cc
)

# Collect Ethos-U specific files
set(ETHOS_U_SRCS
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/ethos_u/ethosu.cc
    ${TFLM_BASE_PATH}/third_party/ethos_u_core_driver/src/ethosu_pmu.c
    ${TFLM_BASE_PATH}/third_party/ethos_u_core_driver/src/ethosu_driver.c
    ${TFLM_BASE_PATH}/third_party/ethos_u_core_driver/src/ethosu_device_u55_u65.c
)

# Combine all sources
set(ALL_TFLM_SRCS ${TFLM_SRCS} ${CMSIS_NN_SRCS} ${ETHOS_U_SRCS})

message(STATUS "TFLM source files count: ${ALL_TFLM_SRCS}")

# Include directories
set(TFLM_INCLUDE_DIRS
    ${TFLM_BASE_PATH}
    ${TFLM_BASE_PATH}/tensorflow/lite/micro
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/cmsis_nn
    ${TFLM_BASE_PATH}/tensorflow/lite/micro/kernels/ethos_u
    ${TFLM_BASE_PATH}/tensorflow/lite/core/api
    ${TFLM_BASE_PATH}/tensorflow/lite/core/c
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels
    ${TFLM_BASE_PATH}/tensorflow/lite/kernels/internal
    ${TFLM_BASE_PATH}/tensorflow/lite/schema
    ${TFLM_BASE_PATH}/third_party/flatbuffers/include
    ${TFLM_BASE_PATH}/third_party/gemmlowp
    ${TFLM_BASE_PATH}/third_party/ruy
    ${TFLM_BASE_PATH}/third_party/ethos_u_core_driver/include
)

# Compiler definitions specific to TFLM
set(TFLM_COMPILE_DEFINITIONS
    TF_LITE_MCU_DEBUG_LOG
    TF_LITE_STATIC_MEMORY
    TFLM2412_U55TAG2411
    ARM_MATH_DSP
    ARM_MATH_LOOPUNROLL
    ARM_MATH_MVEI
    CMSIS_NN
    ETHOSU55
    ETHOSU_ARCH=u55
    ETHOSU_LOG_SEVERITY=ETHOSU_LOG_WARN
    ETHOS_U
)

# Compiler options for TFLM
set(TFLM_COMPILE_OPTIONS
    -Os
    -fmessage-length=0
    -fno-builtin
    -ffunction-sections
    -fdata-sections
    -funsigned-char
    -MMD
    -fno-delete-null-pointer-checks
    -fomit-frame-pointer
    -Wall
    -Wextra
    -Wno-unused-parameter
    -Wno-missing-field-initializers
    -Wno-write-strings
    -Wno-sign-compare
    -Wno-type-limits
    -Wno-unused-function
)

# Register the TFLM component
component_register(
    COMPONENT_NAME tflm
    SRCS ${ALL_TFLM_SRCS}
    INCLUDE_DIRS ${TFLM_INCLUDE_DIRS}
    COMPILE_DEFINITIONS ${TFLM_COMPILE_DEFINITIONS}
    PRIVATE_COMPILE_OPTIONS ${TFLM_COMPILE_OPTIONS}
    PRIVATE_REQUIREDS cmsis-nn
)

# Set C++ standard for the component
if(TARGET tflm)
    set_target_properties(tflm PROPERTIES
        CXX_STANDARD 14
        CXX_STANDARD_REQUIRED ON
        CXX_EXTENSIONS OFF
    )

    # Disable specific warnings for TFLM
    target_compile_options(tflm PRIVATE
        -Wno-error=maybe-uninitialized
        -Wno-error=array-bounds
        -Wno-error=stringop-overflow
    )
endif()
