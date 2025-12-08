#ifndef REID_H
#define REID_H

#include <stdint.h>
#include <stddef.h>
#include <vector>

#define REID_INPUT_WIDTH  128
#define REID_INPUT_HEIGHT 256
#define REID_FEATURE_DIM  512

class ReIDMatcher {
public:
    ReIDMatcher();
    ~ReIDMatcher();
    
    bool init(const void* model_data, size_t model_size);
    
    // 提取特徵
    bool extractFeatures(const uint8_t* person_image, int width, int height, float* features);
    
    // 準備 Interpreter (每次切換模型時調用)
    bool prepare();

    void printStats() const;
    
private:
    void* interpreter_;
    void* input_tensor_;
    void* output_tensor_;
    uint8_t* tensor_arena_;
    
    int total_inferences_;
    float total_inference_time_;
    
    bool createInterpreter();  // Create interpreter on-demand
    void preprocessImage(const uint8_t* image, int width, int height);
    void extractAndNormalize(float* features);
};

#endif // REID_H