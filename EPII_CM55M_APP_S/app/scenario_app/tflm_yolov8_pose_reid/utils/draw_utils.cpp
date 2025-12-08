/*
 * draw_utils.cpp - 繪圖工具函式實現
 */

#include "draw_utils.h"
#include <cstdlib>
#include <cmath>

// 簡單的 5x7 數字點陣字體 (0-9)
// 每個數字用 5 列 x 7 行表示，1 = 填充，0 = 空
static const uint8_t DIGIT_FONT[10][7] = {
    // 0
    {0b01110,
     0b10001,
     0b10011,
     0b10101,
     0b11001,
     0b10001,
     0b01110},
    // 1
    {0b00100,
     0b01100,
     0b00100,
     0b00100,
     0b00100,
     0b00100,
     0b01110},
    // 2
    {0b01110,
     0b10001,
     0b00001,
     0b00110,
     0b01000,
     0b10000,
     0b11111},
    // 3
    {0b01110,
     0b10001,
     0b00001,
     0b00110,
     0b00001,
     0b10001,
     0b01110},
    // 4
    {0b00010,
     0b00110,
     0b01010,
     0b10010,
     0b11111,
     0b00010,
     0b00010},
    // 5
    {0b11111,
     0b10000,
     0b11110,
     0b00001,
     0b00001,
     0b10001,
     0b01110},
    // 6
    {0b00110,
     0b01000,
     0b10000,
     0b11110,
     0b10001,
     0b10001,
     0b01110},
    // 7
    {0b11111,
     0b00001,
     0b00010,
     0b00100,
     0b01000,
     0b01000,
     0b01000},
    // 8
    {0b01110,
     0b10001,
     0b10001,
     0b01110,
     0b10001,
     0b10001,
     0b01110},
    // 9
    {0b01110,
     0b10001,
     0b10001,
     0b01111,
     0b00001,
     0b00010,
     0b01100}
};

// "ID" 字樣
static const uint8_t CHAR_I[7] = {
    0b01110,
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b01110
};

static const uint8_t CHAR_D[7] = {
    0b11100,
    0b10010,
    0b10001,
    0b10001,
    0b10001,
    0b10010,
    0b11100
};

static const uint8_t CHAR_COLON[7] = {
    0b00000,
    0b00100,
    0b00100,
    0b00000,
    0b00100,
    0b00100,
    0b00000
};

static const uint8_t CHAR_PERCENT[7] = {
    0b11000,
    0b11001,
    0b00010,
    0b00100,
    0b01000,
    0b10011,
    0b00011
};

void DrawUtils::drawPixel(uint8_t* image, int width, int height,
                          int x, int y, const Color& color) {
    if (x < 0 || x >= width || y < 0 || y >= height) return;
    
    int idx = (y * width + x) * 3;
    image[idx + 0] = color.r;
    image[idx + 1] = color.g;
    image[idx + 2] = color.b;
}

void DrawUtils::drawRect(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color, int thickness) {
    // 確保座標有效
    if (x1 > x2) { int t = x1; x1 = x2; x2 = t; }
    if (y1 > y2) { int t = y1; y1 = y2; y2 = t; }
    
    // 繪製上下邊
    for (int t = 0; t < thickness; t++) {
        for (int x = x1; x <= x2; x++) {
            drawPixel(image, width, height, x, y1 + t, color);
            drawPixel(image, width, height, x, y2 - t, color);
        }
    }
    
    // 繪製左右邊
    for (int t = 0; t < thickness; t++) {
        for (int y = y1; y <= y2; y++) {
            drawPixel(image, width, height, x1 + t, y, color);
            drawPixel(image, width, height, x2 - t, y, color);
        }
    }
}

void DrawUtils::fillRect(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color) {
    if (x1 > x2) { int t = x1; x1 = x2; x2 = t; }
    if (y1 > y2) { int t = y1; y1 = y2; y2 = t; }
    
    for (int y = y1; y <= y2; y++) {
        for (int x = x1; x <= x2; x++) {
            drawPixel(image, width, height, x, y, color);
        }
    }
}

