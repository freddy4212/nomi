#include "image_utils.h"
#include <stdio.h>
#include <string.h>
// #include "ff.h"
#include "xprintf.h"

// ARM cycle counter
extern "C" uint32_t get_cycle_count() {
#if defined(__aarch64__)
    uint32_t value;
    // Read PMCCNTR
    __asm volatile("MRS %0, PMCCNTR_EL0" : "=r"(value));
    return value;
#else
    // Cortex-M DWT Cycle Counter
    // Address of DWT_CYCCNT
    volatile uint32_t *DWT_CYCCNT = (uint32_t *)0xE0001004;
    return *DWT_CYCCNT;
#endif
}

void ImageUtils::resize(const uint8_t* src, int src_w, int src_h,
                       uint8_t* dst, int dst_w, int dst_h) {
    // 最近鄰插值
    for (int y = 0; y < dst_h; y++) {
        for (int x = 0; x < dst_w; x++) {
            int src_x = (x * src_w) / dst_w;
            int src_y = (y * src_h) / dst_h;
            
            int src_idx = (src_y * src_w + src_x) * 3;
            int dst_idx = (y * dst_w + x) * 3;
            
            dst[dst_idx + 0] = src[src_idx + 0];
            dst[dst_idx + 1] = src[src_idx + 1];
            dst[dst_idx + 2] = src[src_idx + 2];
        }
    }
}

void ImageUtils::crop(const uint8_t* src, int src_w, int src_h,
                     uint8_t* dst, int x, int y, int crop_w, int crop_h) {
    for (int row = 0; row < crop_h; row++) {
        if (y + row < 0 || y + row >= src_h) continue;
        
        for (int col = 0; col < crop_w; col++) {
            if (x + col < 0 || x + col >= src_w) continue;
            
            int src_idx = ((y + row) * src_w + (x + col)) * 3;
            int dst_idx = (row * crop_w + col) * 3;
            
            dst[dst_idx + 0] = src[src_idx + 0];
            dst[dst_idx + 1] = src[src_idx + 1];
            dst[dst_idx + 2] = src[src_idx + 2];
        }
    }
}

/*
void ImageUtils::savePPM(const char* filename, const uint8_t* image,
                        int width, int height) {
    FIL fp;
    FRESULT res = f_open(&fp, filename, FA_WRITE | FA_CREATE_ALWAYS);
    if (res != FR_OK) {
        xprintf("Failed to open file %s for writing. Error: %d\n", filename, res);
        return;
    }
    
    char header[64];
    int len = snprintf(header, sizeof(header), "P6\n%d %d\n255\n", width, height);
    UINT bw;
    f_write(&fp, header, len, &bw);
    
    // Write image data
    f_write(&fp, image, width * height * 3, &bw);
    f_close(&fp);
    xprintf("Saved %s\n", filename);
}
*/