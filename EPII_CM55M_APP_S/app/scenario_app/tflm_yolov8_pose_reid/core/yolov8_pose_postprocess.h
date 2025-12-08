#ifndef YOLOV8_POSE_POSTPROCESS_H
#define YOLOV8_POSE_POSTPROCESS_H

#include <vector>
#include <forward_list>
#include <cmath>
#include <algorithm>
#include "tensorflow/lite/c/common.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "spi_protocol.h"
#include "send_result.h"
// #include "yolo_postprocessing.h" // For struct box

// Constants
#define HUMAN_POSE_POINT_NUM 17
#define KEYPOINT_NUM 17
// #define MAX_TRACKED_YOLOV8_ALGO_RES 10 // Already defined in spi_protocol.h? No, it is used there but maybe defined elsewhere.
// Let's check spi_protocol.h again. It uses MAX_TRACKED_YOLOV8_ALGO_RES.
// If it is defined in spi_protocol.h, we don't need to redefine it.
// If it is not, we need it.
// Based on usage in spi_protocol.h: typedef struct { detection_yolov8_pose dypr[MAX_TRACKED_YOLOV8_ALGO_RES]; ... }
// It must be defined before spi_protocol.h or inside it.
// Let's assume it is available via spi_protocol.h or common headers.

// Structs
typedef struct box {
    float x, y, w, h;
} box;

struct detection_cls_yolov8 {
    box bbox;
    float confidence;
    float index;
};

struct struct_human_pose_17 {
    struct_human_pose hpr[HUMAN_POSE_POINT_NUM];
};

// Functions
float sigmoid(float x);
float box_iou(box a, box b);

void yolov8_pose_post_processing(
    tflite::MicroInterpreter* static_interpreter,
    float modelScoreThreshold, 
    float modelNMSThreshold, 
    struct_yolov8_pose_algoResult *alg,
    std::forward_list<el_keypoint_t> &el_keypoint_algo,
    int dim_total_size,
    float* anchor_756_2,
    float* stride_756_1,
    uint32_t img_w,
    uint32_t img_h,
    uint32_t tensor_w,
    uint32_t tensor_h
);

#endif // YOLOV8_POSE_POSTPROCESS_H
