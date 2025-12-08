#ifndef YOLO_POSE_H
#define YOLO_POSE_H

#include <stdint.h>
#include <stddef.h>
#include <vector>

#define YOLO_INPUT_WIDTH  256
#define YOLO_INPUT_HEIGHT 256
#define NUM_KEYPOINTS 17

// YOLOv8 使用 3 個尺度: 8, 16, 32
// 對於 256x256 輸入:
// stride 8:  32x32 = 1024 個候選框
// stride 16: 16x16 = 256 個候選框
// stride 32: 8x8   = 64 個候選框
// 總共 1344 個候選框
#define YOLO_TOTAL_ANCHORS ((YOLO_INPUT_WIDTH/8)*(YOLO_INPUT_HEIGHT/8) + \
                            (YOLO_INPUT_WIDTH/16)*(YOLO_INPUT_HEIGHT/16) + \
                            (YOLO_INPUT_WIDTH/32)*(YOLO_INPUT_HEIGHT/32))

struct Box {
    float x, y, w, h;  // Bounding box (x,y 為左上角，像素座標)
};

struct HumanPose {
    uint32_t x;
    uint32_t y;
    float score;
};

struct PersonDetection {
    Box bbox;
    float confidence;
    HumanPose keypoints[NUM_KEYPOINTS];
};

class YoloPoseDetector {
public:
    YoloPoseDetector();
    ~YoloPoseDetector();
    
    bool init(const void* model_data, size_t model_size);
    std::vector<PersonDetection> detect(const uint8_t* image, int width, int height);
    
    void printStats() const;
    
private:
    void* interpreter_;
    void* input_tensor_;
    uint8_t* tensor_arena_;
    
    int total_inferences_;
    float total_inference_time_;
    
    // Anchor 和 Stride 矩陣（預先計算）
    float* stride_array_;      // [total_anchors_]
    float** anchor_array_;     // [total_anchors_][2]
    int total_anchors_;        // 實際的 anchor 總數
    int out_dim_size_[3];      // 各尺度的累積大小邊界
    
    void preprocessImage(const uint8_t* image, int width, int height);
    std::vector<PersonDetection> parseOutput();
    
    // YOLOv8 後處理函數
    void initAnchorsAndStrides();
    void freeAnchorsAndStrides();
    
    float sigmoid(float x);
    void softmax(float* input, size_t len);
    
    float dequantize(int8_t value, float scale, int32_t zero_point);
    float getBboxDequantValue(int dim1, int dim2, void* tensor);
    float getKeypointDequantValue(int dim1, int dim2, void* tensor, 
                                   float anchor0, float anchor1, float stride);
    void calculateXYWH(int j, void** outputs, Box* bbox, int* out_dim_size);
    
    // NMS
    float boxIou(const Box& a, const Box& b);
    void nmsBoxes(std::vector<Box>& boxes, std::vector<float>& confidences,
                  float scoreThreshold, float nmsThreshold, std::vector<int>& result);
};

#endif // YOLO_POSE_H