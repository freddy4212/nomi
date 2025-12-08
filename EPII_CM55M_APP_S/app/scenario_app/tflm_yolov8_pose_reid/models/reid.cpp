#include "reid.h"
#include "image_utils.h"
#include <stdio.h>
#include <string.h>
#include <cmath>

extern "C" uint32_t SystemCoreClock;

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

namespace tflite {
extern TFLMRegistration* Register_ETHOSU();
extern const char* GetString_ETHOSU();
}

#define REID_TENSOR_ARENA_SIZE (1450 * 1024)  // Increased to ~1.45MB to fit 888x658 decoding
extern "C" {
    uint8_t reid_tensor_arena[REID_TENSOR_ARENA_SIZE] __attribute__((section(".tensor_arena"), aligned(16)));
}

ReIDMatcher::ReIDMatcher()
    : interpreter_(nullptr)
    , input_tensor_(nullptr)
    , output_tensor_(nullptr)
    , tensor_arena_(nullptr)
    , total_inferences_(0)
    , total_inference_time_(0.0f)
{
    tensor_arena_ = reid_tensor_arena;
}

ReIDMatcher::~ReIDMatcher() {
    // Static buffer
}

// Store model pointer for on-demand initialization
static const void* s_reid_model_data = nullptr;

bool ReIDMatcher::init(const void* model_data, size_t model_size) {
    printf("[ReID] Initializing Re-ID matcher (on-demand mode)...\n");
    
    const tflite::Model* model = tflite::GetModel(model_data);
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        printf("[ReID] Model schema mismatch\n");
        return false;
    }
    
    // Just store the model pointer, don't create interpreter yet
    // Interpreter will be created on-demand during extractFeatures()
    s_reid_model_data = model_data;
    
    // Create interpreter immediately (since we have dedicated arena)
    if (!createInterpreter()) {
        printf("[ReID] Failed to create interpreter during init\n");
        return false;
    }
    
    printf("[ReID] Model validated and initialized\n");
    
    return true;
}

// Prepare interpreter for inference (call this before using extractFeatures if arena was used by another model)
bool ReIDMatcher::prepare() {
    return createInterpreter();
}

// Create interpreter (called once during init)
bool ReIDMatcher::createInterpreter() {
    if (s_reid_model_data == nullptr) {
        printf("[ReID] Model not loaded\n");
        return false;
    }
    
    const tflite::Model* model = tflite::GetModel(s_reid_model_data);
    
    // Use placement new to create interpreter in the arena
    static tflite::MicroMutableOpResolver<13> micro_op_resolver;
    static bool resolver_initialized = false;
    
    if (!resolver_initialized) {
        micro_op_resolver.AddCustom(tflite::GetString_ETHOSU(), tflite::Register_ETHOSU());
        micro_op_resolver.AddConv2D();
        micro_op_resolver.AddDepthwiseConv2D();
        micro_op_resolver.AddFullyConnected();
        micro_op_resolver.AddReshape();
        micro_op_resolver.AddQuantize();
        micro_op_resolver.AddDequantize();
        micro_op_resolver.AddMaxPool2D();
        micro_op_resolver.AddAveragePool2D();
        micro_op_resolver.AddAdd();
        micro_op_resolver.AddMul();
        micro_op_resolver.AddSoftmax();
        micro_op_resolver.AddL2Normalization();
        resolver_initialized = true;
    }
    
    // Create interpreter (will reuse the arena that YOLOv8 Pose used)
    static tflite::MicroInterpreter* interpreter_ptr = nullptr;
    static uint8_t interpreter_buffer[sizeof(tflite::MicroInterpreter)] __attribute__((aligned(16)));
    
    // NO memset of arena needed as it is dedicated
    // memset(tensor_arena_, 0, REID_TENSOR_ARENA_SIZE);
    
    // Create new interpreter using placement new (don't destroy old one, just overwrite)
    interpreter_ptr = new (interpreter_buffer) tflite::MicroInterpreter(
        model, micro_op_resolver, tensor_arena_,
        REID_TENSOR_ARENA_SIZE
    );
    
    if (interpreter_ptr->AllocateTensors() != kTfLiteOk) {
        printf("[ReID] AllocateTensors failed\n");
        return false;
    }
    
    interpreter_ = (void*)interpreter_ptr;
    input_tensor_ = (void*)interpreter_ptr->input(0);
    output_tensor_ = (void*)interpreter_ptr->output(0);
    
    return true;
}

