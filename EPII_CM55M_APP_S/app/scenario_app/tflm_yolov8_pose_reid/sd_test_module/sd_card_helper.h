#ifndef SD_CARD_HELPER_H
#define SD_CARD_HELPER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

extern int g_sd_img_w;
extern int g_sd_img_h;

int sd_card_init(void);
int sd_card_read_image(const char *filename, uint8_t *buffer, uint32_t buffer_size);
int sd_card_get_next_file(char *filename_buf, int buf_len);

// Get pointer to the decoded image buffer (allocated via malloc, survives tensor arena reinit)
uint8_t* sd_get_decoded_image(void);
int sd_get_decoded_image_size(void);

// Release the decoded image buffer (call after copying to input tensor)
void sd_release_decoded_image(void);

#ifdef __cplusplus
}
#endif

#endif // SD_CARD_HELPER_H
