#ifndef SD_CARD_HELPER_H
#define SD_CARD_HELPER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

int sd_card_init(void);
int sd_card_read_image(const char *filename, uint8_t *buffer, uint32_t buffer_size);
int sd_card_get_next_file(char *filename_buf, int buf_len);

#ifdef __cplusplus
}
#endif

#endif // SD_CARD_HELPER_H