void DrawUtils::drawLine(uint8_t* image, int width, int height,
                         int x1, int y1, int x2, int y2,
                         const Color& color, int thickness) {
    // Bresenham's line algorithm
    int dx = abs(x2 - x1);
    int dy = abs(y2 - y1);
    int sx = (x1 < x2) ? 1 : -1;
    int sy = (y1 < y2) ? 1 : -1;
    int err = dx - dy;
    
    while (true) {
        // 繪製粗線
        for (int tx = -thickness/2; tx <= thickness/2; tx++) {
            for (int ty = -thickness/2; ty <= thickness/2; ty++) {
                drawPixel(image, width, height, x1 + tx, y1 + ty, color);
            }
        }
        
        if (x1 == x2 && y1 == y2) break;
        
        int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x1 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y1 += sy;
        }
    }
}

void DrawUtils::drawCircle(uint8_t* image, int width, int height,
                           int cx, int cy, int radius,
                           const Color& color, bool filled) {
    if (filled) {
        for (int y = -radius; y <= radius; y++) {
            for (int x = -radius; x <= radius; x++) {
                if (x*x + y*y <= radius*radius) {
                    drawPixel(image, width, height, cx + x, cy + y, color);
                }
            }
        }
    } else {
        // Midpoint circle algorithm
        int x = radius;
        int y = 0;
        int err = 0;
        
        while (x >= y) {
            drawPixel(image, width, height, cx + x, cy + y, color);
            drawPixel(image, width, height, cx + y, cy + x, color);
            drawPixel(image, width, height, cx - y, cy + x, color);
            drawPixel(image, width, height, cx - x, cy + y, color);
            drawPixel(image, width, height, cx - x, cy - y, color);
            drawPixel(image, width, height, cx - y, cy - x, color);
            drawPixel(image, width, height, cx + y, cy - x, color);
            drawPixel(image, width, height, cx + x, cy - y, color);
            
            y++;
            err += 1 + 2*y;
            if (2*(err - x) + 1 > 0) {
                x--;
                err += 1 - 2*x;
            }
        }
    }
}

void DrawUtils::drawDigit(uint8_t* image, int width, int height,
                          int x, int y, int digit,
                          const Color& color, int scale) {
    if (digit < 0 || digit > 9) return;
    
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (DIGIT_FONT[digit][row] & (1 << (4 - col))) {
                // 繪製縮放後的像素
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        drawPixel(image, width, height, 
                                  x + col * scale + sx, 
                                  y + row * scale + sy, 
                                  color);
                    }
                }
            }
        }
    }
}

void DrawUtils::drawNumber(uint8_t* image, int width, int height,
                           int x, int y, int number,
                           const Color& color, int scale) {
    if (number < 0) number = 0;
    
    // 計算數字位數
    int digits[10];
    int num_digits = 0;
    
    if (number == 0) {
        digits[0] = 0;
        num_digits = 1;
    } else {
        int n = number;
        while (n > 0) {
            digits[num_digits++] = n % 10;
            n /= 10;
        }
    }
    
    // 反向繪製數字
    int offset = 0;
    for (int i = num_digits - 1; i >= 0; i--) {
        drawDigit(image, width, height, x + offset, y, digits[i], color, scale);
        offset += 6 * scale; // 5 pixels + 1 spacing
    }
}

void DrawUtils::drawPersonID(uint8_t* image, int width, int height,
                             int x, int y, int person_id,
                             const Color& color, int scale) {
    // 繪製 "I"
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (CHAR_I[row] & (1 << (4 - col))) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        drawPixel(image, width, height, 
                                  x + col * scale + sx, 
                                  y + row * scale + sy, 
                                  color);
                    }
                }
            }
        }
    }
    
    // 繪製 "D"
    int offset = 6 * scale;
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (CHAR_D[row] & (1 << (4 - col))) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        drawPixel(image, width, height, 
                                  x + offset + col * scale + sx, 
                                  y + row * scale + sy, 
                                  color);
                    }
                }
            }
        }
    }
    
    // 繪製 ":"
    offset += 6 * scale;
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (CHAR_COLON[row] & (1 << (4 - col))) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        drawPixel(image, width, height, 
                                  x + offset + col * scale + sx, 
                                  y + row * scale + sy, 
                                  color);
                    }
                }
            }
        }
    }
    
    // 繪製數字
    offset += 6 * scale;
    drawNumber(image, width, height, x + offset, y, person_id, color, scale);
}

