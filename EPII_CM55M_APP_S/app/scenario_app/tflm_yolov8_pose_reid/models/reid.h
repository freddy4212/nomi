#ifndef REID_H
#define REID_H

#include <stdint.h>
#include <stddef.h>
#include <vector>

#define REID_INPUT_WIDTH  128
#define REID_INPUT_HEIGHT 256
#define REID_FEATURE_DIM  512
#define MAX_GALLERY_SIZE  20

struct PersonFeature {
    float features[REID_FEATURE_DIM];
    int person_id;
    uint32_t last_seen_frame;
};

class ReIDMatcher {
public:
    ReIDMatcher(float similarity_threshold = 0.6f);
    ~ReIDMatcher();
    
    bool init(const void* model_data, size_t model_size);
    
    // 提取特徵
    bool extractFeatures(const uint8_t* person_image, int width, int height, float* features);
    
    // 在 Gallery 中匹配
    int matchInGallery(const float* features, uint32_t current_frame);
    
    // 加入新人到 Gallery
    int addToGallery(const float* features, uint32_t current_frame);
    
    // 獲取 Gallery 大小
    int getGallerySize() const { return gallery_count_; }
    
    void printStats() const;
    void printGallery() const;
    
private:
    void* interpreter_;
    void* input_tensor_;
    void* output_tensor_;
    uint8_t* tensor_arena_;
    
    PersonFeature gallery_[MAX_GALLERY_SIZE];
    int gallery_count_;
    int next_person_id_;
    float similarity_threshold_;
    
    int total_inferences_;
    float total_inference_time_;
    
    bool createInterpreter();  // Create interpreter on-demand
    void preprocessImage(const uint8_t* image, int width, int height);
    void extractAndNormalize(float* features);
    float computeSimilarity(const float* feat1, const float* feat2) const;
};

#endif // REID_H