#ifndef IMAGE_UTILS_H
#define IMAGE_UTILS_H

#include <stdint.h>

class ImageUtils {
public:
    // 圖像縮放
    static void resize(const uint8_t* src, int src_w, int src_h,
                      uint8_t* dst, int dst_w, int dst_h);
    
    // 裁切 ROI
    static void crop(const uint8_t* src, int src_w, int src_h,
                    uint8_t* dst, int x, int y, int crop_w, int crop_h);
    
    // 儲存為 PPM 格式
    static void savePPM(const char* filename, const uint8_t* image, 
                       int width, int height);
};

// 取得 CPU cycle count (FVP專用)
extern "C" uint32_t get_cycle_count();

#endif // IMAGE_UTILS_H