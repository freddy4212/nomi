/*
 * datapath.h
 *
 * Data path interface abstraction for raw data output only
 * Follows the same design pattern as MIPI CSI and SCCB abstractions
 */

#ifndef STREAM_MPIX_DATAPATH_H_
#define STREAM_MPIX_DATAPATH_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * \struct datapath_config_t
 * \brief Data path configuration for raw data output
 */
typedef struct {
    uint32_t width;             ///< Image width in pixels
    uint32_t height;            ///< Image height in pixels
    uint8_t  pixel_depth;       ///< Pixel depth (8, 10, 12 bits)
    bool     enable_crop;       ///< Enable cropping
    uint32_t crop_x;            ///< Crop start X coordinate
    uint32_t crop_y;            ///< Crop start Y coordinate
    uint32_t crop_width;        ///< Crop width
    uint32_t crop_height;       ///< Crop height
} datapath_config_t;

/**
 * Initialize data path with configuration
 * 
 * @param config Data path configuration
 * @return 0 on success, negative error code on failure
 */
int datapath_init(const datapath_config_t *config);

/**
 * Start data path processing
 * 
 * @return 0 on success, negative error code on failure
 */
int datapath_start(void);

/**
 * Stop data path processing
 * 
 * @return 0 on success, negative error code on failure
 */
int datapath_stop(void);


/**
 * @brief frame ready status
 * 
 * @return true 
 * @return false 
 */
bool datapath_is_frame_ready(void);
/**
 * Acquire the latest raw buffer
 * 
 * @param buffer Pointer to buffer info structure to fill
 * @return 0 on success, negative error code on failure
 */
uint32_t datapath_acquire_raw_buffer();

/**
 * Release the acquired raw buffer
 * 
 * @return 0 on success, negative error code on failure
 */
int datapath_release_raw_buffer(void);



/**
 * Configure data path parameters dynamically
 * 
 * @param config New data path configuration
 * @return 0 on success, negative error code on failure
 */
int datapath_configure(const datapath_config_t *config);

/**
 * Get current data path status
 * 
 * @return 1 if running, 0 if stopped, negative error code on failure
 */
int datapath_get_status(void);

/**
 * Deinitialize data path
 * 
 * @return 0 on success, negative error code on failure
 */
int datapath_deinit(void);

#ifdef __cplusplus
}
#endif

#endif /* STREAM_MPIX_DATAPATH_H_ */
