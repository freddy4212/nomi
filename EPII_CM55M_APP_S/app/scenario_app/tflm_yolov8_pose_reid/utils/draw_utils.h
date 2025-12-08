/*
 * draw_utils.h - 繪圖工具函式
 * 用於在影像上繪製 bounding box、骨架和文字
 */

#ifndef DRAW_UTILS_H
#define DRAW_UTILS_H

#include <stdint.h>
#include "yolo_pose.h"  // 引入 PersonDetection, HumanPose 等定義

// 顏色定義 (RGB888)
struct Color {
    uint8_t r, g, b;
};

// 預定義顏色
static const Color COLOR_RED     = {255, 0, 0};
static const Color COLOR_GREEN   = {0, 255, 0};
static const Color COLOR_BLUE    = {0, 0, 255};
static const Color COLOR_YELLOW  = {255, 255, 0};
static const Color COLOR_CYAN    = {0, 255, 255};
static const Color COLOR_MAGENTA = {255, 0, 255};
static const Color COLOR_WHITE   = {255, 255, 255};
static const Color COLOR_BLACK   = {0, 0, 0};

// Person ID 對應的顏色
static const Color PERSON_COLORS[] = {
    {255, 0, 0},     // 紅
    {0, 255, 0},     // 綠
    {0, 0, 255},     // 藍
    {255, 255, 0},   // 黃
    {0, 255, 255},   // 青
    {255, 0, 255},   // 品紅
    {255, 128, 0},   // 橙
    {128, 0, 255},   // 紫
    {0, 255, 128},   // 春綠
    {255, 128, 128}, // 淺紅
};
#define NUM_PERSON_COLORS 10

// 骨架連接定義 (COCO format)
// 17 keypoints: nose, left_eye, right_eye, left_ear, right_ear,
//               left_shoulder, right_shoulder, left_elbow, right_elbow,
//               left_wrist, right_wrist, left_hip, right_hip,
//               left_knee, right_knee, left_ankle, right_ankle
static const int SKELETON_CONNECTIONS[][2] = {
    {0, 1},   // nose -> left_eye
    {0, 2},   // nose -> right_eye
    {1, 3},   // left_eye -> left_ear
    {2, 4},   // right_eye -> right_ear
    {5, 6},   // left_shoulder -> right_shoulder
    {5, 7},   // left_shoulder -> left_elbow
    {7, 9},   // left_elbow -> left_wrist
    {6, 8},   // right_shoulder -> right_elbow
    {8, 10},  // right_elbow -> right_wrist
    {5, 11},  // left_shoulder -> left_hip
    {6, 12},  // right_shoulder -> right_hip
    {11, 12}, // left_hip -> right_hip
    {11, 13}, // left_hip -> left_knee
    {13, 15}, // left_knee -> left_ankle
    {12, 14}, // right_hip -> right_knee
    {14, 16}, // right_knee -> right_ankle
};
#define NUM_SKELETON_CONNECTIONS 16

class DrawUtils {
public:
    // 繪製像素點
    static void drawPixel(uint8_t* image, int width, int height,
                          int x, int y, const Color& color);
    
    // 繪製矩形框
    static void drawRect(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color, int thickness = 2);
    
    // 繪製填充矩形
    static void fillRect(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color);
    
    // 繪製線段
    static void drawLine(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color, int thickness = 1);
    
    // 繪製圓形
    static void drawCircle(uint8_t* image, int width, int height,
                           int cx, int cy, int radius,
                           const Color& color, bool filled = false);
    
    // 繪製數字 (0-9)
    static void drawDigit(uint8_t* image, int width, int height,
                          int x, int y, int digit,
                          const Color& color, int scale = 1);
    
    // 繪製數字序列 (用於 Person ID)
    static void drawNumber(uint8_t* image, int width, int height,
                           int x, int y, int number,
                           const Color& color, int scale = 1);
    
    // 繪製 "ID:" 前綴和數字
    static void drawPersonID(uint8_t* image, int width, int height,
                             int x, int y, int person_id,
                             const Color& color, int scale = 1);
    
    // 繪製百分比 (用於 confidence)
    static void drawConfidence(uint8_t* image, int width, int height,
                               int x, int y, float confidence,
                               const Color& color, int scale = 1);
    
    // 繪製骨架
    static void drawSkeleton(uint8_t* image, int width, int height,
                             const HumanPose keypoints[NUM_KEYPOINTS],
                             float scale_x, float scale_y,
                             const Color& color, float threshold = 0.3f);
    
    // 繪製完整的偵測結果 (bounding box + ID + skeleton)
    static void drawDetection(uint8_t* image, int width, int height,
                              const PersonDetection& detection,
                              int person_id,
                              float scale_x, float scale_y);
    
    // 根據 Person ID 獲取顏色
    static Color getColorForPerson(int person_id);
};

#endif // DRAW_UTILS_H
