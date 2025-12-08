#ifndef REID_INFERENCE_H
#define REID_INFERENCE_H

#include <vector>
#include <forward_list>
#include "send_result.h"
#include "reid.h"

void run_reid_pipeline(
    std::forward_list<el_keypoint_t> &el_keypoint_algo,
    uint32_t raw_addr,
    uint32_t img_w,
    uint32_t img_h,
    ReIDMatcher* reid_matcher,
    uint8_t* reid_input_buffer,
    std::vector<std::vector<float>>& reid_vectors
);

#endif // REID_INFERENCE_H