void DrawUtils::drawConfidence(uint8_t* image, int width, int height,
                               int x, int y, float confidence,
                               const Color& color, int scale) {
    int percent = (int)(confidence * 100);
    if (percent > 99) percent = 99;
    if (percent < 0) percent = 0;
    
    // 繪製百分比數字
    drawNumber(image, width, height, x, y, percent, color, scale);
    
    // 繪製 % 符號
    int num_digits = (percent >= 10) ? 2 : 1;
    int offset = num_digits * 6 * scale;
    
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (CHAR_PERCENT[row] & (1 << (4 - col))) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        drawPixel(image, width, height, 
                                  x + offset + col * scale + sx, 
                                  y + row * scale + sy, 
                                  color);
                    }
                }
            }
        }
    }
}

void DrawUtils::drawSkeleton(uint8_t* image, int width, int height,
                             const HumanPose keypoints[NUM_KEYPOINTS],
                             float scale_x, float scale_y,
                             const Color& color, float threshold) {
    // 繪製骨架連接
    for (int i = 0; i < NUM_SKELETON_CONNECTIONS; i++) {
        int p1 = SKELETON_CONNECTIONS[i][0];
        int p2 = SKELETON_CONNECTIONS[i][1];
        
        if (keypoints[p1].score > threshold && keypoints[p2].score > threshold) {
            int x1 = (int)((float)keypoints[p1].x * scale_x);
            int y1 = (int)((float)keypoints[p1].y * scale_y);
            int x2 = (int)((float)keypoints[p2].x * scale_x);
            int y2 = (int)((float)keypoints[p2].y * scale_y);
            
            drawLine(image, width, height, x1, y1, x2, y2, color, 2);
        }
    }
    
    // 繪製關鍵點
    for (int i = 0; i < NUM_KEYPOINTS; i++) {
        if (keypoints[i].score > threshold) {
            int x = (int)((float)keypoints[i].x * scale_x);
            int y = (int)((float)keypoints[i].y * scale_y);
            drawCircle(image, width, height, x, y, 3, color, true);
        }
    }
}

void DrawUtils::drawDetection(uint8_t* image, int width, int height,
                              const PersonDetection& detection,
                              int person_id,
                              float scale_x, float scale_y) {
    Color color = getColorForPerson(person_id);
    
    // 計算縮放後的 bounding box
    int x1 = (int)(detection.bbox.x * scale_x);
    int y1 = (int)(detection.bbox.y * scale_y);
    int x2 = (int)((detection.bbox.x + detection.bbox.w) * scale_x);
    int y2 = (int)((detection.bbox.y + detection.bbox.h) * scale_y);
    
    // 繪製 bounding box
    drawRect(image, width, height, x1, y1, x2, y2, color, 3);
    
    // 繪製標籤背景
    /*
    int label_height = 14 * 2; // Scale 2
    int label_y1 = y1 - label_height - 2;
    if (label_y1 < 0) label_y1 = y1 + 2;
    int label_y2 = label_y1 + label_height;
    
    Color bg_color = {0, 0, 0};
    fillRect(image, width, height, x1, label_y1, x1 + 80 * 2, label_y2, bg_color);
    */
    
    // 繪製 Person ID
    int label_height = 14 * 2; // Scale 2
    int label_y1 = y1 - label_height - 2;
    if (label_y1 < 0) label_y1 = y1 + 2;
    drawPersonID(image, width, height, x1 + 2, label_y1 + 2, person_id, color, 2);
    
    // 繪製骨架
    drawSkeleton(image, width, height, detection.keypoints, scale_x, scale_y, color, 0.3f);
}

Color DrawUtils::getColorForPerson(int person_id) {
    if (person_id < 0) person_id = 0;
    return PERSON_COLORS[person_id % NUM_PERSON_COLORS];
}
