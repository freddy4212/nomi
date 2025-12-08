#include "sd_card_helper.h"
#include "jpeg_decoder.h"
#include "ff.h"
#include "xprintf.h"
#include "hx_drv_gpio.h"
#include "hx_drv_scu.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <strings.h>
#include "cisdp_sensor.h" // For app_get_jpeg_addr and app_set_jpeg_size

static FATFS fs;
static bool fs_mounted = false;
static DIR dir;
static bool dir_opened = false;

int g_sd_img_w = 0;
int g_sd_img_h = 0;

// GPIO configuration for SD card (SPI mode)
// These functions are already defined in drivers/spi_fatfs.c
// We only need them if they are NOT defined elsewhere.
// Since the linker error says they are multiply defined, we should comment them out here
// or declare them as weak if we wanted to override (but we likely want the driver ones).

/*
void SSPI_CS_GPIO_Output_Level(bool setLevelHigh)
{
    hx_drv_gpio_set_out_value(GPIO16, (GPIO_OUT_LEVEL_E) setLevelHigh);
}

void SSPI_CS_GPIO_Pinmux(bool setGpioFn)
{
    if (setGpioFn)
        hx_drv_scu_set_PB5_pinmux(SCU_PB5_PINMUX_GPIO16, 0);
    else
        hx_drv_scu_set_PB5_pinmux(SCU_PB5_PINMUX_SPI_M_CS_1, 0);
}

void SSPI_CS_GPIO_Dir(bool setDirOut)
{
    if (setDirOut)
        hx_drv_gpio_set_output(GPIO16, GPIO_OUT_HIGH);
    else
        hx_drv_gpio_set_input(GPIO16);
}
*/

int sd_card_init(void) {
    FRESULT res;

    // Configure SPI pins for SD card
    hx_drv_scu_set_PB2_pinmux(SCU_PB2_PINMUX_SPI_M_DO_1, 1);
    hx_drv_scu_set_PB3_pinmux(SCU_PB3_PINMUX_SPI_M_DI_1, 1);
    hx_drv_scu_set_PB4_pinmux(SCU_PB4_PINMUX_SPI_M_SCLK_1, 1);
    hx_drv_scu_set_PB5_pinmux(SCU_PB5_PINMUX_SPI_M_CS_1, 1);

    res = f_mount(&fs, "", 1);
    if (res != FR_OK) {
        xprintf("f_mount failed: %d\n", res);
        return -1;
    }

    fs_mounted = true;
    xprintf("SD card mounted successfully\n");
    return 0;
}

int sd_card_get_next_file(char *filename_buf, int buf_len) {
    FRESULT res;
    FILINFO fno;

    if (!fs_mounted) {
        if (sd_card_init() != 0) {
            return -1;
        }
    }

    if (!dir_opened) {
        res = f_opendir(&dir, "test");
        if (res != FR_OK) {
            xprintf("f_opendir failed: %d\n", res);
            return -1;
        }
        dir_opened = true;
    }

    while (1) {
        res = f_readdir(&dir, &fno);
        if (res != FR_OK || fno.fname[0] == 0) {
            // End of directory or error, rewind
            f_closedir(&dir);
            dir_opened = false;
            return 1; // Signal end of list
        }

        if (fno.fattrib & AM_DIR) {
            continue; // Skip directories
        }

        // Check extension (simple check)
        char *ext = strrchr(fno.fname, '.');
        if (ext) {
            if (strcasecmp(ext, ".jpg") == 0 || strcasecmp(ext, ".jpeg") == 0 || strcasecmp(ext, ".raw") == 0) {
                strncpy(filename_buf, fno.fname, buf_len);
                return 0; // Found a file
            }
        }
    }
}

int sd_card_read_image(const char *filename, uint8_t *buffer, uint32_t buffer_size) {
    FIL fil;
    FRESULT res;
    UINT br;
    uint8_t *file_buf = NULL;
    uint32_t file_size;
    char full_path[64];

    if (!fs_mounted) {
        if (sd_card_init() != 0) {
            return -1;
        }
    }

    // Prepend "test/" to the filename
    snprintf(full_path, sizeof(full_path), "test/%s", filename);

    res = f_open(&fil, full_path, FA_READ);
    if (res != FR_OK) {
        xprintf("f_open failed for %s: %d\n", full_path, res);
        return -1;
    }

    file_size = f_size(&fil);
    file_buf = (uint8_t*)malloc(file_size);
    if (!file_buf) {
        xprintf("Malloc failed for file buffer\n");
        f_close(&fil);
        return -1;
    }

    res = f_read(&fil, file_buf, file_size, &br);
    f_close(&fil);

    if (res != FR_OK || br != file_size) {
        xprintf("f_read failed\n");
        free(file_buf);
        return -1;
    }

    // Check if it is a JPEG
    if (file_size > 2 && file_buf[0] == 0xFF && file_buf[1] == 0xD8) {
        // Copy raw JPEG to the application's JPEG buffer for UART transmission
        uint8_t *jpeg_dst = (uint8_t *)app_get_jpeg_addr();
        if (jpeg_dst) {
            // We assume the buffer is large enough. 
            // In cisdp_sensor.c, g_wdma2_baseaddr is usually allocated with enough space.
            memcpy(jpeg_dst, file_buf, file_size);
            app_set_jpeg_size(file_size);
        }

        // It's a JPEG, decode it
        xprintf("Decoding JPEG...\n");
        nj_result_t nj_res = njDecode(file_buf, file_size);
        if (nj_res != NJ_OK) {
            xprintf("JPEG decode failed: %d\n", nj_res);
            free(file_buf);
            return -1;
        }

        int w = njGetWidth();
        int h = njGetHeight();
        g_sd_img_w = w;
        g_sd_img_h = h;
        uint8_t *img = njGetImage();
        int img_size = njGetImageSize();

        xprintf("Decoded: %dx%d, size: %d\n", w, h, img_size);

        // Use memmove instead of memcpy because buffer (raw_addr) and img (nj.rgb) 
        // might overlap in the shared tensor arena.
        if (img_size <= buffer_size) {
            memmove(buffer, img, img_size);
        } else {
            xprintf("Buffer too small! Needed %d, got %d\n", img_size, buffer_size);
            memmove(buffer, img, buffer_size); // Copy what fits
        }
    } else {
        // Assume RAW
        xprintf("Reading RAW...\n");
        if (file_size <= buffer_size) {
            memmove(buffer, file_buf, file_size);
        } else {
            memmove(buffer, file_buf, buffer_size);
        }
    }

    free(file_buf);
    return 0;
}
