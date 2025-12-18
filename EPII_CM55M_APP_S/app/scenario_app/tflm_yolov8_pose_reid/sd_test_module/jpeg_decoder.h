#ifndef _JPEG_DECODER_H_
#define _JPEG_DECODER_H_

#ifdef __cplusplus
extern "C" {
#endif

typedef enum _nj_result {
    NJ_OK = 0,        // no error, decoding successful
    NJ_NO_JPEG,       // not a JPEG file
    NJ_UNSUPPORTED,   // unsupported format
    NJ_OUT_OF_MEM,    // out of memory
    NJ_INTERNAL_ERR,  // internal error
    NJ_SYNTAX_ERROR,  // syntax error
    NJ___COUNT
} nj_result_t;

// Init the decoder
void njInit(void);

// Set external RGB buffer (must be at least 256*256*3 bytes)
// If set, decoder will output to this buffer instead of allocating from tensor arena
// Pass NULL to use default allocation
void njSetExternalRGBBuffer(unsigned char* buf, int size);

// Decode a JPEG image.
// jpeg: pointer to the JPEG data
// size: size of the JPEG data
// Returns NJ_OK on success.
nj_result_t njDecode(const void* jpeg, int size);

// Get the width of the decoded image.
int njGetWidth(void);

// Get the height of the decoded image.
int njGetHeight(void);

// Get the size of the decoded image in bytes.
int njGetImageSize(void);

// Get the pointer to the decoded image data (RGB888).
unsigned char* njGetImage(void);

#ifdef __cplusplus
}
#endif

#endif /* _JPEG_DECODER_H_ */
