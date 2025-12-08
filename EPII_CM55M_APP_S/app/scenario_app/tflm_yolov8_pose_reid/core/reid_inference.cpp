#include "reid_inference.h"
#include "xprintf.h"

void run_reid_pipeline(
    std::forward_list<el_keypoint_t> &el_keypoint_algo,
    uint32_t raw_addr,
    uint32_t img_w,
    uint32_t img_h,
    ReIDMatcher* reid_matcher,
    uint8_t* reid_input_buffer,
    std::vector<std::vector<float>>& reid_vectors
) {
    // 1. Prepare Data Structures
    int person_count = 0;
    for (auto& tmp : el_keypoint_algo) { (void)tmp; person_count++; }

    // 2. Process Each Person (ReID + Drawing)
    int person_idx = 0;
    for (auto& kp : el_keypoint_algo) {
        int x = kp.el_box.x;
        int y = kp.el_box.y;
        int w = kp.el_box.w;
        int h = kp.el_box.h;
        
        // Boundary checks
        if (x < 0) x = 0;
        if (y < 0) y = 0;
        if (x + w > (int)img_w) w = img_w - x;
        if (y + h > (int)img_h) h = img_h - y;

        // Extract ReID features
        std::vector<float> features_vec;
        if (w > 10 && h > 10 && reid_matcher && reid_input_buffer) {
            uint8_t* src = (uint8_t*)raw_addr;
            uint8_t* dst = reid_input_buffer;
            int dst_w = REID_INPUT_WIDTH;
            int dst_h = REID_INPUT_HEIGHT;
            
            // Resize/Crop (BGR to RGB)
            for (int dy = 0; dy < dst_h; dy++) {
                for (int dx = 0; dx < dst_w; dx++) {
                    int sx = x + (dx * w) / dst_w;
                    int sy = y + (dy * h) / dst_h;
                    if (sx >= (int)img_w) sx = img_w - 1;
                    if (sy >= (int)img_h) sy = img_h - 1;
                    int src_idx = (sy * img_w + sx) * 3;
                    int dst_idx = (dy * dst_w + dx) * 3;
                    dst[dst_idx + 0] = src[src_idx + 2]; // R
                    dst[dst_idx + 1] = src[src_idx + 1]; // G
                    dst[dst_idx + 2] = src[src_idx + 0]; // B
                }
            }
            
            float features[REID_FEATURE_DIM];
            // Shared Arena: Must prepare ReID interpreter (overwrites YOLO)
            bool reid_ok = false;
            if (reid_matcher->prepare()) {
                if (reid_matcher->extractFeatures(reid_input_buffer, REID_INPUT_WIDTH, REID_INPUT_HEIGHT, features)) {
                    features_vec.assign(features, features + REID_FEATURE_DIM);
                    reid_ok = true;
                }
            }
            if (!reid_ok) {
                xprintf("ReID failed for person %d\n", person_idx);
            }
        }
        reid_vectors.push_back(features_vec);

        person_idx++;
    }
}
