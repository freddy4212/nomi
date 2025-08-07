#include <stdio.h>
#include <string.h>
#include <stdint.h>

const char base64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

void base64_encode(uint8_t *input, uint32_t input_len, char *output) {
    uint32_t i = 0, j = 0;
    for (; i < input_len; i += 3) {
        uint32_t triplet = (input[i] << 16) | 
                          ((i+1 < input_len) ? input[i+1] << 8 : 0) | 
                          ((i+2 < input_len) ? input[i+2] : 0);

        output[j++] = base64_table[(triplet >> 18) & 0x3F];
        output[j++] = base64_table[(triplet >> 12) & 0x3F];
        output[j++] = (i+1 < input_len) ? base64_table[(triplet >> 6) & 0x3F] : '=';
        output[j++] = (i+2 < input_len) ? base64_table[triplet & 0x3F] : '=';
    }
    output[j] = '\0'; 
}

#define BLOCK_SIZE 48 

void send_raw_base64_data(uint8_t *buf, uint32_t len)
{
    printf("\xAA\x55%08X", len);  

    uint32_t blocks = len / BLOCK_SIZE;
    uint32_t remain = len % BLOCK_SIZE;
    char base64_block[65];  

    for (uint32_t i = 0; i < blocks; i++) {
        base64_encode(buf + i * BLOCK_SIZE, BLOCK_SIZE, base64_block);
        base64_block[64] = '\0'; 
        printf("%s", base64_block); 
    }

    if (remain > 0) {
        base64_encode(buf + blocks * BLOCK_SIZE, remain, base64_block);
        uint32_t encoded_len = 4 * ((remain + 2) / 3);  
        base64_block[encoded_len] = '\0'; 
        printf("%s", base64_block);
    }

    printf("\x0D\x0A");  
}

void send_raw_data(uint8_t *buf, uint32_t len)
{
    send_raw_base64_data(buf, len);
}