// Static buffer for resize operation - REMOVED to save memory (96KB)
// We ensure input is already resized in cvapp
// static uint8_t resize_buffer[REID_INPUT_WIDTH * REID_INPUT_HEIGHT * 3] __attribute__((section(".bss.NoInit"), aligned(16)));

void ReIDMatcher::preprocessImage(const uint8_t* image, int width, int height) {
    auto* input = (TfLiteTensor*)input_tensor_;
    if (input == nullptr || input->data.int8 == nullptr) {
        printf("[ReID] preprocessImage: input tensor is null\n");
        return;
    }
    int8_t* input_data = input->data.int8;
    
    const uint8_t* src_data = image;
    
    if (width != REID_INPUT_WIDTH || height != REID_INPUT_HEIGHT) {
        printf("[ReID] Error: Input image must be resized to %dx%d\n", REID_INPUT_WIDTH, REID_INPUT_HEIGHT);
        return;
        /*
        // Resize needed - use static buffer instead of dynamic allocation
        ImageUtils::resize(image, width, height,
                          resize_buffer, REID_INPUT_WIDTH, REID_INPUT_HEIGHT);
        src_data = resize_buffer;
        */
    }
    
    // Normalize
    for (int i = 0; i < REID_INPUT_WIDTH * REID_INPUT_HEIGHT * 3; i++) {
        float normalized = (src_data[i] / 255.0f - 0.5f) * 2.0f;
        input_data[i] = (int8_t)(normalized * 127.0f);
    }
}

void ReIDMatcher::extractAndNormalize(float* features) {
    auto* output = (TfLiteTensor*)output_tensor_;
    if (output == nullptr || output->data.int8 == nullptr) {
        printf("[ReID] extractAndNormalize: output tensor is null\n");
        // Return zero vector
        for (int i = 0; i < REID_FEATURE_DIM; i++) {
            features[i] = 0.0f;
        }
        return;
    }
    int8_t* output_data = output->data.int8;
    float scale = output->params.scale;
    int32_t zero_point = output->params.zero_point;
    
    // Dequantize
    float norm = 0.0f;
    for (int i = 0; i < REID_FEATURE_DIM; i++) {
        features[i] = (output_data[i] - zero_point) * scale;
        norm += features[i] * features[i];
    }
    
    // L2 normalize
    norm = sqrtf(norm);
    if (norm > 0.0f) {
        for (int i = 0; i < REID_FEATURE_DIM; i++) {
            features[i] /= norm;
        }
    }
}

bool ReIDMatcher::extractFeatures(const uint8_t* person_image, int width, int height, float* features) {
    // Interpreter is already created in init()
    if (interpreter_ == nullptr) {
        printf("[ReID] Interpreter not initialized\n");
        return false;
    }
    
    auto* interpreter = (tflite::MicroInterpreter*)interpreter_;
    
    // Preprocess
    preprocessImage(person_image, width, height);
    
    // Inference
    uint32_t start = get_cycle_count();
    
    TfLiteStatus invoke_status = interpreter->Invoke();
    
    uint32_t end = get_cycle_count();
    float inference_ms = (end - start) / (float)(SystemCoreClock / 1000);
    
    total_inferences_++;
    total_inference_time_ += inference_ms;
    
    if (invoke_status != kTfLiteOk) {
        printf("[ReID] Invoke failed\n");
        return false;
    }
    
    // Extract features
    extractAndNormalize(features);
    
    printf("[ReID] Features extracted (%.1f ms)\n", inference_ms);
    
    return true;
}

void ReIDMatcher::printStats() const {
    if (total_inferences_ > 0) {
        printf("[ReID] Statistics:\n");
        printf("  Total inferences: %d\n", total_inferences_);
        printf("  Average time: %.2f ms\n", total_inference_time_ / total_inferences_);
    }
}